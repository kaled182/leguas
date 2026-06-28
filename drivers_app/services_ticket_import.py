"""Serviços de importação/processamento da planilha de *exceptions* Cainiao.

A planilha exportada da plataforma Cainiao tem (entre outras) as colunas:

    Exception ID | LP number | Tracking Number | Ticket No. |
    Exception Creation Time | Exception Type | Exception name |
    Description | Ticket Type | Exception Resource | Exception Stage |
    ... | HUB | STATION | DSP Partner | Driver's name | ...

O `Tracking Number` (CNPRT…) é o nosso waybill. A coluna `Driver's name`
vem quase sempre vazia, por isso resolvemos o motorista pelo nosso sistema
(CainiaoOperationTask → courier), e cruzamos o estado interno com
CustomerComplaint (reclamação) e settlements.DriverClaim (recurso/desconto).
"""
from __future__ import annotations

from django.utils import timezone


# Mapeamento "Exception name" → tipo de reclamação interno (CustomerComplaint)
# Inclui variantes da Cainiao em chinês (ex.: 虚假试投 = Fake Delivery).
EXCEPTION_TO_TIPO = {
    "fake delivery": "ENTREGA_FALSA",
    "虚假试投": "ENTREGA_FALSA",
    "expedited delivery": "ENTREGA_ATRASADA",
    "missing item": "ITEM_FALTANDO",
    "faltan": "ITEM_FALTANDO",
    "damaged": "PACOTE_DANIFICADO",
    "parcel lost": "OUTRO",
    "lost": "OUTRO",
}

# Normalização dos cabeçalhos da planilha → chave canónica.
HEADER_ALIASES = {
    "exception id": "exception_id",
    "lp number": "lp_number",
    "tracking number": "waybill_number",
    "ticket no.": "ticket_no",
    "ticket no": "ticket_no",
    "exception creation time": "exception_creation_time",
    "exception type": "exception_type",
    "exception name": "exception_name",
    "description": "description",
    "ticket type": "ticket_type",
    "exception resource": "exception_resource",
    "exception stage": "exception_stage",
    "hub": "hub",
    "station": "station",
    "dsp partner": "dsp_partner",
    "driver's name": "driver_name_raw",
    "drivers name": "driver_name_raw",
    "handling method": "handling_method",
    "processing result": "processing_result",
}


def _norm_header(h) -> str:
    return str(h or "").strip().lower()


def _cell(v):
    if v is None:
        return ""
    return str(v).strip()


def _parse_dt(raw):
    """A planilha traz strings tipo '2026-06-26 09:42:22'. Devolve tz-aware."""
    if raw is None or raw == "":
        return None
    from django.utils.dateparse import parse_datetime
    from datetime import datetime
    dt = None
    if isinstance(raw, datetime):
        dt = raw
    else:
        s = str(raw).strip()
        dt = parse_datetime(s)
        if dt is None:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M"):
                try:
                    dt = datetime.strptime(s, fmt)
                    break
                except ValueError:
                    continue
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt


def parse_workbook(file_obj):
    """Lê a 1ª folha do xlsx e devolve uma lista de dicts (chaves canónicas).

    Tolerante a colunas extra/reordenadas — mapeia pelos cabeçalhos.
    """
    import openpyxl

    # NB: NÃO usar read_only=True — alguns exports da Cainiao trazem a
    # metainformação de dimensões corrompida (A1:A1), e o modo read_only
    # confia nela, devolvendo 0 linhas. O modo normal lê tudo.
    wb = openpyxl.load_workbook(file_obj, data_only=True)
    ws = wb.worksheets[0]
    rows_iter = ws.iter_rows(values_only=True)

    try:
        header = next(rows_iter)
    except StopIteration:
        return []

    # índice de coluna → chave canónica
    col_map = {}
    for idx, h in enumerate(header):
        key = HEADER_ALIASES.get(_norm_header(h))
        if key:
            col_map[idx] = key

    parsed = []
    for row in rows_iter:
        if row is None or all(c is None or _cell(c) == "" for c in row):
            continue
        rec = {"raw": {}}
        for idx, value in enumerate(row):
            # guarda tudo no raw (cabeçalho original)
            if idx < len(header):
                rec["raw"][_cell(header[idx]) or f"col{idx}"] = _cell(value)
            key = col_map.get(idx)
            if key:
                rec[key] = _cell(value)
        # precisa de pelo menos waybill ou ticket
        if rec.get("waybill_number") or rec.get("ticket_no"):
            parsed.append(rec)

    wb.close()
    return parsed


