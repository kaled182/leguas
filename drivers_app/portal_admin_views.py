"""Páginas admin dedicadas no portal individual:
   editar, documentos, veículos, helpers, reclamações.

Substitui o modal monstruoso por páginas próprias modernas.
"""
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db import models
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import (
    DriverDocument, DriverProfile, Vehicle, VehicleDocument,
    CustomerComplaint, EmpresaParceira,
)


def _is_admin(u):
    return u.is_authenticated and (u.is_staff or u.is_superuser)


admin_required = user_passes_test(_is_admin, login_url="/auth/login/")


# ─── EDITAR PERFIL (admin) ──────────────────────────────────────────

EDITABLE_BY_ADMIN = [
    # Identificação
    "nif", "nome_completo", "apelido", "courier_id_cainiao", "niss",
    "data_nascimento", "nacionalidade",
    # Contacto
    "telefone", "email", "endereco_residencia", "codigo_postal", "cidade",
    # Vínculo
    "tipo_vinculo", "nome_frota",
    # Comerciais
    "daily_capacity", "price_per_package", "advance_monthly_limit",
    "bonus_performance_enabled",
    # Fiscal
    "vat_regime", "irs_retention_pct",
    # Status
    "status", "is_active", "notas",
]


@admin_required
@require_http_methods(["GET", "POST"])
def driver_admin_edit(request, driver_id):
    """Edição admin completa — sem aprovação."""
    driver = get_object_or_404(DriverProfile, pk=driver_id)

    # Campos numéricos que aceitam NULL no DB (vazio → None em vez de "")
    NUMERIC_NULLABLE = (
        "daily_capacity", "price_per_package", "advance_monthly_limit",
    )
    # Campos numéricos NOT NULL (vazio → 0)
    NUMERIC_DEFAULT_ZERO = ("irs_retention_pct",)

    if request.method == "POST":
        from decimal import Decimal, InvalidOperation
        for field in EDITABLE_BY_ADMIN:
            if field in request.POST:
                value = request.POST.get(field, "").strip()

                # Booleans (checkbox): "on" se ticado
                if field in ("is_active", "bonus_performance_enabled"):
                    setattr(driver, field, value == "on")
                    continue

                # Datas vazias → None
                if field == "data_nascimento":
                    setattr(driver, field, value or None)
                    continue

                # Numéricos vazios → None; senão converter
                if field in NUMERIC_NULLABLE:
                    if not value:
                        setattr(driver, field, None)
                        continue
                    try:
                        if field == "daily_capacity":
                            value = int(value)
                        else:
                            value = Decimal(value)
                    except (InvalidOperation, ValueError):
                        messages.error(
                            request, f"Valor inválido em {field}: '{value}'",
                        )
                        continue
                    setattr(driver, field, value)
                    continue

                # Numéricos com default zero (NOT NULL no modelo)
                if field in NUMERIC_DEFAULT_ZERO:
                    if not value:
                        setattr(driver, field, Decimal("0"))
                        continue
                    try:
                        setattr(driver, field, Decimal(value))
                    except (InvalidOperation, ValueError):
                        messages.error(
                            request, f"Valor inválido em {field}: '{value}'",
                        )
                    continue

                # Strings normais
                setattr(driver, field, value)

        # Campos boolean fora do POST → False
        if "is_active" not in request.POST:
            driver.is_active = False
        if "bonus_performance_enabled" not in request.POST:
            driver.bonus_performance_enabled = False

        # Empresa parceira (FK)
        ep_id = request.POST.get("empresa_parceira", "").strip()
        if ep_id:
            try:
                driver.empresa_parceira = EmpresaParceira.objects.get(pk=ep_id)
            except EmpresaParceira.DoesNotExist:
                pass
        else:
            driver.empresa_parceira = None

        try:
            driver.save()
            messages.success(request, "Perfil actualizado com sucesso.")
            return redirect("drivers_app:driver_admin_edit", driver_id=driver.id)
        except Exception as e:
            messages.error(request, f"Erro ao guardar: {e}")

    return render(request, "drivers_app/portal/admin_edit.html", {
        "driver": driver,
        "fleets": EmpresaParceira.objects.filter(ativo=True).order_by("nome"),
    })


