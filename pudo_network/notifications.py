"""Notificações da Rede PUDO (best-effort, nunca bloqueiam transições).

Reutiliza a infra WhatsApp já usada nos OTP/lembretes
(`system_config.whatsapp_helper`). Qualquer falha é engolida pelo chamador.
"""


def notify_client_arrived(package):
    """Avisa o cliente final que o pacote chegou ao PUDO e pode levantar.

    Fase 1: o número/nome do cliente vem do `payload` da transação ou do
    soft-link do pacote. Enquanto não houver contacto do destinatário
    modelado, esta função é um no-op silencioso — o gancho fica pronto.
    """
    phone = _client_phone(package)
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
    """Extrai o telefone do cliente das transações do pacote, se existir."""
    txn = package.transactions.exclude(payload={}).order_by("-synced_at").first()
    if txn and isinstance(txn.payload, dict):
        for key in ("client_phone", "telefone_cliente", "phone"):
            val = (txn.payload.get(key) or "").strip()
            if val:
                return val
    return ""
