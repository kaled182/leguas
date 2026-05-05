"""Unificação de cadastros de motoristas.

Quando o mesmo motorista existe duas vezes na DB (ex: importação
duplicada com courier_ids diferentes), o admin pode usar
`merge_drivers(source, target, user)` para:

  1. Mover todos os FKs apontados ao `source` para `target`
     (DriverPreInvoice, DriverAccess, DriverCourierMapping, etc.)
  2. Apagar o `source` driver
  3. Gravar registo de auditoria em `DriverMergeAudit`

Tudo dentro de uma única transacção atómica — se algum passo falhar,
nada é alterado.

Estratégia: Django introspection descobre dinamicamente todos os
ForeignKey que apontam para DriverProfile. Isto evita listas
hard-coded ficarem desactualizadas quando novos modelos são
adicionados.
"""
from django.db import transaction

from .models import DriverMergeAudit, DriverProfile


def _find_driver_fk_targets():
    """Descobre todas as classes Model com FK directa para DriverProfile.

    Devolve lista de (Model, fk_field_name) percorrendo o registo de
    apps do Django. Inclui ForeignKey e OneToOneField — tanto faz para
    o `update()` que vamos fazer.

    Skips:
      - Relações inversas (related_objects)
      - ManyToMany (precisariam de tratamento separado)
      - Self-references no próprio DriverProfile
    """
    from django.apps import apps
    targets = []
    for model in apps.get_models():
        if model is DriverProfile:
            continue
        for field in model._meta.get_fields():
            if not field.is_relation:
                continue
            # Só FK e OneToOne (forward), não M2M nem reverse
            if not (
                getattr(field, "many_to_one", False)
                or getattr(field, "one_to_one", False)
            ):
                continue
            # Ignora reverse relations (são auto)
            if getattr(field, "auto_created", False) and not getattr(
                field, "concrete", False,
            ):
                continue
            related = getattr(field, "related_model", None)
            if related is DriverProfile:
                targets.append((model, field.name))
    return targets


def preview_merge(source: DriverProfile, target: DriverProfile) -> dict:
    """Conta quantas linhas serão transferidas, sem alterar nada.

    Devolve dict {"<app.Model>": int, "_total": int}.
    """
    counts = {}
    total = 0
    for Model, field_name in _find_driver_fk_targets():
        try:
            n = Model.objects.filter(**{field_name: source}).count()
        except Exception:
            continue
        if n > 0:
            label = f"{Model._meta.app_label}.{Model.__name__}"
            counts[label] = n
            total += n
    counts["_total"] = total
    return counts


@transaction.atomic
def merge_drivers(source: DriverProfile, target: DriverProfile,
                  user=None, notes: str = "") -> DriverMergeAudit:
    """Move tudo do `source` para o `target` e apaga `source`.

    Levanta ValueError se source == target ou se source/target não existem.
    Levanta RuntimeError se algum reassign falhar (toda a transacção é
    revertida via @transaction.atomic).
    """
    if source.pk == target.pk:
        raise ValueError("Source e target são o mesmo motorista.")
    if not DriverProfile.objects.filter(pk=source.pk).exists():
        raise ValueError(f"Source driver #{source.pk} não existe.")
    if not DriverProfile.objects.filter(pk=target.pk).exists():
        raise ValueError(f"Target driver #{target.pk} não existe.")

    transferred = {}
    failed = []

    for Model, field_name in _find_driver_fk_targets():
        label = f"{Model._meta.app_label}.{Model.__name__}.{field_name}"
        try:
            n = Model.objects.filter(**{field_name: source}).update(
                **{field_name: target}
            )
        except Exception as e:
            # Caso raríssimo (constraint custom, etc.) — recolhe mas não
            # interrompe se for 0 linhas afectadas.
            if Model.objects.filter(**{field_name: source}).exists():
                failed.append(f"{label}: {e}")
            continue
        if n > 0:
            transferred[
                f"{Model._meta.app_label}.{Model.__name__}"
            ] = n

    if failed:
        raise RuntimeError(
            "Falha a reassignar: " + " | ".join(failed)
        )

    # Snapshot textual do source antes de apagar
    source_repr = (
        f"#{source.pk} · {source.nome_completo} · {source.apelido or '-'}"
    )
    if source.courier_id_cainiao:
        source_repr += f" · cainiao={source.courier_id_cainiao}"

    audit = DriverMergeAudit.objects.create(
        source_driver_repr=source_repr,
        source_driver_id=source.pk,
        target_driver=target,
        transferred_counts=transferred,
        notes=notes,
        merged_by=user if (user and user.is_authenticated) else None,
    )

    source.delete()

    return audit
