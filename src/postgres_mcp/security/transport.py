"""HTTP ingress policy using the MCP SDK's bearer authentication middleware."""

import ipaddress
import re
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from urllib.parse import urlsplit

import uvicorn
from mcp.server.auth.middleware.auth_context import AuthContextMiddleware
from mcp.server.auth.middleware.bearer_auth import BearerAuthBackend
from mcp.server.auth.middleware.bearer_auth import RequireAuthMiddleware
from mcp.server.auth.provider import AccessToken
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.types import ASGIApp
from starlette.types import Receive
from starlette.types import Scope
from starlette.types import Send


def _valid_authority(value: str) -> bool:
    if not value or not value.isascii() or re.search(r"[^A-Za-z0-9.\[\]:-]", value):
        return False
    try:
        parsed = urlsplit(f"https://{value}")
        if not parsed.hostname or parsed.port == 0 or parsed.path or parsed.query or parsed.fragment:
            return False
        if ":" in parsed.hostname:
            return ipaddress.ip_address(parsed.hostname).version == 6
        return all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?", label) for label in parsed.hostname.split("."))
    except ValueError:
        return False


@dataclass(frozen=True)
class HttpAuthConfig:
    token: str | None = field(default=None, repr=False)
    allowed_hosts: tuple[str, ...] = ()
    allowed_origins: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.token is None and not self.allowed_hosts and not self.allowed_origins:
            return
        if (
            self.token is None
            or len(self.token) < 32
            or not self.token.isascii()
            or not all(33 <= ord(char) <= 126 for char in self.token)
            or not self.allowed_hosts
            or not all(_valid_authority(host) for host in self.allowed_hosts)
            or not self.allowed_origins
            or not all(origin.startswith("https://") and _valid_authority(origin[8:]) for origin in self.allowed_origins)
        ):
            raise ValueError("Invalid HTTP authentication configuration.")

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "HttpAuthConfig":
        hosts = env.get("MCP_HTTP_ALLOWED_HOSTS")
        origins = env.get("MCP_HTTP_ALLOWED_ORIGINS")
        return cls(
            token=env.get("MCP_HTTP_AUTH_TOKEN"),
            allowed_hosts=tuple(host.strip() for host in hosts.split(",")) if hosts is not None else (),
            allowed_origins=tuple(origin.strip() for origin in origins.split(",")) if origins is not None else (),
        )


def validate_http_deployment(transport: str, host: str, auth: HttpAuthConfig) -> None:
    if transport == "stdio":
        return
    try:
        loopback = host == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = False
    if not loopback and auth.token is None:
        raise ValueError("Authenticated HTTP configuration is required for non-loopback binds.")


class _ConfiguredTokenVerifier:
    def __init__(self, token: str) -> None:
        self.token = token

    async def verify_token(self, token: str) -> AccessToken | None:
        if not secrets.compare_digest(token.encode(), self.token.encode()):
            return None
        return AccessToken(token=token, client_id="configured-http-client", scopes=["postgres-mcp"])


def authenticated_http_app(server: FastMCP, transport: str, auth: HttpAuthConfig) -> ASGIApp:
    if auth.token is None:
        raise ValueError("Authenticated HTTP configuration is required for non-loopback binds.")
    server.settings.transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=list(auth.allowed_hosts),
        allowed_origins=list(auth.allowed_origins),
    )
    app = server.sse_app() if transport == "sse" else server.streamable_http_app()
    authenticated = AuthenticationMiddleware(
        AuthContextMiddleware(RequireAuthMiddleware(app, required_scopes=["postgres-mcp"])),
        backend=BearerAuthBackend(_ConfiguredTokenVerifier(auth.token)),
    )

    async def dispatch(scope: Scope, receive: Receive, send: Send) -> None:
        # The SDK's RequireAuthMiddleware handles HTTP only; preserve the app's ASGI lifespan.
        await (authenticated if scope["type"] == "http" else app)(scope, receive, send)

    return dispatch


async def run_authenticated_http(server: FastMCP, transport: str, auth: HttpAuthConfig) -> None:
    app = authenticated_http_app(server, transport, auth)
    config = uvicorn.Config(app, host=server.settings.host, port=server.settings.port, log_level=server.settings.log_level.lower(), access_log=False)
    await uvicorn.Server(config).serve()
