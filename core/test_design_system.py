from django.contrib.auth.models import AnonymousUser, User
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase

from core.templatetags.ui import eur, pct, pt_int, status_label, status_tone

NBSP = " "


class FormatTests(SimpleTestCase):
    def test_money(self):
        self.assertEqual(eur(1234.56), f"1{NBSP}234,56{NBSP}€")
        self.assertEqual(eur("-8865.93"), f"−8{NBSP}865,93{NBSP}€")
        self.assertEqual(eur(0), f"0,00{NBSP}€")
        self.assertEqual(eur(None), "—")

    def test_integer_and_percent(self):
        self.assertEqual(pt_int(3692), f"3{NBSP}692")
        self.assertEqual(pct(94.8), f"94,8{NBSP}%")

    def test_status_keeps_unknown_value(self):
        self.assertEqual(status_label("Delivered"), "Entregue")
        self.assertEqual(status_tone("Delivered"), "success")
        self.assertEqual(status_label("Novo"), "Novo")
        self.assertEqual(status_tone("Novo"), "neutral")


class PageHeaderTests(SimpleTestCase):
    def test_title_date_and_primary_action(self):
        html = render_to_string("components/page_header.html", {
            "title": "Motoristas", "subtitle": "Central",
            "action_label": "Novo motorista", "action_url": "/x/",
        })
        self.assertInHTML('<h1 class="lf-page-title">Motoristas</h1>', html)
        self.assertIn('class="lf-btn lf-btn-primary" href="/x/"', html)

    def test_no_action_without_label(self):
        html = render_to_string("components/page_header.html", {"title": "A"})
        self.assertNotIn("lf-page-actions", html)


class KpiCardTests(SimpleTestCase):
    def test_value_stays_neutral_and_delta_uses_tone(self):
        html = render_to_string("components/kpi_card.html", {
            "label": "Entregues", "value": "3 501",
            "delta": "+2 %", "delta_tone": "success",
        })
        self.assertIn('<span class="lf-kpi-value">3 501</span>', html)
        self.assertIn("lf-tone-success", html)

    def test_link_when_url_is_given(self):
        html = render_to_string("components/kpi_card.html", {"label": "A", "value": "1", "url": "/y/"})
        self.assertIn('<a class="lf-kpi" href="/y/">', html)


class DataTableTests(TestCase):
    columns = [{"key": "name", "label": "Nome", "sortable": True}, {"key": "n", "label": "N", "numeric": True}]

    def render(self, rows, url="/?hub=1", **extra):
        request = RequestFactory().get(url)
        request.user = AnonymousUser()
        request.session = {}
        return render_to_string("components/data_table.html", {
            "columns": self.columns, "rows": rows, "request": request, **extra,
        }, request=request)

    def test_rows_and_count(self):
        rows = [{"cells": [{"text": "Ana"}, {"text": "2", "numeric": True}]}]
        html = self.render(rows)
        self.assertIn("Ana", html)
        self.assertIn("1 resultado", html)

    def test_count_uses_total_across_pages(self):
        html = self.render([{"cells": [{"text": "Ana"}]}], total=6)
        self.assertIn("6 resultados", html)

    def test_sort_link_keeps_filters(self):
        html = self.render([{"cells": [{"text": "Ana"}, {"text": "2"}]}])
        self.assertIn("hub=1", html)
        self.assertIn("sort=name", html)

    def test_empty_state(self):
        html = self.render([], empty_title="Sem motoristas")
        self.assertIn("Sem motoristas", html)
        self.assertNotIn("<table", html)

    def test_pagination(self):
        page = Paginator([1, 2, 3], 1).get_page(2)
        html = self.render([{"cells": [{"text": "A"}]}], page=page, total=3)
        self.assertIn("Página 2 de 3", html)
        self.assertIn("page=3", html)


