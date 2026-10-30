from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.utils import timezone

GESTAO_ONLY_PATHS = [
    "/accounting/hub/",
    "/accounting/contas-a-pagar/",
    "/payroll/folhas/",
    "/pricing/tariffs/",
    "/system/",
    "/system/users/",
    "/admin/",
    "/settlements/claims/",
    "/settlements/recursos/",
    "/settlements/invoices/",
    "/driversapp/admin/pagamentos/",
    "/driversapp/portal/1/faturas/",
    "/driversapp/portal/1/descontos/",
    "/core/partners/1/financial/",
    "/core/partners/create/",
    "/contracts/admin/templates/",
    "/analytics/reports/fleet-costs/",
    "/dashboard_v2/",
]

OPERATOR_PATHS = [
    "/",
    "/driversapp/admin/central/",
    "/driversapp/admin/criar/",
    "/driversapp/admin/aprovar/",
    "/settlements/packages/",
    "/settlements/pudo/fake-delivery-suspects/",
    "/settlements/cainiao/map/",
    "/core/partners/",
    "/contracts/admin/signed/",
    "/analytics/integrations/status/",
]

PUBLIC_PATHS = [
    "/health/",
    "/auth/login/",
    "/auth/driver/login/",
    "/auth/empresa/login/",
    "/driversapp/cadastro/",
]


class PermissionTestCase(TestCase):
    def login(self, **flags):
        user = User.objects.create_user("user", password="x", **flags)
        self.client.force_login(user)
        return user


class OperatorProfileTests(PermissionTestCase):
    def setUp(self):
        self.login(is_staff=True)

    def test_operator_opens_allowed_pages(self):
        for path in OPERATOR_PATHS:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_operator_is_refused_on_gestao_pages(self):
        for path in GESTAO_ONLY_PATHS:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 403)

    def test_operator_cannot_read_financial_models_in_admin(self):
        response = self.client.get("/admin/settlements/driverclaim/")
        self.assertEqual(response.status_code, 403)

    def test_dashboard_hides_payment_cards(self):
        response = self.client.get("/")
        self.assertNotContains(response, "PF por aprovar")


class GestaoProfileTests(PermissionTestCase):
    def test_superuser_is_never_refused(self):
        self.login(is_staff=True, is_superuser=True)
        for path in GESTAO_ONLY_PATHS + OPERATOR_PATHS:
            with self.subTest(path=path):
                self.assertNotEqual(self.client.get(path).status_code, 403)

    def test_group_member_is_gestao(self):
        user = self.login(is_staff=True)
        user.groups.add(Group.objects.create(name="Gestão"))
        self.assertEqual(self.client.get("/accounting/hub/").status_code, 200)

    def test_dashboard_shows_payment_cards(self):
        self.login(is_staff=True, is_superuser=True)
        self.assertContains(self.client.get("/"), "PF por aprovar")


INTERNAL_PATHS = [
    path for path in OPERATOR_PATHS + GESTAO_ONLY_PATHS
    if not path.startswith("/driversapp/portal/")
]


class NoProfileTests(PermissionTestCase):
    def test_user_without_staff_is_refused(self):
        self.login()
        for path in INTERNAL_PATHS:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 403)

    def test_anonymous_goes_to_login(self):
        for path in INTERNAL_PATHS:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/auth/login/", response["Location"])


class PortalSessionTests(TestCase):
    def client_with_session(self, **values):
        session = self.client.session
        session.update(values)
        session.save()
        return self.client

    def test_driver_session_stays_outside_internal_pages(self):
        client = self.client_with_session(is_driver_authenticated=True)
        for path in ("/accounting/hub/", "/settlements/packages/", "/"):
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 302)

    def test_company_session_stays_outside_internal_pages(self):
        client = self.client_with_session(is_empresa_authenticated=True)
        self.assertEqual(client.get("/accounting/hub/").status_code, 302)

    def test_portal_view_keeps_its_own_check(self):
        response = self.client.get("/driversapp/portal/1/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/driver/", response["Location"])


