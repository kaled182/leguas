"""Tasks Celery do módulo GeoZonas."""

from celery import shared_task

from .models import IngestJob
from .services.ingest import ingest_cp4, preencher_coordenadas_em_falta


def _pegar_job(job_id):
    """Marca o job como A_CORRER assim que o worker lhe toca."""
    if not job_id:
        return None
    job = IngestJob.objects.filter(id=job_id).first()
    if job:
        job.status = "A_CORRER"
        job.save(update_fields=["status", "updated_at"])
    return job


@shared_task(name="geozonas.ingest_cp4")
def ingest_cp4_task(cp4, com_coordenadas=False, job_id=None, forcar_coords=False):
    """Importa um prefixo CP4 da GeoAPI de forma assíncrona, reportando progresso."""
    job = _pegar_job(job_id)
    try:
        return ingest_cp4(
            cp4, com_coordenadas=com_coordenadas, job=job,
            forcar_coords=forcar_coords,
        )
    except Exception as exc:
        if job:
            job.status = "ERRO"
            job.erro = str(exc)[:2000]
            job.save(update_fields=["status", "erro", "updated_at"])
        raise


@shared_task(name="geozonas.coords_faltam")
def coords_faltam_task(cp4, job_id=None):
    """Vai buscar GPS só aos CP3 do prefixo que ainda não têm coordenadas."""
    job = _pegar_job(job_id)
    try:
        return preencher_coordenadas_em_falta(cp4, job=job)
    except Exception as exc:
        if job:
            job.status = "ERRO"
            job.erro = str(exc)[:2000]
            job.save(update_fields=["status", "erro", "updated_at"])
        raise