class DesignPageTests(TestCase):
    def test_staff_opens_the_page(self):
        self.client.force_login(User.objects.create_user("o", password="x", is_staff=True))
        response = self.client.get("/_design/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sistema de design · Léguas Gestão")

    def test_user_without_staff_is_refused(self):
        self.client.force_login(User.objects.create_user("v", password="x"))
        self.assertEqual(self.client.get("/_design/").status_code, 403)

    def test_anonymous_goes_to_login(self):
        self.assertEqual(self.client.get("/_design/").status_code, 302)


class TailwindSafelistTests(SimpleTestCase):
    def test_dynamic_component_classes_are_kept_by_the_build(self):
        from pathlib import Path

        from django.conf import settings

        config = (Path(settings.BASE_DIR) / "theme/tailwind.config.js").read_text()
        self.assertIn("lf-(btn|tone|skeleton)-", config)


class ShellTests(TestCase):
    def login(self, **flags):
        self.client.force_login(User.objects.create_user("u", password="x", **flags))

    def test_title_uses_the_new_name(self):
        self.login(is_staff=True, is_superuser=True)
        self.assertContains(self.client.get("/"), "· Léguas Gestão</title>")

    def test_no_tailwind_cdn_in_the_shell(self):
        self.login(is_staff=True, is_superuser=True)
        response = self.client.get("/")
        self.assertNotContains(response, "cdn.tailwindcss.com")
        self.assertContains(response, "brand/app.css")

    def test_gestao_sees_finance_in_the_menu(self):
        self.login(is_staff=True, is_superuser=True)
        self.assertContains(self.client.get("/"), "Faturas de frotas subcontratadas")

    def test_operator_menu_has_no_finance(self):
        self.login(is_staff=True)
        response = self.client.get("/")
        self.assertNotContains(response, "Visão financeira")
        self.assertContains(response, "Central")

    def test_active_item_is_marked(self):
        self.login(is_staff=True, is_superuser=True)
        response = self.client.get("/driversapp/admin/central/")
        self.assertContains(response, 'aria-current="page"')


class GlobalSearchTests(TestCase):
    def login(self, **flags):
        self.client.force_login(User.objects.create_user("u", password="x", **flags))

    def setUp(self):
        from core.models import Partner
        from drivers_app.models import DriverProfile
        from settlements.models import CainiaoOperationTask
        from django.utils import timezone

        Partner.objects.create(name="Cainiao", nif="517307243", contact_email="c@example.test")
        DriverProfile.objects.create(
            nif="100000003", nome_completo="Ricardo Milhazes", telefone="910", email="r@example.test",
        )
        CainiaoOperationTask.objects.create(
            waybill_number="LF123456", task_date=timezone.localdate(), task_status="Delivered",
        )

    def labels(self, q):
        data = self.client.get("/search/", {"q": q}).json()
        return {group["label"]: [r["label"] for r in group["results"]] for group in data["groups"]}

    def test_finds_package_driver_partner_and_postal_code(self):
        self.login(is_staff=True, is_superuser=True)
        self.assertEqual(self.labels("LF1234")["Pacotes"], ["LF123456"])
        self.assertEqual(self.labels("Milhazes")["Motoristas"], ["Ricardo Milhazes"])
        self.assertEqual(self.labels("Cain")["Clientes e plataformas"], ["Cainiao"])
        self.assertEqual(self.labels("4740")["CP4"], ["4740"])

    def test_short_query_returns_nothing(self):
        self.login(is_staff=True)
        self.assertEqual(self.labels("L"), {})

    def test_anonymous_cannot_search(self):
        self.assertEqual(self.client.get("/search/", {"q": "LF12"}).status_code, 302)


