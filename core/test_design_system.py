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
