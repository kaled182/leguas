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

    def test_name_match_ignores_case_and_accents(self):
        """Como a collation do MySQL (utf8mb4_0900_ai_ci) usada no portal."""
        a = _driver("100000008", apelido="José Da Silva_LF")
        _task("W8", self.today, name="jose da silva_LF")
        self.assertEqual(last_activity_map(self.today)[a.id], self.today)

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


class PortalAliasOwnerTests(TestCase):
    """O portal e a regra de atividade dão a mesma task ao mesmo motorista."""

    def setUp(self):
        from core.models import Partner
        from settlements.models import CourierNameAlias

        self.today = timezone.localdate()
        self.partner = Partner.objects.create(
            name="CAINIAO", nif="500000000", contact_email="c@x.pt",
        )
        self.old = _driver("400000001", apelido="Antigo_LF", cid="C-OLD")
        self.new = _driver("400000002", apelido="Novo_LF", cid="C-NEW")
        CourierNameAlias.objects.create(
            partner=self.partner, courier_name="Renomeado_LF",
            courier_id="C-NEW", source="manual",
        )

    def _portal(self, driver):
        from .portal_views import _driver_base_queryset

        return set(_driver_base_queryset(driver, self.today, self.today)
                   .values_list("waybill_number", flat=True))

    def test_stale_id_does_not_count_for_previous_owner(self):
        _task("W20", self.today, name="Renomeado_LF", cid="C-OLD")
        self.assertEqual(self._portal(self.old), set())
        self.assertEqual(self._portal(self.new), {"W20"})
        self.assertEqual(last_activity_map(self.today), {self.new.id: self.today})

    def test_alias_of_own_id_still_counts(self):
        _task("W21", self.today, name="Renomeado_LF", cid="C-NEW")
        self.assertEqual(self._portal(self.new), {"W21"})

    def test_alias_of_unowned_id_keeps_id_match(self):
        from settlements.models import CourierNameAlias

        CourierNameAlias.objects.create(
            partner=self.partner, courier_name="Sem_Dono_LF",
            courier_id="C-NONE", source="manual",
        )
        _task("W22", self.today, name="Sem_Dono_LF", cid="C-OLD")
        self.assertEqual(self._portal(self.old), {"W22"})


class LoginTransferTests(TestCase):
    def setUp(self):
        from core.models import Partner
        from settlements.models import DriverCourierMapping

        self.today = timezone.localdate()
        partner = Partner.objects.create(
            name="CAINIAO", nif="500000000", contact_email="c@x.pt",
        )
        self.source = _driver("500000001", apelido="Login_LF", cid="C-1")
        self.target = _driver("500000002", apelido="Destino_LF", cid="C-2")
        self.mapping = DriverCourierMapping.objects.create(
            driver=self.source, partner=partner,
            courier_id="C-1", courier_name="Login_LF",
        )

    def _count(self, driver):
        from .portal_views import _driver_base_queryset

        return _driver_base_queryset(driver, self.today, self.today).count()

    def test_tasks_stay_only_with_target(self):
        from .services_login_transfer import transfer_login

        _task("W30", self.today, name="Login_LF", cid="C-1")
        counts = transfer_login(self.mapping, self.target)
        self.source.refresh_from_db()
        self.assertEqual((self.source.apelido, self.source.courier_id_cainiao), ("", ""))
        self.assertEqual(counts["source_cleared"], ["courier_id_cainiao", "apelido"])
        self.assertEqual((self._count(self.source), self._count(self.target)), (0, 1))

    def test_other_identifiers_stay_on_source(self):
        from .services_login_transfer import transfer_login

        DriverProfile.objects.filter(pk=self.source.pk).update(
            apelido="Outro_LF", courier_id_cainiao="C-9",
        )
        self.mapping.refresh_from_db()
        counts = transfer_login(self.mapping, self.target)
        self.source.refresh_from_db()
        self.assertEqual((self.source.apelido, self.source.courier_id_cainiao), ("Outro_LF", "C-9"))
        self.assertEqual(counts["source_cleared"], [])


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
        self.admin = User.objects.create_user("adm", password="x", is_staff=True, is_superuser=True)
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