# ─────────────────────────────────────────────────────────────────────────
# Resolução de motorista a partir do waybill
# ─────────────────────────────────────────────────────────────────────────
def _resolve_driver_from_courier(courier_id, courier_name):
    """courier_id_cainiao → apelido → nome_completo. Devolve DriverProfile|None."""
    from .models import DriverProfile
    if courier_id:
        d = DriverProfile.objects.filter(courier_id_cainiao=courier_id).first()
        if d:
            return d
    name = (courier_name or "").strip()
    if name and name.upper() != "SYSTEM":
        d = DriverProfile.objects.filter(apelido__iexact=name).first()
        if d:
            return d
        d = DriverProfile.objects.filter(nome_completo__iexact=name).first()
        if d:
            return d
    return None


def resolve_driver_for_waybill(waybill, fallback_name=""):
    """Resolve o motorista responsável pela entrega de um waybill.

    1) CainiaoOperationTask mais recente do waybill → courier_id/courier_name
    2) Fallback: nome da planilha (`Driver's name`) por apelido/nome.
    """
    from settlements.models import CainiaoOperationTask, DriverClaim

    wb = DriverClaim.normalize_waybill(waybill) or (waybill or "").strip()
    if wb:
        task = (
            CainiaoOperationTask.objects.filter(waybill_number=wb)
            .order_by("-task_date", "-id")
            .first()
        )
        if task:
            d = _resolve_driver_from_courier(
                getattr(task, "courier_id_cainiao", "") or "",
                task.courier_name or "",
            )
            if d:
                return d
    # Fallback pelo nome vindo da planilha
    if fallback_name:
        return _resolve_driver_from_courier("", fallback_name)
    return None


# ─────────────────────────────────────────────────────────────────────────
# Cruzamento do estado interno
# ─────────────────────────────────────────────────────────────────────────
def classify_internal_status(waybill):
    """Cruza o waybill com reclamações e claims e devolve um tuplo:

        (internal_status, complaint_obj_or_None, claim_pk_or_None)

    Prioridade: DESCONTADA > EM_RECURSO > (FECHADA/ABERTA) > SEM_RECLAMACAO.
    """
    from .models import CustomerComplaint, TicketImportRow
    from settlements.models import DriverClaim

    wb = (waybill or "").strip()
    if not wb:
        return (TicketImportRow.STATUS_SEM_RECLAMACAO, None, None)

    # Claim activo (recurso/desconto) tem prioridade — é dinheiro envolvido.
    claim = DriverClaim.active_claim_for_waybill(wb)
    claim_pk = claim.pk if claim else None
    if claim:
        if claim.status == "APPROVED":
            status_claim = TicketImportRow.STATUS_DESCONTADA
        elif claim.status == "APPEALED":
            status_claim = TicketImportRow.STATUS_EM_RECURSO
        else:
            status_claim = None  # PENDING/QUARANTINE → deixa decidir pela reclamação
    else:
        status_claim = None

    # Reclamação interna (não cancelada) mais recente do waybill.
    complaint = (
        CustomerComplaint.objects
        .filter(numero_pacote__iexact=wb)
        .exclude(status="CANCELADO")
        .order_by("-created_at")
        .first()
    )

    if status_claim is not None:
        return (status_claim, complaint, claim_pk)

    if complaint:
        if complaint.status == "FECHADO":
            return (TicketImportRow.STATUS_FECHADA, complaint, claim_pk)
        return (TicketImportRow.STATUS_ABERTA, complaint, claim_pk)

    return (TicketImportRow.STATUS_SEM_RECLAMACAO, None, claim_pk)


