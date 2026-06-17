"""Construtores de dicts JSON para a API da app (campos reais dos modelos)."""


def driver_dict(p):
    return {
        "id": p.id,
        "nome_completo": p.nome_completo,
        "apelido": p.apelido or "",
        "telefone": p.telefone,
        "email": p.email,
        "nif": p.nif,
        "status": p.status,
        "status_display": p.get_status_display(),
        "is_active": p.is_active,
        "tipo_vinculo": p.tipo_vinculo,
        "courier_id_cainiao": p.courier_id_cainiao or "",
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def pre_invoice_summary(pf):
    return {
        "id": pf.id,
        "numero": pf.numero,
        "periodo_inicio": (
            pf.periodo_inicio.isoformat() if pf.periodo_inicio else None
        ),
        "periodo_fim": pf.periodo_fim.isoformat() if pf.periodo_fim else None,
        "status": pf.status,
        "status_display": pf.get_status_display(),
        "total_a_receber": str(pf.total_a_receber),
        "data_pagamento": (
            pf.data_pagamento.isoformat() if pf.data_pagamento else None
        ),
    }


def pre_invoice_detail(pf):
    d = pre_invoice_summary(pf)
    d.update({
        "base_entregas": str(pf.base_entregas),
        "total_bonus": str(pf.total_bonus),
        "total_pudo": str(pf.total_pudo),
        "total_extras": str(pf.total_extras),
        "total_pacotes_perdidos": str(pf.total_pacotes_perdidos),
        "total_adiantamentos": str(pf.total_adiantamentos),
        "referencia_pagamento": pf.referencia_pagamento or "",
    })
    return d


def claim_dict(c):
    situacao = None
    try:
        situacao = c.situacao
    except Exception:  # noqa: BLE001 — propriedade defensiva
        situacao = None
    return {
        "id": c.id,
        "claim_type": c.claim_type,
        "claim_type_display": c.get_claim_type_display(),
        "status": c.status,
        "status_display": c.get_status_display(),
        "amount": str(c.amount),
        "waybill_number": c.waybill_number or "",
        "description": c.description or "",
        "occurred_at": c.occurred_at.isoformat() if c.occurred_at else None,
        "operation_task_date": (
            c.operation_task_date.isoformat() if c.operation_task_date else None
        ),
        "situacao": situacao,
    }
