"""OCR de tickets de reclamação Cainiao (Exception Details).

Reutiliza a infra de providers (Anthropic/Gemini) e leitura de
ficheiros de `accounting/services_ocr.py`, mas com prompt e schema
dedicados aos tickets de exception da plataforma Cainiao.

Devolve dict normalizado:
{
  "tracking_number": str,
  "exception_id": str,
  "exception_name": str,
  "description": str,
  "delivery_driver": str,
  "partner_status": str,
  "deadline": "YYYY-MM-DD HH:MM:SS" | None,
  "submission_role": str,
  "submission_source": str,
  "submitter": str,
  "dsp": str,
  "status": str,
  "receiver_name": str,
  "receiver_phone": str,
  "receiver_email": str,
  "remark": str,
  "processing_history": [
    {"time": "YYYY-MM-DD HH:MM:SS", "action": str, "content": str, "update_person": str},
    ...
  ],
  "confidence": "low|medium|high",
}
"""
import json
import logging
import re

from accounting.services_ocr import (
    _get_ocr_settings,
    _read_file_b64,
)

logger = logging.getLogger(__name__)


_PROMPT_TICKET = """És um assistente especializado em extracção de dados
de tickets de reclamação/exception da plataforma Cainiao (logística).
Analisa o documento anexado (print ou PDF do "Exception Details") e
devolve EXCLUSIVAMENTE um objecto JSON (sem markdown, sem texto extra)
com a seguinte estrutura:

{
  "tracking_number": "número de tracking/waybill (ex: CNPRT49807411234006462118 ou LP88020...)",
  "exception_id": "ID do exception/ticket (numérico, ex: 380818032)",
  "exception_name": "nome do tipo de exceção (ex: Potentially lost, Multiple customer complaints, Fake delivery)",
  "description": "campo Description — o relato do problema",
  "delivery_driver": "nome do motorista (Delivery Driver, ex: JorgeFernandes_LF) — '' se for SYSTEM ou não legível",
  "partner_status": "campo Partner Status (ex: Processed, init, Waiting for processing)",
  "deadline": "campo Deadline em formato 'YYYY-MM-DD HH:MM:SS' se houver; '' se não",
  "submission_role": "campo Submission role (ex: Customer Service Report)",
  "submission_source": "campo Submission source (ex: Customer Service System)",
  "submitter": "campo Submitter (numérico/ID)",
  "dsp": "campo DSP (ex: LEGUAS FRANZINAS - UNIPESSOAL LDA)",
  "status": "campo Status (ex: Waiting for processing, Processed)",
  "receiver_name": "Receiver's name — pode estar mascarado (ex: '******'); devolve mesmo assim ou ''",
  "receiver_phone": "Receiver's tel number — pode estar mascarado",
  "receiver_email": "Receiver's Email — pode estar mascarado (ex: '***@***.com')",
  "remark": "campo Remark se houver",
  "processing_history": [
    {
      "time": "YYYY-MM-DD HH:MM:SS",
      "action": "tipo de acção (ex: Exception Task Created, Processed, Customer Service Judgement done)",
      "content": "texto da coluna Content",
      "update_person": "ID/nome da pessoa que fez a acção"
    }
  ],
  "confidence": "low | medium | high"
}

Regras estritas:
- Usa "" (string vazia) se um campo não estiver legível ou ausente.
- Datas/horas em formato 'YYYY-MM-DD HH:MM:SS' (24h).
- Mantém os textos originais — NÃO traduzas o description nem o content.
- Se receiver_name/phone/email estão mascarados com '*' ou '***',
  devolve EXACTAMENTE como aparecem (preservar mascaramento).
- processing_history é um array (pode estar vazio []). Inclui TODAS as
  linhas da tabela "Processing Information" do ticket, da mais antiga
  à mais recente (a ordem que aparece no print serve).
- tracking_number normalmente começa por 'CNPRT' (cadastro) ou 'LP88...'
  (waybill da operação). Devolve o valor exacto do documento.
- exception_id é só dígitos.
- confidence: 'high' se conseguiste ler todos os campos principais;
  'medium' se alguns estavam mascarados/parciais; 'low' se documento
  ilegível ou parcial.
- Não inventes dados — se um campo não está no documento, usa "".

Devolve APENAS o JSON. Nada de comentários, explicações ou markdown.
"""


