"""Local Sign in with ChatGPT plan-usage OAuth and Responses transport.

This is the plan-usage grant, not identity-only website sign-in. Credentials
live outside the repository and are never included in model prompts.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import tempfile
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

AUTHORIZATION_URL = "https://auth.openai.com/api/accounts/authorize"
TOKEN_URL = "https://auth.openai.com/api/accounts/oauth/token"
DISCOVERY_URL = "https://auth.openai.com/.well-known/openid-configuration"
RESOURCE = "https://api.openai.com/v1"
REQUIRED_SCOPE = "chatgpt.tokens.use.direct"
SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
CALLBACK_PATH = "/auth/callback"
DEFAULT_CREDENTIALS = Path.home() / ".config" / "bricksmith" / "chatgpt-plan.json"


def _read_json(url: str, *, method: str = "GET", data: dict | None = None,
               access_token: str | None = None) -> dict:
    body = None if data is None else urlencode(data).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as exc:
        # Deliberately omit response bodies: auth services may echo sensitive data.
        raise RuntimeError(f"OpenAI request failed (HTTP {exc.code})") from exc


def _write_private(path: Path, value: dict) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".chatgpt-plan-")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _load(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError("Not signed in. Run `python scripts/chatgpt_plan.py login` first.")
    if path.stat().st_mode & 0o077:
        raise RuntimeError(f"Credential file permissions are too open: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_id_token(token: str, client_id: str, nonce: str) -> dict:
    try:
        import jwt
    except ImportError as exc:
        raise RuntimeError("Install requirements.txt to verify the OpenAI ID token.") from exc
    discovery = _read_json(DISCOVERY_URL)
    if discovery.get("issuer") != "https://auth.openai.com":
        raise RuntimeError("Unexpected OpenAI identity issuer")
    jwks_uri = discovery.get("jwks_uri", "")
    if not jwks_uri.startswith("https://auth.openai.com/"):
        raise RuntimeError("Unexpected OpenAI JWKS URL")
    key = jwt.PyJWKClient(jwks_uri).get_signing_key_from_jwt(token)
    claims = jwt.decode(token, key.key, algorithms=["RS256"],
                        audience=client_id, issuer=discovery["issuer"],
                        options={"require": ["exp", "iat", "sub"]}, leeway=5)
    if claims.get("nonce") != nonce or not claims.get("sub"):
        raise RuntimeError("OpenAI ID token nonce or subject did not validate")
    return claims


def _callback_server() -> tuple[HTTPServer, dict]:
    result: dict = {}

    class Callback(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler contract
            parsed = urlparse(self.path)
            if parsed.path != CALLBACK_PATH:
                self.send_error(404)
                return
            params = {key: values[0] for key, values in parse_qs(parsed.query).items()}
            result.update(params)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"BrickSmith received the sign-in result. Return to the terminal.")

        def log_message(self, *_args):
            # The request URL contains the authorization code; never log it.
            pass

    server = HTTPServer(("127.0.0.1", 0), Callback)
    server.timeout = 180
    return server, result


def login(path: Path = DEFAULT_CREDENTIALS, *, open_browser: bool = True) -> dict:
    current = _load(path) if path.exists() else {}
    host_id = current.get("ext_agent_host_id") or f"urn:uuid:{uuid.uuid4()}"
    # Persist the host before sign-in, including if the user cancels.
    if not current:
        _write_private(path, {"ext_agent_host_id": host_id})
    state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    client_id = current.get("client_id", "dynamic_agent_client")
    server, callback = _callback_server()
    redirect_uri = f"http://127.0.0.1:{server.server_port}{CALLBACK_PATH}"
    params = {
        "client_id": client_id, "ext_agent_host_id": host_id,
        "response_type": "code", "redirect_uri": redirect_uri,
        "scope": SCOPES, "resource": RESOURCE, "state": state,
        "nonce": nonce, "code_challenge_method": "S256", "code_challenge": challenge,
    }
    if client_id == "dynamic_agent_client":
        params["agent_name_hint"] = "BrickSmith"
    elif current.get("id_token"):
        params["id_token_hint"] = current["id_token"]
    auth_url = AUTHORIZATION_URL + "?" + urlencode(params)
    try:
        if open_browser:
            print("Opening ChatGPT authorization in your browser. Waiting up to 3 minutes...")
            webbrowser.open(auth_url)
        else:
            # This URL can include id_token_hint on repeat login: caller must not log it.
            print("Open this authorization URL privately:", auth_url)
        server.handle_request()
    finally:
        server.server_close()
    if not callback or not secrets.compare_digest(callback.get("state", ""), state):
        raise RuntimeError("ChatGPT sign-in timed out or callback state did not match")
    if callback.get("error"):
        raise RuntimeError(f"ChatGPT authorization was not granted: {callback['error']}")
    code = callback.get("code")
    issued_id = callback.get("client_id", "")
    if not code:
        raise RuntimeError("ChatGPT callback did not include an authorization code")
    if client_id == "dynamic_agent_client":
        if not issued_id.startswith("oaiapp_"):
            raise RuntimeError("ChatGPT did not issue a valid client ID")
    elif issued_id and issued_id != client_id:
        raise RuntimeError("ChatGPT callback client ID did not match the saved registration")
    else:
        issued_id = client_id
    tokens = _read_json(TOKEN_URL, method="POST", data={
        "grant_type": "authorization_code", "client_id": issued_id,
        "code": code, "code_verifier": verifier,
        "redirect_uri": redirect_uri, "resource": RESOURCE,
    })
    claims = _verify_id_token(tokens["id_token"], issued_id, nonce)
    if current.get("subject") and current["subject"] != claims["sub"]:
        raise RuntimeError("A different ChatGPT account was selected; existing credentials were preserved")
    scopes = tokens.get("scope", "").split()
    if REQUIRED_SCOPE not in scopes:
        raise RuntimeError("ChatGPT identity was granted, but plan-usage permission was not; no credentials saved")
    if not tokens.get("access_token") or not tokens.get("refresh_token"):
        raise RuntimeError("ChatGPT did not return renewable plan-usage credentials")
    record = {
        "client_id": issued_id, "ext_agent_host_id": host_id,
        "subject": claims["sub"], "email": claims.get("email"),
        "issuer": claims["iss"], "id_token": tokens["id_token"],
        "access_token": tokens["access_token"], "refresh_token": tokens["refresh_token"],
        "scopes": scopes, "expires_at": time.time() + int(tokens.get("expires_in", 3600)),
    }
    _write_private(path, record)
    return {"signed_in": True, "email": record["email"], "plan_usage": True,
            "credential_file": str(path)}


def access_token(path: Path = DEFAULT_CREDENTIALS) -> str:
    record = _load(path)
    if REQUIRED_SCOPE not in record.get("scopes", []):
        raise RuntimeError("Saved connection has no ChatGPT plan-usage grant")
    if record.get("expires_at", 0) > time.time() + 120:
        return record["access_token"]
    tokens = _read_json(TOKEN_URL, method="POST", data={
        "grant_type": "refresh_token", "client_id": record["client_id"],
        "refresh_token": record["refresh_token"], "resource": RESOURCE,
    })
    scopes = tokens.get("scope", " ".join(record["scopes"])).split()
    if REQUIRED_SCOPE not in scopes or not tokens.get("access_token"):
        raise RuntimeError("Renewed session has no ChatGPT plan-usage grant")
    record.update(access_token=tokens["access_token"],
                  refresh_token=tokens.get("refresh_token", record["refresh_token"]),
                  scopes=scopes, expires_at=time.time() + int(tokens.get("expires_in", 3600)))
    if tokens.get("id_token"):
        record["id_token"] = tokens["id_token"]
    _write_private(path, record)
    return record["access_token"]


def list_models(path: Path = DEFAULT_CREDENTIALS) -> list[str]:
    response = _read_json(RESOURCE + "/models", access_token=access_token(path))
    return [model["slug"] for model in response.get("models", [])
            if model.get("visibility") == "list" and model.get("slug")]


def ask(model: str, prompt: str, instructions: str, path: Path = DEFAULT_CREDENTIALS) -> str:
    if model not in list_models(path):
        raise ValueError(f"Model {model!r} is not listed for this ChatGPT connection")
    payload = {"model": model, "input": [{"role": "user", "content": prompt}],
               "store": False, "stream": True}
    if instructions:
        payload["instructions"] = instructions
    request = Request(RESOURCE + "/responses", data=json.dumps(payload).encode(),
                      headers={"Authorization": f"Bearer {access_token(path)}",
                               "Content-Type": "application/json", "Accept": "text/event-stream"},
                      method="POST")
    parts: list[str] = []
    completed = False
    try:
        with urlopen(request, timeout=300) as response:
            for raw in response:
                line = raw.decode("utf-8").strip()
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                event = json.loads(data)
                kind = event.get("type")
                if kind == "response.output_text.delta":
                    parts.append(event.get("delta", ""))
                elif kind == "response.completed":
                    completed = True
                elif kind in ("response.failed", "response.incomplete", "error"):
                    error = (event.get("response") or {}).get("error") or event.get("error") or {}
                    raise RuntimeError(f"Responses stream {kind}: {error.get('code', 'unknown')}")
    except HTTPError as exc:
        raise RuntimeError(f"OpenAI Responses request failed (HTTP {exc.code})") from exc
    if not completed:
        raise RuntimeError("Responses stream ended without response.completed")
    return "".join(parts)


def respond(model: str, instructions: str, history: list[dict], tools: list[dict],
            path: Path = DEFAULT_CREDENTIALS) -> dict:
    """Make one streamed plan-usage request and return full output items.

    The caller must replay all output items and tool results on the next step
    because this OAuth route requires store=False and has no HTTP continuation.
    """
    if model not in list_models(path):
        raise ValueError(f"Model {model!r} is not listed for this ChatGPT connection")
    payload = {"model": model, "instructions": instructions, "input": history,
               "tools": tools, "store": False, "stream": True,
               "include": ["reasoning.encrypted_content"]}
    request = Request(RESOURCE + "/responses", data=json.dumps(payload).encode(),
                      headers={"Authorization": f"Bearer {access_token(path)}",
                               "Content-Type": "application/json", "Accept": "text/event-stream"},
                      method="POST")
    completed_response = None
    streamed_items: dict[int, dict] = {}
    try:
        with urlopen(request, timeout=300) as response:
            for raw in response:
                line = raw.decode("utf-8").strip()
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                event = json.loads(data)
                kind = event.get("type")
                if kind == "response.output_item.done":
                    item = event.get("item")
                    index = event.get("output_index")
                    if isinstance(index, int) and isinstance(item, dict):
                        streamed_items[index] = item
                elif kind == "response.completed":
                    completed_response = event.get("response")
                elif kind in ("response.failed", "response.incomplete", "error"):
                    error = (event.get("response") or {}).get("error") or event.get("error") or {}
                    code = error.get("code", "unknown")
                    if code == "subscription_sharing_usage_limit_exceeded":
                        raise RuntimeError(
                            "ChatGPT plan-token sharing limit reached; pause live model requests. "
                            "This can differ from the Codex app usage display. "
                            "The design session was not advanced."
                        )
                    raise RuntimeError(f"Responses stream {kind}: {code}")
    except HTTPError as exc:
        raise RuntimeError(f"OpenAI Responses request failed (HTTP {exc.code})") from exc
    if not completed_response or not isinstance(completed_response.get("output"), list):
        raise RuntimeError("Responses stream ended without complete output items")
    # Some plan-usage streams account for output items in the final usage but
    # leave response.output empty. The per-item done events carry the actual
    # complete function calls/messages needed for the next tool turn.
    if streamed_items and len(streamed_items) > len(completed_response["output"]):
        completed_response["output"] = [streamed_items[i] for i in sorted(streamed_items)]
    return completed_response
