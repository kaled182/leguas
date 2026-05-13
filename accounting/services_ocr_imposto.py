"""OCR de guias de pagamento de impostos (AT, Segurança Social, etc.).

Reutiliza a infra de providers (Anthropic/Gemini) e leitura de
ficheiros de `services_ocr.py`, mas com prompt dedicado para guias
de pagamento portuguesas — IVA, IRC, IRS Retenções, Segurança Social,
IUC, etc.

Schema devolvido:
{
  "tipo": "IVA | IRC | IRS_RETENCOES | IRS_DECLARACAO | SS | IUC | OUTRO",
  "designacao": str (ex: 'IVA Janeiro 2026', 'SS Fevereiro 2026'),
  "entidade_credora": "AT" | "SS" | str,
  "periodo_ano": int | None,
  "periodo_mes": int | None,  (1-12)
  "valor": "123.45" | None,
  "mb_entidade": str (5 dígitos),
  "mb_referencia": str (9 dígitos),
  "data_vencimento": "YYYY-MM-DD" | None,
  "confidence": "low|medium|high",
}
"""
import json
import logging
import re
from decimal import Decimal, InvalidOperation

from .services_ocr import _get_ocr_settings, _read_file_b64

logger = logging.getLogger(__name__)


_PROMPT_IMPOSTO = """És um assistente especializado em extracção de dados
de guias de pagamento de impostos portuguesas (Autoridade Tributária,
Segurança Social, IUC, planos de pagamento em prestações). Analisa o
documento anexado e devolve EXCLUSIVAMENTE um objecto JSON (sem
markdown, sem texto extra) com:

{
  "tipo": "um de: IVA | IRC | IRS_RETENCOES | IRS_DECLARACAO | SS | IUC | OUTRO",
  "designacao": "designação curta em PT — ver regras de designação abaixo",
  "entidade_credora": "AT (Autoridade Tributária) | SS (Segurança Social) | nome literal",
  "periodo_ano": "ano de referência (ex: 2026)",
  "periodo_mes": "mês 1-12 (mensal IVA/SS/IRS-Retenções); vazio anual/parcelado",
  "valor": "valor total a pagar nesta guia, ponto decimal (ex: 1234.56)",
  "mb_entidade": "código entidade MB (5 dígitos, ex: '10788' AT, '21810' SS)",
  "mb_referencia": "referência MB (9 dígitos, SEM espaços)",
  "data_vencimento": "data limite de pagamento YYYY-MM-DD",

  "numero_plano": "número do plano/processo (ex: '8482/2026', '8482.2026'); '' se não for plano em prestações",
  "parcela_numero": "número desta prestação (ex: 1, 2, 3); null se não aplicável",
  "parcela_total": "total de prestações no plano (ex: 12); null se não aplicável",
  "valor_capital": "componente capital/imposto (ponto decimal); null se não decomposto",
  "valor_juros": "componente juros de mora (ponto decimal); null se zero/não decomposto",
  "valor_outros": "outros encargos/custas (ponto decimal); null se não houver",

  "nif_contribuinte": "NIF do contribuinte/devedor (9 dígitos PT)",
  "nome_contribuinte": "razão social do contribuinte se visível",
  "documento_origem": "nº do documento de origem (liquidação, processo executivo, ex: 'LIQ 12345')",
  "iban_pagamento": "IBAN para pagamento bancário PT (ex: 'PT50 ...'); '' se só há MB",
  "data_emissao_guia": "data de emissão DESTA guia YYYY-MM-DD (≠ vencimento); '' se não distinguível",

  "confidence": "low | medium | high"
}

Regras estritas:
- Usa "" para strings vazias e null para numéricos/datas ausentes.
- Datas em ISO YYYY-MM-DD.
- Valores com ponto decimal (não vírgula).
- mb_entidade e mb_referencia SÓ DÍGITOS, sem espaços nem hífenes.
- nif_contribuinte: 9 dígitos PT, sem espaços nem prefixo 'PT'.
- iban_pagamento: mantém formato com espaços (ex: 'PT50 0036 ...').
- numero_plano: preserva separador original ('8482/2026' ou '8482.2026').

Mapeamento do tipo (case-insensitive):
- IVA: "IVA", "Imposto sobre o Valor Acrescentado", declaração periódica.
- IRC: "IRC", "pagamento por conta", Modelo 22.
- IRS_RETENCOES: "Retenção na Fonte", "Retenções", guia mensal cat. A/B/F.
- IRS_DECLARACAO: declaração anual de IRS — Modelo 3.
- SS: "Segurança Social", "Contribuições", "TSU", "IGFSS".
- IUC: "IUC", "Imposto Único de Circulação", referência a matrícula.
- OUTRO: dívidas executivas mistas ou outros impostos. Para PLANOS DE
  PAGAMENTO de execuções fiscais (sem tipo claro), usa o tipo do imposto
  original quando indicado; se misto, OUTRO.

Reconhecimento de entidade:
- Autoridade Tributária e Aduaneira → entidade_credora="AT".
- Instituto da Segurança Social / IGFSS → entidade_credora="SS".
- Outro nome literal se diferente.

Designação sugerida (português):
- IVA mensal: 'IVA <Mês por extenso> <Ano>' (ex: 'IVA Janeiro 2026')
- IVA trimestral: 'IVA <Trim> <Ano>' (ex: 'IVA 1T 2026')
- SS mensal: 'SS <Mês> <Ano>'
- IRS Retenções mensal: 'IRS Retenções <Mês> <Ano>'
- IRC: 'IRC <Ano> — <descrição>' (ex: 'IRC 2024 — 1º PPC')
- IUC: 'IUC <matrícula se visível> <ano>'
- PLANO em prestações: 'Plano <numero_plano> — Prestação <X>/<Y>'
  (ex: 'Plano 8482/2026 — Prestação 1/12'). Se há tipo identificável,
  prefixa: 'IVA · Plano 8482/2026 — Prestação 1/12'.

Confidence:
- 'high': todos os campos críticos (tipo, valor, mb_referencia,
  data_vencimento) legíveis claramente.
- 'medium': falta um ou dois campos não críticos.
- 'low': documento ilegível ou parcial.

Não inventes dados. Devolve APENAS o JSON.
"""


