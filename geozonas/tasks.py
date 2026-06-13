"""Tasks Celery do módulo GeoZonas."""

from celery import shared_task

from .models import IngestJob
from .services.ingest import ingest_cp4


@shared_task(name="geozonas.ingest_cp4")
def ingest_cp4_task(cp4, com_coordenadas=False, job_id=None):
    """Importa um prefixo CP4 da GeoAPI de forma assíncrona, reportando progresso."""
    job = None
    if job_id:
        job = IngestJob.objects.filter(id=job_id).first()
    try:
        return ingest_cp4(cp4, com_coordenadas=com_coordenadas, job=job)
    except Exception as exc:
        if job:
            job.status = "ERRO"
            job.erro = str(exc)[:2000]
            job.save(update_fields=["status", "erro", "updated_at"])
        raise
