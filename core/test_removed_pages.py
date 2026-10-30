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
