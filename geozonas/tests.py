from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import NoReverseMatch, reverse

from .services.triagem import resolver_triagem


class RemovedPagesTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_user("adm", password="x", is_staff=True))

    def test_pages_are_gone(self):
        for url in (
            "/sorting/", "/sorting/historico/", "/geozonas/mapa/",
            "/geozonas/catalogo/", "/geozonas/api/zonas/",
        ):
            self.assertEqual(self.client.get(url).status_code, 404, url)

    def test_menu_has_no_links(self):
        r = self.client.get(reverse("drivers_app:drivers_central"))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "/geozonas/")
        self.assertNotContains(r, "/sorting/")

    def test_sorting_namespace_is_gone(self):
        with self.assertRaises(NoReverseMatch):
            reverse("sorting:workspace")


class KeptConsumersTests(TestCase):
    url = "/geozonas/api/zonas/export/"

    @override_settings(ZONAS_EXPORT_KEY="chave")
    def test_export_for_reliablemaps(self):
        self.assertEqual(Client().get(self.url).status_code, 401)
        r = Client().get(self.url, HTTP_AUTHORIZATION="Bearer chave")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["type"], "FeatureCollection")

    def test_triage_for_mobile_app(self):
        self.assertTrue(resolver_triagem("4990-008")["ok"])