def lookup_customer_data(waybill):
    """Dados consolidados do destinatário/morada para auto-preencher a
    reclamação ao abrir em massa. Mesma lógica de
    ``views.waybill_lookup_for_complaint`` (Task → Delivery → Planning)."""
    from settlements.models import CainiaoOperationTask

    wb = (waybill or "").strip()
    out = {
        "nome_cliente": "", "telefone_cliente": "", "email_cliente": "",
        "morada": "", "codigo_postal": "", "cidade": "", "data_entrega": None,
    }
    if not wb:
        return out

    task = (
        CainiaoOperationTask.objects.filter(waybill_number=wb)
        .order_by("-task_date", "-id").first()
    )
    if task:
        out["morada"] = task.detailed_address or ""
        out["codigo_postal"] = task.zip_code or ""
        out["cidade"] = task.destination_city or ""
        out["data_entrega"] = task.delivery_time

    try:
        from settlements.models import CainiaoDelivery
        d = CainiaoDelivery.objects.filter(tracking_number=wb).order_by("-id").first()
        if d:
            out["nome_cliente"] = out["nome_cliente"] or (d.receiver_name or "")
            out["telefone_cliente"] = out["telefone_cliente"] or (
                d.receiver_phone or getattr(d, "receiver_contact_number", "") or ""
            )
            out["email_cliente"] = out["email_cliente"] or (d.receiver_email or "")
            out["morada"] = out["morada"] or (d.receiver_address or "")
            out["codigo_postal"] = out["codigo_postal"] or (d.receiver_zip or "")
            out["cidade"] = out["cidade"] or (d.receiver_city or "")
    except Exception:
        pass

    try:
        from settlements.models import CainiaoPlanningPackage
        p = (CainiaoPlanningPackage.objects
             .filter(waybill_number=wb).order_by("-id").first())
        if p:
            out["codigo_postal"] = out["codigo_postal"] or (p.receiver_zip or "")
            out["cidade"] = out["cidade"] or (p.receiver_city or "")
            out["morada"] = out["morada"] or (p.receiver_address or "")
    except Exception:
        pass

    return out


def suggest_tipo(exception_name):
    key = (exception_name or "").strip().lower()
    for frag, tipo in EXCEPTION_TO_TIPO.items():
        if frag in key:
            return tipo
    return "ENTREGA_FALSA"


def normalize_category(exception_name):
    """Normaliza o 'Exception name' (inclui variantes em chinês) numa das
    categorias de TicketImportRow."""
    from .models import TicketImportRow as R
    key = (exception_name or "").strip().lower()
    if "expedited" in key:
        return R.CAT_EXPEDITED
    if "fake" in key or "虚假" in key:
        return R.CAT_FAKE_DELIVERY
    if "lost" in key or "丢失" in key:
        return R.CAT_PARCEL_LOST
    return R.CAT_OTHER


def get_delivery_info(waybill):
    """Verifica se o pacote foi entregue (CainiaoOperationTask.task_status
    == 'Delivered'). Devolve (is_delivered, delivered_at)."""
    from settlements.models import CainiaoOperationTask, DriverClaim

    wb = DriverClaim.normalize_waybill(waybill) or (waybill or "").strip()
    if not wb:
        return (None, None)
    task = (
        CainiaoOperationTask.objects.filter(waybill_number=wb)
        .order_by("-task_date", "-id").first()
    )
    if not task:
        return (None, None)
    delivered = (task.task_status or "").strip().lower() == "delivered"
    if not delivered and task.delivery_time:
        delivered = True  # tem timestamp de entrega
    return (delivered, task.delivery_time)


# ─────────────────────────────────────────────────────────────────────────
# Preview: contar categorias da planilha SEM criar nada
# ─────────────────────────────────────────────────────────────────────────
def preview_categories(file_obj):
    """Faz parse e devolve a contagem por categoria, para o operador
    escolher o que importar. Não toca na BD."""
    from .models import TicketImportRow as R
    records = parse_workbook(file_obj)
    counts = {}
    for rec in records:
        cat = normalize_category(rec.get("exception_name", ""))
        counts[cat] = counts.get(cat, 0) + 1
    labels = dict(R.CATEGORY_CHOICES)
    types = [
        {"category": c, "label": labels.get(c, c), "count": n}
        for c, n in sorted(counts.items(), key=lambda kv: -kv[1])
    ]
    return {"total": len(records), "types": types}


