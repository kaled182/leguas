"""Decisões do operador sobre um desconto (DriverClaim), com a pré-fatura em dia.

Três acções, sempre com motivo e registo de quem/quando:

  • change_claim_amount — alterar o valor. Linha em PF aberta → actualiza-se.
    Já paga → a PF paga fica intacta e a diferença entra como ajuste na PF
    aberta mais recente (marker auto:driver_claim_adjust:<id>).
  • remove_claim — tirar o desconto ao motorista (fica REJECTED). Linhas em
    PF aberta saem; o que já foi pago volta como crédito na PF aberta mais
    recente (auto:driver_claim_credit:<id>) ou na próxima gerada.
  • restore_claim — desfaz uma remoção: volta a APPROVED e a descontar.

Uma PF paga nunca é alterada. Todas as linhas deste claim vivem nos markers
auto:driver_claim:<id> (o desconto), …_adjust:<id> e …_credit:<id>.
"""
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from .services_claims_in_pf import EDITABLE_PF_STATES, apply_claim_now, claim_is_applied


class ClaimActionError(Exception):
    pass


def _markers(claim_id):
    return {
        "main": f"auto:driver_claim:{claim_id}",
        "adjust": f"auto:driver_claim_adjust:{claim_id}",
        "credit": f"auto:driver_claim_credit:{claim_id}",
    }


def _lines(claim, kind, paid=None):
    from .models import PreInvoiceLostPackage

    qs = PreInvoiceLostPackage.objects.filter(api_source=_markers(claim.id)[kind]).select_related("pre_invoice")
    if paid is True:
        qs = qs.filter(pre_invoice__status="PAGO")
    elif paid is False:
        qs = qs.exclude(pre_invoice__status="PAGO")
    return list(qs)


def _paid_total(claim):
    """Quanto deste desconto já foi efectivamente cobrado em PFs pagas."""
    total = Decimal("0")
    for kind in ("main", "adjust", "credit"):
        total += sum((line.valor or Decimal("0")) for line in _lines(claim, kind, paid=True))
    return total


def _open_pf(claim):
    from .models import DriverPreInvoice

    return (DriverPreInvoice.objects
            .filter(driver_id=claim.driver_id, status__in=EDITABLE_PF_STATES)
            .order_by("-periodo_fim").first())


def _set_open_line(claim, kind, valor, descricao):
    """Deixa uma só linha `kind` numa PF aberta com este valor (0 → sem linha).
    Devolve o número da PF, "" se não fica linha, ou None se faltava PF aberta."""
    from .models import PreInvoiceLostPackage

    touched = set()
    existing = _lines(claim, kind, paid=False)
    for line in existing[1:]:
        touched.add(line.pre_invoice)
        line.delete()
    line = existing[0] if existing else None
    pf_numero = ""
    if not valor:
        if line:
            touched.add(line.pre_invoice)
            line.delete()
    elif line:
        line.valor = valor
        line.descricao = descricao[:300]
        line.save(update_fields=["valor", "descricao"])
        touched.add(line.pre_invoice)
        pf_numero = line.pre_invoice.numero
    else:
        pf = _open_pf(claim)
        if pf is None:
            pf_numero = None
        else:
            PreInvoiceLostPackage.objects.create(
                pre_invoice=pf,
                data=timezone.now().date(),
                numero_pacote=claim.waybill_number or f"claim-{claim.id}",
                descricao=descricao[:300],
                valor=valor,
                api_source=_markers(claim.id)[kind],
                observacoes=f"DriverClaim #{claim.id}"[:300],
            )
            touched.add(pf)
            pf_numero = pf.numero
    for pf in touched:
        if pf is not None:
            pf.recalcular()
    return pf_numero


def _log(claim, user, text):
    who = user.get_username() if user else "sistema"
    stamp = timezone.localtime().strftime("%d/%m/%Y %H:%M")
    claim.review_notes = f"{claim.review_notes}\n[{stamp} · {who}] {text}".strip()
    claim.reviewed_at = timezone.now()
    claim.reviewed_by = user


def _parse_amount(raw):
    try:
        value = Decimal(str(raw).replace(",", ".").strip())
    except (InvalidOperation, ValueError):
        raise ClaimActionError(f"Valor inválido: {raw}")
    if value < 0:
        raise ClaimActionError("O valor não pode ser negativo.")
    return value.quantize(Decimal("0.01"))


def _need_reason(reason):
    reason = (reason or "").strip()
    if not reason:
        raise ClaimActionError("Indica o motivo.")
    return reason


