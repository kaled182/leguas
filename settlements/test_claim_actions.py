from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from core.models import Partner

from .models import DriverClaim, DriverPreInvoice, PreInvoiceLostPackage
from .services_claim_actions import (
    ClaimActionError, carry_forward_pending_credits, change_claim_amount, claim_billing_state,
    remove_claim, restore_claim,
)
from .services_claims_in_pf import apply_claim_now
from .services_courier_onboarding import create_driver_for_courier_name

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


def _lines(claim, kind="main"):
    marker = {"main": "auto:driver_claim:", "adjust": "auto:driver_claim_adjust:",
              "credit": "auto:driver_claim_credit:"}[kind]
    return list(PreInvoiceLostPackage.objects.filter(api_source=f"{marker}{claim.id}").select_related("pre_invoice"))


@override_settings(CACHES=LOCMEM)
class ClaimActionsTests(TestCase):
    def setUp(self):
        Partner.objects.create(name="CAINIAO", nif="514154411", contact_email="c@x.pt")
        self.driver_id = create_driver_for_courier_name("Ana_LF", "1576538000001")["driver_id"]
        self.user = get_user_model().objects.create_user("operador", password="x", is_staff=True)
        self.pf = self._pf("PF-1", date(2026, 9, 1), date(2026, 9, 15), "CALCULADO")
        self.claim = DriverClaim.objects.create(
            driver_id=self.driver_id, claim_type="CUSTOMER_COMPLAINT", amount=Decimal("30.00"),
            description="Fake Delivery", waybill_number="CNPRT1", operation_task_date=date(2026, 9, 10),
            status="APPROVED",
        )
        apply_claim_now(self.claim)

    def _pf(self, numero, ini, fim, status):
        return DriverPreInvoice.objects.create(
            numero=numero, driver_id=self.driver_id, periodo_inicio=ini, periodo_fim=fim, status=status,
        )

    def _pay(self, pf):
        pf.status = "PAGO"
        pf.save()

    def test_estado_e_alterar_valor_em_pf_aberta(self):
        self.assertEqual(claim_billing_state(self.claim)["code"], "em_fatura")
        change_claim_amount(self.claim, "250", self.user, "valor real do pacote")
        (line,) = _lines(self.claim)
        self.assertEqual(line.valor, Decimal("250.00"))
        self.assertIn("€ 30.00 → € 250.00", self.claim.review_notes)
        self.assertIn("operador", self.claim.review_notes)

    def test_alterar_valor_ja_pago_nao_mexe_na_pf_paga_e_ajusta_na_aberta(self):
        self._pay(self.pf)
        nova = self._pf("PF-2", date(2026, 9, 16), date(2026, 9, 30), "CALCULADO")
        change_claim_amount(self.claim, "20", self.user, "acordo com o motorista")
        self.assertEqual(_lines(self.claim)[0].valor, Decimal("30.00"), "a PF paga fica intacta")
        (adj,) = _lines(self.claim, "adjust")
        self.assertEqual((adj.pre_invoice_id, adj.valor), (nova.id, Decimal("-10.00")))
        # Mudar outra vez substitui o ajuste, não soma.
        change_claim_amount(self.claim, "50", self.user, "afinal é mais")
        (adj,) = _lines(self.claim, "adjust")
        self.assertEqual(adj.valor, Decimal("20.00"))

    def test_remover_em_pf_aberta_tira_a_linha(self):
        r = remove_claim(self.claim, self.user, "prova de entrega válida")
        self.assertEqual(self.claim.status, "REJECTED")
        self.assertEqual(_lines(self.claim), [])
        self.assertIn("já não desconta", r["message"])
        self.assertEqual(claim_billing_state(self.claim)["code"], "removido")

    def test_remover_ja_pago_devolve_em_credito_e_repor_desfaz(self):
        self._pay(self.pf)
        nova = self._pf("PF-2", date(2026, 9, 16), date(2026, 9, 30), "CALCULADO")
        remove_claim(self.claim, self.user, "decisão da gestão")
        (credit,) = _lines(self.claim, "credit")
        self.assertEqual((credit.pre_invoice_id, credit.valor), (nova.id, Decimal("-30.00")))

        restore_claim(self.claim, self.user, "removido por engano")
        self.assertEqual(self.claim.status, "APPROVED")
        self.assertEqual(_lines(self.claim, "credit"), [])
        self.assertEqual(len(_lines(self.claim)), 1, "continua só o desconto já pago")

    def test_remover_pago_sem_pf_aberta_credita_na_proxima_gerada(self):
        self._pay(self.pf)
        r = remove_claim(self.claim, self.user, "decisão da gestão")
        self.assertIn("próxima pré-fatura", r["message"])
        self.assertEqual(_lines(self.claim, "credit"), [])
        nova = self._pf("PF-2", date(2026, 9, 16), date(2026, 9, 30), "CALCULADO")
        self.assertEqual(carry_forward_pending_credits(nova), 1)
        self.assertEqual(_lines(self.claim, "credit")[0].valor, Decimal("-30.00"))
        self.assertEqual(carry_forward_pending_credits(nova), 0, "idempotente")

    def test_motivo_obrigatorio_e_valor_valido(self):
        with self.assertRaises(ClaimActionError):
            remove_claim(self.claim, self.user, "")
        with self.assertRaises(ClaimActionError):
            change_claim_amount(self.claim, "-5", self.user, "x")
        with self.assertRaises(ClaimActionError):
            restore_claim(self.claim, self.user, "x")