# ─── DOCUMENTOS ─────────────────────────────────────────────────────

@admin_required
@require_http_methods(["GET", "POST"])
def driver_documents(request, driver_id):
    """Lista + upload de documentos."""
    driver = get_object_or_404(DriverProfile, pk=driver_id)

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "upload":
            tipo = request.POST.get("tipo_documento", "")
            arquivo = request.FILES.get("arquivo")
            data_validade = request.POST.get("data_validade", "") or None
            categoria = request.POST.get("categoria_cnh", "")
            obs = request.POST.get("observacoes", "")

            if not tipo or not arquivo:
                messages.error(request, "Tipo e ficheiro são obrigatórios.")
            else:
                doc = DriverDocument(
                    motorista=driver,
                    tipo_documento=tipo,
                    arquivo=arquivo,
                    data_validade=data_validade,
                    categoria_cnh=categoria,
                    observacoes=obs,
                )
                doc.save()
                messages.success(request, f"Documento '{doc.get_tipo_documento_display()}' adicionado.")
            return redirect("drivers_app:driver_documents", driver_id=driver.id)

        if action == "delete":
            doc_id = request.POST.get("doc_id", "")
            doc = DriverDocument.objects.filter(pk=doc_id, motorista=driver).first()
            if doc:
                tipo_label = doc.get_tipo_documento_display()
                doc.delete()
                messages.success(request, f"Documento '{tipo_label}' eliminado.")
            return redirect("drivers_app:driver_documents", driver_id=driver.id)

    documents = driver.documents.all().order_by("-uploaded_at")

    # Stats
    total = documents.count()
    expired = sum(1 for d in documents if d.is_expired)
    expiring_soon = sum(
        1 for d in documents
        if d.data_validade and 0 <= (d.data_validade - timezone.now().date()).days <= 30
    )

    return render(request, "drivers_app/portal/admin_documents.html", {
        "driver": driver,
        "documents": documents,
        "total": total,
        "expired": expired,
        "expiring_soon": expiring_soon,
        "tipo_choices": DriverDocument.TIPO_DOCUMENTO_CHOICES,
    })


# ─── VEÍCULOS ───────────────────────────────────────────────────────

@admin_required
@require_http_methods(["GET", "POST"])
def driver_vehicles(request, driver_id):
    """Lista + adicionar veículos."""
    driver = get_object_or_404(DriverProfile, pk=driver_id)

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "add":
            matricula = request.POST.get("matricula", "").strip().upper()
            marca = request.POST.get("marca", "").strip()
            modelo = request.POST.get("modelo", "").strip()
            tipo = request.POST.get("tipo_veiculo", "")
            ano = request.POST.get("ano", "") or None
            cor = request.POST.get("cor", "").strip()

            if not matricula or not marca or not modelo or not tipo:
                messages.error(request, "Matrícula, marca, modelo e tipo são obrigatórios.")
            elif Vehicle.objects.filter(matricula=matricula).exists():
                messages.error(request, f"Já existe veículo com matrícula '{matricula}'.")
            else:
                v = Vehicle(
                    motorista=driver,
                    matricula=matricula, marca=marca, modelo=modelo,
                    tipo_veiculo=tipo, ano=ano or None, cor=cor,
                )
                v.save()
                messages.success(request, f"Veículo '{matricula}' adicionado.")
            return redirect("drivers_app:driver_vehicles", driver_id=driver.id)

        if action == "toggle_active":
            v_id = request.POST.get("vehicle_id", "")
            v = Vehicle.objects.filter(pk=v_id, motorista=driver).first()
            if v:
                v.is_active = not v.is_active
                v.save(update_fields=["is_active", "updated_at"])
                messages.success(request, f"Veículo '{v.matricula}' {'activado' if v.is_active else 'desactivado'}.")
            return redirect("drivers_app:driver_vehicles", driver_id=driver.id)

        if action == "delete":
            v_id = request.POST.get("vehicle_id", "")
            v = Vehicle.objects.filter(pk=v_id, motorista=driver).first()
            if v:
                m = v.matricula
                v.delete()
                messages.success(request, f"Veículo '{m}' eliminado.")
            return redirect("drivers_app:driver_vehicles", driver_id=driver.id)

    vehicles = driver.vehicles.all().order_by("-is_active", "-created_at")

    return render(request, "drivers_app/portal/admin_vehicles.html", {
        "driver": driver,
        "vehicles": vehicles,
        "tipo_choices": Vehicle.TIPO_VEICULO_CHOICES,
        "active_count": sum(1 for v in vehicles if v.is_active),
        "inactive_count": sum(1 for v in vehicles if not v.is_active),
    })


