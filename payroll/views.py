"""Views da Folha de Pagamento (acesso restrito a staff).

Endpoints:
  - employees/        : lista funcionários
  - employees/novo/   : criar
  - employees/<id>/   : editar
  - employees/<id>/delete/ : remover (apenas se sem folhas)
  - payrolls/         : lista folhas
  - payrolls/gerar/   : gera lote mensal
  - payrolls/<id>/    : detalhe
  - payrolls/<id>/component/add/   : adicionar componente manual
  - payrolls/<id>/component/<cid>/delete/ : remover componente
  - payrolls/<id>/recalc/ : recalcular
  - payrolls/<id>/approve/ : aprovar (cria Impostos)
  - payrolls/<id>/pay/     : marcar como paga (cria Bill)
  - payrolls/<id>/cancel/  : cancelar (anula em cascata)
  - payrolls/<id>/recibo.pdf : PDF do recibo
"""
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from .forms import EmployeeForm, PayrollGenerateForm, PayrollComponentForm
from .models import Employee, Payroll, PayrollComponent
from .services import (
    approve_payroll, cancel_payroll, generate_monthly_batch,
    generate_monthly_payroll, mark_payroll_paid,
)


def _staff_required(view):
    return user_passes_test(
        lambda u: u.is_authenticated and (u.is_staff or u.is_superuser)
    )(view)


# ── Employees ──────────────────────────────────────────────────────────

@login_required
@_staff_required
def employee_list(request):
    qs = Employee.objects.all()
    apenas_activos = request.GET.get("ativo", "1") == "1"
    if apenas_activos:
        qs = qs.filter(ativo=True)
    total = qs.count()
    folha_mensal = qs.aggregate(
        bruto=Sum("vencimento_base"),
    )["bruto"] or Decimal("0")
    return render(request, "payroll/employee_list.html", {
        "employees": qs,
        "total": total,
        "folha_mensal_bruto": folha_mensal,
        "apenas_activos": apenas_activos,
    })


@login_required
@_staff_required
def employee_create(request):
    if request.method == "POST":
        form = EmployeeForm(request.POST)
        if form.is_valid():
            emp = form.save()
            messages.success(request, f"Funcionário {emp.nome} criado.")
            return redirect("payroll:employee_list")
    else:
        form = EmployeeForm()
    return render(request, "payroll/employee_form.html", {
        "form": form, "title": "Novo Funcionário",
    })


@login_required
@_staff_required
def employee_edit(request, pk):
    emp = get_object_or_404(Employee, pk=pk)
    if request.method == "POST":
        form = EmployeeForm(request.POST, instance=emp)
        if form.is_valid():
            form.save()
            messages.success(request, "Funcionário actualizado.")
            return redirect("payroll:employee_list")
    else:
        form = EmployeeForm(instance=emp)
    return render(request, "payroll/employee_form.html", {
        "form": form, "title": f"Editar — {emp.nome}", "employee": emp,
    })


@login_required
@_staff_required
@require_POST
def employee_delete(request, pk):
    emp = get_object_or_404(Employee, pk=pk)
    if emp.payrolls.exists():
        messages.error(
            request,
            "Não é possível remover — existem folhas associadas. "
            "Marque como inactivo em vez disso.",
        )
        return redirect("payroll:employee_list")
    nome = emp.nome
    emp.delete()
    messages.success(request, f"Funcionário {nome} removido.")
    return redirect("payroll:employee_list")


# ── Payrolls ──────────────────────────────────────────────────────────

@login_required
@_staff_required
def payroll_list(request):
    qs = Payroll.objects.select_related("employee").all()
    ano = request.GET.get("ano")
    mes = request.GET.get("mes")
    status = request.GET.get("status")
    emp_id = request.GET.get("emp")
    if ano:
        qs = qs.filter(periodo_ano=int(ano))
    if mes:
        qs = qs.filter(periodo_mes=int(mes))
    if status:
        qs = qs.filter(status=status)
    if emp_id:
        qs = qs.filter(employee_id=int(emp_id))

    today = date.today()
    agg = qs.aggregate(
        bruto=Sum("total_bruto"),
        liquido=Sum("total_liquido"),
        tsu=Sum("tsu_empregador"),
        descontos=Sum("total_descontos"),
    )
    return render(request, "payroll/payroll_list.html", {
        "payrolls": qs,
        "agg": agg,
        "anos": sorted(
            {p.periodo_ano for p in Payroll.objects.all()},
            reverse=True,
        ) or [today.year],
        "employees": Employee.objects.filter(ativo=True),
        "f_ano": ano, "f_mes": mes, "f_status": status, "f_emp": emp_id,
        "today": today,
    })


