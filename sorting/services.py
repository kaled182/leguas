"""Lógica do Sorting: resolve cada pacote lido (scan) para a bigbag certa.

Reutiliza o motor de triagem das geozonas (`resolver_triagem`) que, a partir
de um waybill, devolve o código postal e a zona desenhada (com motorista).
"""
from .models import SortingBigbag, SortingParcel, SortingSession


def _get_or_create_bigbag(session, cp4, zona_obj):
    """Bigbag de (sessão, cp4, zona). Cria com motorista auto da zona."""
    bigbag, created = SortingBigbag.objects.get_or_create(
        session=session, cp4=cp4, zona=zona_obj,
    )
    if created:
        zona_nome = zona_obj.nome if zona_obj else ""
        codigo = f"BB-{session.id}-{cp4 or 'XX'}"
        if zona_obj:
            codigo += f"-{zona_obj.codigo}"
        bigbag.zona_nome = zona_nome
        bigbag.codigo = codigo
        # Motorista automático pela geozona (editável depois)
        if zona_obj and zona_obj.motorista_default_id:
            bigbag.driver = zona_obj.motorista_default
        bigbag.save(update_fields=["zona_nome", "codigo", "driver"])
    return bigbag, created


def scan_parcel(session, waybill, user=None):
    """Lê um pacote para a sessão. Resolve CP/zona e coloca na bigbag.

    Devolve dict: {status, message, parcel, bigbag, created_bigbag}.
    status: OK | DUP | UNRESOLVED.
    """
    from geozonas.models import ZonaGeo
    from geozonas.services.triagem import resolver_triagem

    wb = (waybill or "").strip().upper()
    if not wb:
        return {"status": "ERROR", "message": "Waybill vazio."}

    # Anti-duplicado dentro da MESMA sessão
    dup = SortingParcel.objects.filter(
        session=session, waybill_number=wb,
    ).select_related("bigbag").first()
    if dup:
        return {
            "status": "DUP",
            "message": f"Já lido nesta sessão ({dup.zona_nome or dup.cp4 or '—'}).",
            "parcel": parcel_to_dict(dup),
            "bigbag": bigbag_to_dict(dup.bigbag) if dup.bigbag else None,
            "created_bigbag": False,
        }

    res = resolver_triagem(wb)
    cp = (res.get("cp") or "").strip()
    cp4 = cp[:4] if cp else ""
    localidade = res.get("localidade") or ""
    zona = res.get("zona")  # dict {id,nome,cor,motorista} ou None

    # Dados do destinatário (para a folha do motorista)
    cust = _customer_data(wb)

    # Sem CP → não classificado (divergência)
    if not cp4:
        parcel = SortingParcel.objects.create(
            session=session, waybill_number=wb,
            localidade=localidade,
            nome_cliente=cust["nome"], telefone_cliente=cust["telefone"],
            morada=cust["morada"],
            status=SortingParcel.STATUS_UNRESOLVED,
            note="Sem CP/zona resolvida", scanned_by=user,
        )
        return {
            "status": "UNRESOLVED", "sound": "unknown",
            "message": "Não foi possível resolver o CP deste pacote.",
            "parcel": parcel_to_dict(parcel),
            "bigbag": None, "created_bigbag": False,
        }

    # Determina a zona (apenas no modo Geozona)
    zona_obj = None
    if session.mode == SortingSession.MODE_ZONA and zona and zona.get("id"):
        zona_obj = (
            ZonaGeo.objects.filter(id=zona["id"])
            .select_related("motorista_default").first()
        )

    # Divergência: fora dos CP4 alvo (se definidos)
    targets = _target_set(session)
    divergent = bool(targets) and cp4 not in targets

    bigbag, created = _get_or_create_bigbag(session, cp4, zona_obj)

    parcel = SortingParcel.objects.create(
        session=session, bigbag=bigbag, waybill_number=wb,
        cp=cp, cp4=cp4, zona_nome=(zona_obj.nome if zona_obj else ""),
        localidade=localidade,
        nome_cliente=cust["nome"], telefone_cliente=cust["telefone"],
        morada=cust["morada"],
        status=SortingParcel.STATUS_OK, divergent=divergent,
        scanned_by=user,
    )
    return {
        "status": "OK",
        "sound": "wrong" if divergent else "ok",
        "divergent": divergent,
        "message": (
            f"CP {cp4} fora dos alvos da sessão." if divergent
            else "Classificado."
        ),
        "parcel": parcel_to_dict(parcel),
        "bigbag": bigbag_to_dict(bigbag),
        "created_bigbag": created,
    }