_VALID_TIPOS = {
    "IVA", "IRC", "IRS_RETENCOES", "IRS_DECLARACAO",
    "SS", "IUC", "OUTRO",
}


def _normalize_imposto_response(raw_json: str) -> dict:
    """Parse JSON com fallback defensivo."""
    cleaned = (raw_json or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        logger.warning("[ocr-imposto] JSON inválido: %s", cleaned[:200])
        return {
            "tipo": "", "designacao": "", "entidade_credora": "",
            "periodo_ano": None, "periodo_mes": None, "valor": None,
            "mb_entidade": "", "mb_referencia": "",
            "data_vencimento": None,
            "numero_plano": "", "parcela_numero": None,
            "parcela_total": None,
            "valor_capital": None, "valor_juros": None,
            "valor_outros": None,
            "nif_contribuinte": "", "nome_contribuinte": "",
            "documento_origem": "", "iban_pagamento": "",
            "data_emissao_guia": None,
            "confidence": "low",
        }

    def _s(v):
        return (v or "").strip() if isinstance(v, str) else ""

    def _int(v, lo=None, hi=None):
        if v in (None, ""):
            return None
        try:
            n = int(float(str(v)))
            if lo is not None and n < lo:
                return None
            if hi is not None and n > hi:
                return None
            return n
        except (TypeError, ValueError):
            return None

    def _dec(v):
        if v in (None, ""):
            return None
        try:
            return str(Decimal(str(v).replace(",", ".")))
        except (InvalidOperation, TypeError, ValueError):
            return None

    tipo = _s(data.get("tipo")).upper()
    if tipo not in _VALID_TIPOS:
        tipo = ""

    # Normaliza numero_plano (preserva separador / ou .)
    numero_plano_raw = _s(data.get("numero_plano"))
    numero_plano = re.sub(r"[^\d./-]", "", numero_plano_raw)[:32]

    # IBAN: normaliza espaços
    iban_raw = _s(data.get("iban_pagamento")).upper()
    iban_clean = re.sub(r"\s+", " ", iban_raw).strip()

    return {
        "tipo": tipo,
        "designacao": _s(data.get("designacao")),
        "entidade_credora": _s(data.get("entidade_credora")),
        "periodo_ano": _int(data.get("periodo_ano"), lo=2000, hi=2100),
        "periodo_mes": _int(data.get("periodo_mes"), lo=1, hi=12),
        "valor": _dec(data.get("valor")),
        "mb_entidade": re.sub(
            r"\D", "", _s(data.get("mb_entidade")),
        )[:5],
        "mb_referencia": re.sub(
            r"\D", "", _s(data.get("mb_referencia")),
        )[:9],
        "data_vencimento": _s(data.get("data_vencimento")) or None,
        # ── Campos extra (parcelamento, decomposição, contribuinte) ──
        "numero_plano": numero_plano,
        "parcela_numero": _int(data.get("parcela_numero"), lo=1, hi=999),
        "parcela_total": _int(data.get("parcela_total"), lo=1, hi=999),
        "valor_capital": _dec(data.get("valor_capital")),
        "valor_juros": _dec(data.get("valor_juros")),
        "valor_outros": _dec(data.get("valor_outros")),
        "nif_contribuinte": re.sub(
            r"\D", "", _s(data.get("nif_contribuinte")),
        )[:9],
        "nome_contribuinte": _s(data.get("nome_contribuinte")),
        "documento_origem": _s(data.get("documento_origem")),
        "iban_pagamento": iban_clean,
        "data_emissao_guia": _s(data.get("data_emissao_guia")) or None,
        "confidence": _s(data.get("confidence")).lower() or "low",
    }


def _extract_anthropic(file_obj, ocr_cfg):
    if not ocr_cfg["anthropic_key"]:
        raise RuntimeError("Anthropic API key não configurada.")
    import base64  # noqa: F401  (base64 não é usado mas mantém paridade)
    from anthropic import Anthropic
    client = Anthropic(api_key=ocr_cfg["anthropic_key"])
    b64, media_type = _read_file_b64(file_obj)
    if media_type == "application/pdf":
        content = [
            {"type": "document", "source": {
                "type": "base64", "media_type": "application/pdf", "data": b64,
            }},
            {"type": "text", "text": _PROMPT_IMPOSTO},
        ]
    else:
        content = [
            {"type": "image", "source": {
                "type": "base64", "media_type": media_type, "data": b64,
            }},
            {"type": "text", "text": _PROMPT_IMPOSTO},
        ]
    resp = client.messages.create(
        model=ocr_cfg["anthropic_model"],
        max_tokens=1024,
        messages=[{"role": "user", "content": content}],
    )
    text = resp.content[0].text if resp.content else ""
    return _normalize_imposto_response(text)


def _extract_gemini(file_obj, ocr_cfg):
    if not ocr_cfg["gemini_key"]:
        raise RuntimeError("Gemini API key não configurada.")
    import base64
    import google.generativeai as genai
    genai.configure(api_key=ocr_cfg["gemini_key"])
    model = genai.GenerativeModel(ocr_cfg["gemini_model"])
    b64, media_type = _read_file_b64(file_obj)
    raw = base64.b64decode(b64)
    file_part = {"mime_type": media_type, "data": raw}
    resp = model.generate_content(
        [_PROMPT_IMPOSTO, file_part],
        generation_config={
            "temperature": 0.1,
            "response_mime_type": "application/json",
        },
    )
    return _normalize_imposto_response(resp.text or "")


def extract_imposto_data(file_obj, provider: str | None = None) -> dict:
    """Extrai dados de uma guia de pagamento de imposto."""
    cfg = _get_ocr_settings()
    chosen = (provider or cfg["provider"]).lower()
    if chosen == "anthropic":
        return _extract_anthropic(file_obj, cfg)
    if chosen == "gemini":
        return _extract_gemini(file_obj, cfg)
    raise ValueError(f"OCR provider desconhecido: {chosen}")
