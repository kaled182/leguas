"""Celery tasks de drivers_app — reclamações, etc."""
import logging
from decimal import Decimal

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


# Valor default de claim para reclamação não respondida no prazo.
# €30 corresponde a LM-F7 da Cainiao (perda standard).
DEFAULT_AUTO_CLAIM_AMOUNT = Decimal("30.00")


@shared_task(name="drivers_app.auto_close_expired_complaints")
def auto_close_expired_complaints():
    """Cenário 3 — fecha reclamações com deadline expirada.

    Critério:
      - status ∈ {ABERTO, NOTIFICADO}
      - deadline NÃO nulo e < agora
      - sem resposta_driver
      - sem DriverClaim já associado (idempotente)

    Para cada uma:
      1. Cria DriverClaim (claim_type baseado em complaint.tipo)
      2. Aprova o claim → dispara auto_include_approved_claims (inclui
         na PF aberta como PreInvoiceLostPackage)
      3. Marca a reclamação como FECHADO
      4. Regista resposta_driver = '[Auto] Sem resposta no prazo'

    Devolve dict com contagem para audit.
    """
    from .models import CustomerComplaint
    from settlements.models import DriverClaim

    now = timezone.now()
    qs = (
        CustomerComplaint.objects
        .filter(status__in=("ABERTO", "NOTIFICADO"))
        .filter(deadline__isnull=False, deadline__lt=now)
        .filter(Q(resposta_driver__isnull=True) | Q(resposta_driver=""))
        .exclude(driver_claims__isnull=False)
        .select_related("driver")
    )

    type_map = {
        "ENTREGA_FALSA": "CUSTOMER_COMPLAINT",
        "ITEM_FALTANDO": "ORDER_LOSS",
        "PACOTE_DANIFICADO": "ORDER_DAMAGE",
        "ENTREGA_ATRASADA": "LATE_DELIVERY",
        "OUTRO": "CUSTOMER_COMPLAINT",
    }

    processed = 0
    errors = []
    for complaint in qs:
        try:
            claim_type = type_map.get(
                complaint.tipo, "CUSTOMER_COMPLAINT",
            )
            occurred = complaint.data_entrega or complaint.created_at

            description = (
                f"[AUTO] Reclamação #{complaint.id} fechada por "
                f"vencimento do prazo (deadline {complaint.deadline:%d/%m/%Y %H:%M}).\n"
                f"Cliente: {complaint.nome_cliente or '—'} "
                f"({complaint.telefone_cliente or '—'})\n"
                f"Pacote: {complaint.numero_pacote}\n"
                f"Tipo: {complaint.get_tipo_display()}\n"
                f"Relato: {complaint.descricao[:1500] if complaint.descricao else ''}"
            )[:2000]

            claim = DriverClaim.objects.create(
                driver=complaint.driver,
                customer_complaint=complaint,
                claim_type=claim_type,
                amount=DEFAULT_AUTO_CLAIM_AMOUNT,
                description=description,
                occurred_at=occurred,
                waybill_number=complaint.numero_pacote or "",
                status="PENDING",
            )

            # Aprovar → dispara auto-inclusão em PF
            claim.approve(
                user=None,
                notes="Auto-aprovado por vencimento do prazo de resposta.",
            )

            # Fechar reclamação
            complaint.status = "FECHADO"
            complaint.data_fecho = now
            if not complaint.resposta_driver:
                complaint.resposta_driver = (
                    "[Auto] Sem resposta no prazo — claim aplicado."
                )
            complaint.save(update_fields=[
                "status", "data_fecho", "resposta_driver", "updated_at",
            ])

            processed += 1
            logger.info(
                "[auto_close_complaints] Reclamação #%s fechada · "
                "Claim #%s criado (€%s, driver=%s).",
                complaint.id, claim.id, DEFAULT_AUTO_CLAIM_AMOUNT,
                complaint.driver_id,
            )
        except Exception as exc:
            logger.exception(
                "[auto_close_complaints] Erro a fechar reclamação #%s: %s",
                complaint.id, exc,
            )
            errors.append({"complaint_id": complaint.id, "error": str(exc)})

    result = {
        "processed": processed,
        "errors": errors,
        "ran_at": now.isoformat(),
    }
    logger.info("[auto_close_complaints] %s", result)
    return result
