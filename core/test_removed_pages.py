from django.contrib.auth.models import User
from django.test import TestCase


class RemovedPagesRedirectTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser("g", password="x"))

    def assert_moved(self, path, target):
        response = self.client.get(path)
        self.assertRedirects(
            response, target, status_code=301, fetch_redirect_response=False,
        )

    def test_fleet_goes_to_dashboard(self):
        for path in ("/fleet/dashboard/", "/fleet/vehicles/1/", "/fleet/incidents/"):
            with self.subTest(path=path):
                self.assert_moved(path, "/")

    def test_fleet_reports_go_to_api_status(self):
        for path in (
            "/analytics/incidents/", "/analytics/vehicles/",
            "/analytics/reports/fleet-costs/",
        ):
            with self.subTest(path=path):
                self.assert_moved(path, "/analytics/integrations/status/")

    def test_pricing_goes_to_partners(self):
        for path in ("/pricing/tariffs/", "/pricing/zones/1/", "/pricing/calculator/"):
            with self.subTest(path=path):
                self.assert_moved(path, "/core/partners/")

    def test_old_accounting_pages_go_to_hub(self):
        for path in ("/accounting/", "/accounting/receitas/", "/accounting/despesas/1/", "/accounting/relatorios/"):
            with self.subTest(path=path):
                self.assert_moved(path, "/accounting/hub/")

    def test_ticket_import_goes_to_complaints(self):
        self.assert_moved("/driversapp/admin/tickets-cainiao/", "/driversapp/admin/reclamacoes/")

    def test_forecast_and_file_imports_go_to_partners(self):
        for path in (
            "/settlements/forecast-plan/", "/settlements/cainiao/forecast/cp4/",
            "/settlements/cainiao/planning/import/",
            "/settlements/cainiao/operation/import/",
            "/settlements/cainiao/parcel-list/import/",
            "/settlements/cainiao/driver-stat/import/",
            "/settlements/cainiao/driver-detail/import/",
        ):
            with self.subTest(path=path):
                self.assert_moved(path, "/core/partners/")


class EpodSyncStaysTests(TestCase):
    def test_sync_import_function_is_kept(self):
        from settlements.cainiao_views import import_operation_file

        self.assertTrue(callable(import_operation_file))


# Já partido antes do rebrand, numa página sem view (docs/seguranca/pendentes.md).
KNOWN_OLD_LINKS = {"driversmanager_manager"}


class DeadLinkTests(TestCase):
    def test_every_url_tag_resolves(self):
        import re
        from pathlib import Path

        from django.conf import settings
        from django.urls import get_resolver

        def names(resolver, prefix=""):
            found = set()
            for entry in resolver.url_patterns:
                if hasattr(entry, "url_patterns"):
                    space = f"{prefix}{entry.namespace}:" if entry.namespace else prefix
                    found |= names(entry, space)
                elif entry.name:
                    found.add(prefix + entry.name)
            return found

        known = names(get_resolver())
        missing = []
        tag = re.compile(r"""\{%\s*url\s+['"]([^'"]+)['"]""")
        for path in Path(settings.BASE_DIR).rglob("*.html"):
            if "docs" in path.parts or "staticfiles" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            missing += [
                f"{path.name}: {name}" for name in tag.findall(text)
                if name not in known and name not in KNOWN_OLD_LINKS
            ]
        self.assertEqual(missing, [])


class PartnerPagePriceTests(TestCase):
    def test_operator_template_hides_same_door_amount(self):
        from pathlib import Path

        from django.conf import settings

        path = Path(settings.BASE_DIR) / "core/templates/core/partner_detail.html"
        text = path.read_text(encoding="utf-8")
        line = next(row for row in text.splitlines() if "adicionais{% if" in row)
        self.assertLess(line.index("{% if is_gestao %}"), line.index("€"))
        self.assertGreater(line.index("{% endif %}"), line.rindex("}}"))