class DriversCentralLoginSearchTests(TestCase):
    def setUp(self):
        from core.models import Partner
        from settlements.models import CourierNameAlias, DriverCourierMapping

        self.client.force_login(User.objects.create_user("adm", password="x", is_staff=True, is_superuser=True))
        self.url = reverse("drivers_app:drivers_central")
        self.partner = Partner.objects.create(name="CAINIAO", nif="500000000", contact_email="c@x.pt")
        self.owner = _driver("310000001", apelido="Ricardo_LF")
        self.other = _driver("310000002", apelido="Outro_LF")
        self.mapping = DriverCourierMapping.objects.create(
            driver=self.owner, partner=self.partner,
            courier_id="9988", courier_name="Ricardo_Milhazes_2_LF",
        )
        CourierNameAlias.objects.create(
            partner=self.partner, courier_name="Nome_Antigo_LF", courier_id="9988",
        )
        CourierNameAlias.objects.create(
            partner=self.partner, courier_name="Perfil_Antigo_LF", courier_id="7777",
        )
        DriverProfile.objects.filter(pk=self.other.pk).update(courier_id_cainiao="7777")

    def _ids(self, q, tab="todos"):
        r = self.client.get(self.url, {"tab": tab, "q": q})
        return {d.id for d in r.context["drivers"]}

    def test_finds_saved_login(self):
        self.assertEqual(self._ids("Ricardo_Milhazes_2_LF"), {self.owner.id})
        self.assertEqual(self._ids("9988"), {self.owner.id})

    def test_space_matches_underscore(self):
        self.assertEqual(self._ids("Ricardo Milhazes 2_LF"), {self.owner.id})
        self.assertEqual(self._ids("ricardo milhazes 2 lf"), {self.owner.id})

    def test_finds_old_login_name(self):
        self.assertEqual(self._ids("Nome_Antigo"), {self.owner.id})
        self.assertEqual(self._ids("Perfil Antigo"), {self.other.id})

    def test_terms_must_match_same_field(self):
        self.assertEqual(self._ids("Milhazes Outro"), set())

    def test_no_duplicates_with_several_logins(self):
        from settlements.models import DriverCourierMapping

        DriverCourierMapping.objects.create(
            driver=self.owner, partner=self.partner,
            courier_id="9989", courier_name="Ricardo_Milhazes_3_LF",
        )
        r = self.client.get(self.url, {"tab": "todos", "q": "Milhazes"})
        self.assertEqual([d.id for d in r.context["drivers"]], [self.owner.id])
        self.assertEqual({k: n for k, _l, n in r.context["tabs"]}["todos"], 1)

    def test_opens_tab_with_results(self):
        DriverProfile.objects.filter(pk=self.owner.pk).update(
            inactive_since=timezone.localdate(),
        )
        r = self.client.get(self.url, {"tab": "ativos", "q": "Milhazes"})
        self.assertEqual(r.context["tab"], "inativos")
        self.assertEqual(r.context["moved_from_tab"], "Ativos")
        self.assertEqual({d.id for d in r.context["drivers"]}, {self.owner.id})

    def test_keeps_tab_without_results(self):
        r = self.client.get(self.url, {"tab": "ativos", "q": "inexistente"})
        self.assertEqual((r.context["tab"], r.context["moved_from_tab"]), ("ativos", ""))

    def test_row_shows_login_and_instant_filter_text(self):
        r = self.client.get(self.url, {"tab": "todos"})
        self.assertContains(r, "Ricardo_Milhazes_2_LF")
        self.assertContains(r, "nome_antigo_lf")
        self.assertContains(r, reverse("drivers_app:driver_logins", args=[self.owner.id]))


class LegacyListRemovedTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_user("adm", password="x", is_staff=True, is_superuser=True))
        self.drv = _driver("320000001", apelido="Leg_LF")

    def test_pages_and_actions_are_gone(self):
        for url in (
            "/driversapp/admin/ativos/",
            "/driversapp/admin/bulk/export-csv/",
            "/driversapp/admin/bulk/block/",
            f"/driversapp/admin/excluir/{self.drv.id}/",
            f"/driversapp/admin/quickview/{self.drv.id}/",
        ):
            self.assertEqual(self.client.get(url).status_code, 404, url)
            self.assertEqual(self.client.post(url).status_code, 404, url)
        self.assertTrue(DriverProfile.objects.filter(pk=self.drv.id).exists())

    def test_menu_and_create_page_have_no_link(self):
        r = self.client.get(reverse("drivers_app:admin_create_driver"))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "/driversapp/admin/ativos/")
        self.assertNotContains(r, "legacy")

    def test_replacement_pages_open(self):
        for name in ("driver_complaints", "driver_vehicles", "driver_documents"):
            r = self.client.get(reverse(f"drivers_app:{name}", args=[self.drv.id]))
            self.assertEqual(r.status_code, 200, name)


