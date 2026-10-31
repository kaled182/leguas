"""Controlo de acesso por perfil.

Regras aprovadas em docs/seguranca/mapa-permissoes.md e allowlist.md.
Tudo o que não estiver listado aqui é só para Gestão.
"""
import re

GESTAO_GROUP = "Gestão"

PUBLIC_PATHS = frozenset({
    "/health/",
    "/media-auth/",
    "/auth/", "/auth/authenticate/", "/auth/login/", "/auth/logout/",
    "/auth/driver/", "/auth/driver/login/", "/auth/driver/logout/",
    "/auth/driver/send-code/", "/auth/driver/verify-code/",
    "/auth/empresa/", "/auth/empresa/login/", "/auth/empresa/logout/",
    "/driversapp/logout/",
    "/driversapp/cadastro/", "/driversapp/cadastro-completo/",
    "/geozonas/api/zonas/export/",
    "/system/whatsapp/webhook/",
})

PUBLIC_PATTERNS = tuple(re.compile(p) for p in (
    r"^/api/app/v1/",
    r"^/core/pre-invoice/sign/[^/]+/$",
    r"^/static/",
    r"^/media/",
))

# A view destas rotas valida a sessão do motorista ou da frota.
PORTAL_PATTERNS = tuple(re.compile(p) for p in (
    r"^/driversapp/portal/",
    r"^/contracts/portal/",
    r"^/settlements/empresas/\d+/portal/",
))

OPERATOR_PATTERNS = tuple(re.compile(p) for p in (
    r"^/$",
    r"^/sla/prazos/$",
    r"^/_design/$",
    r"^/atencao/$",
    r"^/search/$",
    r"^/driversapp/admin/(?!pagamentos|tickets-cainiao)",
    r"^/driversapp/empresas-parceiras/$",
    r"^/driversapp/api/(waybill-lookup|complaints|admin/reclamacoes)",
    r"^/driversapp/complaints/",
    r"^/driversapp/portal/\d+/(?!faturas|financeiro|descontos|pf/|relatorios|caderneta)",
    r"^/settlements/packages/",
    r"^/settlements/pacote/",
    r"^/settlements/pudo/",
    r"^/settlements/cainiao/(?!.*(import|planning|forecast|driver-stat|parcel-list))",
    r"^/core/partners/$",
    r"^/core/partners/\d+/$",
    r"^/core/integrations/dashboard/$",
    r"^/contracts/admin/(signed|missing|gerar|gerado)",
    r"^/contracts/portal/",
    r"^/analytics/(incidents|vehicles|integrations)/",
    r"^/fleet/",
    r"^/converter/",
    r"^/management/tools/",
))


def is_gestao(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=GESTAO_GROUP).exists()


def is_public(path):
    return path in PUBLIC_PATHS or any(p.search(path) for p in PUBLIC_PATTERNS)


def is_portal(path):
    return any(p.search(path) for p in PORTAL_PATTERNS)


def operator_can_access(path):
    return any(p.search(path) for p in OPERATOR_PATTERNS)
