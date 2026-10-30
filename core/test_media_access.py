from django.contrib.auth.models import User
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings

from core.media_access import signed_media_url
from drivers_app.models import DriverDocument, DriverProfile, EmpresaParceira

AUTH_URL = "/media-auth/"


def make_driver(nif):
    return DriverProfile.objects.create(
        nif=nif, nome_completo=f"Motorista {nif}", telefone=nif,
        email=f"{nif}@example.test",
    )


class MediaAuthCase(TestCase):
    def check(self, name, query=""):
        return self.client.get(
            AUTH_URL, HTTP_X_FORWARDED_URI=f"/media/{name}{query}",
        ).status_code

    def setUp(self):
        self.driver = make_driver("100000001")
        self.other = make_driver("100000002")
        self.doc = "driver_documents/2026/10/cc.pdf"
        DriverDocument.objects.create(
            motorista=self.driver, tipo_documento="CC", arquivo=self.doc,
        )
        self.bill = "accounting/bills/1/fatura.pdf"

    def session(self, **values):
        session = self.client.session
        session.update(values)
        session.save()


class AnonymousTests(MediaAuthCase):
    def test_private_file_goes_to_login(self):
        self.assertEqual(self.check(self.doc), 302)

    def test_logos_stay_public(self):
        self.assertEqual(self.check("company/logos/logo.png"), 204)
        self.assertEqual(self.check("system_config/logos/logo.png"), 204)

    def test_path_traversal_is_refused(self):
        for name in ("company/../driver_documents/a.pdf", "../etc/passwd"):
            with self.subTest(name=name):
                self.assertNotEqual(self.check(name), 204)

    def test_missing_header_is_refused(self):
        self.assertEqual(self.client.get(AUTH_URL).status_code, 403)


class StaffTests(MediaAuthCase):
    def test_gestao_reads_everything(self):
        self.client.force_login(User.objects.create_superuser("g", password="x"))
        self.assertEqual(self.check(self.bill), 204)
        self.assertEqual(self.check(self.doc), 204)

    def test_operator_reads_operation_files_only(self):
        self.client.force_login(User.objects.create_user("o", password="x", is_staff=True))
        self.assertEqual(self.check(self.doc), 204)
        self.assertEqual(self.check(self.bill), 403)
        self.assertEqual(self.check("pre_invoices/faturas/2026/10/f.pdf"), 403)
        self.assertEqual(self.check("claims/evidence/2026/10/p.jpg"), 403)


class PortalTests(MediaAuthCase):
    def test_driver_reads_own_document(self):
        self.session(is_driver_authenticated=True, driver_profile_id=self.driver.id)
        self.assertEqual(self.check(self.doc), 204)

    def test_driver_cannot_read_other_driver_document(self):
        self.session(is_driver_authenticated=True, driver_profile_id=self.other.id)
        self.assertEqual(self.check(self.doc), 403)

    def test_company_reads_own_document_only(self):
        from customauth.models import EmpresaAccess
        from settlements.models import FleetDocument

        own = EmpresaParceira.objects.create(nome="Frota A", nif="200000001")
        other = EmpresaParceira.objects.create(nome="Frota B", nif="200000002")
        access = EmpresaAccess.objects.create(empresa=own, is_active=True)
        name = "fleet_documents/2026/10/seguro.pdf"
        FleetDocument.objects.create(empresa=other, file=name, kind="OTHER", description="Seguro")
        self.session(is_empresa_authenticated=True, empresa_access_id=access.id)
        self.assertEqual(self.check(name), 403)
        FleetDocument.objects.filter(file=name).update(empresa=own)
        self.assertEqual(self.check(name), 204)


class SignedUrlTests(MediaAuthCase):
    def test_signed_url_opens_the_file(self):
        name = "incidences/2026/10/30/foto.jpg"
        query = signed_media_url(name).split("?", 1)[1]
        self.assertEqual(self.check(name, f"?{query}"), 204)

    def test_signature_does_not_open_another_file(self):
        query = signed_media_url("incidences/2026/10/30/foto.jpg").split("?", 1)[1]
        self.assertNotEqual(self.check(self.doc, f"?{query}"), 204)

    @override_settings(MEDIA_URL="/media/")
    def test_storage_url_keeps_media_prefix(self):
        self.assertTrue(default_storage.url("temp/a.jpg").startswith("/media/"))

    def test_expired_signature_is_refused(self):
        name = "incidences/2026/10/30/foto.jpg"
        query = signed_media_url(name).split("?", 1)[1]
        with self.settings(PERMISSIONS_ENFORCE=True):
            import core.media_access as media

            original = media.SIGNED_URL_MAX_AGE
            media.SIGNED_URL_MAX_AGE = -1
            try:
                self.assertNotEqual(self.check(name, f"?{query}"), 204)
            finally:
                media.SIGNED_URL_MAX_AGE = original


class SwitchTests(MediaAuthCase):
    @override_settings(PERMISSIONS_ENFORCE=False)
    def test_switch_off_opens_files(self):
        self.assertEqual(self.check(self.doc), 204)


class AppApiImageTests(TestCase):
    def test_incidence_image_url_is_signed(self):
        from types import SimpleNamespace

        from app_api.serializers import incidence_dict

        image = SimpleNamespace(name="incidences/2026/10/30/foto.jpg")
        self.assertIn("?sig=", _image_url(incidence_dict, image))


def _image_url(build, image):
    from unittest import mock

    incidence = mock.MagicMock(package_image=image)
    return build(incidence)["package_image"]