# ─────────────────────────────────────────────────────────────────────────
# Orquestração: criar batch + linhas a partir do ficheiro
# ─────────────────────────────────────────────────────────────────────────
def create_batch_from_file(file_obj, filename="", user=None,
                           categories=None, auto_close_delivered=True):
    """Faz parse da planilha, cria o batch e popula as linhas já cruzadas.

    - ``categories``: lista de categorias a importar (None = todas).
    - ``auto_close_delivered``: tickets Expedited Delivery cujo pacote já foi
      entregue (após a criação da exception) são fechados automaticamente,
      respeitando a linha do tempo do pacote.
    """
    from .models import TicketImportRow

    records = parse_workbook(file_obj)
    cat_filter = set(categories) if categories else None

    batch = _new_batch(filename, file_obj, user)

    rows = []
    n_kept = 0
    n_auto_closed = 0
    for rec in records:
        cat = normalize_category(rec.get("exception_name", ""))
        if cat_filter is not None and cat not in cat_filter:
            continue
        n_kept += 1

        waybill = rec.get("waybill_number", "")
        driver = resolve_driver_for_waybill(
            waybill, fallback_name=rec.get("driver_name_raw", ""),
        )
        status, complaint, claim_pk = classify_internal_status(waybill)
        is_delivered, delivered_at = get_delivery_info(waybill)
        created_dt = _parse_dt(rec.get("exception_creation_time"))

        row_action = TicketImportRow.ACTION_NONE
        notes = ""
        # Auto-fecho do Expedited entregue (atraso resolvido). Respeita a
        # linha do tempo: só fecha se a entrega é POSTERIOR à criação do
        # ticket (ou sem data, mas marcado entregue). Não mexe noutras
        # categorias nem em linhas já com reclamação/recurso/desconto.
        if (auto_close_delivered
                and cat == TicketImportRow.CAT_EXPEDITED
                and is_delivered
                and status == TicketImportRow.STATUS_SEM_RECLAMACAO):
            timeline_ok = (
                delivered_at is None
                or created_dt is None
                or delivered_at >= created_dt
            )
            if timeline_ok:
                row_action = TicketImportRow.ACTION_CLOSED
                when = (
                    delivered_at.strftime("%Y-%m-%d %H:%M")
                    if delivered_at else "data desconhecida"
                )
                notes = f"Auto-fechado: pacote entregue ({when})."
                n_auto_closed += 1

        rows.append(TicketImportRow(
            batch=batch,
            exception_id=rec.get("exception_id", "")[:60],
            lp_number=rec.get("lp_number", "")[:60],
            waybill_number=waybill[:100],
            ticket_no=rec.get("ticket_no", "")[:60],
            exception_creation_time=created_dt,
            exception_name=rec.get("exception_name", "")[:120],
            ticket_type=rec.get("ticket_type", "")[:40],
            description=rec.get("description", ""),
            hub=rec.get("hub", "")[:120],
            driver_name_raw=rec.get("driver_name_raw", "")[:200],
            raw=rec.get("raw", {}),
            driver=driver,
            internal_status=status,
            complaint=complaint,
            claim_id_ref=claim_pk,
            category=cat,
            is_delivered=is_delivered,
            delivered_at=delivered_at,
            row_action=row_action,
            operator_notes=notes,
            suggested_tipo=suggest_tipo(rec.get("exception_name", "")),
        ))

    TicketImportRow.objects.bulk_create(rows, batch_size=200)
    batch.total_rows = n_kept
    batch.save(update_fields=["total_rows"])
    batch.n_auto_closed = n_auto_closed  # atributo efémero p/ feedback
    return batch


def _new_batch(filename, file_obj, user):
    from .models import TicketImportBatch
    return TicketImportBatch.objects.create(
        nome="",
        ficheiro_nome=filename or getattr(file_obj, "name", ""),
        total_rows=0,
        created_by=user,
    )