# ─── HELPERS ────────────────────────────────────────────────────────

@admin_required
@require_http_methods(["GET", "POST"])
def driver_helpers(request, driver_id):
    """Lista + adicionar/remover helpers."""
    from settlements.models import DriverHelper
    driver = get_object_or_404(DriverProfile, pk=driver_id)

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "add":
            helper_name = request.POST.get("helper_name", "").strip()
            if not helper_name:
                messages.error(request, "Nome do helper é obrigatório.")
            elif DriverHelper.objects.filter(driver=driver, helper_name=helper_name).exists():
                messages.error(request, f"Helper '{helper_name}' já existe para este driver.")
            else:
                DriverHelper.objects.create(driver=driver, helper_name=helper_name)
                messages.success(request, f"Helper '{helper_name}' adicionado.")
            return redirect("drivers_app:driver_helpers", driver_id=driver.id)

        if action == "delete":
            h_id = request.POST.get("helper_id", "")
            h = DriverHelper.objects.filter(pk=h_id, driver=driver).first()
            if h:
                name = h.helper_name
                h.delete()
                messages.success(request, f"Helper '{name}' removido.")
            return redirect("drivers_app:driver_helpers", driver_id=driver.id)

    helpers = driver.helpers.all().order_by("helper_name")

    return render(request, "drivers_app/portal/admin_helpers.html", {
        "driver": driver,
        "helpers": helpers,
    })


# ─── LOGINS POR PARCEIRO (DriverCourierMapping) ─────────────────────

@admin_required
@require_http_methods(["GET", "POST"])
def driver_logins(request, driver_id):
    """Gestão de logins por parceiro. Cada parceiro tem o seu courier_id."""
    from settlements.models import DriverCourierMapping
    from core.models import Partner

    driver = get_object_or_404(DriverProfile, pk=driver_id)

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "add":
            partner_id = request.POST.get("partner_id", "")
            courier_id = request.POST.get("courier_id", "").strip()
            courier_name = request.POST.get("courier_name", "").strip()

            if not partner_id or not courier_id:
                messages.error(request, "Parceiro e Courier ID são obrigatórios.")
            else:
                try:
                    partner = Partner.objects.get(pk=partner_id)
                except Partner.DoesNotExist:
                    messages.error(request, "Parceiro inválido.")
                    return redirect("drivers_app:driver_logins", driver_id=driver.id)

                # Verifica unique constraint (partner + courier_id)
                if DriverCourierMapping.objects.filter(
                    partner=partner, courier_id=courier_id
                ).exclude(driver=driver).exists():
                    messages.error(request, f"Courier ID '{courier_id}' já está atribuído a outro motorista neste parceiro.")
                else:
                    DriverCourierMapping.objects.update_or_create(
                        driver=driver, partner=partner, courier_id=courier_id,
                        defaults={"courier_name": courier_name},
                    )
                    messages.success(request, f"Login '{courier_id}' adicionado para {partner.name}.")
            return redirect("drivers_app:driver_logins", driver_id=driver.id)

        if action == "edit":
            mapping_id = request.POST.get("mapping_id", "")
            new_courier_id = request.POST.get("courier_id", "").strip()
            new_courier_name = request.POST.get("courier_name", "").strip()
            m = DriverCourierMapping.objects.filter(pk=mapping_id, driver=driver).first()
            if m and new_courier_id:
                # Verifica conflito de courier_id no mesmo partner
                conflict = DriverCourierMapping.objects.filter(
                    partner=m.partner, courier_id=new_courier_id,
                ).exclude(pk=m.pk).exists()
                if conflict:
                    messages.error(request, f"Courier ID '{new_courier_id}' já existe noutro motorista.")
                else:
                    m.courier_id = new_courier_id
                    m.courier_name = new_courier_name
                    m.save()
                    messages.success(request, "Login actualizado.")
            return redirect("drivers_app:driver_logins", driver_id=driver.id)

        if action == "delete":
            mapping_id = request.POST.get("mapping_id", "")
            m = DriverCourierMapping.objects.filter(pk=mapping_id, driver=driver).first()
            if m:
                ref = f"{m.partner.name}/{m.courier_id}"
                m.delete()
                messages.success(request, f"Login '{ref}' removido.")
            return redirect("drivers_app:driver_logins", driver_id=driver.id)

    mappings = DriverCourierMapping.objects.filter(driver=driver).select_related("partner")
    partners = Partner.objects.all().order_by("name")

    return render(request, "drivers_app/portal/admin_logins.html", {
        "driver": driver,
        "mappings": mappings,
        "partners": partners,
    })