@login_required
@_staff_required
def payroll_generate(request):
    today = date.today()
    if request.method == "POST":
        form = PayrollGenerateForm(request.POST)
        if form.is_valid():
            ano = form.cleaned_data["ano"]
            mes = form.cleaned_data["mes"]
            dias = form.cleaned_data["dias_uteis"]
            recreate = form.cleaned_data["recreate"]
            if recreate:
                Payroll.objects.filter(
                    periodo_ano=ano, periodo_mes=mes,
                    status=Payroll.STATUS_RASCUNHO,
                ).delete()
            results = generate_monthly_batch(ano, mes, dias_uteis=dias)
            messages.success(
                request,
                f"Lote gerado: {len(results['created'])} folha(s) criada(s). "
                f"{len(results['skipped'])} ignoradas, "
                f"{len(results['errors'])} erro(s).",
            )
            for err in results["errors"]:
                messages.error(request, f"Emp #{err['emp']}: {err['error']}")
            return redirect(
                f"{reverse('payroll:payroll_list')}?ano={ano}&mes={mes}"
            )
    else:
        # Default: mês anterior
        mes = today.month - 1 or 12
        ano = today.year if today.month > 1 else today.year - 1
        form = PayrollGenerateForm(initial={"ano": ano, "mes": mes})

    return render(request, "payroll/payroll_generate.html", {
        "form": form,
        "active_count": Employee.objects.filter(ativo=True).count(),
    })


@login_required
@_staff_required
def payroll_detail(request, pk):
    pf = get_object_or_404(
        Payroll.objects.select_related(
            "employee", "tsu_imposto", "irs_imposto", "bill_espelho",
        ).prefetch_related("componentes"),
        pk=pk,
    )
    brutos = [c for c in pf.componentes.all() if c.tipo in PayrollComponent.TIPOS_BRUTO]
    descontos = [c for c in pf.componentes.all() if c.tipo in PayrollComponent.TIPOS_DESCONTO]
    form = PayrollComponentForm()
    return render(request, "payroll/payroll_detail.html", {
        "pf": pf, "brutos": brutos, "descontos": descontos,
        "form": form,
        "editavel": pf.status == Payroll.STATUS_RASCUNHO,
    })


@login_required
@_staff_required
@require_POST
def payroll_component_add(request, pk):
    pf = get_object_or_404(Payroll, pk=pk)
    if pf.status != Payroll.STATUS_RASCUNHO:
        messages.error(request, "Só rascunhos podem ser editados.")
        return redirect("payroll:payroll_detail", pk=pk)
    form = PayrollComponentForm(request.POST)
    if form.is_valid():
        c = form.save(commit=False)
        c.payroll = pf
        c.save()
        pf.recalcular()
        pf.save()
        messages.success(request, "Componente adicionado.")
    else:
        messages.error(request, "Dados inválidos.")
    return redirect("payroll:payroll_detail", pk=pk)


@login_required
@_staff_required
@require_POST
def payroll_component_delete(request, pk, cid):
    pf = get_object_or_404(Payroll, pk=pk)
    if pf.status != Payroll.STATUS_RASCUNHO:
        messages.error(request, "Só rascunhos podem ser editados.")
        return redirect("payroll:payroll_detail", pk=pk)
    c = get_object_or_404(PayrollComponent, pk=cid, payroll=pf)
    c.delete()
    pf.recalcular()
    pf.save()
    messages.success(request, "Componente removido.")
    return redirect("payroll:payroll_detail", pk=pk)


@login_required
@_staff_required
@require_POST
def payroll_recalc(request, pk):
    pf = get_object_or_404(Payroll, pk=pk)
    if pf.status != Payroll.STATUS_RASCUNHO:
        messages.error(request, "Só rascunhos podem ser recalculados.")
        return redirect("payroll:payroll_detail", pk=pk)
    # Regenera todos os componentes a partir do funcionário
    generate_monthly_payroll(
        pf.employee, pf.periodo_ano, pf.periodo_mes, recreate=True,
    )
    messages.success(request, "Folha recalculada.")
    return redirect("payroll:payroll_detail", pk=pk)