class AllowlistTests(TestCase):
    def test_public_pages_open_without_session(self):
        for path in PUBLIC_PATHS:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_export_keeps_its_own_key_check(self):
        self.assertEqual(self.client.get("/geozonas/api/zonas/export/").status_code, 401)

    def test_whatsapp_webhook_reaches_the_view(self):
        response = self.client.post(
            "/system/whatsapp/webhook/", "{}", content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def test_app_api_answers_without_session(self):
        self.assertEqual(self.client.get("/api/app/v1/me").status_code, 401)


class EnforceSwitchTests(PermissionTestCase):
    @override_settings(PERMISSIONS_ENFORCE=False)
    def test_switch_off_restores_previous_behaviour(self):
        self.login(is_staff=True)
        self.assertEqual(self.client.get("/accounting/hub/").status_code, 200)


LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@override_settings(CACHES=LOCMEM)
class RateLimitTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_driver_otp_send_is_limited_by_ip(self):
        for _ in range(10):
            self.client.post("/auth/driver/send-code/", {"phone": "1"})
        response = self.client.post("/auth/driver/send-code/", {"phone": "1"})
        self.assertEqual(response.status_code, 429)

    def test_driver_otp_verify_is_limited_by_ip(self):
        for _ in range(30):
            self.client.post("/auth/driver/verify-code/", {"phone": "1"})
        response = self.client.post("/auth/driver/verify-code/", {"phone": "1"})
        self.assertEqual(response.status_code, 429)

    def test_app_otp_send_is_limited_by_ip(self):
        path = "/api/app/v1/auth/request-code"
        for _ in range(10):
            self.client.post(path, "{}", content_type="application/json")
        response = self.client.post(path, "{}", content_type="application/json")
        self.assertEqual(response.status_code, 429)

    def test_public_register_is_limited_by_ip(self):
        for _ in range(10):
            self.client.post("/driversapp/cadastro/", {"nif": ""})
        response = self.client.post("/driversapp/cadastro/", {"nif": ""})
        self.assertEqual(response.status_code, 429)


class RemoteSignTests(TestCase):
    def make_pre_invoice(self, status="CALCULADO", sent_days_ago=0):
        from drivers_app.models import DriverProfile
        from settlements.models import DriverPreInvoice

        driver = DriverProfile.objects.create(
            nif="517307243", nome_completo="Ana", telefone="910000000",
            email="a@example.test",
        )
        return DriverPreInvoice.objects.create(
            numero="PF-T1", driver=driver, status=status,
            periodo_inicio=timezone.localdate(), periodo_fim=timezone.localdate(),
            signed_token="token-teste",
            whatsapp_sent_at=timezone.now() - timedelta(days=sent_days_ago),
        )

    URL = "/core/pre-invoice/sign/token-teste/"

    def test_valid_link_signs_once(self):
        pre = self.make_pre_invoice()
        self.client.post(self.URL)
        pre.refresh_from_db()
        first_signature = pre.signed_at
        self.assertEqual(pre.status, "APROVADO")
        pre.status = "PAGO"
        pre.save(update_fields=["status"])
        self.client.post(self.URL)
        pre.refresh_from_db()
        self.assertEqual(pre.status, "PAGO")
        self.assertEqual(pre.signed_at, first_signature)

    def test_expired_link_does_not_sign(self):
        pre = self.make_pre_invoice(sent_days_ago=8)
        self.client.post(self.URL)
        pre.refresh_from_db()
        self.assertIsNone(pre.signed_at)
        self.assertEqual(pre.status, "CALCULADO")

    def test_paid_invoice_cannot_be_signed(self):
        pre = self.make_pre_invoice(status="PAGO")
        self.client.post(self.URL)
        pre.refresh_from_db()
        self.assertIsNone(pre.signed_at)
        self.assertEqual(pre.status, "PAGO")
