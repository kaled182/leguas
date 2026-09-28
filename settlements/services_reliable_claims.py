"""Descontos a partir do julgamento da Cainiao, lido do ReliableMaps.

As reclamações (Fake Delivery) são geridas no ReliableMaps: o motorista
responde lá, o agente envia ao CES, e a Cainiao julga. Aqui só se consome o
veredicto (/api/integracoes/v1/reclamacoes/?julgadas_desde=…):

  • "contra" (Liability established) → DriverClaim APROVADO para o motorista
    do login, com o valor por omissão do parceiro (Partner.verdict_claim_amount).
    approve() inclui-o na pré-fatura, como qualquer outro claim.
  • "a_favor" (Liability is not established) → sem desconto; se esta
    sincronização já tinha criado um para o ticket, estorna-o.

O login, exactamente como vem, identifica o motorista (DriverCourierMapping /
CourierNameAlias / apelido); um login de helper desconta ao motorista principal. Um login sem motorista fica "no_driver" e é
retentado em cada volta até ser ligado. Nunca se toca num claim que não tenha
sido criado aqui, nem se muda o valor de um claim já criado (pode ter sido
editado à mão).
"""
import logging
from datetime import timedelta

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .services_reliable_sync import ReliableSyncError, _config, _get

logger = logging.getLogger(__name__)

LOCK_KEY = "settlements:reliable_claims_sync"
LOCK_TIMEOUT = 25 * 60
FIRST_RUN_WINDOW = timedelta(days=60)
OVERLAP = timedelta(hours=6)
MAX_PAGES = 20


def resolve_driver_for_login(login):
    """DriverProfile do login Cainiao (comparação exacta), ou None."""
    from drivers_app.models import DriverProfile

    from .models import CourierNameAlias, DriverCourierMapping

    login = (login or "").strip()
    if not login:
        return None
    m = (DriverCourierMapping.objects
         .filter(partner__name__iexact="CAINIAO", courier_name=login)
         .select_related("driver").first())
    if m:
        return m.driver
    alias = CourierNameAlias.objects.filter(partner__name__iexact="CAINIAO", courier_name=login).first()
    if alias:
        m = (DriverCourierMapping.objects
             .filter(partner__name__iexact="CAINIAO", courier_id=alias.courier_id)
             .select_related("driver").first())
        if m:
            return m.driver
    drivers = list(DriverProfile.objects.filter(apelido=login)[:2])
    return drivers[0] if len(drivers) == 1 else None


def resolve_responsible_driver(login):
    """(DriverProfile que responde pelo login, nota) — o helper responde pelo principal.

    Um login de helper desconta sempre ao motorista principal (Paulo, 28/09/2026).
    O principal vem da User List do CES (tipo COURIER_HELPER + principal, via
    ReliableMaps); sem isso, de um DriverHelper activo com esse nome. Senão, o
    próprio login.
    """
    from .models import DriverHelper
    from .services_courier_onboarding import _ces_users

    login = (login or "").strip()
    ces = next((u for u in _ces_users() if (u.get("login") or "").strip() == login), None)
    if ces and ces.get("tipo") == "COURIER_HELPER" and (ces.get("principal") or "").strip():
        principal = ces["principal"].strip()
        return resolve_driver_for_login(principal), f"helper de {principal}"
    helpers = list(DriverHelper.objects.filter(helper_name=login, is_active=True).select_related("driver")[:2])
    if len(helpers) == 1:
        return helpers[0].driver, f"helper de {helpers[0].driver.nome_completo}"
    return resolve_driver_for_login(login), ""


def _list_verdicts(base, key, since):
    rows, desde = [], since
    for _ in range(MAX_PAGES):
        data = _get(base, key, "reclamacoes/", params={"julgadas_desde": desde.isoformat()}).json()
        page = data.get("reclamacoes", [])
        rows.extend(page)
        if len(page) < data.get("limite", 500):
            break
        desde = parse_datetime(page[-1]["veredicto_em"])
    unique = {r["ticket"]: r for r in rows}  # a paginação repete o último
    return list(unique.values())


def _task_date_for(waybill):
    from .models import CainiaoOperationTask

    return (CainiaoOperationTask.objects.filter(waybill_number=waybill)
            .order_by("-task_date").values_list("task_date", flat=True).first())


def _create_claim(record, driver, partner, helper_note=""):
    from .models import DriverClaim

    task_date = _task_date_for(record.waybill)
    claim = DriverClaim.objects.create(
        driver=driver,
        claim_type="CUSTOMER_COMPLAINT",
        amount=partner.verdict_claim_amount,
        description=(
            f"{record.exception_name or 'Reclamação'} — ticket {record.ticket}. "
            f"Cainiao: responsabilidade nossa ({record.verdict_raw})."
            + (f" Nota: {record.verdict_note}" if record.verdict_note else "")
        ),
        justification=(f"Resposta do motorista: {record.driver_answer}" if record.driver_answer else ""),
        waybill_number=DriverClaim.normalize_waybill(record.waybill),
        operation_task_date=task_date,
        occurred_at=record.verdict_at or timezone.now(),
        auto_detected=True,
        dsp_observation=(
            f"Veredicto Cainiao via ReliableMaps (login {record.login}"
            + (f", {helper_note}" if helper_note else "") + ")."
        ),
    )
    claim.approve(None, notes="Aprovado automaticamente: veredicto da Cainiao (ReliableMaps).")
    return claim


