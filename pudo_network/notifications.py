"""Notificações da Rede PUDO (best-effort, nunca bloqueiam transições).

Reutiliza a infra WhatsApp já usada nos OTP/lembretes
(`system_config.whatsapp_helper`). Qualquer falha é engolida pelo chamador.
"""


def notify_client_arrived(package):
    """Avisa o cliente final que o pacote chegou ao PUDO e pode levantar.

    Corre após o commit do handshake. O contacto vem do campo
    `cliente_telefone` do pacote ou do `payload` das transações. Sem contacto,
    é um no-op silencioso.
    """
    phone = (package.cliente_telefone or "").strip() or _client_phone(package)
    if not phone:
        return  # sem contacto do cliente ainda → gancho preparado, no-op

    from system_config.whatsapp_helper import (
        WhatsAppWPPConnectAPI,
        to_whatsapp_number,
    )

    api = WhatsAppWPPConnectAPI.from_config()
    msg = (
        f"Olá! A sua encomenda ({package.tracking_ref}) já está disponível "
        f"para levantamento no ponto {package.store.numero} — "
        f"{package.store.nome}."
    )
    if package.store.morada:
        msg += f"\nMorada: {package.store.morada}"
    api.send_text_reliable(to_whatsapp_number(phone), msg)


def _client_phone(package):
    """Extrai o telefone do cliente das transações do pacote, se existir.

    Itera em Python (evita comparações JSON tipo `exclude(payload={})` que
    podem falhar em MySQL).
    """
    for txn in package.transactions.order_by("-synced_at"):
        payload = txn.payload
        if isinstance(payload, dict):
            for key in ("client_phone", "telefone_cliente", "phone"):
                val = (payload.get(key) or "").strip()
                if val:
                    return val
    return ""