@override_settings(CACHES=LOCMEM)
class PortalAndDetailViewsTests(TestCase):
    def setUp(self):
        Partner.objects.create(name="CAINIAO", nif="514154411", contact_email="c@x.pt")
        self.driver_id = create_driver_for_courier_name("Ana_LF", "1576538000001")["driver_id"]
        self.pf = DriverPreInvoice.objects.create(
            numero="PF-1", driver_id=self.driver_id, periodo_inicio=date(2026, 9, 1),
            periodo_fim=date(2026, 9, 15), status="CALCULADO",
        )
        self.claim = DriverClaim.objects.create(
            driver_id=self.driver_id, claim_type="CUSTOMER_COMPLAINT", amount=Decimal("30.00"),
            description="Fake Delivery", waybill_number="CNPRT1", operation_task_date=date(2026, 9, 10),
            status="APPROVED",
        )
        apply_claim_now(self.claim)
        admin = get_user_model().objects.create_superuser("admin", "a@x.pt", "x")
        self.client.force_login(admin)

    def test_portal_mostra_e_decide(self):
        page = f"/driversapp/portal/{self.driver_id}/descontos/"
        r = self.client.get(page, secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Na pré-fatura (por pagar) · PF-1")
        self.assertContains(r, "Remover desconto")

        url = f"/driversapp/portal/{self.driver_id}/descontos/{self.claim.id}/decidir/"
        self.client.post(url, {"action": "change_amount", "amount": "45", "reason": "valor real"}, secure=True)
        self.assertEqual(_lines(self.claim)[0].valor, Decimal("45.00"))
        r = self.client.post(url, {"action": "remove", "reason": ""}, secure=True, follow=True)
        self.assertContains(r, "Indica o motivo")
        self.client.post(url, {"action": "remove", "reason": "prova válida"}, secure=True)
        self.claim.refresh_from_db()
        self.assertEqual(self.claim.status, "REJECTED")
        self.assertEqual(_lines(self.claim), [])
        self.assertEqual(self.client.get(page, secure=True).status_code, 200)

    def test_detalhe_rejeitar_aprovado_tira_da_pf_e_apagar_pago_e_bloqueado(self):
        self.assertEqual(self.client.get(f"/settlements/claims/{self.claim.id}/", secure=True).status_code, 200)
        self.client.post(f"/settlements/claims/{self.claim.id}/", {"action": "reject", "review_notes": "ok"}, secure=True)
        self.claim.refresh_from_db()
        self.assertEqual((self.claim.status, _lines(self.claim)), ("REJECTED", []))

        other = DriverClaim.objects.create(
            driver_id=self.driver_id, claim_type="ORDER_LOSS", amount=Decimal("50"), description="x",
            waybill_number="CNPRT2", operation_task_date=date(2026, 9, 10), status="APPROVED",
        )
        apply_claim_now(other)
        self.pf.status = "PAGO"
        self.pf.save()
        self.client.post(f"/settlements/claims/{other.id}/delete/", secure=True)
        self.assertTrue(DriverClaim.objects.filter(pk=other.id).exists(), "pago não se apaga")
