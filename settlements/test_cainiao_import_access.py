from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse


class CainiaoImportAccessTests(TestCase):
    def test_anonymous_cannot_import(self):
        response = self.client.post(reverse("cainiao-operation-import"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login/", response["Location"])

    def test_anonymous_cannot_preview(self):
        response = self.client.post(reverse("cainiao-parcel-list-preview"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login/", response["Location"])

    def test_authenticated_user_keeps_access(self):
        user = User.objects.create_user("u", password="x", is_staff=True, is_superuser=True)
        self.client.force_login(user)
        response = self.client.post(reverse("cainiao-operation-import"))
        self.assertEqual(response.status_code, 400)

    def test_error_response_hides_internal_details(self):
        user = User.objects.create_user("u", password="x", is_staff=True, is_superuser=True)
        self.client.force_login(user)
        target = "settlements.cainiao_views._cainiao_operation_import_impl"
        with patch(target, side_effect=RuntimeError("segredo interno")):
            response = self.client.post(
                reverse("cainiao-operation-import"),
                {"ficheiro": SimpleUploadedFile("a.xlsx", b"x")},
            )
        self.assertEqual(response.status_code, 500)
        body = response.json()
        self.assertNotIn("traceback", body)
        self.assertNotIn("segredo interno", body["error"])