class FichaTests(TestCase):
    def setUp(self):
        from decimal import Decimal

        from contracts.models import HubContractTerms, HubZoneTariff
        from settlements.models import CainiaoHub, CainiaoHubCP4

        from .models import EmpresaParceira

        self.admin = User.objects.create_user("adm2", password="x", is_staff=True, is_superuser=True)
        self.client.force_login(self.admin)
        self.fleet = EmpresaParceira.objects.create(nome="Frota X", nif="509999999")
        self.d = _driver("400000001", apelido="Fi_LF")
        self.d.empresa_parceira = self.fleet
        self.d.niss = None
        self.d.save()
        self.hub = CainiaoHub.objects.create(name="Fão")
        CainiaoHubCP4.objects.create(hub=self.hub, cp4="4740")
        HubContractTerms.objects.create(hub=self.hub, allows_weekly=True)
        HubZoneTariff.objects.create(
            hub=self.hub, cp4="4740", zone_name="Esposende", tier="A",
            price_monthly=Decimal("0.95"),
        )
        self.url = reverse("drivers_app:driver_admin_edit", args=[self.d.id])

    def _post(self, section, **data):
        payload = {"section": section}
        payload.update({f"{section}-{k}": v for k, v in data.items()})
        return self.client.post(self.url, payload)

    def test_get_renders_without_none_text(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'value="None"')
        self.assertContains(r, "Dados para o contrato")

    def test_section_save_keeps_other_fields(self):
        r = self._post(
            "contacto", telefone="912000111", email="novo@x.pt",
            endereco_residencia="Rua A", codigo_postal="4740-001", cidade="Esposende",
        )
        self.assertEqual(r.status_code, 302)
        self.d.refresh_from_db()
        self.assertEqual(self.d.telefone, "912000111")
        # Campos de outros blocos não mudam (o bug antigo punha False / None).
        self.assertTrue(self.d.is_active)
        self.assertEqual(self.d.empresa_parceira_id, self.fleet.id)
        log = self.d.edit_logs.get()
        self.assertEqual(log.section, "contacto")
        self.assertEqual(log.changes["telefone"], ["912345678", "912000111"])

    def test_empty_niss_saved_as_null(self):
        self._post(
            "identificacao", nome_completo="Fi", apelido="Fi_LF", courier_id_cainiao="",
            nif="400000001", niss="", data_nascimento="", nacionalidade="Portugal",
        )
        self.d.refresh_from_db()
        self.assertIsNone(self.d.niss)

    def test_invalid_value_shows_errors_and_does_not_save(self):
        r = self._post(
            "identificacao", nome_completo="Fi", apelido="Fi_LF", courier_id_cainiao="",
            nif="12", niss="", data_nascimento="", nacionalidade="Portugal",
        )
        self.assertEqual(r.status_code, 200)
        self.d.refresh_from_db()
        self.assertEqual(self.d.nif, "400000001")

    def test_regime_change_effective_next_cycle(self):
        from .models import DriverPaymentRegimeChange

        fin = dict(
            payment_regime="SEMANAL", payment_regime_since="", iban="PT50000000000000000000000",
            price_per_package="", advance_monthly_limit="", daily_capacity="",
            bonus_performance_enabled="on", vat_regime="isento", irs_retention_pct="0",
        )
        self._post("financeiro", **fin)
        self.d.refresh_from_db()
        today = timezone.localdate()
        self.assertEqual(self.d.payment_regime_since, today)  # 1.ª definição: já
        fin["payment_regime"] = "MENSAL"
        self._post("financeiro", **fin)
        self.d.refresh_from_db()
        self.assertEqual(self.d.payment_regime_since.day, 1)
        self.assertGreater(self.d.payment_regime_since, today)
        self.assertEqual(DriverPaymentRegimeChange.objects.filter(driver=self.d).count(), 2)

    def test_save_hubs_and_completeness(self):
        from .services_hubs import contract_completeness

        pct_before, missing = contract_completeness(self.d)
        self.assertIn("Hub e CP contratados", missing)
        self.client.post(self.url, {
            "section": "hubs", f"cp_{self.hub.id}": ["4740"], "primary_hub": str(self.hub.id),
        })
        a = self.d.hub_assignments.get()
        self.assertEqual((a.cp4s, a.is_primary), (["4740"], True))
        pct_after, missing = contract_completeness(self.d)
        self.assertNotIn("Hub e CP contratados", missing)
        self.assertGreater(pct_after, pct_before)
        self.assertEqual(self.d.edit_logs.get().section, "hubs")

    def test_weekly_price_fallback(self):
        from decimal import Decimal

        from contracts.models import HubZoneTariff

        t = HubZoneTariff.objects.get(cp4="4740")
        self.assertEqual(t.price_for("SEMANAL"), Decimal("0.9000"))
        self.assertEqual(t.price_for("MENSAL"), Decimal("0.95"))


