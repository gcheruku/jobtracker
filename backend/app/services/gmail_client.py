"""Gmail access for job-alert ingestion (read-only).

Uses the stored OAuth token (token.json). Refreshes it automatically when
expired and writes the refreshed token back to disk. No interactive login is
needed as long as the refresh token is valid.
"""
from __future__ import annotations

import base64
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from ..config import GMAIL_LABEL, GMAIL_SCOPES, GMAIL_TOKEN_PATH
from ..logging_config import logger


def get_service():
    """Build an authorized Gmail API client from the stored token."""
    if not GMAIL_TOKEN_PATH.exists():
        raise FileNotFoundError(f"Gmail token not found at {GMAIL_TOKEN_PATH}")
    creds = Credentials.from_authorized_user_file(str(GMAIL_TOKEN_PATH), GMAIL_SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            GMAIL_TOKEN_PATH.write_text(creds.to_json())
            logger.info("Refreshed Gmail OAuth token")
        else:
            raise RuntimeError("Gmail credentials invalid and not refreshable")
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def get_label_id(service, name: str = GMAIL_LABEL) -> Optional[str]:
    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    for lbl in labels:
        if lbl["name"].lower() == name.lower():
            return lbl["id"]
    return None


def list_message_ids(service, label_id: str, after_epoch: int, max_results: int):
    """List message ids in the label delivered after `after_epoch` (unix seconds).

    Gmail's `after:` query is day-granular, so we over-fetch by query and filter
    precisely on internalDate in `fetch_message` callers.
    """
    query = f"after:{max(0, after_epoch)}" if after_epoch else ""
    ids: list[str] = []
    page_token = None
    while len(ids) < max_results:
        resp = (
            service.users()
            .messages()
            .list(
                userId="me",
                labelIds=[label_id],
                q=query,
                maxResults=min(100, max_results - len(ids)),
                pageToken=page_token,
            )
            .execute()
        )
        ids.extend(m["id"] for m in resp.get("messages", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return ids


def fetch_message(service, msg_id: str) -> dict:
    return (
        service.users()
        .messages()
        .get(userId="me", id=msg_id, format="full")
        .execute()
    )


def header(full_msg: dict, name: str) -> str:
    for h in full_msg.get("payload", {}).get("headers", []):
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def internal_epoch(full_msg: dict) -> int:
    return int(full_msg.get("internalDate", "0")) // 1000


def html_body(payload: dict) -> str:
    """Depth-first search for the first text/html part."""
    if payload.get("mimeType") == "text/html" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode(
            "utf-8", "ignore"
        )
    for part in payload.get("parts", []) or []:
        found = html_body(part)
        if found:
            return found
    return ""
