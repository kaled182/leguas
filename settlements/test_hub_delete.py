from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from drivers_app.models import DriverHubAssignment, DriverProfile
from settlements.models import CainiaoHub, CainiaoHubCP4


class HubDeleteTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser("adm", "a@x.pt", "x"))
        self.hub = CainiaoHub.objects.create(name="Extinto")
        self.url = reverse("cainiao-hub-delete", args=[self.hub.id])

    def test_hub_with_cp_and_driver_returns_reason(self):
        CainiaoHubCP4.objects.create(hub=self.hub, cp4="4480")
        driver = DriverProfile.objects.create(
            nif="600000001", nome_completo="Ana", apelido="Ana_LF",
            telefone="912345678", email="a1@x.pt",
        )
        DriverHubAssignment.objects.create(driver=driver, hub=self.hub)
        r = self.client.post(self.url)
        self.assertEqual(r.status_code, 409)
        self.assertIn("Ana_LF", r.json()["error"])
        self.assertTrue(CainiaoHub.objects.filter(id=self.hub.id).exists())

    def test_hub_without_driver_is_deleted(self):
        r = self.client.post(self.url)
        self.assertEqual(r.json(), {"success": True})
        self.assertFalse(CainiaoHub.objects.filter(id=self.hub.id).exists())

    def test_hub_without_cp_releases_driver(self):
        driver = DriverProfile.objects.create(
            nif="600000002", nome_completo="Rui", apelido="Rui_LF",
            telefone="912345678", email="a2@x.pt",
        )
        DriverHubAssignment.objects.create(driver=driver, hub=self.hub, cp4s=["4970"])
        r = self.client.post(self.url)
        self.assertEqual(r.json(), {"success": True})
        self.assertFalse(driver.hub_assignments.exists())
