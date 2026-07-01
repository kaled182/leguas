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