def _normalize_ticket_response(raw_json: str) -> dict:
    """Parse JSON com fallback defensivo."""
    cleaned = (raw_json or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        logger.warning("[ocr-complaint] JSON inválido: %s", cleaned[:200])
        return {
            "tracking_number": "", "exception_id": "",
            "exception_name": "", "description": "",
            "delivery_driver": "", "partner_status": "",
            "deadline": "", "submission_role": "",
            "submission_source": "", "submitter": "", "dsp": "",
            "status": "", "receiver_name": "", "receiver_phone": "",
            "receiver_email": "", "remark": "",
            "processing_history": [],
            "confidence": "low",
        }

    # Normalizar campos
    def _s(v):
        return (v or "").strip() if isinstance(v, str) else ""

    history_raw = data.get("processing_history") or []
    history = []
    if isinstance(history_raw, list):
        for h in history_raw:
            if isinstance(h, dict):
                history.append({
                    "time": _s(h.get("time")),
                    "action": _s(h.get("action")),
                    "content": _s(h.get("content")),
                    "update_person": _s(h.get("update_person")),
                })

    return {
        "tracking_number": _s(data.get("tracking_number")),
        "exception_id": re.sub(r"\D", "", _s(data.get("exception_id"))),
        "exception_name": _s(data.get("exception_name")),
        "description": _s(data.get("description")),
        "delivery_driver": _s(data.get("delivery_driver")),
        "partner_status": _s(data.get("partner_status")),
        "deadline": _s(data.get("deadline")),
        "submission_role": _s(data.get("submission_role")),
        "submission_source": _s(data.get("submission_source")),
        "submitter": _s(data.get("submitter")),
        "dsp": _s(data.get("dsp")),
        "status": _s(data.get("status")),
        "receiver_name": _s(data.get("receiver_name")),
        "receiver_phone": _s(data.get("receiver_phone")),
        "receiver_email": _s(data.get("receiver_email")),
        "remark": _s(data.get("remark")),
        "processing_history": history,
        "confidence": _s(data.get("confidence")).lower() or "low",
    }


def _extract_anthropic(file_obj, ocr_cfg):
    if not ocr_cfg["anthropic_key"]:
        raise RuntimeError("Anthropic API key não configurada.")
    from anthropic import Anthropic
    import base64
    client = Anthropic(api_key=ocr_cfg["anthropic_key"])
    b64, media_type = _read_file_b64(file_obj)
    if media_type == "application/pdf":
        content = [
            {"type": "document", "source": {
                "type": "base64", "media_type": "application/pdf", "data": b64,
            }},
            {"type": "text", "text": _PROMPT_TICKET},
        ]
    else:
        content = [
            {"type": "image", "source": {
                "type": "base64", "media_type": media_type, "data": b64,
            }},
            {"type": "text", "text": _PROMPT_TICKET},
        ]
    resp = client.messages.create(
        model=ocr_cfg["anthropic_model"],
        max_tokens=2048,
        messages=[{"role": "user", "content": content}],
    )
    text = resp.content[0].text if resp.content else ""
    return _normalize_ticket_response(text)


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
        [_PROMPT_TICKET, file_part],
        generation_config={
            "temperature": 0.1,
            "response_mime_type": "application/json",
        },
    )
    return _normalize_ticket_response(resp.text or "")


def extract_complaint_data(file_obj, provider: str | None = None) -> dict:
    """Extrai dados de um ticket de exception Cainiao."""
    cfg = _get_ocr_settings()
    chosen = (provider or cfg["provider"]).lower()
    if chosen == "anthropic":
        return _extract_anthropic(file_obj, cfg)
    if chosen == "gemini":
        return _extract_gemini(file_obj, cfg)
    raise ValueError(f"OCR provider desconhecido: {chosen}")
