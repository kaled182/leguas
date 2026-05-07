"""Signals do app accounting.

post_save em CainiaoHub: cria automaticamente um CostCenter type=HUB
ligado, garantindo que cada HUB tem onde alocar as suas despesas
(renda, electricidade, manutenção, salários afectos ao armazém).

Idempotente: usa get_or_create por code; se o operador já criou
manualmente, não duplica.
"""
import logging
import re

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _hub_to_cost_center_code(hub_name: str) -> str:
    """Normaliza nome do HUB para código de CostCenter.

    'Aveiro' → 'HUB-AVEIRO'
    'Ponte da Barca' → 'HUB-PONTE-DA-BARCA'
    'Fão' → 'HUB-FAO' (acentos removidos)
    """
    import unicodedata
    n = unicodedata.normalize("NFKD", hub_name or "")
    n = n.encode("ascii", "ignore").decode("ascii")
    n = re.sub(r"[^a-zA-Z0-9]+", "-", n).strip("-").upper()
    code = f"HUB-{n}"[:20]  # CostCenter.code max_length=20
    return code


@receiver(post_save, sender="settlements.CainiaoHub")
def create_cost_center_for_hub(sender, instance, created, **kwargs):
    """Quando um HUB é criado, cria CostCenter type=HUB ligado.

    Não actualiza nada em updates (mudanças de nome no HUB não
    propagam para o CostCenter — preservar referências históricas
    em Bills é prioritário sobre cosmetic sync).
    """
    if not created:
        return

    from .models import CostCenter

    # Já existe CostCenter para este HUB? (ex: criado manualmente antes)
    if CostCenter.objects.filter(cainiao_hub=instance).exists():
        return

    code = _hub_to_cost_center_code(instance.name)
    # Se o code já estiver tomado por outro CostCenter, sufixar
    base_code = code
    suffix = 2
    while CostCenter.objects.filter(code=code).exists():
        code = f"{base_code}-{suffix}"[:20]
        suffix += 1

    try:
        CostCenter.objects.create(
            code=code,
            name=instance.name,
            type=CostCenter.TYPE_HUB,
            cainiao_hub=instance,
            is_active=True,
            notes=(
                f"Centro de Custo criado automaticamente para o HUB "
                f"#{instance.id} ({instance.name})."
            ),
        )
        logger.info(
            "[accounting] CostCenter %s criado automaticamente para "
            "HUB #%s (%s)",
            code, instance.id, instance.name,
        )
    except Exception:
        logger.exception(
            "[accounting] Falha ao criar CostCenter para HUB #%s",
            instance.id,
        )
