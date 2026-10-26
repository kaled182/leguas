"""O que ainda falta descontar a um motorista: lançamentos da
conta-corrente e descontos (DriverClaim).

"Falta descontar" = ainda não saiu numa PF paga:
  - lançamento PENDENTE (entra na próxima PF) ou INCLUIDO_PF numa PF
    ainda não paga;
  - desconto pendente de aprovação, em recurso, na PF por pagar, à espera
    da próxima PF ou adiado. Descontos pagos ou removidos não entram.
"""
from decimal import Decimal

CLAIM_OPEN_CODES = ("pendente", "recurso", "em_fatura", "a_espera", "adiado")
# Estes já contam como desconto certo (aprovados).
CLAIM_CONFIRMED_CODES = ("em_fatura", "a_espera", "adiado")
# Entram na próxima PF que for emitida.
NEXT_PF_CLAIM_CODES = ("a_espera",)


def pending_deductions(driver, include_unapproved=True):
    from settlements.models import DriverClaim, PreInvoiceAdvance
    from settlements.services_claim_actions import claim_billing_state

    advances = list(
        PreInvoiceAdvance.objects.filter(driver=driver)
        .select_related("pre_invoice").order_by("-data", "-id")
    )
    to_deduct, history = [], []
    for a in advances:
        open_in_pf = (
            a.status == "INCLUIDO_PF" and a.pre_invoice_id
            and a.pre_invoice.status != "PAGO"
        )
        if a.status == "PENDENTE" or open_in_pf:
            to_deduct.append(a)
        else:
            history.append(a)

    claims = []
    for c in DriverClaim.objects.filter(driver=driver).exclude(status="REJECTED").order_by("-occurred_at"):
        state = claim_billing_state(c)
        if state["code"] not in CLAIM_OPEN_CODES:
            continue
        if not include_unapproved and state["code"] == "pendente":
            continue
        c.billing = state
        claims.append(c)

    def s(items, attr):
        return sum((getattr(i, attr) or Decimal("0") for i in items), Decimal("0"))

    adv_total = s(to_deduct, "valor")
    claims_confirmed = [c for c in claims if c.billing["code"] in CLAIM_CONFIRMED_CODES]
    claims_review = [c for c in claims if c.billing["code"] not in CLAIM_CONFIRMED_CODES]
    next_pf = (
        s([a for a in to_deduct if a.status == "PENDENTE"], "valor")
        + s([c for c in claims if c.billing["code"] in NEXT_PF_CLAIM_CODES], "amount")
    )
    return {
        "advances": to_deduct,
        "history": history,
        "advances_total": adv_total,
        "claims": claims,
        "claims_confirmed_total": s(claims_confirmed, "amount"),
        "claims_review_total": s(claims_review, "amount"),
        "claims_review_n": len(claims_review),
        "total": adv_total + s(claims_confirmed, "amount"),
        "next_pf_total": next_pf,
    }


# ════════════════════════════════════════════════════════════════════
# PF com valor negativo → transitar o saldo para a próxima PF (D2 = A)
# ════════════════════════════════════════════════════════════════════

class CarryError(Exception):
    pass


def _min_cover(items, deficit):
    """Subconjunto de [(id, valor)] com soma >= deficit e o menor excesso.
    Devolve lista de ids ou None se nem todos juntos chegam."""
    cents = [(i, int(round(v * 100))) for i, v in items if v > 0]
    need = int(round(deficit * 100))
    if sum(c for _i, c in cents) < need:
        return None
    best = None  # (soma, ids)
    reach = {0: ()}
    cap = need + max((c for _i, c in cents), default=0)
    for i, c in cents:
        for s, ids in list(reach.items()):
            t = s + c
            if t > cap:
                continue
            if t >= need:
                cand = (t, len(ids) + 1)
                if best is None or cand < (best[0], len(best[1])):  # menor excesso, depois menos lançamentos
                    best = (t, ids + (i,))
                continue
            if t not in reach:
                reach[t] = ids + (i,)
    return list(best[1]) if best else None


def carry_negative_balance(pf, user=None, dry_run=False):
    """Fecha uma PF negativa o mais perto possível de 0 €.

    1. Liberta adiantamentos (voltam a PENDENTE → entram sozinhos na
       próxima PF), escolhendo os que cobrem o défice com menor excesso.
    2. Se não chegarem, passa descontos (claims) desta PF para a próxima
       (services_claim_actions.defer_claim, com motivo).
    Só em PF CALCULADO (recalcular() repõe CALCULADO). Devolve um resumo.
    """
    from decimal import Decimal

    from django.db import transaction
    from django.utils import timezone

    from settlements.models import DriverClaim, PreInvoiceLostPackage

    if pf.status != "CALCULADO":
        raise CarryError(f"{pf.numero} está em {pf.get_status_display()}: só PF em CALCULADO.")
    deficit = -(pf.total_a_receber or Decimal("0"))
    if deficit <= 0:
        return {"pf": pf.numero, "changed": False, "message": f"{pf.numero} não está negativa."}

    advances = list(pf.adiantamentos.filter(status="INCLUIDO_PF").order_by("-data", "-id"))
    chosen = _min_cover([(a.id, a.valor) for a in advances], deficit)
    adv_moved = [a for a in advances if chosen and a.id in chosen] if chosen else list(advances)
    adv_total = sum((a.valor for a in adv_moved), Decimal("0"))
    rest = deficit - adv_total

    claims = []
    if rest > 0:
        lines = list(PreInvoiceLostPackage.objects.filter(
            pre_invoice=pf, api_source__startswith="auto:driver_claim:",
        ))
        by_claim = {}
        for line in lines:
            try:
                cid = int(line.api_source.rsplit(":", 1)[1])
            except ValueError:
                continue
            by_claim[cid] = by_claim.get(cid, Decimal("0")) + (line.valor_com_iva or line.valor or 0)
        pick = _min_cover(list(by_claim.items()), rest) or list(by_claim)
        claims = list(DriverClaim.objects.filter(id__in=pick, status="APPROVED"))

    summary = {
        "pf": pf.numero, "deficit": deficit, "changed": False,
        "advances": [(a.id, a.descricao, a.valor) for a in adv_moved],
        "advances_total": adv_total,
        "claims": [(c.id, c.amount) for c in claims],
    }
    if dry_run:
        return summary

    from settlements.services_claim_actions import defer_claim

    with transaction.atomic():
        if adv_moved:
            type(adv_moved[0]).objects.filter(id__in=[a.id for a in adv_moved]).update(
                status="PENDENTE", pre_invoice=None,
            )
            pf.recalcular()
        for c in claims:
            defer_claim(c, user=user, reason=f"Saldo negativo da {pf.numero} transitado para a próxima PF")
        pf.refresh_from_db()
        if pf.status != "CALCULADO":
            pf.recalcular()
        stamp = timezone.now().strftime("%d/%m/%Y %H:%M")
        who = getattr(user, "username", "sistema")
        note = (
            f"[SALDO] {stamp} {who}: défice €{deficit:.2f} transitado para a próxima PF — "
            f"{len(adv_moved)} lançamento(s) €{adv_total:.2f}"
            + (f", {len(claims)} desconto(s) adiado(s)" if claims else "")
            + f". Total agora €{pf.total_a_receber:.2f}."
        )
        pf.observacoes = ((pf.observacoes or "") + "\n" + note).strip()
        pf.save(update_fields=["observacoes"])
    summary.update(changed=True, total_after=pf.total_a_receber,
                   message=f"{pf.numero}: {note.split(': ', 1)[1]}")
    return summary
