from django.urls import reverse
from datetime import datetime, time, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone


class DashboardTests(TestCase):
    def setUp(self):
        from settlements.models import (
            CainiaoHub, CainiaoHubCP4, CainiaoOperationTask, CainiaoOperationTaskHistory,
        )

        self.user = User.objects.create_user("u", password="x", is_staff=True)
        self.client.force_login(self.user)
        self.today = timezone.localdate()
        hub = CainiaoHub.objects.create(name="Fão")
        CainiaoHubCP4.objects.create(hub=hub, cp4="4740")
        n = 0

        def task(status, cp="4740-001", courier="Ana_LF", day=None):
            nonlocal n
            n += 1
            day = day or self.today
            dt = timezone.make_aware(datetime.combine(day, time(10, 30)))
            CainiaoOperationTask.objects.create(
                waybill_number=f"W{n}", task_date=day, task_status=status,
                zip_code=cp, courier_name=courier,
                delivery_time=dt if status == "Delivered" else None,
            )
            CainiaoOperationTaskHistory.objects.create(
                waybill_number=f"W{n}", task_date=day, task_status=status,
                courier_name=courier, change_type="signature",
            )

        for _ in range(8):
            task("Delivered")
        for _ in range(2):
            task("Attempt Failure")
        for _ in range(3):
            task("Driver_received", cp="9999-001")
        # Outro motorista com poucas tentativas (era ele que estragava o KPI).
        task("Delivered", courier="Rui_LF")
        task("Delivered", day=self.today - timedelta(days=7))

    def test_kpis_and_regression_attempted(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        k = r.context["kpis"]
        self.assertEqual((k["total"], k["delivered"], k["failures"], k["en_route"]), (14, 9, 2, 3))
        # Bug antigo: "entregues de N tentadas" usava o N do último motorista.
        self.assertEqual(k["attempted"], 11)
        self.assertEqual(r.context["compare"]["total_d7"], 1)
        self.assertEqual(r.context["compare"]["delta_total_d7"], 1300)

    def test_hubs_charts_and_drivers(self):
        r = self.client.get("/")
        hubs = {h["name"]: h for h in r.context["hubs"]}
        self.assertEqual((hubs["Fão"]["delivered"], hubs["Fão"]["failures"]), (9, 2))
        self.assertEqual(hubs["Sem hub"]["en_route"], 3)
        ch = r.context["charts"]
        self.assertEqual(len(ch["days"]), 30)
        self.assertEqual(ch["delivered"][-1], 9)
        self.assertEqual(sum(x or 0 for x in ch["rhythm"]["avg"][:1]), 0)
        self.assertEqual(r.context["top_volume"][0]["name"], "Ana_LF")
        self.assertEqual(r.context["attention"][0]["failures"], 2)
        self.assertContains(r, 'id="dash-charts"')

    def test_tv_mode_and_past_date(self):
        d = (self.today - timedelta(days=7)).isoformat()
        r = self.client.get("/", {"date": d, "tv": "1"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.context["is_today"])
        self.assertEqual(r.context["kpis"]["delivered"], 1)


class SlaTests(TestCase):
    def test_calendar_working_days(self):
        from datetime import date

        from settlements.models import Holiday

        from .services_sla import SlaCalendar

        Holiday.objects.create(name="Implantação", date=date(2026, 10, 5))
        cal = SlaCalendar(date(2026, 10, 1), date(2026, 10, 31))
        self.assertEqual(cal.deadline(date(2026, 10, 1)), date(2026, 10, 2))   # qui → sex
        self.assertEqual(cal.deadline(date(2026, 10, 3)), date(2026, 10, 6))   # sáb → (dom, feriado) → ter
        self.assertEqual(cal.elapsed(date(2026, 10, 3), date(2026, 10, 6)), 1)
        corr = SlaCalendar(date(2026, 10, 1), date(2026, 10, 31), working_days=False)
        self.assertEqual(corr.deadline(date(2026, 10, 3)), date(2026, 10, 4))

    def test_report_by_cp4(self):
        from datetime import date, datetime, time

        from settlements.models import CainiaoHub, CainiaoHubCP4, CainiaoOperationTask

        from .services_sla import sla_report

        hub = CainiaoHub.objects.create(name="Fão")
        CainiaoHubCP4.objects.create(hub=hub, cp4="4740")
        aware = lambda d, h=8: timezone.make_aware(datetime.combine(d, time(h)))  # noqa: E731
        n = 0

        def task(cp, rec, dlv, status="Delivered", day=None):
            nonlocal n
            n += 1
            CainiaoOperationTask.objects.create(
                waybill_number=f"S{n}", task_date=day or dlv, task_status=status, zip_code=f"{cp}-001",
                receipt_time=aware(rec), delivery_time=aware(dlv, 15) if status == "Delivered" else None,
            )

        task("4740", date(2026, 10, 20), date(2026, 10, 20))   # D+0
        task("4740", date(2026, 10, 20), date(2026, 10, 21))   # D+1 no prazo
        task("4740", date(2026, 10, 19), date(2026, 10, 22))   # D+3 fora do prazo
        task("4490", date(2026, 10, 17), date(2026, 10, 19))   # sáb → seg: no prazo
        task("4740", date(2026, 10, 20), date(2026, 10, 23), status="Driver_received", day=date(2026, 10, 23))
        r = sla_report(date(2026, 10, 23), days=7)
        cps = {c["key"]: c for c in r["cps"]}
        self.assertEqual((cps["4740"]["n"], cps["4740"]["on_time"], cps["4740"]["b"]), (3, 2, [1, 1, 0, 1]))
        self.assertEqual(cps["4740"]["open_late"], 1)
        self.assertEqual(cps["4740"]["avg_late"], 2)
        self.assertEqual(cps["4490"]["sla"], 100)
        self.assertEqual((r["total"]["n"], r["total"]["on_time"]), (4, 3))
        self.assertEqual({h["key"] for h in r["hubs"]}, {"Fão", "Sem hub"})

    def test_dashboard_renders_sla(self):
        user = User.objects.create_user("s", password="x", is_staff=True)
        self.client.force_login(user)
        r = self.client.get("/", {"sla_days": "14", "sla_cal": "corridos"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.context["sla"]["days"], r.context["sla"]["working_days"]), (14, False))
        self.assertContains(r, "Configurar prazos")


class SlaRulesTests(TestCase):
    def test_seed_has_t2_remote_zones(self):
        from .models import SlaZoneRule

        self.assertEqual(
            sorted(SlaZoneRule.objects.values_list("cp4", "sla_days", "label")),
            [(cp, 2, "T+2 R") for cp in ("4920", "4930", "4940", "4950")],
        )

    def setUp(self):
        from datetime import date, datetime, time

        from .models import SlaZoneRule

        if self._testMethodName != "test_seed_has_t2_remote_zones":
            SlaZoneRule.objects.all().delete()  # partir de "tudo T+1"

        from settlements.models import CainiaoHub, CainiaoHubCP4, CainiaoOperationTask

        hub = CainiaoHub.objects.create(name="Ponte da Barca")
        CainiaoHubCP4.objects.create(hub=hub, cp4="4950")
        aware = lambda d, h=8: timezone.make_aware(datetime.combine(d, time(h)))  # noqa: E731
        # Chegada seg 19/10, entrega qua 21/10 = 2 dias úteis.
        CainiaoOperationTask.objects.create(
            waybill_number="R1", task_date=date(2026, 10, 21), task_status="Delivered",
            zip_code="4950-001", receipt_time=aware(date(2026, 10, 19)),
            delivery_time=aware(date(2026, 10, 21), 15),
        )
        self.date = date

    def test_rule_changes_on_time(self):
        from .models import SlaZoneRule
        from .services_sla import _sla_report

        r = _sla_report(self.date(2026, 10, 23), days=7)
        c = r["cps"][0]
        self.assertEqual((c["sla"], c["rule_label"], c["sim"]), (0, "T+1", [0, 100, 100]))
        SlaZoneRule.objects.create(cp4="4950", sla_days=2, label="T+2 R")
        r = _sla_report(self.date(2026, 10, 23), days=7)
        c = r["cps"][0]
        self.assertEqual((c["sla"], c["rule_days"], c["rule_label"]), (100, 2, "T+2 R"))

    def test_page_saves_and_resets(self):
        from .models import SlaZoneRule

        user = User.objects.create_user("cfg", password="x", is_staff=True)
        self.client.force_login(user)
        url = reverse("dashboard_leguas:sla_rules")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "4950")
        self.client.post(url, {"cp": ["4950"], "d_4950": "2", "l_4950": "T+2 R"})
        rule = SlaZoneRule.objects.get(cp4="4950")
        self.assertEqual((rule.sla_days, rule.label, rule.updated_by_id), (2, "T+2 R", user.id))
        # Voltar a T+1 sem etiqueta apaga a regra (fica no valor por omissão).
        self.client.post(url, {"cp": ["4950"], "d_4950": "1", "l_4950": ""})
        self.assertFalse(SlaZoneRule.objects.exists())


class DashboardV2AccessTests(TestCase):
    def test_anonymous_is_sent_to_login(self):
        response = self.client.get(reverse("dashboard_leguas:dashboard_v2"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login/", response["Location"])