class FleetInvoiceListTests(TestCase):
    def setUp(self):
        from datetime import date

        from drivers_app.models import EmpresaParceira
        from settlements.models import FleetInvoice

        self.a = EmpresaParceira.objects.create(nome="Frota A", nif="200000001")
        self.b = EmpresaParceira.objects.create(nome="Frota B", nif="200000002")
        dates = {"periodo_inicio": date(2026, 9, 1), "periodo_fim": date(2026, 9, 30)}
        FleetInvoice.objects.create(numero="FF-1", empresa=self.a, status="PAGO", **dates)
        FleetInvoice.objects.create(numero="FF-2", empresa=self.b, status="RASCUNHO", **dates)

    def test_gestao_sees_and_filters(self):
        self.client.force_login(User.objects.create_superuser("g", password="x"))
        response = self.client.get("/settlements/fleet-invoices/", {"empresa": self.a.id})
        self.assertContains(response, "FF-1")
        self.assertNotContains(response, "FF-2")

    def test_status_filter(self):
        self.client.force_login(User.objects.create_superuser("g", password="x"))
        response = self.client.get("/settlements/fleet-invoices/", {"estado": "RASCUNHO"})
        self.assertContains(response, "FF-2")
        self.assertNotContains(response, "FF-1")

    def test_operator_is_refused(self):
        self.client.force_login(User.objects.create_user("o", password="x", is_staff=True))
        self.assertEqual(self.client.get("/settlements/fleet-invoices/").status_code, 403)


class PackagesCsvTests(TestCase):
    def test_export_uses_filters_and_blocks_formulas(self):
        from django.utils import timezone
        from settlements.models import CainiaoHub, CainiaoHubCP4, CainiaoOperationTask

        hub = CainiaoHub.objects.create(name="Fão")
        CainiaoHubCP4.objects.create(hub=hub, cp4="4740")
        task = {"task_date": timezone.localdate(), "task_status": "Delivered", "zip_code": "4740-001"}
        CainiaoOperationTask.objects.create(waybill_number="LF1", courier_name="=HYPERLINK()", **task)
        CainiaoOperationTask.objects.create(waybill_number="ZZ2", courier_name="Ana", **task)
        self.client.force_login(User.objects.create_superuser("g", password="x"))

        response = self.client.get("/settlements/cainiao/packages/search/", {"export": "csv", "q": "LF1"})

        body = response.content.decode("utf-8-sig")
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("LF1", body)
        self.assertNotIn("ZZ2", body)
        self.assertIn("'=HYPERLINK()", body)


class PartnerPermissionTests(TestCase):
    """Decisão P4: o Operador não vê preços nem ações de gestão do cliente."""

    def setUp(self):
        from core.models import Partner

        self.partner = Partner.objects.create(
            name="CAINIAO",
            nif="500000000",
            contact_email="ops@example.test",
            price_per_package="1.2345",
        )
        self.operator = User.objects.create_user("op", password="x", is_staff=True)
        self.manager = User.objects.create_superuser("gestor", password="x")

    def test_operator_does_not_see_price(self):
        self.client.force_login(self.operator)
        r = self.client.get(f"/core/partners/{self.partner.pk}/")
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "Valor por pacote")
        self.assertNotContains(r, f"/core/partners/{self.partner.pk}/edit/")
        self.assertNotContains(r, "s.total_cost_eur")

    def test_manager_sees_price(self):
        self.client.force_login(self.manager)
        r = self.client.get(f"/core/partners/{self.partner.pk}/")
        self.assertContains(r, "Valor por pacote")

    def test_list_hides_delete_from_operator(self):
        self.client.force_login(self.operator)
        r = self.client.get("/core/partners/")
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "lf-menu-danger")
        self.client.force_login(self.manager)
        self.assertContains(self.client.get("/core/partners/"), "lf-menu-danger")


class MissingContractsCoverageTests(TestCase):
    def test_coverage_shows_signed_count(self):
        from datetime import timedelta

        from django.utils import timezone

        from contracts.models import ContractTemplate
        from drivers_app.models import DriverProfile

        ContractTemplate.objects.create(
            name="Termo",
            version="1.0",
            content="x",
            scope="all",
            is_active=True,
            effective_from=timezone.now().date() - timedelta(days=1),
        )
        DriverProfile.objects.create(nif="500000001", nome_completo="Ana", apelido="ana", telefone="910000000", email="ana@example.test", status="ATIVO")
        self.client.force_login(User.objects.create_superuser("g", password="x"))
        r = self.client.get("/contracts/admin/missing/")
        self.assertContains(r, ">0/1<")


