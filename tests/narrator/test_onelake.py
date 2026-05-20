"""Tests for narrator onelake.py (T029).

Tests verify:
- Fabric workspace URL → abfss:// path resolution
- abfss:// direct path passthrough
- workspace URL written to narrator.config.yaml cache after first resolution
"""
import yaml
from pathlib import Path
from unittest.mock import patch

import pytest


class TestWorkspaceUrlResolution:
    def test_fabric_workspace_url_resolves_to_abfss(self, tmp_path):
        from narrator.mcp_server.onelake import resolve_workspace_url
        url = "https://app.fabric.microsoft.com/groups/contoso-workspace-guid-0001/synapseanalytics"
        result = resolve_workspace_url(url)
        assert result.startswith("abfss://")
        assert "contoso-workspace-guid-0001" in result
        assert "onelake.dfs.fabric.microsoft.com" in result

    def test_groups_uuid_extracted(self, tmp_path):
        from narrator.mcp_server.onelake import resolve_workspace_url
        url = "https://app.fabric.microsoft.com/groups/aabbccdd-1122-3344-5566-7788990011aa/overview"
        result = resolve_workspace_url(url)
        assert "aabbccdd-1122-3344-5566-7788990011aa" in result

    def test_abfss_passthrough(self, tmp_path):
        from narrator.mcp_server.onelake import resolve_workspace_url
        abfss = "abfss://contoso-workspace-guid-0001@onelake.dfs.fabric.microsoft.com/"
        result = resolve_workspace_url(abfss)
        assert result == abfss

    def test_abfss_with_path_passthrough(self, tmp_path):
        from narrator.mcp_server.onelake import resolve_workspace_url
        abfss = "abfss://ws-001@onelake.dfs.fabric.microsoft.com/Files/modeling-readiness/"
        result = resolve_workspace_url(abfss)
        assert result == abfss


class TestConfigCaching:
    def test_resolved_url_written_to_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "narrator.config.yaml"
        config_file.write_text(
            "workspace_url: ''\ntoken_cache: false\nsimilarity_threshold: 0.85\ndemo_workspace: false\n",
            encoding="utf-8",
        )

        from narrator.mcp_server.onelake import resolve_workspace_url
        url = "https://app.fabric.microsoft.com/groups/ws-cache-test-guid/overview"
        resolve_workspace_url(url, config_path=str(config_file))

        saved = yaml.safe_load(config_file.read_text())
        assert saved.get("workspace_url") == url or "ws-cache-test-guid" in saved.get("workspace_url", "")
