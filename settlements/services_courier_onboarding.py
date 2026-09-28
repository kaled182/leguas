"""Cadastro de motorista novo a partir de um courier_name sem mapping.

O EPOD_TASK_LIST_V2 só traz o login (coluna "Driver"), não o Courier ID. O
Courier ID vem da User List do CES, que o robô do ReliableMaps lê
(/api/integracoes/v1/utilizadores/); se esse endpoint não existir ou o login
não aparecer, o operador escreve-o à mão.
"""
import re

from django.core.cache import cache
from django.db import transaction

from .services_reliable_sync import ReliableSyncError, _config, _get

CES_USERS_CACHE_KEY = "settlements:ces_users"
CES_USERS_CACHE_TTL = 10 * 60
_COURIER_ID_RE = re.compile(r"^\d{6,20}$")


class OnboardingError(Exception):
    pass


def suggested_full_name(courier_name):
    """'Josuel Lobato_LF' → 'Josuel Lobato'."""
    name = re.sub(r"[\s_\-]+(LF|APOIO|MRB)$", "", (courier_name or "").strip(), flags=re.IGNORECASE)
    return re.sub(r"[_\s]+", " ", name).strip()


def _ces_users():
    """Utilizadores do CES (todos os hubs) vistos pelo ReliableMaps. [] se indisponível."""
    cached = cache.get(CES_USERS_CACHE_KEY)
    if cached is not None:
        return cached
    _, base, key = _config()
    if not base or not key:
        return []
    try:
        users = _get(base, key, "utilizadores/").json().get("utilizadores", [])
    except (ReliableSyncError, ValueError):
        users = []
    cache.set(CES_USERS_CACHE_KEY, users, CES_USERS_CACHE_TTL)
    return users


def lookup_courier_id(courier_name):
    """Procura o Courier ID de um login. Devolve dict ou None:
    {courier_id, login, source, tipo, principal, hub}.

    O login da planilha é a identidade do motorista (entregas, incidências,
    claims) e cada login tem o seu Courier ID: só conta a correspondência
    caractere a caractere. 'Donovan silva LF' e 'Donovan_silva_LF' são logins
    diferentes e nunca se misturam.

    Fontes, por ordem: Driver Statistic já importados (COURIER_DELIVERY_STATISTIC,
    colunas Courier ID + Driver) e a User List do CES via ReliableMaps.
    """
    from .models import CainiaoDriverStat

    name = (courier_name or "").strip()
    if not name:
        return None

    stat = (CainiaoDriverStat.objects.filter(courier_name=name)
            .order_by("-batch_id").values("courier_id", "courier_name").first())
    if stat:
        return {"courier_id": stat["courier_id"], "login": stat["courier_name"],
                "source": "driver_statistic", "tipo": "", "principal": "", "hub": ""}

    users = _ces_users()

    def _found(u):
        return {"courier_id": str(u.get("courier_id") or ""), "login": u.get("login") or "",
                "source": "ces", "tipo": u.get("tipo") or "", "principal": u.get("principal") or "",
                "hub": u.get("hub") or ""}

    for u in users:
        if (u.get("login") or "").strip() == name and u.get("courier_id"):
            return _found(u)
    return None


def _placeholder_nif(courier_id):
    from drivers_app.models import DriverProfile

    base = ("9" + courier_id)[-9:]
    nif, n = base, 0
    while DriverProfile.objects.filter(nif=nif).exists() and n < 99:
        n += 1
        nif = f"{base[:7]}{n:02d}"
    return nif


def create_driver_for_courier_name(old_courier_name, courier_id, nome="", nif="", telefone="", email="", user=None):
    """Cria DriverProfile PENDENTE + DriverCourierMapping + CourierNameAlias e marca
    as entregas sem Courier ID deste courier_name. Tudo ou nada."""
    from core.models import Partner
    from drivers_app.models import DriverProfile

    from .models import CainiaoOperationTask, CourierNameAlias, DriverCourierMapping

    old_courier_name = (old_courier_name or "").strip()
    courier_id = (courier_id or "").strip()
    if not old_courier_name:
        raise OnboardingError("Courier name em falta.")
    if len(old_courier_name) > 100:
        # O login é a chave: nunca se trunca (apelido tem 100 chars).
        raise OnboardingError("Login com mais de 100 caracteres: não é possível guardá-lo tal e qual.")
    if not _COURIER_ID_RE.match(courier_id):
        raise OnboardingError("Courier ID inválido: são só dígitos (ex.: 1576538850919).")

    partner = Partner.objects.filter(name__iexact="CAINIAO").first()
    if partner is None:
        raise OnboardingError("Parceiro CAINIAO não encontrado.")

    existing = DriverCourierMapping.objects.filter(partner=partner, courier_id=courier_id).select_related("driver").first()
    if existing:
        raise OnboardingError(
            f"O Courier ID {courier_id} já pertence a {existing.driver.nome_completo}. "
            "Usa \"Marcar entregas\" para ligar este nome a esse login."
        )

    nif = (nif or "").strip()
    if nif and DriverProfile.objects.filter(nif=nif).exists():
        raise OnboardingError(f"Já existe um motorista com o NIF {nif}.")

    who = f" por {user.get_username()}" if user else ""
    with transaction.atomic():
        driver = DriverProfile.objects.create(
            nif=nif or _placeholder_nif(courier_id),
            nome_completo=(nome or "").strip() or suggested_full_name(old_courier_name) or old_courier_name,
            apelido=old_courier_name,
            courier_id_cainiao=courier_id,
            telefone=(telefone or "").strip() or "000000000",
            email=(email or "").strip() or f"driver.{courier_id}@import.local",
            tipo_vinculo="DIRETO",
            status="PENDENTE",
            is_active=False,
            importado_auto=True,
            observacoes=(
                f"Criado no painel 'names sem mapping' Cainiao{who} "
                f"(login: {old_courier_name}, Courier ID: {courier_id}). "
                "Pendente de aprovação: completar NIF/dados reais."
            ),
        )
        DriverCourierMapping.objects.create(
            partner=partner, courier_id=courier_id, courier_name=old_courier_name, driver=driver,
        )
        CourierNameAlias.objects.update_or_create(
            partner=partner, courier_name=old_courier_name,
            defaults={"courier_id": courier_id, "source": "manual"},
        )
        updated = CainiaoOperationTask.objects.filter(
            courier_name=old_courier_name, courier_id_cainiao="",
        ).update(courier_id_cainiao=courier_id)

    return {"driver_id": driver.id, "driver_name": driver.nome_completo, "courier_id": courier_id, "updated": updated}