class ContractGeneratorTests(TestCase):
    def setUp(self):
        import json
        from decimal import Decimal

        from contracts.models import HubContractTerms, HubZoneTariff
        from settlements.models import CainiaoHub

        from .models import DriverHubAssignment

        self.json = json
        self.admin = User.objects.create_user("adm3", password="x", is_staff=True, is_superuser=True)
        self.client.force_login(self.admin)
        self.d = _driver("500000001", apelido="Gen_LF")
        self.fao = CainiaoHub.objects.create(name="Fão", address="N13 40 5, Fão")
        self.ave = CainiaoHub.objects.create(name="Aveiro", address="R. de São João 157, Válega")
        HubContractTerms.objects.create(hub=self.fao, signing_place="Esposende", allows_weekly=True)
        HubContractTerms.objects.create(
            hub=self.ave, signing_place="Válega", allows_weekly=False,
            monthly_payment_mode="DAY_OF_NEXT_MONTH", monthly_payment_value=15,
        )
        HubZoneTariff.objects.create(hub=self.fao, cp4="4740", zone_name="Esposende", tier="A", price_monthly=Decimal("0.95"), price_weekly=Decimal("0.90"))
        HubZoneTariff.objects.create(hub=self.fao, cp4="4920", zone_name="Cerveira", tier="C", price_monthly=Decimal("1.15"), price_weekly=Decimal("1.10"))
        HubZoneTariff.objects.create(hub=self.ave, cp4="3880", zone_name="Ovar", price_monthly=Decimal("1.00"))
        DriverHubAssignment.objects.create(driver=self.d, hub=self.fao, cp4s=["4740", "4920"], is_primary=True)
        DriverHubAssignment.objects.create(driver=self.d, hub=self.ave, cp4s=["3880"])

    def test_generator_payload(self):
        r = self.client.get(reverse("contracts:contract_generator", args=[self.d.id]))
        self.assertEqual(r.status_code, 200)
        gen = r.context["gen"]
        self.assertEqual(gen["primary_hub_id"], self.fao.id)
        fao = next(h for h in gen["hubs"] if h["id"] == self.fao.id)
        self.assertEqual([c["cp"] for c in fao["cps"] if c["checked"]], ["4740", "4920"])
        self.assertEqual(r.context["signing_place"], "Esposende")
        r = self.client.get(reverse("contracts:contract_generator", args=[self.d.id]), {"kind": "ADITIVO"})
        self.assertContains(r, 'id="g_dorig"')

    def test_save_and_lifecycle(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from contracts.models import GeneratedContract

        from .central_views import _contract_driver_ids

        url = reverse("contracts:contract_generator_save", args=[self.d.id])
        self.client.post(url, {
            "kind": "CONTRATO", "regime": "MENSAL", "html": "<div class='a4'>x</div>",
            "hubs": self.json.dumps([{"hub_id": self.fao.id, "name": "Fão", "cp4s": ["4740"]}]),
            "params": self.json.dumps({"local": "Esposende"}),
        })
        c = GeneratedContract.objects.get()
        self.assertEqual((c.status, c.regime, len(c.content_hash)), ("GERADO", "MENSAL", 64))
        self.assertNotIn(self.d.id, _contract_driver_ids())

        act = reverse("contracts:generated_contract_action", args=[c.id])
        self.client.post(act, {"action": "sent"})
        c.refresh_from_db()
        self.assertEqual(c.status, "ENVIADO")
        self.client.post(act, {"action": "signed"})  # sem ficheiro → recusa
        c.refresh_from_db()
        self.assertEqual(c.status, "ENVIADO")
        self.client.post(act, {"action": "signed", "signed_file": SimpleUploadedFile("a.pdf", b"%PDF")})
        c.refresh_from_db()
        self.assertEqual(c.status, "ASSINADO")
        self.assertIn(self.d.id, _contract_driver_ids())
        r = self.client.get(reverse("contracts:generated_contract_view", args=[c.id]))
        self.assertContains(r, "<div class='a4'>x</div>", html=False)


class PaymentsTests(TestCase):
    def setUp(self):
        from datetime import date

        from contracts.models import HubContractTerms
        from settlements.models import CainiaoHub

        self.date = date
        self.admin = User.objects.create_user("adm4", password="x", is_staff=True, is_superuser=True)
        self.client.force_login(self.admin)
        self.ave = CainiaoHub.objects.create(name="Aveiro")
        self.ave_terms = HubContractTerms.objects.create(
            hub=self.ave, monthly_payment_mode="DAY_OF_NEXT_MONTH", monthly_payment_value=15,
        )

    def test_expected_dates(self):
        from .services_payments import expected_payment_date

        d = self.date
        # Semanal: semana de seg. 7/09 → terça 4 semanas depois (6/10).
        self.assertEqual(expected_payment_date(d(2026, 9, 7), d(2026, 9, 13)), d(2026, 10, 6))
        # Mensal Viana (omissão): 30 dias após o fecho.
        self.assertEqual(expected_payment_date(d(2026, 9, 1), d(2026, 9, 30)), d(2026, 10, 31))
        # Mensal Aveiro: dia 15 do mês seguinte (e passagem de ano).
        self.assertEqual(expected_payment_date(d(2026, 9, 1), d(2026, 9, 30), self.ave_terms), d(2026, 10, 15))
        self.assertEqual(expected_payment_date(d(2026, 12, 1), d(2026, 12, 31), self.ave_terms), d(2027, 1, 15))

    def test_signal_fills_expected_date_from_primary_hub(self):
        from settlements.models import DriverPreInvoice

        from .models import DriverHubAssignment

        drv = _driver("600000001")
        DriverHubAssignment.objects.create(driver=drv, hub=self.ave, cp4s=["3880"], is_primary=True)
        pf = DriverPreInvoice.objects.create(
            numero="PF-T1", driver=drv, periodo_inicio=self.date(2026, 9, 1),
            periodo_fim=self.date(2026, 9, 30), status="CALCULADO",
        )
        self.assertEqual(pf.data_prevista_pagamento, self.date(2026, 10, 15))

    def test_dashboard_bulk_approve_and_csv(self):
        from settlements.models import DriverPreInvoice

        drv = _driver("600000002")
        drv.iban = "PT50123"
        drv.save()
        today = timezone.localdate()
        late = DriverPreInvoice.objects.create(
            numero="PF-T2", driver=drv, periodo_inicio=today - timedelta(days=90),
            periodo_fim=today - timedelta(days=60), status="CALCULADO", total_a_receber=100,
        )
        url = reverse("drivers_app:payments_dashboard")
        r = self.client.get(url, {"tab": "atraso"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual([p.id for p in r.context["rows"]], [late.id])
        self.assertEqual(r.context["kpis"]["approve_n"], 1)
        self.assertEqual(r.context["kpis"]["overdue_n"], 1)

        bulk = reverse("drivers_app:payments_bulk")
        self.client.post(bulk, {"ids": [late.id], "action": "approve"})
        late.refresh_from_db()
        self.assertEqual(late.status, "APROVADO")
        r = self.client.post(bulk, {"ids": [late.id], "action": "csv"})
        body = r.content.decode("utf-8-sig")
        self.assertIn("PF-T2;Driver 600000002;600000002;PT50123", body)
        self.assertIn("100,00", body)

    def test_negative_pf_not_counted_as_payable(self):
        from settlements.models import DriverPreInvoice

        drv = _driver("600000003")
        today = timezone.localdate()
        neg = DriverPreInvoice.objects.create(
            numero="PF-T3", driver=drv, periodo_inicio=today - timedelta(days=90),
            periodo_fim=today - timedelta(days=60), status="CALCULADO", total_a_receber=-50,
        )
        r = self.client.get(reverse("drivers_app:payments_dashboard"), {"tab": "negativas"})
        k = r.context["kpis"]
        self.assertEqual((k["overdue_n"], k["overdue_total"]), (0, 0))
        self.assertEqual(r.context["alerts"]["negativas"], 1)
        self.assertEqual([p.id for p in r.context["rows"]], [neg.id])


class CpPricingTests(TestCase):
    """Valor negociado na ficha → base; a tarifa do hub não paga o motorista."""

    def setUp(self):
        from datetime import date
        from decimal import Decimal

        from contracts.models import ContractSettings, HubContractTerms, HubZoneTariff
        from core.models import Partner
        from settlements.models import CainiaoHub

        from .models import DriverHubAssignment

        self.D = Decimal
        self.date = date
        self.partner = Partner.objects.create(
            name="CAINIAO", nif="500000000", contact_email="c@x.pt",
            driver_default_price_per_package=Decimal("1.00"),
        )
        st = ContractSettings.get()
        st.cp_pricing_from = date(2026, 11, 1)
        st.save()
        self.hub = CainiaoHub.objects.create(name="Fão")
        HubContractTerms.objects.create(hub=self.hub, allows_weekly=True)
        for cp, pm, pw in [("4740", "0.95", "0.90"), ("4920", "1.15", "1.10"), ("4900", "1.00", "0.95")]:
            HubZoneTariff.objects.create(
                hub=self.hub, cp4=cp, zone_name=cp, price_monthly=Decimal(pm),
                price_weekly=Decimal(pw), valid_from=date(2026, 1, 1),
            )
        self.drv = _driver("700000001", apelido="Cp_LF")
        self.drv.price_per_package = Decimal("1.20")  # preço individual antigo
        self.drv.save()
        DriverHubAssignment.objects.create(
            driver=self.drv, hub=self.hub, cp4s=["4740", "4920"], is_primary=True,
            cp_prices={"4740": "1.10", "4900": "9.99"},  # 4900 não selecionado → ignorado
        )

    def _pricer(self, ini, fim):
        from .services_cp_pricing import CpPricer

        return CpPricer(self.drv, self.partner, ini, fim)

    def test_cascade(self):
        d = self.date
        p = self._pricer(d(2026, 11, 1), d(2026, 11, 30))
        self.assertEqual(p.price("4740-123")[:2], (self.D("1.10"), "negociado"))
        # CP selecionado sem valor negociado: preço do motorista, não a tarifa.
        self.assertEqual(p.price("4920-001")[:2], (self.D("1.20"), "base"))
        # CP não selecionado: o valor 9,99 não conta.
        self.assertEqual(p.price("4900-001")[:2], (self.D("1.20"), "base"))
        # CP sem tarifa: preço do motorista.
        self.assertEqual(p.price("4490-001")[:2], (self.D("1.20"), "base"))

    def test_weekly_period_keeps_same_rule(self):
        d = self.date
        p = self._pricer(d(2026, 11, 2), d(2026, 11, 8))
        self.assertEqual(p.price("4920")[:2], (self.D("1.20"), "base"))
        self.assertEqual(p.price("4740")[:2], (self.D("1.10"), "negociado"))

    def test_partner_price_when_profile_has_no_price(self):
        d = self.date
        DriverProfile.objects.filter(pk=self.drv.pk).update(price_per_package=None)
        self.drv.refresh_from_db()
        p = self._pricer(d(2026, 11, 1), d(2026, 11, 30))
        self.assertEqual(p.price("4920")[:2], (self.D("1.00"), "base"))

    def test_inactive_before_start_date(self):
        d = self.date
        p = self._pricer(d(2026, 10, 1), d(2026, 10, 31))
        self.assertEqual(p.price("4920")[:2], (self.D("1.20"), "base"))

    def test_pre_invoice_create_uses_cp_prices(self):
        import json

        from settlements.models import DriverPreInvoice

        d = self.date
        for i, (cp, n) in enumerate([("4740", 3), ("4920", 2), ("4490", 1)]):
            for k in range(n):
                _task(f"W{cp}{k}", d(2026, 11, 3 + k), name="Cp_LF").__class__.objects.filter(
                    waybill_number=f"W{cp}{k}").update(zip_code=f"{cp}-00{k}", detailed_address=f"Rua {cp} {k}")
        admin = User.objects.create_superuser("su", "s@x.pt", "x")
        self.client.force_login(admin)
        r = self.client.post(
            f"/settlements/pre-invoices/driver/{self.drv.id}/create/",
            data=json.dumps({"periodo_inicio": "2026-11-01", "periodo_fim": "2026-11-30"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200, r.content[:300])
        pf = DriverPreInvoice.objects.get(driver=self.drv)
        lines = {(l.taxa_por_entrega, l.total_pacotes, l.api_source) for l in pf.linhas.all()}
        self.assertEqual(lines, {
            (self.D("1.10"), 3, "auto:per_login_cp"),
            (self.D("1.20"), 3, "auto:per_login"),
        })
        self.assertEqual(pf.base_entregas, self.D("6.90"))
        # O portal (driver_breakdown) mostra o mesmo valor à porta.
        from settlements.services_driver_breakdown import driver_breakdown

        bd = driver_breakdown(self.drv, d(2026, 11, 1), d(2026, 11, 30), partner=self.partner)
        self.assertEqual(bd["amounts"]["door_normal"], self.D("6.90"))

    def test_ficha_saves_negotiated_price_only_for_valid_values(self):
        admin = User.objects.create_user("adm5", password="x", is_staff=True, is_superuser=True)
        self.client.force_login(admin)
        url = reverse("drivers_app:driver_admin_edit", args=[self.drv.id])
        self.client.post(url, {
            "section": "hubs", f"cp_{self.hub.id}": ["4740", "4920"],
            "primary_hub": str(self.hub.id),
            f"cpp_{self.hub.id}_4740": "1,05", f"cpp_{self.hub.id}_4920": "abc",
        })
        a = self.drv.hub_assignments.get()
        self.assertEqual(a.cp_prices, {"4740": "1.05"})


class CopyIndividualPriceCommandTests(TestCase):
    def test_copies_only_where_individual_price_is_higher(self):
        from datetime import date
        from decimal import Decimal

        from django.core.management import call_command

        from contracts.models import HubZoneTariff
        from settlements.models import CainiaoHub

        hub = CainiaoHub.objects.create(name="Fão")
        porto = CainiaoHub.objects.create(name="Porto")
        HubZoneTariff.objects.create(hub=hub, cp4="4740", zone_name="E", price_monthly=Decimal("0.95"), valid_from=date(2026, 1, 1))
        HubZoneTariff.objects.create(hub=porto, cp4="4490", zone_name="P", price_monthly=Decimal("1.10"), valid_from=date(2026, 1, 1))
        drv = _driver("800000001", apelido="Ind_LF")
        drv.price_per_package = Decimal("1.00")
        drv.save()
        today = timezone.localdate()
        for i, cp in enumerate(["4740", "4740", "4490"]):
            t = _task(f"I{i}", today - timedelta(days=2), name="Ind_LF")
            t.zip_code = f"{cp}-001"
            t.save()
        call_command("copy_individual_price_to_cp", "--dry-run")
        self.assertFalse(drv.hub_assignments.exists())
        call_command("copy_individual_price_to_cp")
        a = drv.hub_assignments.get()
        self.assertEqual((a.hub_id, a.cp4s, a.cp_prices, a.is_primary), (hub.id, ["4740"], {"4740": "1.00"}, True))
        # Segunda corrida não duplica nem altera.
        call_command("copy_individual_price_to_cp")
        self.assertEqual(drv.hub_assignments.get().cp_prices, {"4740": "1.00"})
        self.assertEqual(drv.edit_logs.count(), 1)


class PendingDeductionsTests(TestCase):
    def setUp(self):
        from datetime import date
        from decimal import Decimal

        from settlements.models import DriverClaim, DriverPreInvoice, PreInvoiceAdvance

        self.D = Decimal
        self.drv = _driver("900000001", apelido="Ded_LF")
        paid = DriverPreInvoice.objects.create(numero="PF-P", driver=self.drv, periodo_inicio=date(2026, 8, 1), periodo_fim=date(2026, 8, 31), status="PAGO")
        open_pf = DriverPreInvoice.objects.create(numero="PF-O", driver=self.drv, periodo_inicio=date(2026, 9, 1), periodo_fim=date(2026, 9, 30), status="CALCULADO")
        mk = lambda **kw: PreInvoiceAdvance.objects.create(driver=self.drv, data=date(2026, 9, 1), **kw)  # noqa: E731
        self.pend = mk(valor=Decimal("20"), status="PENDENTE")
        self.in_open = mk(valor=Decimal("35"), status="INCLUIDO_PF", pre_invoice=open_pf)
        self.in_paid = mk(valor=Decimal("1000"), status="INCLUIDO_PF", pre_invoice=paid)
        self.cancel = mk(valor=Decimal("7"), status="CANCELADO")
        now = timezone.now()
        mkc = lambda **kw: DriverClaim.objects.create(driver=self.drv, claim_type="ORDER_LOSS", occurred_at=now, description="x", **kw)  # noqa: E731
        self.c_wait = mkc(amount=Decimal("50"), status="APPROVED")
        self.c_pending = mkc(amount=Decimal("30"), status="PENDING")
        self.c_rejected = mkc(amount=Decimal("99"), status="REJECTED")

    def test_only_what_is_still_to_deduct(self):
        from .services_deductions import pending_deductions

        d = pending_deductions(self.drv)
        self.assertEqual({a.id for a in d["advances"]}, {self.pend.id, self.in_open.id})
        self.assertEqual({a.id for a in d["history"]}, {self.in_paid.id, self.cancel.id})
        self.assertEqual({c.id for c in d["claims"]}, {self.c_wait.id, self.c_pending.id})
        self.assertEqual(d["advances_total"], self.D("55"))
        self.assertEqual(d["claims_confirmed_total"], self.D("50"))
        self.assertEqual(d["claims_review_total"], self.D("30"))
        self.assertEqual(d["total"], self.D("105"))
        self.assertEqual(d["next_pf_total"], self.D("70"))  # 20 pendente + 50 à espera
        # O motorista não vê descontos ainda por aprovar.
        d2 = pending_deductions(self.drv, include_unapproved=False)
        self.assertEqual({c.id for c in d2["claims"]}, {self.c_wait.id})

    def test_invoices_page_admin(self):
        admin = User.objects.create_user("adm6", password="x", is_staff=True, is_superuser=True)
        self.client.force_login(admin)
        r = self.client.get(reverse("drivers_app:driver_portal_invoices", args=[self.drv.id]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "A descontar")
        self.assertContains(r, "Entra na próxima pré-fatura")
        self.assertContains(r, "Ver histórico (2)")


class BeatHealthTests(TestCase):
    def test_fails_when_old_and_passes_when_recent(self):
        from django.core.management import CommandError, call_command
        from django_celery_beat.models import IntervalSchedule, PeriodicTask

        sched = IntervalSchedule.objects.create(every=1, period="hours")
        t = PeriodicTask.objects.create(name="x", task="x", interval=sched)
        with self.assertRaises(CommandError):
            call_command("beat_health")  # nunca correu
        t.last_run_at = timezone.now() - timedelta(minutes=300)
        t.save()
        with self.assertRaises(CommandError):
            call_command("beat_health")
        t.last_run_at = timezone.now() - timedelta(minutes=10)
        t.save()
        call_command("beat_health")


class CarryNegativeBalanceTests(TestCase):
    def setUp(self):
        from datetime import date
        from decimal import Decimal

        from settlements.models import DriverPreInvoice, PreInvoiceAdvance

        self.D = Decimal
        self.drv = _driver("910000001")
        self.pf = DriverPreInvoice.objects.create(
            numero="PF-N1", driver=self.drv, periodo_inicio=date(2026, 9, 1),
            periodo_fim=date(2026, 9, 30), status="CALCULADO", ajuste_manual=Decimal("100"),
        )
        for v in ("80", "50", "30", "20"):
            PreInvoiceAdvance.objects.create(
                driver=self.drv, data=date(2026, 9, 10), valor=Decimal(v),
                status="INCLUIDO_PF", pre_invoice=self.pf,
            )
        self.pf.recalcular()  # 100 − 180 = −80

    def test_min_cover(self):
        from .services_deductions import _min_cover

        self.assertEqual(sorted(_min_cover([(1, 80), (2, 50), (3, 30), (4, 20)], 80)), [1])
        self.assertEqual(sorted(_min_cover([(1, 50), (2, 30), (3, 25)], 54)), [2, 3])
        self.assertIsNone(_min_cover([(1, 10)], 20))

    def test_carry_frees_minimal_advances(self):
        from settlements.models import PreInvoiceAdvance

        from .services_deductions import carry_negative_balance

        self.assertEqual(self.pf.total_a_receber, self.D("-80"))
        r = carry_negative_balance(self.pf)
        self.pf.refresh_from_db()
        self.assertEqual(self.pf.total_a_receber, self.D("0"))
        self.assertEqual(r["advances_total"], self.D("80"))
        pend = PreInvoiceAdvance.objects.filter(driver=self.drv, status="PENDENTE")
        self.assertEqual([a.valor for a in pend], [self.D("80")])
        self.assertIn("[SALDO]", self.pf.observacoes)

    def test_bulk_carry_and_invoices_page(self):
        admin = User.objects.create_user("adm7", password="x", is_staff=True, is_superuser=True)
        self.client.force_login(admin)
        r = self.client.get(reverse("drivers_app:driver_portal_invoices", args=[self.drv.id]))
        self.assertContains(r, "Saldo devedor")
        self.assertContains(r, "Próximo pagamento")
        self.client.post(reverse("drivers_app:payments_bulk"), {"ids": [self.pf.id], "action": "carry"})
        self.pf.refresh_from_db()
        self.assertEqual(self.pf.total_a_receber, self.D("0"))