def sync_batch_statuses(batch):
    """Re-sincroniza o estado interno de TODAS as linhas do lote com a
    realidade do sistema (reclamação + claim) — respeitando a "vida" do
    ticket em ambos os sentidos. Não toca na disposição do operador
    (row_action). Devolve o nº de linhas alteradas. Eficiente: poucas
    queries independentemente do nº de linhas."""
    from .models import CustomerComplaint, TicketImportRow
    from settlements.models import DriverClaim

    rows = list(batch.rows.all())
    if not rows:
        return 0

    def _key(wb):
        return DriverClaim.normalize_waybill(wb) or (wb or "").strip().upper()

    raw_waybills = [r.waybill_number for r in rows if r.waybill_number]
    if not raw_waybills:
        return 0

    # Reclamação não-cancelada mais recente por waybill
    comp_map = {}
    for c in (CustomerComplaint.objects
              .filter(numero_pacote__in=raw_waybills)
              .exclude(status="CANCELADO")
              .order_by("-created_at")):
        k = _key(c.numero_pacote)
        if k not in comp_map:
            comp_map[k] = c

    # Claim activo (não rejeitado) mais antigo por waybill
    claim_map = {}
    for cl in (DriverClaim.objects
               .filter(waybill_number__in=raw_waybills)
               .exclude(status="REJECTED")
               .order_by("created_at")):
        k = _key(cl.waybill_number)
        if k not in claim_map:
            claim_map[k] = cl

    changed = []
    for r in rows:
        k = _key(r.waybill_number)
        complaint = comp_map.get(k)
        claim = claim_map.get(k)

        new_status = TicketImportRow.STATUS_SEM_RECLAMACAO
        if claim and claim.status == "APPROVED":
            new_status = TicketImportRow.STATUS_DESCONTADA
        elif claim and claim.status == "APPEALED":
            new_status = TicketImportRow.STATUS_EM_RECURSO
        elif complaint:
            new_status = (
                TicketImportRow.STATUS_FECHADA
                if complaint.status == "FECHADO"
                else TicketImportRow.STATUS_ABERTA
            )

        new_complaint_id = complaint.id if complaint else None
        new_claim_id = claim.id if claim else None

        if (r.internal_status != new_status
                or r.complaint_id != new_complaint_id
                or r.claim_id_ref != new_claim_id):
            r.internal_status = new_status
            r.complaint_id = new_complaint_id
            r.claim_id_ref = new_claim_id
            changed.append(r)

    if changed:
        TicketImportRow.objects.bulk_update(
            changed, ["internal_status", "complaint", "claim_id_ref"],
        )
    return len(changed)


def auto_close_delivered_expedited(batch):
    """Re-verifica os tickets Expedited Delivery do batch e fecha os que já
    estão entregues (atraso resolvido), respeitando a linha do tempo.
    Devolve o nº de linhas fechadas. Idempotente."""
    from .models import TicketImportRow

    qs = batch.rows.filter(
        category=TicketImportRow.CAT_EXPEDITED,
        row_action=TicketImportRow.ACTION_NONE,
        internal_status=TicketImportRow.STATUS_SEM_RECLAMACAO,
    )
    n = 0
    for row in qs:
        is_delivered, delivered_at = get_delivery_info(row.waybill_number)
        if not is_delivered:
            continue
        created_dt = row.exception_creation_time
        if not (delivered_at is None or created_dt is None
                or delivered_at >= created_dt):
            continue
        row.is_delivered = True
        row.delivered_at = delivered_at
        row.row_action = TicketImportRow.ACTION_CLOSED
        when = (
            delivered_at.strftime("%Y-%m-%d %H:%M")
            if delivered_at else "data desconhecida"
        )
        extra = f"Auto-fechado: pacote entregue ({when})."
        row.operator_notes = (
            (row.operator_notes + "\n" + extra).strip()
            if row.operator_notes else extra
        )
        row.save(update_fields=[
            "is_delivered", "delivered_at", "row_action",
            "operator_notes", "updated_at",
        ])
        n += 1
    return n