def _target_set(session):
    """Conjunto de CP4 alvo da sessão (normalizados)."""
    raw = (session.target_cps or "").replace(";", ",")
    return {c.strip()[:4] for c in raw.split(",") if c.strip()}


def _customer_data(waybill):
    """Nome/telefone/morada do destinatário (reutiliza o lookup dos tickets)."""
    try:
        from drivers_app.services_ticket_import import lookup_customer_data
        d = lookup_customer_data(waybill)
        return {
            "nome": (d.get("nome_cliente") or "")[:200],
            "telefone": (d.get("telefone_cliente") or "")[:40],
            "morada": (d.get("morada") or "")[:255],
        }
    except Exception:
        return {"nome": "", "telefone": "", "morada": ""}


# ─────────────────────────────────────────────────────────────────────────
# Serialização
# ─────────────────────────────────────────────────────────────────────────
def parcel_to_dict(p):
    return {
        "id": p.id,
        "waybill_number": p.waybill_number,
        "cp": p.cp,
        "cp4": p.cp4,
        "zona_nome": p.zona_nome,
        "localidade": p.localidade,
        "nome_cliente": p.nome_cliente,
        "telefone_cliente": p.telefone_cliente,
        "morada": p.morada,
        "status": p.status,
        "divergent": p.divergent,
        "bigbag_id": p.bigbag_id,
        "scanned_at": p.scanned_at.isoformat() if p.scanned_at else None,
    }


def bigbag_to_dict(b):
    return {
        "id": b.id,
        "cp4": b.cp4,
        "zona_nome": b.zona_nome,
        "codigo": b.codigo,
        "label": b.label,
        "driver_id": b.driver_id,
        "driver_nome": b.driver.nome_completo if b.driver else "",
        "observacao": b.observacao,
        "parcel_count": b.parcels.count(),
    }


def bigbag_cp7_list(bigbag):
    """CP7 (código postal completo) distintos dentro da bigbag — para a
    etiqueta de fecho (estilo Cainiao 'Zip Code')."""
    cps = (
        bigbag.parcels.exclude(cp="")
        .values_list("cp", flat=True).distinct().order_by("cp")
    )
    return list(cps)


def session_summary(session):
    """Estrutura completa da sessão: bigbags (com contagem) + não
    classificados. Usado na página e no fecho."""
    bigbags = (
        session.bigbags.select_related("driver", "zona")
        .prefetch_related("parcels")
    )
    out_bigbags = []
    for b in bigbags:
        d = bigbag_to_dict(b)
        out_bigbags.append(d)

    unresolved = session.parcels.filter(
        status=SortingParcel.STATUS_UNRESOLVED,
    )
    total = session.parcels.count()
    return {
        "session": {
            "id": session.id,
            "nome": session.nome,
            "hub": session.hub,
            "mode": session.mode,
            "mode_display": session.get_mode_display(),
            "status": session.status,
            "status_display": session.get_status_display(),
            "observacao": session.observacao,
            "created_at": (
                session.created_at.isoformat() if session.created_at else None
            ),
            "finished_at": (
                session.finished_at.isoformat() if session.finished_at else None
            ),
            "total_parcels": total,
            "n_bigbags": len(out_bigbags),
            "n_unresolved": unresolved.count(),
        },
        "bigbags": out_bigbags,
        "unresolved": [parcel_to_dict(p) for p in unresolved],
    }