# ─── FINANCEIRO (Conta-Corrente + Relatório de Entregas) ────────────

@admin_required
def driver_financeiro(request, driver_id):
    """Redirect — Faturas e Financeiro foram unificados."""
    return redirect("drivers_app:driver_portal_invoices", driver_id=driver_id)


@admin_required
def driver_pre_invoice_detail(request, driver_id, pre_invoice_id):
    """Detalhe completo de uma Pré-Fatura — substitui modal antigo."""
    import re
    from collections import Counter
    from settlements.models import (
        DriverPreInvoice, PreInvoiceLine, PreInvoiceBonus, PreInvoiceAdvance,
        DriverCourierMapping, CourierNameAlias, WaybillAttributionOverride,
    )
    from core.models import Partner

    driver = get_object_or_404(DriverProfile, pk=driver_id)
    pf = get_object_or_404(DriverPreInvoice, pk=pre_invoice_id, driver=driver)

    linhas = list(pf.linhas.all().select_related("parceiro").order_by("parceiro__name"))

    # ─── Anotar cada linha com nome amigável e info de transferências ───
    # Helper: extrai "Login Cainiao: NOME (via ...)" da observação
    obs_login_re = re.compile(r"Login.*?:\s*([A-Za-z0-9_.\-]+)", re.IGNORECASE)

    # Pré-load mappings deste parceiro/driver
    mappings_by_courier_id = {}
    for m in DriverCourierMapping.objects.filter(driver=driver).select_related("partner"):
        mappings_by_courier_id[(m.partner_id, m.courier_id)] = m.courier_name
    for a in CourierNameAlias.objects.filter().select_related("partner"):
        mappings_by_courier_id.setdefault((a.partner_id, a.courier_id), a.courier_name)

    # Detectar transferências recebidas no período → mostrar drivers de origem
    transfers = WaybillAttributionOverride.objects.filter(
        attributed_to_driver=driver,
        task_date__gte=pf.periodo_inicio,
        task_date__lte=pf.periodo_fim,
    )
    # Agregar por driver de origem (courier name)
    transfers_by_origin = Counter(
        (t.original_courier_name or t.original_courier_id or "Desconhecido")
        for t in transfers
    )

    for l in linhas:
        l.is_transfer = "transferência" in (l.courier_id or "").lower() \
                        or "↻" in (l.observacoes or "")
        # Nome do login amigável
        if l.is_transfer:
            l.display_name = "Transferências recebidas"
            # Drivers de origem (top-N)
            l.transfer_origins = transfers_by_origin.most_common(10)
        else:
            # Tenta primeiro: mapping pelo (partner_id, courier_id)
            name = mappings_by_courier_id.get((l.parceiro_id, l.courier_id))
            if not name:
                # Tenta extrair do observacoes
                m = obs_login_re.search(l.observacoes or "")
                if m:
                    name = m.group(1)
            # Se courier_id já é nome (não puramente numérico), usa-o
            if not name and not (l.courier_id or "").isdigit():
                name = l.courier_id
            l.display_name = name or ""

    bonus = pf.bonificacoes.all().order_by("-data") if hasattr(pf, "bonificacoes") else []
    advances = pf.adiantamentos.all().order_by("-data") if hasattr(pf, "adiantamentos") else []
    lost_packages = pf.pacotes_perdidos.all().order_by("-data") if hasattr(pf, "pacotes_perdidos") else []

    # ─── Comissões de Indicação (mesma lógica do recalcular()/PDF) ───
    # Conta entregas Delivered confirmadas do indicado no período.
    from decimal import Decimal as _D
    from .portal_views import referred_delivered_count
    indicacoes_detail = []
    indicacoes_total = _D("0.00")
    for ref in driver.referrals_given.filter(
        ativo=True
    ).select_related("referred"):
        delivered = referred_delivered_count(
            ref.referred, pf.periodo_inicio, pf.periodo_fim,
        )
        ref_valor = _D(delivered) * ref.comissao_por_pacote
        indicacoes_total += ref_valor
        indicacoes_detail.append({
            "nome": ref.referred.nome_completo or ref.referred.apelido or "—",
            "referred_id": ref.referred.id,
            "pacotes": delivered,
            "comissao_por_pacote": ref.comissao_por_pacote,
            "valor": ref_valor,
        })

    partners = Partner.objects.all().order_by("name")

    return render(request, "drivers_app/portal/admin_pf_detail.html", {
        "driver": driver,
        "pf": pf,
        "linhas": linhas,
        "bonus": bonus,
        "advances": advances,
        "lost_packages": lost_packages,
        "indicacoes_detail": indicacoes_detail,
        "indicacoes_total": indicacoes_total,
        "partners": partners,
    })


