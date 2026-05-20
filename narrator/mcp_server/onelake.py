"""OneLake path resolution for the Modeling Readiness narrator MCP server.

Resolves a Fabric workspace URL (https://app.fabric.microsoft.com/groups/<uuid>/...)
to its OneLake abfss:// path. Passes abfss:// paths through unchanged.
Caches the resolved URL to narrator.config.yaml on first successful resolution.

FR-021: Resolve workspace URL to OneLake path.
"""
from __future__ import annotations

import os
import re

import yaml

ONELAKE_HOST = "onelake.dfs.fabric.microsoft.com"
FABRIC_URL_PATTERN = re.compile(
    r"https://app\.fabric\.microsoft\.com/groups/([^/?#]+)",
    re.IGNORECASE,
)
DEFAULT_CONFIG = "narrator.config.yaml"


def resolve_workspace_url(
    url_or_abfss: str,
    config_path: str = DEFAULT_CONFIG,
) -> str:
    """Resolve a workspace URL or abfss path to an abfss:// OneLake root.

    Args:
        url_or_abfss: Either a full Fabric workspace URL or an abfss:// path.
        config_path: Path to narrator.config.yaml for caching.

    Returns:
        abfss:// path rooted at the workspace on OneLake.

    Raises:
        ValueError: If the URL cannot be resolved to a workspace ID.
    """
    if url_or_abfss.startswith("abfss://"):
        return url_or_abfss

    match = FABRIC_URL_PATTERN.match(url_or_abfss)
    if not match:
        raise ValueError(
            f"Cannot resolve workspace URL: {url_or_abfss!r}. "
            "Expected https://app.fabric.microsoft.com/groups/<uuid>/... or abfss://..."
        )

    workspace_id = match.group(1)
    abfss_path = f"abfss://{workspace_id}@{ONELAKE_HOST}/"

    # Cache the resolved URL back to narrator.config.yaml
    _update_config_url(url_or_abfss, config_path)

    return abfss_path


def _update_config_url(workspace_url: str, config_path: str) -> None:
    """Write workspace_url to narrator.config.yaml if it changed."""
    if not os.path.exists(config_path):
        return
    with open(config_path, encoding="utf-8") as fh:
        config = yaml.safe_load(fh) or {}
    if config.get("workspace_url") != workspace_url:
        config["workspace_url"] = workspace_url
        with open(config_path, "w", encoding="utf-8") as fh:
            yaml.dump(config, fh, default_flow_style=False, allow_unicode=True)