class CainiaoCostVisibilityTests(TestCase):
    """Decisão P4: o custo de Não chegaram deriva do preço do cliente."""

    @classmethod
    def setUpTestData(cls):
        from datetime import date
        from decimal import Decimal

        from settlements.models import NotArrivedSnapshot, NotArrivedSnapshotRow

        cls.operator = User.objects.create_user("op", password="x", is_staff=True)
        cls.manager = User.objects.create_superuser("g", password="x")
        cls.snap = NotArrivedSnapshot.objects.create(
            snapshot_date=date(2026, 10, 30), total_packages=1, total_cost_eur=Decimal("98.76"),
        )
        NotArrivedSnapshotRow.objects.create(
            snapshot=cls.snap, waybill_number="LP1", estimated_cost_eur=Decimal("98.76"),
        )

    def _not_arrived(self, user):
        from unittest.mock import patch

        row = {
            "waybill": "LP1", "courier_name": "Ana", "courier_id_cainiao": "1", "cp4": "1000",
            "city": "Lisboa", "weight_g": 500, "business_days_stuck": 11, "sla_level": "red",
            "should_escalate": True, "estimated_cost_eur": 98.76, "first_seen": "2026-10-01",
        }
        self.client.force_login(user)
        with patch("settlements.cainiao_views._compute_not_arrived", return_value=[row]):
            return self.client.get("/settlements/cainiao/not-arrived/")

    def test_not_arrived_hides_cost_from_operator(self):
        r = self._not_arrived(self.operator)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("98.76", r.content.decode())
        self.assertEqual(r.json()["total"], 1)

    def test_not_arrived_keeps_cost_for_gestao(self):
        data = self._not_arrived(self.manager).json()
        self.assertEqual(data["summary"]["total_cost_eur"], 98.76)
        self.assertEqual(data["rows"][0]["estimated_cost_eur"], 98.76)

    def test_snapshots_hide_cost_from_operator(self):
        self.client.force_login(self.operator)
        for url in ("/settlements/cainiao/snapshots/", f"/settlements/cainiao/snapshots/{self.snap.pk}/"):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertNotIn("98.76", r.content.decode())

    def test_snapshots_keep_cost_for_gestao(self):
        self.client.force_login(self.manager)
        for url in ("/settlements/cainiao/snapshots/", f"/settlements/cainiao/snapshots/{self.snap.pk}/"):
            self.assertIn("98.76", self.client.get(url).content.decode())

    def test_snapshot_excel_hides_cost_from_operator(self):
        import io

        import openpyxl

        def header(user):
            self.client.force_login(user)
            r = self.client.get(f"/settlements/cainiao/snapshots/{self.snap.pk}/xlsx/")
            self.assertEqual(r.status_code, 200)
            return openpyxl.load_workbook(io.BytesIO(r.content)).active["A2"].value

        self.assertNotIn("98.76", header(self.operator))
        self.assertIn("98.76", header(self.manager))


class FinancialAlertResolveTests(TestCase):
    def test_page_button_reaches_resolve_route(self):
        from settlements.models import FinancialAlert

        alert = FinancialAlert.objects.create(kind="OTHER", title="Teste")
        user = User.objects.create_superuser("g", password="x")
        self.client.force_login(user)
        page = self.client.get("/core/financial-alerts/")
        self.assertContains(page, "/core/financial-alerts/${id}/resolve/")
        r = self.client.post(f"/core/financial-alerts/{alert.pk}/resolve/")
        self.assertEqual(r.status_code, 200)
        alert.refresh_from_db()
        self.assertTrue(alert.resolved)
        self.assertEqual(alert.resolved_by, user)

    def test_operator_cannot_resolve(self):
        from settlements.models import FinancialAlert

        alert = FinancialAlert.objects.create(kind="OTHER", title="Teste")
        self.client.force_login(User.objects.create_user("op", password="x", is_staff=True))
        self.client.post(f"/core/financial-alerts/{alert.pk}/resolve/")
        alert.refresh_from_db()
        self.assertFalse(alert.resolved)