# ─── RECLAMAÇÕES ────────────────────────────────────────────────────

@admin_required
def driver_complaints(request, driver_id):
    """Reclamações associadas a este motorista."""
    driver = get_object_or_404(DriverProfile, pk=driver_id)

    complaints = CustomerComplaint.objects.filter(driver=driver).order_by("-created_at")

    counts = {
        "total": complaints.count(),
        "open": complaints.filter(status__in=["ABERTO", "NOTIFICADO"]).count(),
        "responded": complaints.filter(status="RESPONDIDO").count(),
        "closed": complaints.filter(status="FECHADO").count(),
    }

    return render(request, "drivers_app/portal/admin_complaints.html", {
        "driver": driver,
        "complaints": complaints,
        "counts": counts,
    })


# ─── DESCONTOS / DriverClaim ────────────────────────────────────────

@admin_required
def driver_claims(request, driver_id):
    """Descontos (DriverClaim) aplicados ao motorista — com workflow
    de recurso para o operador anexar prova de entrega e contestar
    com a Cainiao.
    """
    from settlements.models import DriverClaim

    driver = get_object_or_404(DriverProfile, pk=driver_id)
    claims = DriverClaim.objects.filter(driver=driver).order_by(
        "-occurred_at",
    )

    counts = {
        "total": claims.count(),
        "pending": claims.filter(status="PENDING").count(),
        "approved": claims.filter(status="APPROVED").count(),
        "rejected": claims.filter(status="REJECTED").count(),
        "appealed": claims.filter(status="APPEALED").count(),
    }
    total_pending_value = claims.filter(status="PENDING").aggregate(
        s=models.Sum("amount"),
    )["s"] or 0
    total_approved_value = claims.filter(status="APPROVED").aggregate(
        s=models.Sum("amount"),
    )["s"] or 0

    return render(request, "drivers_app/portal/admin_claims.html", {
        "driver": driver,
        "claims": claims,
        "counts": counts,
        "total_pending_value": total_pending_value,
        "total_approved_value": total_approved_value,
    })


