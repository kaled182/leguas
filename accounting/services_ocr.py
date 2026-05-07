"""OCR de faturas: extrai estrutura JSON de uma factura/recibo PDF/imagem.

Suporta dois providers — escolhe via settings.OCR_PROVIDER:
  - 'anthropic': Claude Sonnet 4.6 com vision (pago, ~€0,005-0,01/factura)
  - 'gemini':    Gemini 2.0 Flash (free tier 1500 req/dia)

Ambos aceitam PDF e imagens nativamente. Devolve dict normalizado com:
  {
    "supplier_name": str,
    "supplier_nif": str,
    "invoice_number": str,
    "issue_date": "YYYY-MM-DD" | None,
    "amount_net": "123.45" | None,    # sem IVA
    "iva_rate": "23.00" | None,
    "amount_total": "151.84" | None,  # com IVA
    "raw_text": str,                  # primeiras linhas para debug
    "confidence": "low" | "medium" | "high",
  }
"""
import base64
import json
import logging
import re
from decimal import Decimal, InvalidOperation

from django.conf import settings

logger = logging.getLogger(__name__)


# Prompt único para ambos os providers.
_PROMPT = """És um assistente especializado em extracção de dados de
facturas e recibos portugueses. Analisa o documento anexado e devolve
EXCLUSIVAMENTE um objecto JSON (sem markdown, sem texto extra) com a
seguinte estrutura:

{
  "supplier_name": "nome ou razão social do fornecedor/emissor",
  "supplier_nif": "NIF do emissor (9 dígitos PT, sem espaços)",
  "invoice_number": "número da factura (ex: FT 2026/123)",
  "issue_date": "YYYY-MM-DD",
  "amount_net": "valor sem IVA com ponto decimal (ex: 123.45)",
  "iva_rate": "taxa IVA % (ex: 23.00 ou 6.00 ou 13.00)",
  "amount_total": "valor com IVA com ponto decimal (ex: 151.84)",
  "confidence": "low | medium | high"
}

Regras estritas:
- Usa "" (string vazia) se um campo não estiver legível.
- Datas SEMPRE em formato ISO YYYY-MM-DD.
- Valores SEMPRE com ponto decimal (não vírgula).
- NIF SEM espaços nem prefixo "PT".
- supplier_name é o emissor da factura (não o cliente).
- confidence: 'high' se conseguiste ler tudo claramente; 'medium' se
  alguns campos foram inferidos; 'low' se documento ilegível ou parcial.
- Não inventes dados — se um campo não está no documento, usa "".

Devolve APENAS o JSON. Nada de comentários, explicações ou markdown.
"""


def _normalize_response(raw_json: str) -> dict:
    """Tenta parsear JSON do modelo, faz limpeza defensiva."""
    # Remove markdown fences se o modelo não respeitou as instruções
    cleaned = raw_json.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("[ocr] JSON inválido recebido: %s", cleaned[:200])
        return {
            "supplier_name": "", "supplier_nif": "",
            "invoice_number": "", "issue_date": None,
            "amount_net": None, "iva_rate": None, "amount_total": None,
            "confidence": "low", "raw_text": cleaned[:300],
        }

    def _dec(v):
        if not v:
            return None
        try:
            return str(Decimal(str(v).replace(",", ".")))
        except (InvalidOperation, TypeError, ValueError):
            return None

    return {
        "supplier_name": (data.get("supplier_name") or "").strip(),
        "supplier_nif": re.sub(r"\D", "", data.get("supplier_nif") or "")[:9],
        "invoice_number": (data.get("invoice_number") or "").strip(),
        "issue_date": (data.get("issue_date") or "").strip() or None,
        "amount_net": _dec(data.get("amount_net")),
        "iva_rate": _dec(data.get("iva_rate")),
        "amount_total": _dec(data.get("amount_total")),
        "confidence": (data.get("confidence") or "low").lower(),
        "raw_text": "",
    }


def _read_file_b64(file_obj) -> tuple[str, str]:
    """Lê o ficheiro carregado e devolve (base64_str, media_type)."""
    file_obj.seek(0)
    raw = file_obj.read()
    file_obj.seek(0)
    name = (getattr(file_obj, "name", "") or "").lower()
    if name.endswith(".pdf"):
        media_type = "application/pdf"
    elif name.endswith(".png"):
        media_type = "image/png"
    elif name.endswith((".jpg", ".jpeg")):
        media_type = "image/jpeg"
    elif name.endswith(".webp"):
        media_type = "image/webp"
    else:
        # Tentar inferir por magic bytes
        if raw.startswith(b"%PDF"):
            media_type = "application/pdf"
        elif raw.startswith(b"\x89PNG"):
            media_type = "image/png"
        elif raw[:3] == b"\xff\xd8\xff":
            media_type = "image/jpeg"
        else:
            media_type = "application/pdf"  # fallback
    b64 = base64.b64encode(raw).decode("ascii")
    return b64, media_type


# ── Provider: Anthropic Claude ──────────────────────────────────────────

def _extract_anthropic(file_obj) -> dict:
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY não configurada.")
    from anthropic import Anthropic
    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    b64, media_type = _read_file_b64(file_obj)

    if media_type == "application/pdf":
        content = [
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": b64,
                },
            },
            {"type": "text", "text": _PROMPT},
        ]
    else:
        content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": b64,
                },
            },
            {"type": "text", "text": _PROMPT},
        ]

    resp = client.messages.create(
        model=settings.ANTHROPIC_OCR_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": content}],
    )
    text = resp.content[0].text if resp.content else ""
    return _normalize_response(text)


# ── Provider: Google Gemini ─────────────────────────────────────────────

def _extract_gemini(file_obj) -> dict:
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY não configurada.")
    import google.generativeai as genai
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(settings.GEMINI_OCR_MODEL)

    b64, media_type = _read_file_b64(file_obj)
    raw = base64.b64decode(b64)
    file_part = {"mime_type": media_type, "data": raw}

    resp = model.generate_content(
        [_PROMPT, file_part],
        generation_config={"temperature": 0.1, "response_mime_type": "application/json"},
    )
    return _normalize_response(resp.text or "")


# ── Entry point ─────────────────────────────────────────────────────────

def extract_invoice_data(file_obj, provider: str | None = None) -> dict:
    """Extrai dados estruturados de uma factura.

    Args:
      file_obj: ficheiro Django (request.FILES['file']).
      provider: 'anthropic' | 'gemini' | None (usa settings.OCR_PROVIDER).
    """
    provider = (provider or settings.OCR_PROVIDER or "gemini").lower()
    if provider == "anthropic":
        return _extract_anthropic(file_obj)
    if provider == "gemini":
        return _extract_gemini(file_obj)
    raise ValueError(f"OCR provider desconhecido: {provider}")
