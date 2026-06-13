"""Tasks Celery do módulo GeoZonas."""

from celery import shared_task

from .services.ingest import ingest_cp4


@shared_task(name="geozonas.ingest_cp4")
def ingest_cp4_task(cp4, com_coordenadas=False):
    """Importa um prefixo CP4 da GeoAPI de forma assíncrona."""
    return ingest_cp4(cp4, com_coordenadas=com_coordenadas)