def claim_billing_state(claim):
    """Onde está o desconto, em linguagem do operador. Devolve dict
    {code, label, pf} com code em: pendente, recurso, em_fatura, pago,
    a_espera, removido."""
    if claim.status == "PENDING":
        return {"code": "pendente", "label": "Pendente de aprovação — ainda não desconta", "pf": ""}
    if claim.status in ("APPEALED", "QUARANTINE"):
        return {"code": "recurso", "label": "Em recurso", "pf": ""}
    if claim.status == "REJECTED":
        credit = _lines(claim, "credit")
        if credit:
            return {"code": "removido", "label": "Removido — valor devolvido em crédito",
                    "pf": credit[-1].pre_invoice.numero}
        return {"code": "removido", "label": "Removido — não desconta", "pf": ""}
    open_main = _lines(claim, "main", paid=False)
    if open_main:
        return {"code": "em_fatura", "label": "Na pré-fatura (por pagar)", "pf": open_main[0].pre_invoice.numero}
    paid_main = _lines(claim, "main", paid=True)
    if paid_main:
        return {"code": "pago", "label": "Descontado em pré-fatura paga", "pf": paid_main[0].pre_invoice.numero}
    return {"code": "a_espera", "label": "À espera da próxima pré-fatura", "pf": ""}


@transaction.atomic
def change_claim_amount(claim, new_amount, user=None, reason=""):
    reason = _need_reason(reason)
    new_amount = _parse_amount(new_amount)
    if claim.status not in ("PENDING", "APPROVED"):
        raise ClaimActionError(f"Um desconto {claim.get_status_display().lower()} não se altera aqui.")
    old = claim.amount or Decimal("0")
    if new_amount == old:
        return {"changed": False, "message": "O valor é o mesmo."}
    claim.amount = new_amount
    _log(claim, user, f"Valor € {old:.2f} → € {new_amount:.2f}. Motivo: {reason}")
    claim.save(update_fields=["amount", "review_notes", "reviewed_at", "reviewed_by", "updated_at"])

    if claim.status != "APPROVED":
        return {"changed": True, "message": f"Valor alterado para € {new_amount:.2f}."}

    open_main = _lines(claim, "main", paid=False)
    if open_main:
        _set_open_line(claim, "main", new_amount, claim.description or f"Desconto claim #{claim.id}")
        return {"changed": True, "message": f"Valor alterado para € {new_amount:.2f} na pré-fatura {open_main[0].pre_invoice.numero}."}
    if _lines(claim, "main", paid=True):
        diff = new_amount - _paid_total(claim)
        pf = _set_open_line(claim, "adjust", diff, f"Ajuste do desconto do claim #{claim.id} (já pago € {old:.2f})")
        if pf is None:
            return {"changed": True, "message": "Valor alterado. Sem pré-fatura aberta: o ajuste entra quando houver uma — repete a alteração nessa altura."}
        return {"changed": True, "message": f"Valor alterado. Já estava pago: ajuste de € {diff:.2f} na pré-fatura {pf}."}
    return {"changed": True, "message": f"Valor alterado para € {new_amount:.2f}; entra assim na próxima pré-fatura."}


@transaction.atomic
def remove_claim(claim, user=None, reason=""):
    reason = _need_reason(reason)
    if claim.status == "REJECTED":
        raise ClaimActionError("Este desconto já foi removido.")
    for kind in ("main", "adjust"):
        _set_open_line(claim, kind, Decimal("0"), "")
    paid = _paid_total(claim)
    msg = "Desconto removido: já não desconta ao motorista."
    if paid > 0:
        pf = _set_open_line(claim, "credit", -paid, f"Devolução do desconto removido — claim #{claim.id}")
        msg = (f"Desconto removido. Já tinha sido pago: € {paid:.2f} devolvidos em crédito na pré-fatura {pf}."
               if pf else f"Desconto removido. Já tinha sido pago: € {paid:.2f} voltam em crédito na próxima pré-fatura.")
    claim.status = "REJECTED"
    _log(claim, user, f"Removido da fatura do motorista. Motivo: {reason}")
    claim.save(update_fields=["status", "review_notes", "reviewed_at", "reviewed_by", "updated_at"])
    return {"message": msg}


@transaction.atomic
def restore_claim(claim, user=None, reason=""):
    reason = _need_reason(reason)
    if claim.status != "REJECTED":
        raise ClaimActionError("Só se repõe um desconto removido.")
    _set_open_line(claim, "credit", Decimal("0"), "")
    claim.status = "APPROVED"
    _log(claim, user, f"Reposto. Motivo: {reason}")
    claim.save(update_fields=["status", "review_notes", "reviewed_at", "reviewed_by", "updated_at"])
    if _lines(claim, "credit", paid=True):
        return {"message": "Reposto, mas o crédito já foi pago: confirma a próxima pré-fatura."}
    if claim_is_applied(claim):
        return {"message": "Desconto reposto."}
    r = apply_claim_now(claim)
    return {"message": f"Desconto reposto na pré-fatura {r['pf']}." if r.get("applied")
            else "Desconto reposto; entra na próxima pré-fatura."}


def carry_forward_pending_credits(pre_invoice):
    """Na geração de uma PF: créditos de descontos removidos que já estavam
    pagos e ainda não tinham PF aberta onde entrar."""
    from .models import DriverClaim

    added = 0
    for claim in DriverClaim.objects.filter(driver_id=pre_invoice.driver_id, status="REJECTED"):
        if _lines(claim, "credit"):
            continue
        paid = _paid_total(claim)
        if paid > 0 and _set_open_line(claim, "credit", -paid, f"Devolução do desconto removido — claim #{claim.id}"):
            added += 1
    return added
