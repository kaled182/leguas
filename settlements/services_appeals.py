"""Acções de recurso/quarentena de DriverClaim (disputa com parceiro).

Fluxo:
  APPEALED  --enviar ao parceiro-->  QUARANTINE (estornado, relógio 60d)
  QUARANTINE --parceiro aceita-->     REJECTED   (estorno permanente)
  QUARANTINE --parceiro nega-->       APPROVED   (re-aplica o desconto)

O estorno (devolver dinheiro ao motorista) é feito por
services_claims_in_pf.revert_claim_from_preinvoices / reapply_claim.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

log = logging.getLogger(__name__)

QUARANTINE_DAYS = 60


@transaction.atomic
def send_appeals_to_partner(claim_ids, user, partner_id=None):
    """Marca um conjunto de recursos como enviados ao parceiro.

    - Cria um AppealBatch (lote).
    - Para cada claim elegível (APPEALED ou APPROVED): muda para QUARANTINE,
      regista appeal_sent_at/quarantine_until (+60d), liga ao lote e
      ESTORNA o valor (devolve ao motorista).

    Devolve (batch, summary).
    """
    from .models import AppealBatch, DriverClaim
    from .services_claims_in_pf import revert_claim_from_preinvoices

    now = timezone.now()
    until = now.date() + timedelta(days=QUARANTINE_DAYS)

    batch = AppealBatch.objects.create(
        created_by=user if getattr(user, "is_authenticated", False) else None,
        partner_id=partner_id or None,
        sent_at=now,
    )

    claims = DriverClaim.objects.filter(
        id__in=list(claim_ids),
        status__in=("APPEALED", "APPROVED"),
    )
    sent = 0
    estorno = {"removed": 0, "credited": 0, "paid_blocked": 0}
    for claim in claims:
        claim.status = "QUARANTINE"
        claim.appeal_batch = batch
        claim.appeal_sent_at = now
        claim.quarantine_until = until
        claim.partner_response = "PENDING"
        claim.save(update_fields=[
            "status", "appeal_batch", "appeal_sent_at",
            "quarantine_until", "partner_response", "updated_at",
        ])
        r = revert_claim_from_preinvoices(claim)
        for k in estorno:
            estorno[k] += r.get(k, 0)
        sent += 1

    log.info("Lote de recursos #%s enviado: %s claims, estorno=%s", batch.id, sent, estorno)
    return batch, {"sent": sent, "estorno": estorno}


@transaction.atomic
def partner_approved(claim, user, notes=""):
    """Parceiro ACEITOU o recurso — estorno fica permanente (driver não paga)."""
    claim.partner_response = "APPROVED"
    claim.status = "REJECTED"  # do ponto de vista do motorista: sem desconto
    claim.reviewed_at = timezone.now()
    claim.reviewed_by = user if getattr(user, "is_authenticated", False) else None
    if notes:
        claim.review_notes = notes
    claim.save(update_fields=[
        "partner_response", "status", "reviewed_at", "reviewed_by",
        "review_notes", "updated_at",
    ])
    log.info("Recurso do claim #%s ACEITE pelo parceiro", claim.id)
    return claim


@transaction.atomic
def partner_denied(claim, user, notes=""):
    """Parceiro NEGOU o recurso — re-aplica o desconto na PF aberta."""
    from .services_claims_in_pf import reapply_claim

    claim.partner_response = "DENIED"
    claim.status = "APPROVED"
    claim.reviewed_at = timezone.now()
    claim.reviewed_by = user if getattr(user, "is_authenticated", False) else None
    if notes:
        claim.review_notes = notes
    claim.save(update_fields=[
        "partner_response", "status", "reviewed_at", "reviewed_by",
        "review_notes", "updated_at",
    ])
    result = reapply_claim(claim)
    log.info("Recurso do claim #%s NEGADO — re-aplicado (%s)", claim.id, result)
    return claim
