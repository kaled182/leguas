from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import DriverDocument, DriverProfile
from .services_activity import (
    daily_activity, is_inactive, last_activity_map, refresh_driver_activity,
)


def _driver(nif, apelido="", cid="", status="ATIVO", days_old=60):
    d = DriverProfile.objects.create(
        nif=nif, nome_completo=f"Driver {nif}", apelido=apelido,
        courier_id_cainiao=cid, telefone="912345678", email=f"{nif}@x.pt",
        status=status, is_active=status == "ATIVO",
    )
    DriverProfile.objects.filter(pk=d.pk).update(
        created_at=timezone.now() - timedelta(days=days_old),
    )
    d.refresh_from_db()
    return d


def _task(waybill, day, status="Delivered", name="", cid=""):
    from settlements.models import CainiaoOperationTask

    return CainiaoOperationTask.objects.create(
        waybill_number=waybill, task_date=day, task_status=status,
        courier_name=name, courier_id_cainiao=cid,
    )


class InactivityRuleTests(TestCase):
    def test_rule_boundaries(self):
        today = timezone.localdate()
        old = timezone.now() - timedelta(days=60)
        self.assertFalse(is_inactive(today - timedelta(days=7), old, today))
        self.assertTrue(is_inactive(today - timedelta(days=8), old, today))
        # Sem atividade: conta a data de criação.
        self.assertFalse(is_inactive(None, timezone.now() - timedelta(days=3), today))
        self.assertTrue(is_inactive(None, old, today))


class ActivityMappingTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()

    def test_match_by_name_and_id(self):
        a = _driver("100000001", apelido="Ana_LF")
        b = _driver("100000002", cid="C-B")
        _task("W1", self.today - timedelta(days=2), name="Ana_LF")
        _task("W2", self.today - timedelta(days=5), cid="C-B", name="desconhecido")
        m = last_activity_map(self.today)
        self.assertEqual(m[a.id], self.today - timedelta(days=2))
        self.assertEqual(m[b.id], self.today - timedelta(days=5))

    def test_shared_id_with_other_driver_name_not_counted(self):
        """courier_id partilhado (bug EPOD): a task vai para o dono do nome."""
        hub = _driver("100000003", cid="HUB")
        other = _driver("100000004", apelido="Rui_LF")
        _task("W3", self.today, cid="HUB", name="Rui_LF")
        m = last_activity_map(self.today)
        self.assertNotIn(hub.id, m)
        self.assertEqual(m[other.id], self.today)

    def test_driver_received_is_not_activity(self):
        a = _driver("100000005", apelido="Zé_LF")
        _task("W4", self.today, status="Driver_received", name="Zé_LF")
        self.assertNotIn(a.id, last_activity_map(self.today))

    def test_attempt_failure_counts_but_not_as_delivery(self):
        a = _driver("100000006", apelido="Rita_LF")
        _task("W5", self.today, status="Attempt Failure", name="Rita_LF")
        _task("W6", self.today, status="Delivered", name="Rita_LF")
        days = daily_activity(self.today, self.today)
        self.assertEqual(days[a.id][self.today], 1)

    def test_transfer_counts_for_destination(self):
        from settlements.models import WaybillAttributionOverride

        a = _driver("100000007")
        WaybillAttributionOverride.objects.create(
            waybill_number="W7", task_date=self.today - timedelta(days=1),
            attributed_to_driver=a,
        )
        self.assertEqual(last_activity_map(self.today)[a.id], self.today - timedelta(days=1))


class RefreshActivityTests(TestCase):
    def test_inactivate_and_reactivate(self):
        today = timezone.localdate()
        idle = _driver("200000001", apelido="Idle_LF")
        busy = _driver("200000002", apelido="Busy_LF")
        new = _driver("200000003", days_old=2)
        _task("X1", today - timedelta(days=10), name="Idle_LF")
        _task("X2", today - timedelta(days=1), name="Busy_LF")

        r = refresh_driver_activity(today)
        self.assertEqual((r["checked"], r["inactivated"], r["reactivated"]), (3, 1, 0))
        idle.refresh_from_db(); busy.refresh_from_db(); new.refresh_from_db()
        self.assertEqual(idle.inactive_since, today)
        self.assertEqual(idle.last_activity_date, today - timedelta(days=10))
        self.assertIsNone(busy.inactive_since)
        self.assertIsNone(new.inactive_since)
        # O cadastro não muda: continua ATIVO para PF / planeamento.
        self.assertEqual(idle.status, "ATIVO")
        self.assertTrue(idle.is_active)

        _task("X3", today, name="Idle_LF")
        r = refresh_driver_activity(today)
        self.assertEqual((r["inactivated"], r["reactivated"]), (0, 1))
        idle.refresh_from_db()
        self.assertIsNone(idle.inactive_since)


class DriversCentralViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("adm", password="x", is_staff=True)
        self.client.force_login(self.admin)
        today = timezone.localdate()
        self.active = _driver("300000001", apelido="Act_LF")
        self.inactive = _driver("300000002", apelido="Ina_LF")
        self.blocked = _driver("300000003", status="BLOQUEADO")
        _task("Y1", today, name="Act_LF")
        _task("Y2", today - timedelta(days=20), name="Ina_LF")
        refresh_driver_activity(today)
        DriverDocument.objects.create(
            motorista=self.active, tipo_documento="CONTRATO",
            arquivo=SimpleUploadedFile("c.pdf", b"%PDF-1.4"),
        )

    def _ids(self, resp):
        return {d.id for d in resp.context["drivers"]}

    def test_tabs(self):
        url = reverse("drivers_app:drivers_central")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._ids(r), {self.active.id})
        r = self.client.get(url, {"tab": "inativos"})
        self.assertEqual(self._ids(r), {self.inactive.id})
        r = self.client.get(url, {"tab": "bloqueados"})
        self.assertEqual(self._ids(r), {self.blocked.id})
        tabs = {k: n for k, _l, n in r.context["tabs"]}
        self.assertEqual(tabs, {"ativos": 1, "inativos": 1, "pendentes": 0, "bloqueados": 1, "todos": 3})

    def test_contract_flag_counts_attached_document(self):
        url = reverse("drivers_app:drivers_central")
        r = self.client.get(url, {"tab": "todos", "flag": "no_contract"})
        self.assertEqual(self._ids(r), {self.inactive.id, self.blocked.id})
        k = r.context["kpis"]
        self.assertEqual((k["no_contract"], k["active_no_contract"], k["contract_pct"]), (2, 0, 100))

    def test_kpis_and_charts(self):
        r = self.client.get(reverse("drivers_app:drivers_central"))
        k = r.context["kpis"]
        self.assertEqual((k["ativos"], k["inativos"], k["worked_today"], k["deliveries_30d"]), (1, 1, 1, 2))
        self.assertEqual(len(r.context["charts"]["days"]), 30)
        self.assertContains(r, 'id="central-charts"')

    def test_legacy_status_link(self):
        r = self.client.get(reverse("drivers_app:drivers_central"), {"status": "PENDENTE"})
        self.assertEqual(r.context["tab"], "todos")
        self.assertEqual(self._ids(r), set())

    def test_refresh_endpoint(self):
        r = self.client.post(
            reverse("drivers_app:drivers_activity_refresh"),
            {"next": "https://evil.example/"},
        )
        self.assertRedirects(r, reverse("drivers_app:drivers_central"), fetch_redirect_response=False)
