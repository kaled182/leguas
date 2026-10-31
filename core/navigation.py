"""Menu da aplicação. Estrutura aprovada em docs/rebrand/02-navegacao.md."""
from django.urls import reverse

from .permissions import is_gestao, operator_can_access


def item(label, name, icon="circle", count=None):
    return {"label": label, "name": name, "icon": icon, "count_key": count}


def parent(label, icon, *children):
    return {"label": label, "icon": icon, "children": children}


MENU = (
    ("Hoje", (item("Painel do dia", "dashboard_leguas:home", "layout-dashboard"),)),
    ("Operação", (
        parent("Pacotes", "package",
               item("Pesquisa", "cainiao-packages-page"),
               item("Reclamações", "claim-list"),
               item("Recursos", "appeals-inbox"),
               item("Suspeitas de entrega falsa (PUDO)", "pudo-fake-delivery-suspects")),
        parent("Motoristas", "users",
               item("Central", "drivers_app:drivers_central"),
               item("Aprovar cadastros", "drivers_app:admin_approve_drivers", count="pending_drivers_count"),
               item("Pedidos de alteração", "drivers_app:change_requests_list", count="pending_change_requests_count"),
               item("Novo motorista", "drivers_app:admin_create_driver")),
    )),
    ("Rede", (
        parent("Clientes e plataformas", "building-2",
               item("Lista", "core:partner-list"),
               item("Integrações", "core:integrations-dashboard")),
        item("Frotas subcontratadas", "drivers_app:empresas-parceiras", "truck"),
        parent("Contratos", "file-signature",
               item("Assinados", "contracts:admin_signed_contracts"),
               item("Por assinar", "contracts:admin_missing_contracts", count="drivers_missing_contracts"),
               item("Modelos", "contracts:admin_templates_list")),
    )),
    ("Finanças", (
        parent("Visão geral", "wallet",
               item("Visão financeira", "accounting:hub_financeiro"),
               item("Resumo executivo", "accounting:executive_dashboard"),
               item("Tesouraria", "accounting:treasury_dashboard")),
        parent("Pagamentos a motoristas", "hand-coins",
               item("Pagamentos", "drivers_app:payments_dashboard"),
               item("Conta-corrente", "cash-entries-dashboard"),
               item("Pré-faturas", "pre-invoice-admin-list")),
        parent("A receber", "arrow-down-left",
               item("Reconciliação bancária", "accounting:bank_reconciliation"),
               item("Extratos OFX", "accounting:bank_statement_list")),
        parent("A pagar", "arrow-up-right",
               item("Inbox", "accounting:payables_inbox"),
               item("Contas a pagar", "accounting:bill_list"),
               item("Faturas de frotas subcontratadas", "fleet-invoice-list"),
               item("Pendentes de regularização", "accounting:pending_reconciliation"),
               item("Fornecedores", "accounting:fornecedor_list"),
               item("Folha de pagamento", "payroll:payroll_list")),
        parent("Impostos", "landmark",
               item("Impostos", "accounting:imposto_list"),
               item("Planos prestacionais", "accounting:plano_list")),
        parent("Análise", "chart-column",
               item("DRE", "accounting:dre"),
               item("Fluxo de caixa", "accounting:cash_flow"),
               item("Break-even", "accounting:break_even"),
               item("Centros de custo", "accounting:cost_center_list"),
               item("Categorias", "accounting:category_list")),
        parent("Controlo", "shield-check",
               item("Fechos de período", "accounting:period_lock_list"),
               item("Auditoria", "accounting:audit_timeline"),
               item("Calendário", "holiday-list"),
               item("Sócios e reembolsos", "shareholder-dashboard")),
    )),
    ("Relatórios", (
        item("Estado das APIs", "analytics:api_status_dashboard", "activity"),
        item("Registos de sincronização", "analytics:sync_logs_list", "list-checks"),
    )),
    ("Sistema", (
        item("Utilizadores", "system_config:user_list", "user-cog"),
        item("Configurações", "system_config:index", "settings"),
        item("Ferramentas", "management:qr-generator", "qr-code"),
    )),
)


def current_name(request):
    match = getattr(request, "resolver_match", None)
    if not match or not match.url_name:
        return ""
    name = match.url_name.removesuffix("_alias")
    return f"{match.namespace}:{name}" if match.namespace else name


def build_item(entry, request, current, counts, gestao):
    url = reverse(entry["name"])
    if not gestao and not operator_can_access(url):
        return None
    return {
        "label": entry["label"], "url": url, "icon": entry["icon"],
        "active": entry["name"] == current,
        "count": counts.get(entry["count_key"]) if entry["count_key"] else None,
    }


def build_entry(entry, request, current, counts, gestao):
    if "children" not in entry:
        return build_item(entry, request, current, counts, gestao)
    children = [
        built for built in (
            build_item(child, request, current, counts, gestao)
            for child in entry["children"]
        ) if built
    ]
    if not children:
        return None
    return {
        "label": entry["label"], "icon": entry["icon"], "children": children,
        "open": any(child["active"] for child in children),
    }


def build_menu(request, counts=None):
    user = request.user
    if not user.is_authenticated or not user.is_staff:
        return []
    gestao = is_gestao(user)
    current = current_name(request)
    groups = []
    for label, entries in MENU:
        built = [
            result for result in (
                build_entry(entry, request, current, counts or {}, gestao)
                for entry in entries
            ) if result
        ]
        if built:
            groups.append({"label": label, "items": built})
    return groups