class ReportPagesTests(TestCase):
    """Decisão 1A: as páginas leem a sincronização real do ReliableMaps."""

    @classmethod
    def setUpTestData(cls):
        from django.utils import timezone

        from settlements.models import ReliableEpodSync

        now = timezone.now()

        def add(n, status, hub="LIS", **extra):
            return ReliableEpodSync.objects.create(
                remote_id=n, sha256=f"{n:064d}", filename=f"epod_{n}.xlsx", hub=hub,
                remote_loaded_at=now, status=status, **extra,
            )

        add(1, "failed", hub="PRT", message="SHA-256 não confere com o anunciado.")
        add(2, "superseded")
        add(3, "imported", summary={"total_novos": 12, "total_atualizados": 34})
        cls.user = User.objects.create_superuser("g", password="x")

    def setUp(self):
        self.client.force_login(self.user)

    def test_status_page_shows_real_files(self):
        r = self.client.get("/analytics/integrations/status/")
        self.assertEqual(r.context["imported_24h"], 1)
        self.assertEqual(r.context["failed_24h"], 1)
        self.assertEqual([f.hub for f in r.context["hubs"]], ["LIS", "PRT"])
        self.assertContains(r, "epod_3.xlsx")
        self.assertNotContains(r, "epod_2.xlsx")

    def test_status_page_does_not_write(self):
        from settlements.models import ReliableEpodSync

        before = ReliableEpodSync.objects.count()
        self.client.get("/analytics/integrations/status/")
        self.client.get("/analytics/integrations/logs/")
        self.assertEqual(ReliableEpodSync.objects.count(), before)

    def test_disabled_sync_shows_no_data(self):
        r = self.client.get("/analytics/integrations/status/")
        self.assertEqual(r.context["health_status"], "unknown")
        self.assertContains(r, "Sincronização desligada")

    def test_health_rules(self):
        from datetime import datetime, timedelta, timezone as tz
        from types import SimpleNamespace

        from analytics.views import _epod_health

        cfg = SimpleNamespace(reliable_epod_sync_enabled=True, reliable_api_url="u", reliable_api_key="k")
        noon = datetime(2026, 10, 30, 12, 0, tzinfo=tz.utc)
        night = datetime(2026, 10, 30, 3, 0, tzinfo=tz.utc)
        ok = SimpleNamespace(status="imported", hub="LIS")
        bad = SimpleNamespace(status="failed", hub="PRT")
        self.assertEqual(_epod_health(cfg, [ok, bad], noon, noon), ("critical", "Último ficheiro falhou: PRT"))
        self.assertEqual(_epod_health(cfg, [ok], noon - timedelta(hours=1), noon)[0], "healthy")
        self.assertEqual(_epod_health(cfg, [ok], noon - timedelta(hours=3), noon)[0], "warning")
        self.assertEqual(_epod_health(cfg, [ok], night - timedelta(hours=4), night)[0], "healthy")

    def test_logs_page_filters(self):
        r = self.client.get("/analytics/integrations/logs/?status=failed&hub=PRT&days=30")
        self.assertEqual(r.context["total_logs"], 1)
        self.assertContains(r, '<option value="failed" selected>Falhou</option>', html=True)
        self.assertContains(r, "SHA-256")

    def test_invalid_filters_use_default_period(self):
        for query in ("days=abc", "days=0", "days=99999999999999", "integration=abc"):
            r = self.client.get(f"/analytics/integrations/logs/?{query}")
            self.assertEqual(r.status_code, 200, query)
            self.assertEqual(r.context["filters"]["days"], 7, query)

    def test_retry_route_redirects_and_does_not_write(self):
        from core.models import Partner, PartnerIntegration, SyncLog

        integration = PartnerIntegration.objects.create(
            partner=Partner.objects.create(name="C", nif="500000000", contact_email="c@example.test"),
            integration_type="API", last_sync_status="ERROR",
        )
        log = SyncLog.objects.create(integration=integration, operation="UPDATE_STATUS", status="ERROR")
        r = self.client.post(f"/analytics/integrations/logs/{log.pk}/retry/")
        self.assertRedirects(r, "/analytics/integrations/logs/")
        integration.refresh_from_db()
        self.assertEqual(integration.last_sync_status, "ERROR")
        self.assertEqual(SyncLog.objects.count(), 1)


