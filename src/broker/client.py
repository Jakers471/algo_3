"""ProjectX Gateway connection and session.

One job: hold an authenticated HTTP session to the ProjectX (TopstepX) API
and expose a single ``post()`` for every other broker module to reuse. This
is plumbing only — it knows how to talk to the API, not what to ask it.
"""

from __future__ import annotations

import logging

import requests

from src.config import Settings

logger = logging.getLogger(__name__)


class AuthError(RuntimeError):
    """Raised when the API rejects our credentials or token."""


class ProjectXClient:
    """Authenticated session against the ProjectX Gateway API."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base = settings.api_base.rstrip("/")
        self._token: str | None = settings.token
        self._session = requests.Session()
        self._session.headers.update({"accept": "text/plain", "Content-Type": "application/json"})
        if self._token:
            self._apply_token(self._token)

    # --- connection lifecycle --------------------------------------------
    def connect(self) -> None:
        """Ensure we hold a valid token: validate the stored one, else log in."""
        if self._token and self._validate():
            logger.info("Connected to ProjectX (validated stored token).")
            return
        self._login()
        logger.info("Connected to ProjectX (fresh login as %s).", self._settings.username)

    def _login(self) -> None:
        logger.debug("Requesting new session token via loginKey.")
        data = self._raw_post(
            "/api/Auth/loginKey",
            {"userName": self._settings.username, "apiKey": self._settings.api_key},
        )
        token = data.get("token")
        if not data.get("success") or not token:
            raise AuthError(f"loginKey failed (errorCode={data.get('errorCode')}).")
        self._apply_token(token)

    def _validate(self) -> bool:
        """Validate/refresh the current token; return False if it is no good."""
        try:
            data = self._raw_post("/api/Auth/validate", {})
        except requests.HTTPError:
            return False
        if not data.get("success"):
            return False
        new_token = data.get("newToken")
        if new_token:
            self._apply_token(new_token)
        return True

    def _apply_token(self, token: str) -> None:
        self._token = token
        self._session.headers["Authorization"] = f"Bearer {token}"

    @property
    def token(self) -> str | None:
        return self._token

    # --- request helpers --------------------------------------------------
    def post(self, path: str, payload: dict) -> dict:
        """POST an authenticated request and return the parsed JSON body."""
        return self._raw_post(path, payload)

    def _raw_post(self, path: str, payload: dict) -> dict:
        url = f"{self._base}{path}"
        resp = self._session.post(url, json=payload, timeout=30)
        if resp.status_code == 429:
            raise requests.HTTPError("429 Too Many Requests (rate limited)", response=resp)
        resp.raise_for_status()
        return resp.json()
