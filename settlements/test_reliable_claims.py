from decimal import Decimal
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings

from core.models import Partner
from system_config.models import SystemConfiguration

from .models import DriverClaim, ReliableClaimVerdict as V
from .services_courier_onboarding import create_driver_for_courier_name
from .services_reliable_claims import sync_claim_verdicts

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


def _row(ticket, waybill, login, verdict, when="2026-09-25T10:00:00+01:00", **kw):
    raw = {"contra": "Liability established", "a_favor": "Liability is not established"}.get(verdict, "")
    return {"ticket": ticket, "cnprt": waybill, "login_cainiao": login, "reclamacao": "Fake Delivery",
            "veredicto": verdict, "veredicto_cainiao": raw, "veredicto_nota": "LM-F4: DSP sem resposta",
            "veredicto_em": when, "aberta_em": "2026-09-20T09:00:00+01:00", "hub": "viana",
            "quem_respondeu_no_ces": "prazo", "resposta_do_motorista": "", **kw}


@override_settings(CACHES=LOCMEM)
class VerdictSyncTests(TestCase):
    def setUp(self):
        self.partner = Partner.objects.create(name="CAINIAO", nif="514154411", contact_email="c@x.pt")
        cfg = SystemConfiguration.get_config()
        cfg.reliable_api_url, cfg.reliable_api_key = "https://r.test", "segredo"
        cfg.reliable_claims_sync_enabled = True
        cfg.save()
        self.driver_id = create_driver_for_courier_name("Josuel Lobato_LF", "1576539120048")["driver_id"]
        self.rows = []

    def _run(self):
        def get(url, params=None, headers=None, timeout=None):
            if url.endswith("/utilizadores/"):
                return mock.Mock(status_code=200, json=mock.Mock(return_value={"utilizadores": []}))
            assert url.endswith("/reclamacoes/") and "julgadas_desde" in params
            return mock.Mock(status_code=200, json=mock.Mock(return_value={"limite": 500, "reclamacoes": self.rows}))

        with mock.patch("settlements.services_reliable_sync.requests.get", side_effect=get):
            return sync_claim_verdicts()

    def test_contra_cria_desconto_aprovado_com_o_valor_do_parceiro_e_nao_repete(self):
        self.partner.verdict_claim_amount = Decimal("45.00")
        self.partner.save()
        self.rows = [_row("T1", "cnprt111", "Josuel Lobato_LF", "contra")]
        r = self._run()
        self.assertEqual(r["claim_created"], 1)
        claim = DriverClaim.objects.get()
        self.assertEqual((claim.driver_id, claim.status, claim.amount, claim.waybill_number),
                         (self.driver_id, "APPROVED", Decimal("45.00"), "CNPRT111"))
        self.assertIn("T1", claim.description)

        # Valor editado à mão (ex.: pacote de 250 €) não é tocado nas voltas seguintes.
        DriverClaim.objects.filter(pk=claim.pk).update(amount=Decimal("250.00"))
        self._run()
        self.assertEqual(DriverClaim.objects.count(), 1)
        self.assertEqual(DriverClaim.objects.get().amount, Decimal("250.00"))

    def test_a_favor_nao_desconta(self):
        self.rows = [_row("T1", "CNPRT111", "Josuel Lobato_LF", "a_favor")]
        self.assertEqual(self._run()["no_liability"], 1)
        self.assertFalse(DriverClaim.objects.exists())

    def test_sem_veredicto_e_ignorado(self):
        self.rows = [_row("T1", "CNPRT111", "Josuel Lobato_LF", "")]
        self._run()
        self.assertFalse(V.objects.exists())

    def test_veredicto_que_passa_a_favor_estorna_o_desconto_criado_aqui(self):
        self.rows = [_row("T1", "CNPRT111", "Josuel Lobato_LF", "contra")]
        self._run()
        self.rows = [_row("T1", "CNPRT111", "Josuel Lobato_LF", "a_favor", when="2026-09-26T10:00:00+01:00")]
        self._run()
        self.assertEqual(DriverClaim.objects.get().status, "REJECTED")
        self.assertEqual(V.objects.get().outcome, V.OUTCOME_REVERTED)

    def test_login_so_exacto_e_sem_motorista_e_retentado(self):
        self.rows = [_row("T1", "CNPRT111", "Josuel_Lobato_LF", "contra")]  # outro login
        self.assertEqual(self._run()["no_driver"], 1)
        self.assertFalse(DriverClaim.objects.exists())

        create_driver_for_courier_name("Josuel_Lobato_LF", "1576539999999")
        self.rows = []  # já não vem na janela: a volta retenta os no_driver
        self.assertEqual(self._run()["claim_created"], 1)
        self.assertEqual(DriverClaim.objects.get().driver.courier_id_cainiao, "1576539999999")

    def test_helper_desconta_ao_motorista_principal(self):
        ces = [{"login": "Helper-MELAO-LF", "courier_id": "1576538274974", "tipo": "COURIER_HELPER",
                "principal": "Josuel Lobato_LF", "hub": "viana", "estado": "ENABLE"}]
        self.rows = [_row("T1", "CNPRT111", "Helper-MELAO-LF", "contra")]
        with mock.patch("settlements.services_courier_onboarding._ces_users", return_value=ces):
            self.assertEqual(self._run()["claim_created"], 1)
        claim = DriverClaim.objects.get()
        self.assertEqual(claim.driver_id, self.driver_id)
        self.assertIn("helper de Josuel Lobato_LF", claim.dsp_observation)

    def test_helper_conhecido_so_no_leguas_desconta_ao_principal(self):
        from .models import DriverHelper

        DriverHelper.objects.create(driver_id=self.driver_id, helper_name="Helper-X-LF")
        self.rows = [_row("T1", "CNPRT111", "Helper-X-LF", "contra")]
        with mock.patch("settlements.services_courier_onboarding._ces_users", return_value=[]):
            self.assertEqual(self._run()["claim_created"], 1)
        self.assertEqual(DriverClaim.objects.get().driver_id, self.driver_id)

    def test_nao_duplica_se_ja_ha_desconto_para_o_pacote(self):
        existing = DriverClaim.objects.create(
            driver_id=self.driver_id, claim_type="ORDER_LOSS", amount=Decimal("30"),
            description="manual", waybill_number="CNPRT111", status="APPROVED",
        )
        self.rows = [_row("T1", "cnprt111", "Josuel Lobato_LF", "contra")]
        self.assertEqual(self._run()["duplicate"], 1)
        self.assertEqual(DriverClaim.objects.count(), 1)
        self.assertEqual(V.objects.get().claim_id, existing.id)

        # Mesmo que a Cainiao mude para a favor, um claim que não foi criado aqui não se toca.
        self.rows = [_row("T1", "cnprt111", "Josuel Lobato_LF", "a_favor", when="2026-09-26T10:00:00+01:00")]
        self._run()
        self.assertEqual(DriverClaim.objects.get().status, "APPROVED")

    def test_desligado_nao_chama_a_api(self):
        cfg = SystemConfiguration.get_config()
        cfg.reliable_claims_sync_enabled = False
        cfg.save(update_fields=["reliable_claims_sync_enabled"])
        with mock.patch("settlements.services_reliable_sync.requests.get") as get:
            self.assertIn("skipped", sync_claim_verdicts())
        get.assert_not_called()


class EncerrarReclamacoesTests(TestCase):
    def test_so_conta_sem_gravar_e_encerra_com_gravar(self):
        from drivers_app.models import CustomerComplaint

        Partner.objects.create(name="CAINIAO", nif="514154411", contact_email="c@x.pt")
        driver_id = create_driver_for_courier_name("Ana_LF", "1576538000001")["driver_id"]
        for st in ("NOTIFICADO", "RESPONDIDO", "FECHADO"):
            CustomerComplaint.objects.create(driver_id=driver_id, numero_pacote=f"CNPRT{st}", status=st)

        out = StringIO()
        call_command("encerrar_reclamacoes_locais", stdout=out)
        self.assertIn("Abertas: 2", out.getvalue())
        self.assertEqual(CustomerComplaint.objects.filter(status="CANCELADO").count(), 0)

        call_command("encerrar_reclamacoes_locais", "--gravar", stdout=StringIO())
        self.assertEqual(CustomerComplaint.objects.filter(status="CANCELADO").count(), 2)
        self.assertEqual(CustomerComplaint.objects.get(status="FECHADO").numero_pacote, "CNPRTFECHADO")
        self.assertFalse(DriverClaim.objects.exists())