@login_required
@_staff_required
@require_POST
def payroll_approve(request, pk):
    pf = get_object_or_404(Payroll, pk=pk)
    try:
        approve_payroll(pf, user=request.user)
        messages.success(
            request,
            f"Folha aprovada. TSU €{pf.tsu_empregador} criada como Imposto.",
        )
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("payroll:payroll_detail", pk=pk)


@login_required
@_staff_required
@require_POST
def payroll_pay(request, pk):
    pf = get_object_or_404(Payroll, pk=pk)
    paid_date_str = request.POST.get("paid_date")
    paid_date = None
    if paid_date_str:
        try:
            paid_date = date.fromisoformat(paid_date_str)
        except ValueError:
            paid_date = None
    try:
        mark_payroll_paid(pf, paid_date=paid_date, user=request.user)
        messages.success(
            request,
            f"Folha marcada como paga. Bill #{pf.bill_espelho_id} criada.",
        )
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("payroll:payroll_detail", pk=pk)


@login_required
@_staff_required
@require_POST
def payroll_cancel(request, pk):
    pf = get_object_or_404(Payroll, pk=pk)
    cancel_payroll(pf, user=request.user)
    messages.success(request, "Folha cancelada (Impostos/Bill anulados).")
    return redirect("payroll:payroll_detail", pk=pk)


# ── PDF Recibo ─────────────────────────────────────────────────────────

@login_required
@_staff_required
def payroll_recibo_pdf(request, pk):
    pf = get_object_or_404(
        Payroll.objects.select_related("employee"), pk=pk,
    )
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    )

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle(
        "H1", parent=styles["Heading1"], fontSize=14, spaceAfter=6,
    )
    normal = styles["Normal"]
    elements = []

    elements.append(Paragraph("Recibo de Vencimento", h1))
    elements.append(Paragraph(
        f"<b>Funcionário:</b> {pf.employee.nome} "
        f"(NIF {pf.employee.nif or '—'}, NISS {pf.employee.niss or '—'})",
        normal,
    ))
    elements.append(Paragraph(
        f"<b>Período:</b> {pf.periodo_label} &nbsp;&nbsp; "
        f"<b>Contrato:</b> {pf.employee.get_contrato_tipo_display()}",
        normal,
    ))
    elements.append(Paragraph(
        f"<b>Estado:</b> {pf.get_status_display()}",
        normal,
    ))
    elements.append(Spacer(1, 0.4 * cm))

    # Componentes brutos
    data = [["Componente (Bruto)", "Qtd", "Valor (€)"]]
    for c in pf.componentes.filter(tipo__in=PayrollComponent.TIPOS_BRUTO):
        data.append([
            c.get_tipo_display() + (f" — {c.descricao}" if c.descricao else ""),
            f"{c.quantidade}",
            f"{c.valor:.2f}",
        ])
    data.append(["", "Bruto", f"{pf.total_bruto:.2f}"])

    t = Table(data, colWidths=[11 * cm, 2.5 * cm, 3 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.5, colors.black),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.3 * cm))

    # Descontos
    data2 = [["Descontos", "Qtd", "Valor (€)"]]
    for c in pf.componentes.filter(tipo__in=PayrollComponent.TIPOS_DESCONTO):
        data2.append([
            c.get_tipo_display() + (f" — {c.descricao}" if c.descricao else ""),
            f"{c.quantidade}",
            f"{c.valor:.2f}",
        ])
    data2.append(["", "Descontos", f"{pf.total_descontos:.2f}"])
    t2 = Table(data2, colWidths=[11 * cm, 2.5 * cm, 3 * cm])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fee2e2")),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.5, colors.black),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(t2)
    elements.append(Spacer(1, 0.4 * cm))

    # Resumo
    resumo = [
        ["Líquido a receber", f"€ {pf.total_liquido:.2f}"],
        ["TSU empregador (23.75%)", f"€ {pf.tsu_empregador:.2f}"],
        ["Custo total empresa", f"€ {(pf.total_bruto + pf.tsu_empregador):.2f}"],
    ]
    t3 = Table(resumo, colWidths=[10 * cm, 6.5 * cm])
    t3.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (0, 0), 12),
        ("FONTSIZE", (1, 0), (1, 0), 12),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dcfce7")),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(t3)

    doc.build(elements)
    pdf = buf.getvalue()
    buf.close()

    filename = (
        f"recibo_{pf.employee.nome.replace(' ', '_')}_"
        f"{pf.periodo_ano}_{pf.periodo_mes:02d}.pdf"
    )
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="{filename}"'
    return resp