@admin_required
@require_http_methods(["POST"])
def driver_complaint_apply_claim(request, driver_id, complaint_id):
    """A partir de uma CustomerComplaint cria DriverClaim financeiro
    vinculado.

    Pré-preenche:
      - waybill_number ← complaint.numero_pacote
      - description ← complaint.descricao
      - occurred_at ← complaint.data_entrega ou complaint.created_at
      - claim_type ← inferido do tipo da reclamação
      - amount ← do form (default €30 = LM-F7 Cainiao)

    Idempotência: 1 reclamação ↔ no máximo 1 DriverClaim. Se já existe,
    mostra mensagem.
    """
    from settlements.models import DriverClaim

    driver = get_object_or_404(DriverProfile, pk=driver_id)
    complaint = get_object_or_404(
        CustomerComplaint, pk=complaint_id, driver=driver,
    )

    # Idempotente — uma reclamação só dá origem a um claim
    existing = DriverClaim.objects.filter(
        customer_complaint=complaint,
    ).first()
    if existing:
        messages.info(
            request,
            f"Esta reclamação já tem o desconto #{existing.id} associado.",
        )
        return redirect(
            "drivers_app:driver_complaints", driver_id=driver.id,
        )

    # Mapear tipo da reclamação → claim_type
    type_map = {
        "ENTREGA_FALSA": "CUSTOMER_COMPLAINT",
        "ITEM_FALTANDO": "ORDER_LOSS",
        "PACOTE_DANIFICADO": "ORDER_DAMAGE",
        "ENTREGA_ATRASADA": "LATE_DELIVERY",
        "OUTRO": "CUSTOMER_COMPLAINT",
    }
    default_claim_type = type_map.get(complaint.tipo, "CUSTOMER_COMPLAINT")
    requested_type = (request.POST.get("claim_type") or "").strip()
    if requested_type and requested_type in dict(DriverClaim.CLAIM_TYPES):
        claim_type = requested_type
    else:
        claim_type = default_claim_type

    from decimal import Decimal, InvalidOperation
    raw_amount = (request.POST.get("amount") or "30.00").replace(",", ".")
    try:
        amount = Decimal(raw_amount)
    except (InvalidOperation, ValueError):
        amount = Decimal("30.00")

    occurred = complaint.data_entrega or complaint.created_at

    description = (
        f"Reclamação cliente #{complaint.id} — "
        f"{complaint.get_tipo_display()}\n"
        f"Cliente: {complaint.nome_cliente} ({complaint.telefone_cliente})\n"
        f"Pacote: {complaint.numero_pacote}\n"
        f"Relato: {complaint.descricao}"
    )[:2000]

    claim = DriverClaim.objects.create(
        driver=driver,
        customer_complaint=complaint,
        claim_type=claim_type,
        amount=amount,
        description=description,
        occurred_at=occurred,
        waybill_number=complaint.numero_pacote,
        status="PENDING",
        created_by=(
            request.user if request.user.is_authenticated else None
        ),
    )

    messages.success(
        request,
        f"Desconto #{claim.id} (€{amount:.2f}) criado a partir da "
        f"reclamação #{complaint.id}. Agora podes abrir recurso/"
        "anexar prova na tab Descontos.",
    )
    return redirect(
        "drivers_app:driver_claims", driver_id=driver.id,
    )


