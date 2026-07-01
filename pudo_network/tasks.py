"""Tarefas Celery da Rede PUDO (autodiscovered).

Registadas no beat em `my_project/celery.py`.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="pudo_network.mark_expired")
def mark_expired():
    """Aging: passa a EXPIRADO os pacotes cujo prazo de levantamento venceu."""
    from .services import mark_expired_packages
    n = mark_expired_packages()
    if n:
        logger.info("PUDO aging: %s pacote(s) marcados como EXPIRADO.", n)
    return n


@shared_task(name="pudo_network.emit_statements")
def emit_statements():
    """Fecho periódico de extratos por loja (mensal/semanal)."""
    from .services import emit_due_statements
    stmts = emit_due_statements()
    if stmts:
        logger.info("PUDO: %s extrato(s) periódico(s) emitido(s).", len(stmts))
    return len(stmts)


@shared_task(name="pudo_network.process_upstream")
def process_upstream():
    """Prepara/drena a fila de reconciliação a montante (devoluções)."""
    from .services import process_upstream_reconciliations
    preparados, enviados = process_upstream_reconciliations()
    if preparados or enviados:
        logger.info(
            "PUDO upstream: %s preparado(s), %s enviado(s).",
            preparados, enviados,
        )
    return {"preparados": preparados, "enviados": enviados}
