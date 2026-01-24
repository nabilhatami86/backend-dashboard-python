import logging
import requests
from app.config.confiq_whapi import settings

logger = logging.getLogger(__name__)


def send_text_via_baileys(to: str, text: str) -> dict:
    """Send message via Baileys service"""
    url = f"{settings.BAILEYS_SERVICE_URL}/send"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": settings.BAILEYS_API_KEY,
    }
    payload = {"to": to, "text": text}

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        logger.info(f"Baileys message sent to {to}")
        return {"ok": True, "status_code": resp.status_code, "body": body}
    except requests.RequestException as e:
        logger.exception(f"Failed to send Baileys message to {to}")
        return {"ok": False, "error": str(e)}


def send_text_via_whapi(to: str, text: str) -> dict:
    """Send message via WHAPI (legacy)"""
    url = f"{settings.WHAPI_BASE_URL}/messages/text"
    headers = {
        "Authorization": f"Bearer {settings.WHAPI_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {"to": to, "body": text}

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        return {"ok": True, "status_code": resp.status_code, "body": body}
    except requests.RequestException as e:
        logger.exception("Failed to send WHAPI message")
        return {"ok": False, "error": str(e)}


def send_text(to: str, text: str) -> dict:
    """
    Send WhatsApp message using configured provider.
    Provider is set via WA_PROVIDER env var: "baileys" or "whapi"
    """
    if settings.WA_PROVIDER == "baileys":
        return send_text_via_baileys(to, text)
    else:
        return send_text_via_whapi(to, text)
