"""Serviço partilhado de OTP de login do motorista (telemóvel + WhatsApp).

Fonte única de verdade usada tanto pelo login web (sessão) como pela
camada da app (token). Os chamadores tratam o efeito (sessão vs token) e a
serialização; aqui fica a resolução por número, o anti-spam, o envio e a
verificação do código.
"""
import re
from datetime import timedelta

from django.utils import timezone

from customauth.models import DriverLoginOTP
from drivers_app.models import DriverProfile


class OTPError(Exception):
    """Erro amigável de OTP, com código HTTP sugerido."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def normalize_phone(raw):
    """Mantém apenas os dígitos do número."""
    return re.sub(r"\D", "", raw or "")


def mask_phone(phone):
    """Mascara o número (ex.: ••• ••• 678)."""
    d = normalize_phone(phone)
    if len(d) <= 3:
        return "•••"
    return "••• ••• " + d[-3:]


def resolve_driver_by_phone(raw_phone):
    """Encontra um DriverProfile pelo telefone (match pelos últimos 9
    dígitos, robusto a +351/formatação). Levanta OTPError se falhar."""
    digits = normalize_phone(raw_phone)
    if len(digits) < 9:
        raise OTPError("Número de telemóvel inválido.")
    tail = digits[-9:]
    candidatos = DriverProfile.objects.filter(telefone__endswith=tail)
    matches = [
        p for p in candidatos
        if normalize_phone(p.telefone).endswith(tail)
    ]
    if not matches:
        raise OTPError("Não encontrámos nenhum motorista com este número.")
    if len(matches) > 1:
        exatos = [p for p in matches if normalize_phone(p.telefone) == digits]
        if len(exatos) == 1:
            return exatos[0]
        raise OTPError(
            "Vários motoristas com este número. Usa username e password."
        )
    return matches[0]


def send_otp(profile):
    """Gera e envia um código OTP por WhatsApp para o telefone do perfil.

    Aplica anti-spam (1 código/60 s) e invalida códigos anteriores não
    usados. Devolve o número mascarado. Levanta OTPError em falha.
    """
    if not (profile.telefone or "").strip():
        raise OTPError("Motorista sem telefone registado.")

    recente = DriverLoginOTP.objects.filter(
        driver_profile=profile,
        created_at__gte=timezone.now() - timedelta(seconds=60),
    ).exists()
    if recente:
        raise OTPError(
            "Já enviámos um código há instantes. Aguarda um pouco.",
            status=429,
        )

    # invalida códigos anteriores ainda não usados (garante 1 ativo)
    DriverLoginOTP.objects.filter(
        driver_profile=profile, used_at__isnull=True,
    ).update(used_at=timezone.now())

    code = DriverLoginOTP.generate_code()
    otp = DriverLoginOTP.objects.create(
        driver_profile=profile,
        phone=profile.telefone,
        code=code,
        expires_at=timezone.now() + timedelta(minutes=5),
    )

    try:
        from system_config.whatsapp_helper import (
            WhatsAppWPPConnectAPI,
            to_whatsapp_number,
        )
        api = WhatsAppWPPConnectAPI.from_config()
        nome = (profile.nome_completo or profile.apelido or "").split(" ")[0]
        saudacao = f"Olá {nome}! " if nome else "Olá! "
        msg = (
            f"{saudacao}O teu código de acesso ao Portal do Motorista é:\n\n"
            f"*{code}*\n\n"
            f"Válido por 5 minutos. Não partilhes este código com ninguém."
        )
        api.send_text_reliable(
            to_whatsapp_number(profile.telefone),
            msg,
            filename="Codigo-de-acesso.pdf",
        )
    except Exception as exc:  # noqa: BLE001 — erro amigável
        otp.delete()
        raise OTPError(
            f"Não foi possível enviar o código por WhatsApp: {exc}",
            status=502,
        )

    return mask_phone(profile.telefone)


def verify_otp(profile, code):
    """Valida o código OTP do motorista. Marca-o como usado em caso de
    sucesso e devolve o objeto. Levanta OTPError em falha."""
    code = (code or "").strip()
    if not code:
        raise OTPError("Indica o código recebido.")

    otp = DriverLoginOTP.objects.filter(
        driver_profile=profile, used_at__isnull=True,
    ).order_by("-created_at").first()
    if not otp or otp.is_expired:
        raise OTPError("Código expirado. Pede um novo.")
    if otp.attempts >= DriverLoginOTP.MAX_ATTEMPTS:
        raise OTPError(
            "Demasiadas tentativas. Pede um novo código.", status=429,
        )

    if otp.code != code:
        otp.attempts += 1
        otp.save(update_fields=["attempts"])
        restantes = max(0, DriverLoginOTP.MAX_ATTEMPTS - otp.attempts)
        raise OTPError(
            f"Código incorreto. {restantes} tentativa(s) restante(s)."
        )

    otp.used_at = timezone.now()
    otp.save(update_fields=["used_at"])
    return otp
