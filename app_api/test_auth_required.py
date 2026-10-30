from django.test import TestCase

BASE = "/api/app/v1/"
PROTECTED_ROUTES = [
    ("post", "auth/logout"),
    ("get", "me"),
    ("get", "invoices"),
    ("get", "invoices/1"),
    ("get", "invoices/1/pdf"),
    ("get", "discounts"),
    ("get", "complaints"),
    ("get", "sorting"),
    ("post", "incidences/add"),
    ("get", "incidences/history"),
    ("get", "incidences/drivers"),
    ("post", "incidences/scan"),
    ("post", "incidences/ocr"),
    ("post", "incidences/complete"),
    ("post", "incidences/confirm-ocr"),
]


class TokenRequiredTests(TestCase):
    def test_every_protected_route_returns_401_without_token(self):
        for method, path in PROTECTED_ROUTES:
            with self.subTest(path=path):
                response = getattr(self.client, method)(BASE + path)
                self.assertEqual(response.status_code, 401)

    def test_login_routes_are_reachable_without_session(self):
        for path in ("auth/request-code", "auth/verify-code"):
            with self.subTest(path=path):
                response = self.client.post(BASE + path)
                self.assertNotIn(response.status_code, (302, 401, 403))