def _apply(record, partner):
    """Decide o desconto de um veredicto. Idempotente."""
    from .models import DriverClaim, ReliableClaimVerdict as V
    from .services_claims_in_pf import revert_claim_from_preinvoices

    own_claim = record.claim if record.outcome == V.OUTCOME_CLAIM_CREATED else None

    if record.verdict == "a_favor":
        if own_claim and own_claim.status == "APPROVED":
            revert_claim_from_preinvoices(own_claim)
            own_claim.status = "REJECTED"
            own_claim.review_notes = "Estornado: a Cainiao julgou que não é responsabilidade nossa."
            own_claim.save(update_fields=["status", "review_notes", "updated_at"])
            record.outcome, record.message = V.OUTCOME_REVERTED, f"Claim #{own_claim.id} estornado."
        elif record.outcome != V.OUTCOME_REVERTED:
            record.outcome, record.message = V.OUTCOME_NO_LIABILITY, ""
        return

    # contra
    if own_claim or record.outcome == V.OUTCOME_DUPLICATE:
        return
    driver, helper_note = resolve_responsible_driver(record.login)
    record.driver = driver
    if driver is None:
        record.outcome = V.OUTCOME_NO_DRIVER
        who = f" ({helper_note}, sem motorista)" if helper_note else ""
        record.message = f"Login {record.login!r}{who} sem motorista: liga-o em 'names sem mapping' / Logins."
        return
    existing = DriverClaim.active_claim_for_waybill(record.waybill)
    if existing:
        record.claim = existing
        record.outcome = V.OUTCOME_DUPLICATE
        record.message = f"Já existia o claim #{existing.id} ({existing.get_status_display()}) para o pacote."
        return
    record.claim = _create_claim(record, driver, partner, helper_note)
    record.outcome, record.message = V.OUTCOME_CLAIM_CREATED, (f"Login {helper_note}." if helper_note else "")


def sync_claim_verdicts(triggered_by="cron"):
    """Lê os veredictos novos do ReliableMaps e aplica-os. Devolve um resumo."""
    from system_config.models import SystemConfiguration

    _, base, key = _config()
    if not SystemConfiguration.get_config().reliable_claims_sync_enabled:
        return {"ok": True, "skipped": "Descontos pelo julgamento desligados."}
    if not base or not key:
        return {"ok": False, "error": "URL ou chave do ReliableMaps em falta."}
    if not cache.add(LOCK_KEY, triggered_by, LOCK_TIMEOUT):
        return {"ok": True, "skipped": "Já há uma sincronização a correr."}
    try:
        return _sync(base, key)
    except ReliableSyncError as e:
        logger.warning("sync veredictos ReliableMaps: %s", e)
        return {"ok": False, "error": str(e)}
    finally:
        cache.delete(LOCK_KEY)


def _sync(base, key):
    from core.models import Partner

    from .models import ReliableClaimVerdict as V

    partner = Partner.objects.filter(name__iexact="CAINIAO").first()
    if partner is None:
        return {"ok": False, "error": "Parceiro CAINIAO não encontrado."}

    last = V.objects.exclude(verdict_at=None).order_by("-verdict_at").first()
    since = (last.verdict_at - OVERLAP) if last else (timezone.now() - FIRST_RUN_WINDOW)
    rows = _list_verdicts(base, key, since)

    counts = {o: 0 for o, _ in V.OUTCOME_CHOICES}
    seen = set()
    for r in rows:
        verdict = r.get("veredicto") or ""
        if verdict not in ("contra", "a_favor") or not r.get("ticket"):
            continue
        seen.add(r["ticket"])
        with transaction.atomic():
            record = V.objects.select_for_update().filter(ticket=r["ticket"]).first() or V(ticket=r["ticket"])
            record.waybill = (r.get("cnprt") or "").strip()
            record.login = (r.get("login_cainiao") or "").strip()
            record.exception_name = r.get("reclamacao") or ""
            record.hub = r.get("hub") or ""
            record.verdict = verdict
            record.verdict_raw = r.get("veredicto_cainiao") or ""
            record.verdict_note = r.get("veredicto_nota") or ""
            record.verdict_at = parse_datetime(r["veredicto_em"]) if r.get("veredicto_em") else None
            record.opened_at = parse_datetime(r["aberta_em"]) if r.get("aberta_em") else None
            record.answered_in_ces_by = r.get("quem_respondeu_no_ces") or ""
            record.driver_answer = r.get("resposta_do_motorista") or ""
            _apply(record, partner)
            record.save()
        counts[record.outcome] += 1

    # Logins que entretanto ganharam motorista: tenta de novo os "no_driver".
    for record in V.objects.filter(outcome=V.OUTCOME_NO_DRIVER, verdict="contra").exclude(ticket__in=seen):
        with transaction.atomic():
            _apply(record, partner)
            record.save()
        if record.outcome != V.OUTCOME_NO_DRIVER:
            counts[record.outcome] += 1

    return {"ok": True, "read": len(rows), **counts}
