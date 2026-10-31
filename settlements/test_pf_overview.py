from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.models import Partner
from drivers_app.models import DriverProfile
from settlements.models import (
    CainiaoOperationTask, DriverPreInvoice, PreInvoiceLine,
)
from settlements.services_pf_overview import (
    day_series, line_kind, pf_deductions, waterfall_steps,
)


def _line(source, notes=""):
    return SimpleNamespace(api_source=source, observacoes=notes)


def _pf(**values):
    data = dict(
        base_entregas=Decimal("1797.20"), total_pudo=Decimal("4.00"),
        total_bonus=Decimal("0"), total_extras=Decimal("0"),
        ajuste_manual=Decimal("0"), total_comissoes_indicacao=Decimal("0"),
        total_pacotes_perdidos=Decimal("100.00"),
        penalizacoes_gerais=Decimal("0"), vat_amount=Decimal("0"),
        total_adiantamentos=Decimal("1611.10"),
        total_fatura=Decimal("1701.20"), total_com_iva=Decimal("90.10"),
    )
    data.update(values)
    return SimpleNamespace(**data)


class LineKindTests(SimpleTestCase):
    def test_negotiated_shows_the_cp_codes(self):
        line = _line(
            "auto:per_login_cp",
            "Só entregas Delivered. · Valor negociado do CP €1.40: CP 4480, 4485",
        )
        self.assertEqual(line_kind(line), ("Negociado", "4480, 4485"))

    def test_same_door(self):
        line = _line(
            "auto:per_login_special",
            "Preço especial €0.30: Pacote adicional na mesma porta",
        )
        self.assertEqual(line_kind(line), ("Mesma porta", "Todos"))

    def test_package_override(self):
        self.assertEqual(
            line_kind(_line("auto:per_login_special", "Preço especial €1.30: x")),
            ("Preço especial", "—"),
        )

    def test_base_price(self):
        self.assertEqual(
            line_kind(_line("auto:per_login")), ("Preço base", "Restantes"),
        )

    def test_manual_line(self):
        self.assertEqual(line_kind(_line("")), ("Manual", "—"))


class WaterfallTests(SimpleTestCase):
    def test_luis_gomes_october_figures(self):
        steps = waterfall_steps(_pf())
        self.assertEqual(
            [s["label"] for s in steps],
            ["Entregas", "Pacotes perdidos", "Fatura-Recibo", "Adiantamentos",
             "A receber"],
        )
        self.assertEqual(steps[0]["to"], 1801.20)
        self.assertEqual(steps[1]["value"], -100.0)
        self.assertEqual(steps[-1]["to"], 90.10)

    def test_each_step_starts_where_the_previous_ended(self):
        steps = waterfall_steps(_pf(
            total_bonus=Decimal("30"), penalizacoes_gerais=Decimal("5"),
            vat_amount=Decimal("10"), total_fatura=Decimal("1736.20"),
            total_com_iva=Decimal("125.10"),
        ))
        moves = steps[:steps.index(next(s for s in steps if s["total"]))]
        for before, after in zip(moves, moves[1:]):
            self.assertAlmostEqual(before["to"], after["from"])
        self.assertAlmostEqual(moves[-1]["to"], 1736.20)

    def test_negative_total_ends_below_zero(self):
        steps = waterfall_steps(_pf(
            total_fatura=Decimal("1219.20"), total_com_iva=Decimal("-391.90"),
        ))
        self.assertEqual(steps[-1]["to"], -391.90)

    def test_deductions_add_lost_penalties_and_advances(self):
        pf = _pf(penalizacoes_gerais=Decimal("10"))
        self.assertEqual(pf_deductions(pf), Decimal("1721.10"))

    def test_day_series(self):
        series = day_series([{
            "date": date(2026, 10, 1), "door_normal": 48, "same_door": 5,
            "pudo": 0, "failures": 22,
        }])
        self.assertEqual(series["labels"], ["01/10"])
        self.assertEqual(series["failures"], [22])


class PreInvoicePageTests(TestCase):
    def setUp(self):
        self.client.force_login(
            User.objects.create_superuser("adm", "a@a.pt", "x"),
        )
        self.partner = Partner.objects.create(
            name="CAINIAO", nif="500000000", contact_email="c@a.pt",
        )
        self.driver = DriverProfile.objects.create(
            nif="123456789", nome_completo="Luis", telefone="9",
            email="l@a.pt", apelido="Luis", courier_id_cainiao="ID-1",
            status="ATIVO", is_active=True,
        )
        CainiaoOperationTask.objects.create(
            task_date=date(2026, 10, 10), waybill_number="W1",
            task_status="Delivered", courier_name="Luis",
            courier_id_cainiao="ID-1", zip_code="4480-001",
        )
        self.pf = DriverPreInvoice.objects.create(
            numero="PF-0001", driver=self.driver,
            periodo_inicio=date(2026, 10, 1), periodo_fim=date(2026, 10, 31),
        )
        line = PreInvoiceLine(
            pre_invoice=self.pf, parceiro=self.partner, courier_id="ID-1",
            total_pacotes=1, taxa_por_entrega=Decimal("1.40"),
            dsr_percentual=Decimal("0"), api_source="auto:per_login_cp",
            observacoes="Login Cainiao: Luis. · Valor negociado do CP €1.40: CP 4480",
        )
        line.calcular_e_salvar()
        self.pf.recalcular()

    def _page(self):
        res = self.client.get(reverse(
            "drivers_app:driver_pre_invoice_detail",
            args=[self.driver.pk, self.pf.pk],
        ))
        self.assertEqual(res.status_code, 200)
        return res

    def test_summary_comes_before_the_detail(self):
        html = self._page().content.decode()
        self.assertLess(html.index("A receber"), html.index("pf-chart-steps"))
        self.assertLess(html.index("pf-chart-steps"), html.index('data-pf-panel="preco"'))
        self.assertLess(html.index('data-pf-panel="preco"'), html.index('data-pf-panel="dados"'))

    def test_line_shows_type_and_cp(self):
        res = self._page()
        self.assertContains(res, "Negociado")
        self.assertContains(res, "4480")

    def test_matching_pf_says_so(self):
        self.assertContains(self._page(), "Confere com o sistema")

    def test_mismatch_tells_to_generate_again(self):
        CainiaoOperationTask.objects.create(
            task_date=date(2026, 10, 11), waybill_number="W2",
            task_status="Delivered", courier_name="Luis",
            courier_id_cainiao="ID-1", zip_code="4480-001",
        )
        self.assertContains(self._page(), "Elimine a pré-fatura e gere-a de novo")

    def test_every_edit_action_stays_on_the_page(self):
        res = self._page()
        for name in ("addLinha()", "addBonus()", "addExtra()", "addLostPackage()",
                     "addAdvance()", "guardarDadosGerais()", "apagarPF()"):
            self.assertContains(res, name)
