"""Construtores de dicts JSON para a API da app (campos reais dos modelos)."""


def _profile_username(profile):
    access = getattr(profile, "access", None)
    if access and access.username:
        return access.username
    if profile.email:
        return profile.email
    return profile.telefone or f"driver-{profile.id}"


def _profile_name_parts(profile):
    access = getattr(profile, "access", None)
    if access:
        first = (access.first_name or "").strip()
        last = (access.last_name or "").strip()
        if first or last:
            return first, last

    full = (profile.nome_completo or "").strip()
    if not full:
        return "", ""
    parts = full.split(" ", 1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def driver_dict(p):
    access = getattr(p, "access", None)
    linked_user = getattr(access, "user", None)
    first_name, last_name = _profile_name_parts(p)
    return {
        "id": p.id,
        "username": _profile_username(p),
        "first_name": first_name,
        "last_name": last_name,
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
        "is_staff": bool(linked_user and linked_user.is_staff),
        "is_superuser": bool(linked_user and linked_user.is_superuser),
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


def incidence_dict(incidence):
    profile = incidence.driver_profile
    first_name, last_name = _profile_name_parts(profile)
    image_url = ""
    if incidence.package_image:
        try:
            image_url = incidence.package_image.url
        except Exception:  # noqa: BLE001
            image_url = str(incidence.package_image)

    return {
        "id": incidence.id,
        "user_id": profile.id,
        "user_username": _profile_username(profile),
        "user_first_name": first_name,
        "user_last_name": last_name,
        "barcode": incidence.barcode,
        "tracking_number": incidence.tracking_number,
        "client_name": incidence.client_name,
        "address": incidence.address,
        "latitude": str(incidence.latitude),
        "longitude": str(incidence.longitude),
        "package_image": image_url,
        "scanned_at": incidence.scanned_at.isoformat() if incidence.scanned_at else None,
        "updated_at": incidence.updated_at.isoformat() if incidence.updated_at else None,
        "ocr_data": incidence.ocr_data,
        "zone": incidence.zone,
    }


def driver_option_dict(profile):
    first_name, last_name = _profile_name_parts(profile)
    return {
        "id": profile.id,
        "username": _profile_username(profile),
        "first_name": first_name,
        "last_name": last_name,
    }
