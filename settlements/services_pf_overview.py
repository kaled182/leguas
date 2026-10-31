"""Resumo da pré-fatura para a página de detalhe: conta do total e gráficos."""
import re

CP_RE = re.compile(r"CP ([\d, ]+)")
SAME_DOOR_MARK = "mesma porta"


def line_kind(line):
    """Tipo e CP de uma linha, a partir da origem gravada na geração."""
    source = line.api_source or ""
    notes = line.observacoes or ""
    if source.endswith("_special"):
        if SAME_DOOR_MARK in notes.lower():
            return "Mesma porta", "Todos"
        return "Preço especial", "—"
    if source.endswith("_cp"):
        found = CP_RE.search(notes)
        return "Negociado", found.group(1).strip() if found else "—"
    if source.startswith("auto:"):
        return "Preço base", "Restantes"
    return "Manual", "—"


def pf_deductions(pf):
    """Pacotes perdidos, penalizações e adiantamentos."""
    return (
        pf.total_pacotes_perdidos + pf.penalizacoes_gerais
        + pf.total_adiantamentos
    )


def waterfall_steps(pf):
    """Passos da conta, do valor das entregas até ao valor a receber."""
    credits = (
        pf.total_bonus + pf.total_extras + pf.ajuste_manual
        + pf.total_comissoes_indicacao
    )
    moves = [
        ("Entregas", pf.base_entregas + pf.total_pudo),
        ("Bónus e extras", credits),
        ("Pacotes perdidos", -pf.total_pacotes_perdidos),
        ("Penalizações", -pf.penalizacoes_gerais),
        ("IVA", pf.vat_amount),
    ]
    steps, running = [], 0
    for label, value in moves:
        if not value:
            continue
        steps.append(_step(label, running, running + value, value))
        running += value
    steps.append(_step("Fatura-Recibo", 0, pf.total_fatura, pf.total_fatura, True))
    running = pf.total_fatura
    if pf.total_adiantamentos:
        after = running - pf.total_adiantamentos
        steps.append(
            _step("Adiantamentos", running, after, -pf.total_adiantamentos),
        )
    steps.append(
        _step("A receber", 0, pf.total_com_iva, pf.total_com_iva, True),
    )
    return steps


def _step(label, start, end, value, total=False):
    return {
        "label": label, "from": float(start), "to": float(end),
        "value": float(value), "total": total,
    }


def day_series(days):
    """Séries do gráfico de entregas por dia."""
    return {
        "labels": [d["date"].strftime("%d/%m") for d in days],
        "door": [d["door_normal"] for d in days],
        "same_door": [d["same_door"] for d in days],
        "pudo": [d["pudo"] for d in days],
        "failures": [d["failures"] for d in days],
    }