class FinanceFormatTests(SimpleTestCase):
    def test_money_without_cents(self):
        from core.templatetags.ui import eur0

        self.assertEqual(eur0(1234.56), f"1{NBSP}235{NBSP}€")
        self.assertEqual(eur0(None), "—")

    def test_movement_status_in_portuguese(self):
        from core.templatetags.ui import fin_status

        self.assertEqual(fin_status("EM_ATRASO"), "Em atraso")
        self.assertEqual(fin_status("OUTRO"), "OUTRO")


class FinancePagesTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser("g", password="x"))

    def test_overview_pages_open(self):
        for url in ("/accounting/hub/", "/accounting/exec/", "/accounting/tesouraria/", "/accounting/dre/",
                    "/accounting/fluxo-caixa/", "/accounting/break-even/", "/accounting/a-pagar/",
                    "/accounting/contas-a-pagar/", "/accounting/impostos/", "/payroll/folhas/",
                    "/driversapp/admin/pagamentos/", "/settlements/pre-invoices/"):
            self.assertEqual(self.client.get(url, follow=True).status_code, 200, url)

    def test_executive_month_in_portuguese(self):
        r = self.client.get("/accounting/exec/?month=2026-09")
        self.assertContains(r, "Setembro de 2026")


class AuthAndErrorPagesTests(TestCase):
    def test_login_pages_use_brand_layout(self):
        for url in ("/auth/login/", "/auth/driver/login/", "/auth/empresa/login/"):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertContains(r, "lf-auth-card")
            self.assertNotContains(r, "cdn.tailwindcss.com")

    def test_login_error_stays_on_the_page(self):
        r = self.client.post("/auth/login/", {"email_or_nif": "x", "password": "y"})
        self.assertContains(r, 'class="lf-alert lf-tone-danger')
        self.assertContains(r, "Credenciais inválidas.")

    def test_driver_login_keeps_the_otp_flow(self):
        r = self.client.get("/auth/driver/login/")
        for element in ("otp-phone", "otp-code", "btn-send-code", "btn-verify-code", "pane-password", "csrfmiddlewaretoken"):
            self.assertContains(r, element)

    def test_not_found_page(self):
        self.client.force_login(User.objects.create_superuser("g", password="x"))
        r = self.client.get("/nao-existe/")
        self.assertEqual(r.status_code, 404)
        self.assertTemplateUsed(r, "404.html")

    def test_operator_blocked_page_uses_brand_layout(self):
        self.client.force_login(User.objects.create_user("op", password="x", is_staff=True))
        r = self.client.get("/accounting/hub/")
        self.assertEqual(r.status_code, 403)
        self.assertContains(r, "lf-auth-card", status_code=403)

    def test_server_error_page_has_no_template_tags(self):
        from pathlib import Path

        from django.conf import settings

        html = (Path(settings.BASE_DIR) / "templates" / "500.html").read_text(encoding="utf-8")
        self.assertNotIn("{%", html)
        self.assertNotIn("{{", html)


class CredentialMessagesTests(TestCase):
    """A palavra-passe gerada fica na página: um toast desaparecia em 5 segundos."""

    def test_new_password_block_stays_in_the_page(self):
        from pathlib import Path

        from django.conf import settings

        for name in ("admin_driver_credentials.html", "admin_empresa_credentials.html"):
            html = (Path(settings.BASE_DIR) / "customauth" / "templates" / "customauth" / name).read_text(encoding="utf-8")
            self.assertTrue("{% if messages %}" in html or "new_password" in html, name)

