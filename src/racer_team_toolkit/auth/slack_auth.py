"""Slack OAuth authentication using PKCE."""

import base64
import hashlib
import json
import secrets
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from racer_team_toolkit.auth.paths import (
    get_slack_token_path,
)
from racer_team_toolkit.full_release_update.slack_config import (
    SLACK_CLIENT_ID,
    SLACK_REDIRECT_URI,
    SLACK_USER_SCOPES,
)


def generate_code_verifier() -> str:
    """Generate a PKCE code verifier."""

    return secrets.token_urlsafe(64)


def generate_code_challenge(
    code_verifier: str,
) -> str:
    """Generate the SHA-256 PKCE challenge."""

    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()

    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")


def build_authorization_url(
    code_challenge: str,
) -> str:
    """Build the Slack OAuth authorization URL."""

    if not SLACK_CLIENT_ID:
        raise RuntimeError("SLACK_CLIENT_ID is missing.")

    parameters = {
        "client_id": SLACK_CLIENT_ID,
        "user_scope": ",".join(SLACK_USER_SCOPES),
        "redirect_uri": SLACK_REDIRECT_URI,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    return "https://slack.com/oauth/v2/authorize?" + urlencode(parameters)


def wait_for_authorization_code() -> str:
    """Wait for Slack to redirect back with an OAuth code."""

    authorization_code: str | None = None
    authorization_error: str | None = None

    class OAuthHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            nonlocal authorization_code
            nonlocal authorization_error

            query = parse_qs(urlparse(self.path).query)

            if "error" in query:
                authorization_error = query["error"][0]

            elif "code" in query:
                authorization_code = query["code"][0]

            self.send_response(200)
            self.send_header(
                "Content-Type",
                "text/html; charset=utf-8",
            )
            self.end_headers()

            self.wfile.write(
                (
                    "<html><body>"
                    "<h2>Racer Team Toolkit</h2>"
                    "<p>You can close this window "
                    "and return to the toolkit.</p>"
                    "</body></html>"
                ).encode("utf-8")
            )

        def log_message(
            self,
            format: str,
            *args,
        ) -> None:
            """Suppress HTTP server console logging."""

    server = HTTPServer(
        ("localhost", 8765),
        OAuthHandler,
    )

    server.handle_request()
    server.server_close()

    if authorization_error:
        raise RuntimeError(f"Slack authorization failed: {authorization_error}")

    if not authorization_code:
        raise RuntimeError("Slack did not return an authorization code.")

    return authorization_code


def exchange_authorization_code(
    code: str,
    code_verifier: str,
) -> dict:
    """Exchange the OAuth code for the employee's Slack token."""

    if not SLACK_CLIENT_ID:
        raise RuntimeError("SLACK_CLIENT_ID is missing.")

    data = urlencode(
        {
            "client_id": SLACK_CLIENT_ID,
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": SLACK_REDIRECT_URI,
        }
    ).encode("utf-8")

    request = Request(
        "https://slack.com/api/oauth.v2.access",
        data=data,
        method="POST",
    )

    with urlopen(
        request,
        timeout=15,
    ) as response:
        result = json.loads(response.read().decode("utf-8"))

    if not result.get("ok"):
        raise RuntimeError(f"Slack token exchange failed: {result.get('error', 'unknown_error')}")

    return result


def save_slack_token(
    oauth_response: dict,
) -> None:
    """Save the employee's Slack OAuth response locally."""

    token_path = get_slack_token_path()

    token_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    token_path.write_text(
        json.dumps(
            oauth_response,
            indent=2,
        ),
        encoding="utf-8",
    )


def authenticate_with_slack() -> dict:
    """Run Slack OAuth PKCE authentication."""

    code_verifier = generate_code_verifier()

    code_challenge = generate_code_challenge(
        code_verifier,
    )

    authorization_url = build_authorization_url(
        code_challenge,
    )

    webbrowser.open(
        authorization_url,
    )

    authorization_code = wait_for_authorization_code()

    oauth_response = exchange_authorization_code(
        authorization_code,
        code_verifier,
    )

    save_slack_token(
        oauth_response,
    )

    return oauth_response
