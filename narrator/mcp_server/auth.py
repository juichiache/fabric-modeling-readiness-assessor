"""MSAL device code authentication for the Modeling Readiness narrator MCP server.

FR-001: MSAL device code flow; optional token cache via .narrator-token-cache.
Scope: https://storage.azure.com/user_impersonation (OneLake read only).
"""
from __future__ import annotations

import os
from pathlib import Path

import msal
import yaml

SCOPE = ["https://storage.azure.com/user_impersonation"]
FABRIC_SCOPE = ["https://api.fabric.microsoft.com/user_impersonation"]
CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"  # Azure CLI public client — no secret needed
AUTHORITY = "https://login.microsoftonline.com/organizations"
CACHE_FILENAME = ".narrator-token-cache"
DEFAULT_CONFIG = "narrator.config.yaml"


def _load_config(config_path: str) -> dict:
    if os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    return {}


def get_token(config_path: str = DEFAULT_CONFIG) -> str:
    """Acquire an OneLake bearer token via MSAL device code flow.

    When token_cache is enabled in narrator.config.yaml, tokens are
    serialized to .narrator-token-cache in the working directory (gitignored).

    Returns:
        Bearer token string.

    Raises:
        RuntimeError: If token acquisition fails.
    """
    config = _load_config(config_path)
    token_cache_enabled = bool(config.get("token_cache", False))
    cache_path = Path(os.path.dirname(os.path.abspath(config_path))) / CACHE_FILENAME

    # Build token cache
    token_cache = msal.SerializableTokenCache()
    if token_cache_enabled and cache_path.exists():
        token_cache.deserialize(cache_path.read_text(encoding="utf-8"))

    app = msal.PublicClientApplication(
        CLIENT_ID,
        authority=AUTHORITY,
        token_cache=token_cache if token_cache_enabled else None,
    )

    # Try silent acquisition from cache first
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPE, account=accounts[0])
        if result and "access_token" in result:
            _persist_cache(token_cache, cache_path, token_cache_enabled)
            return result["access_token"]

    # Fall back to device code flow
    flow = app.initiate_device_flow(SCOPE)
    if "user_code" not in flow:
        raise RuntimeError(f"Failed to initiate device code flow: {flow}")

    print(flow.get("message", "Sign in via device code."))

    result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        raise RuntimeError(
            f"Token acquisition failed: {result.get('error_description', result)}"
        )

    _persist_cache(token_cache, cache_path, token_cache_enabled)
    return result["access_token"]


def get_fabric_token(config_path: str = DEFAULT_CONFIG) -> str:
    """Acquire a Fabric API bearer token via MSAL device code flow.

    Scope: https://api.fabric.microsoft.com/user_impersonation
    Used for triggering notebook runs via the Fabric REST API.

    Returns:
        Bearer token string.

    Raises:
        RuntimeError: If token acquisition fails.
    """
    config = _load_config(config_path)
    token_cache_enabled = bool(config.get("token_cache", False))
    cache_path = Path(os.path.dirname(os.path.abspath(config_path))) / CACHE_FILENAME

    token_cache = msal.SerializableTokenCache()
    if token_cache_enabled and cache_path.exists():
        token_cache.deserialize(cache_path.read_text(encoding="utf-8"))

    app = msal.PublicClientApplication(
        CLIENT_ID,
        authority=AUTHORITY,
        token_cache=token_cache if token_cache_enabled else None,
    )

    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(FABRIC_SCOPE, account=accounts[0])
        if result and "access_token" in result:
            _persist_cache(token_cache, cache_path, token_cache_enabled)
            return result["access_token"]

    flow = app.initiate_device_flow(FABRIC_SCOPE)
    if "user_code" not in flow:
        raise RuntimeError(f"Failed to initiate device code flow: {flow}")

    print(flow.get("message", "Sign in via device code."))

    result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        raise RuntimeError(
            f"Token acquisition failed: {result.get('error_description', result)}"
        )

    _persist_cache(token_cache, cache_path, token_cache_enabled)
    return result["access_token"]


def _persist_cache(cache: msal.SerializableTokenCache, path: Path, enabled: bool) -> None:
    if enabled and cache.has_state_changed:
        path.write_text(cache.serialize(), encoding="utf-8")
