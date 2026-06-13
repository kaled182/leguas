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
        if job:
            # Marca como "a correr" assim que o worker pega na tarefa, para a
            # UI não ficar presa em "em fila" durante a 1ª chamada à GeoAPI.
            job.status = "A_CORRER"
            job.save(update_fields=["status", "updated_at"])
    try:
        return ingest_cp4(cp4, com_coordenadas=com_coordenadas, job=job)
    except Exception as exc:
        if job:
            job.status = "ERRO"
            job.erro = str(exc)[:2000]
            job.save(update_fields=["status", "erro", "updated_at"])
        raise