@admin_required
@require_http_methods(["POST"])
def driver_claim_appeal(request, driver_id, claim_id):
    """Operador inicia recurso ao claim:
    - Status passa de PENDING/APPROVED → APPEALED
    - Anexa prova de entrega (foto/PDF) + justificação
    - Estado fica em recurso até REJECTED ou cancelado
    """
    from settlements.models import DriverClaim

    driver = get_object_or_404(DriverProfile, pk=driver_id)
    claim = get_object_or_404(DriverClaim, id=claim_id, driver=driver)
    if claim.status not in ("PENDING", "APPROVED"):
        messages.error(
            request,
            f"Estado {claim.get_status_display()} não permite recurso.",
        )
        return redirect("drivers_app:driver_claims", driver_id=driver.id)

    justification = (request.POST.get("justification") or "").strip()
    evidence = request.FILES.get("evidence_file")

    if not justification:
        messages.error(request, "Justificação é obrigatória.")
        return redirect("drivers_app:driver_claims", driver_id=driver.id)

    claim.status = "APPEALED"
    claim.justification = justification
    if evidence:
        claim.evidence_file = evidence
    claim.save(update_fields=[
        "status", "justification", "evidence_file", "updated_at",
    ])

    messages.success(
        request,
        f"Recurso aberto para reclamação #{claim.id}. "
        "Use o detalhe do claim para responder com a Cainiao.",
    )
    return redirect("drivers_app:driver_claims", driver_id=driver.id)


# ─── UNIFICAÇÃO de Cadastros ─────────────────────────────────────────

@require_http_methods(["GET"])
@user_passes_test(_is_admin)
def driver_unify_search(request, driver_id):
    """Devolve lista de drivers candidatos para unificação (excepto o próprio)."""
    from django.http import JsonResponse
    q = (request.GET.get("q") or "").strip()
    qs = DriverProfile.objects.exclude(id=driver_id)
    if q:
        qs = qs.filter(
            Q(nome_completo__icontains=q) |
            Q(apelido__icontains=q) |
            Q(courier_id_cainiao__icontains=q) |
            Q(nif__icontains=q) |
            Q(telefone__icontains=q)
        )
    items = []
    for d in qs.order_by("nome_completo")[:30]:
        items.append({
            "id": d.id,
            "nome_completo": d.nome_completo,
            "apelido": d.apelido or "",
            "courier_id_cainiao": d.courier_id_cainiao or "",
            "nif": d.nif or "",
        })
    return JsonResponse({"results": items})


@require_http_methods(["GET"])
@user_passes_test(_is_admin)
def driver_unify_preview(request, driver_id, target_id):
    """Devolve contagem do que vai ser transferido se source=driver_id → target=target_id."""
    from django.http import JsonResponse
    from .services_merge import preview_merge
    source = get_object_or_404(DriverProfile, pk=driver_id)
    target = get_object_or_404(DriverProfile, pk=target_id)
    if source.pk == target.pk:
        return JsonResponse(
            {"success": False, "error": "Não podes unificar com o próprio."},
            status=400,
        )
    counts = preview_merge(source, target)
    return JsonResponse({
        "success": True,
        "source": {
            "id": source.id, "nome": source.nome_completo,
            "apelido": source.apelido, "courier": source.courier_id_cainiao,
        },
        "target": {
            "id": target.id, "nome": target.nome_completo,
            "apelido": target.apelido, "courier": target.courier_id_cainiao,
        },
        "counts": counts,
    })


@require_http_methods(["POST"])
@user_passes_test(_is_admin)
def driver_unify_execute(request, driver_id):
    """Executa o merge: source=driver_id → target=POST['target_id']."""
    from django.http import JsonResponse
    from .services_merge import merge_drivers
    target_id = request.POST.get("target_id")
    if not target_id:
        return JsonResponse(
            {"success": False, "error": "target_id é obrigatório."},
            status=400,
        )
    try:
        target_id = int(target_id)
    except (TypeError, ValueError):
        return JsonResponse(
            {"success": False, "error": "target_id inválido."},
            status=400,
        )

    source = get_object_or_404(DriverProfile, pk=driver_id)
    target = get_object_or_404(DriverProfile, pk=target_id)
    notes = (request.POST.get("notes") or "").strip()

    try:
        audit = merge_drivers(
            source=source, target=target, user=request.user, notes=notes,
        )
    except (ValueError, RuntimeError) as e:
        return JsonResponse(
            {"success": False, "error": str(e)}, status=400,
        )

    return JsonResponse({
        "success": True,
        "audit_id": audit.id,
        "target_driver_id": target.id,
        "transferred": audit.transferred_counts,
        "redirect_to": f"/driversapp/portal/{target.id}/editar/",
    })
