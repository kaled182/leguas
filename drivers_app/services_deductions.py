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
