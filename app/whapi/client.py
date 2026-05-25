import logging
import requests
from app.config.confiq_whapi import settings

logger = logging.getLogger(__name__)


def send_text_via_baileys(to: str, text: str, mentions: list | None = None) -> dict:
    if settings.BAILEYS_SERVICE_URL is None or settings.BAILEYS_API_KEY is None:
        logger.error("Baileys service URL or API key is not configured")
        return {"ok": False, "error": "Baileys service not configured"}
    """Send message via Baileys service"""
    url = f"{settings.BAILEYS_SERVICE_URL}/send"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": settings.BAILEYS_API_KEY,
    }
    payload = {"to": to, "text": text}
    if mentions:
        payload["mentions"] = mentions

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


def send_text(to: str, text: str, mentions: list | None = None) -> dict:
    """
    Send WhatsApp message using configured provider.
    Provider is set via WA_PROVIDER env var: "baileys" or "whapi"
    """
    if settings.WA_PROVIDER == "baileys":
        return send_text_via_baileys(to, text, mentions)
    else:
        return send_text_via_whapi(to, text)


def send_media_via_baileys(
    to: str,
    media_url: str,
    media_type: str,
    caption: str | None = None,
    filename: str | None = None,
    mentions: list | None = None,
) -> dict:
    """Send media (image/document) via Baileys service"""
    if not settings.BAILEYS_SERVICE_URL or not settings.BAILEYS_API_KEY:
        logger.error("Baileys service URL or API key is not configured")
        return {"ok": False, "error": "Baileys service not configured"}

    url = f"{settings.BAILEYS_SERVICE_URL}/send-media"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": settings.BAILEYS_API_KEY,
    }
    payload = {
        "to": to,
        "mediaUrl": media_url,
        "mediaType": media_type,
    }
    if caption:
        payload["caption"] = caption
    if filename:
        payload["filename"] = filename
    if mentions:
        payload["mentions"] = mentions

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        logger.info(f"Baileys media sent to {to}")
        return {"ok": True, "status_code": resp.status_code, "body": body}
    except requests.RequestException as e:
        logger.exception(f"Failed to send Baileys media to {to}")
        return {"ok": False, "error": str(e)}


def send_media(
    to: str,
    media_url: str,
    media_type: str,
    caption: str | None = None,
    filename: str | None = None,
    mentions: list | None = None,
) -> dict:
    """Send media via configured provider"""
    if settings.WA_PROVIDER == "baileys":
        return send_media_via_baileys(to, media_url, media_type, caption, filename, mentions)
    else:
        # WHAPI doesn't support media in this implementation
        logger.warning("Media sending not supported via WHAPI, sending caption as text")
        return send_text_via_whapi(to, caption or f"[{media_type}]")


def send_presence(to: str, status: str = "composing") -> None:
    """
    Send WhatsApp presence update (typing indicator) to a JID.
    status: "composing" = typing..., "paused" = stopped typing
    Only works when WA_PROVIDER=baileys. Silently ignored otherwise.
    """
    if settings.WA_PROVIDER != "baileys":
        return
    if not settings.BAILEYS_SERVICE_URL or not settings.BAILEYS_API_KEY:
        return
    try:
        requests.post(
            f"{settings.BAILEYS_SERVICE_URL}/send-presence",
            json={"to": to, "status": status},
            headers={"Content-Type": "application/json", "x-api-key": settings.BAILEYS_API_KEY},
            timeout=5,
        )
        logger.info(f"[PRESENCE] {status} → {to}")
    except Exception as e:
        logger.warning(f"[PRESENCE] Failed to send {status} to {to}: {e}")
