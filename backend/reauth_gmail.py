"""Re-authorize Gmail and write a fresh token.json.

Run this when ingestion fails with `invalid_grant: Token has been expired or
revoked` — i.e. the stored refresh token is dead and can't be refreshed. It
opens a browser for the Google consent screen and overwrites the token at
GMAIL_TOKEN_PATH (default backend/secrets/token.json).

    python reauth_gmail.py

Notes:
  * Uses the same credentials.json, scopes, and token path as the app (via
    app.config), so the new token drops straight in.
  * Forces a fresh refresh token (access_type=offline, prompt=consent).
  * If your OAuth consent screen is still in "Testing" mode, Google revokes
    refresh tokens after ~7 days. Publish it to "Production" in Google Cloud
    Console to stop having to re-run this every week.
"""
from __future__ import annotations

from google_auth_oauthlib.flow import InstalledAppFlow

from app.config import GMAIL_CREDENTIALS_PATH, GMAIL_SCOPES, GMAIL_TOKEN_PATH


def main() -> None:
    if not GMAIL_CREDENTIALS_PATH.exists():
        raise SystemExit(
            f"Missing OAuth client file: {GMAIL_CREDENTIALS_PATH}\n"
            "Download a Desktop-app OAuth client from Google Cloud Console and "
            "save it there (see secrets/README.md)."
        )
    flow = InstalledAppFlow.from_client_secrets_file(
        str(GMAIL_CREDENTIALS_PATH), GMAIL_SCOPES
    )
    # access_type=offline + prompt=consent guarantees Google returns a new
    # refresh token (otherwise a re-consent may omit it).
    creds = flow.run_local_server(
        port=0, access_type="offline", prompt="consent"
    )
    GMAIL_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    GMAIL_TOKEN_PATH.write_text(creds.to_json())
    print(f"Wrote fresh token to {GMAIL_TOKEN_PATH}")


if __name__ == "__main__":
    main()
