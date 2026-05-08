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


def _get_ocr_settings():
    """Resolve config OCR: prefere SystemConfiguration (DB), fallback ao
    settings (env vars). Permite ao operador configurar via UI sem editar
    .env e reiniciar.
    """
    try:
        from system_config.models import SystemConfiguration
        cfg = SystemConfiguration.get_config()
    except Exception:
        cfg = None

    def _pick(db_val, env_val):
        return db_val if (db_val or "").strip() else env_val

    if cfg:
        provider = _pick(cfg.ocr_provider, settings.OCR_PROVIDER)
        anthropic_key = _pick(
            cfg.ocr_anthropic_api_key, settings.ANTHROPIC_API_KEY,
        )
        anthropic_model = _pick(
            cfg.ocr_anthropic_model, settings.ANTHROPIC_OCR_MODEL,
        )
        gemini_key = _pick(
            cfg.ocr_gemini_api_key, settings.GEMINI_API_KEY,
        )
        gemini_model = _pick(
            cfg.ocr_gemini_model, settings.GEMINI_OCR_MODEL,
        )
    else:
        provider = settings.OCR_PROVIDER
        anthropic_key = settings.ANTHROPIC_API_KEY
        anthropic_model = settings.ANTHROPIC_OCR_MODEL
        gemini_key = settings.GEMINI_API_KEY
        gemini_model = settings.GEMINI_OCR_MODEL

    return {
        "provider": (provider or "gemini").lower(),
        "anthropic_key": anthropic_key,
        "anthropic_model": anthropic_model or "claude-sonnet-4-6",
        "gemini_key": gemini_key,
        "gemini_model": gemini_model or "gemini-2.5-flash",
    }


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
  "category_hint": "categoria curta em PT, ex: 'Combustível', 'Peças e Manutenção', 'Renda', 'Internet/Telecom', 'Eletricidade', 'Água', 'Honorários', 'Material de Escritório', 'Limpeza', 'Seguros', 'Imposto'",
  "category_keywords": "1-3 palavras-chave dos produtos/serviços facturados, ex: 'gasóleo abastecimento', 'pneus alinhamento', 'fibra 1Gbps'",
  "payment_method": "um de: CASH | CARD | MULTIBANCO | TRANSFER | OTHER (ver guia abaixo)",
  "card_last4": "4 dígitos finais do cartão se aparecerem (ex: '9113'); '' se não",
  "confidence": "low | medium | high"
}

Regras estritas:
- Usa "" (string vazia) se um campo não estiver legível.
- Datas SEMPRE em formato ISO YYYY-MM-DD.
- Valores SEMPRE com ponto decimal (não vírgula).
- NIF SEM espaços nem prefixo "PT".
- supplier_name é o emissor da factura (não o cliente).
- category_hint deve refletir o TIPO DE DESPESA, não o nome do fornecedor.
  Analisa as descrições das linhas/produtos. Ex: factura da BP com gasóleo
  → "Combustível"; factura da MEO com fibra → "Internet/Telecom"; factura
  do mecânico com peças e mão de obra → "Peças e Manutenção".
- payment_method (string vazia se ilegível):
    * CARD       → "Visa", "Mastercard", "Maestro", "Cartão", "Tarjeta"
    * MULTIBANCO → "MB", "Multibanco", referência multibanco/entidade
    * CASH       → "Numerário", "Dinheiro", "Efectivo", "Cash"
    * TRANSFER   → "Transferência bancária", "TRF", "IBAN"
    * OTHER      → cheque ou método não identificável
- card_last4: SÓ DÍGITOS, exactamente 4. Procura padrões como
  "************9113", "VISA ...9113", "Confirmación 9113", "AUTH XXXX",
  ou similar. Se ambíguo (códigos de transacção que não sejam do cartão),
  deixa "".
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

    pm = (data.get("payment_method") or "").strip().upper()
    if pm not in ("CASH", "CARD", "MULTIBANCO", "TRANSFER", "OTHER"):
        pm = ""
    last4_raw = re.sub(r"\D", "", data.get("card_last4") or "")
    last4 = last4_raw[-4:] if len(last4_raw) >= 4 else ""

    return {
        "supplier_name": (data.get("supplier_name") or "").strip(),
        "supplier_nif": re.sub(r"\D", "", data.get("supplier_nif") or "")[:9],
        "invoice_number": (data.get("invoice_number") or "").strip(),
        "issue_date": (data.get("issue_date") or "").strip() or None,
        "amount_net": _dec(data.get("amount_net")),
        "iva_rate": _dec(data.get("iva_rate")),
        "amount_total": _dec(data.get("amount_total")),
        "category_hint": (data.get("category_hint") or "").strip(),
        "category_keywords": (data.get("category_keywords") or "").strip(),
        "payment_method": pm,
        "card_last4": last4,
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

def _extract_anthropic(file_obj, ocr_cfg=None) -> dict:
    cfg = ocr_cfg or _get_ocr_settings()
    if not cfg["anthropic_key"]:
        raise RuntimeError(
            "Anthropic API key não configurada (ver Configurações → "
            "Inteligência Artificial ou ANTHROPIC_API_KEY no .env)."
        )
    from anthropic import Anthropic
    client = Anthropic(api_key=cfg["anthropic_key"])
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
        model=cfg["anthropic_model"],
        max_tokens=1024,
        messages=[{"role": "user", "content": content}],
    )
    text = resp.content[0].text if resp.content else ""
    return _normalize_response(text)


# ── Provider: Google Gemini ─────────────────────────────────────────────

def _extract_gemini(file_obj, ocr_cfg=None) -> dict:
    cfg = ocr_cfg or _get_ocr_settings()
    if not cfg["gemini_key"]:
        raise RuntimeError(
            "Gemini API key não configurada (ver Configurações → "
            "Inteligência Artificial ou GEMINI_API_KEY no .env)."
        )
    import google.generativeai as genai
    genai.configure(api_key=cfg["gemini_key"])
    model = genai.GenerativeModel(cfg["gemini_model"])

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
      provider: 'anthropic' | 'gemini' | None (usa SystemConfiguration > settings).
    """
    cfg = _get_ocr_settings()
    chosen = (provider or cfg["provider"]).lower()
    if chosen == "anthropic":
        return _extract_anthropic(file_obj, ocr_cfg=cfg)
    if chosen == "gemini":
        return _extract_gemini(file_obj, ocr_cfg=cfg)
    raise ValueError(f"OCR provider desconhecido: {chosen}")
