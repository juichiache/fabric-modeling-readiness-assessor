"""Tests for narrator auth.py (T028).

Tests verify:
- Token returned to caller from MSAL mock
- token_cache: false → no .narrator-token-cache file written
- token_cache: true → .narrator-token-cache file created
- SerializableTokenCache round-trip (mocked)
"""
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


class TestTokenAcquired:
    def test_get_token_returns_string(self, tmp_path, monkeypatch):
        """get_token() returns the access_token string from MSAL flow."""
        monkeypatch.chdir(tmp_path)
        # Write minimal config
        (tmp_path / "narrator.config.yaml").write_text(
            "workspace_url: ''\ntoken_cache: false\nsimilarity_threshold: 0.85\ndemo_workspace: false\n",
            encoding="utf-8",
        )

        with patch("narrator.mcp_server.auth.msal") as mock_msal:
            mock_app = MagicMock()
            mock_msal.PublicClientApplication.return_value = mock_app
            mock_app.get_accounts.return_value = []
            mock_app.initiate_device_flow.return_value = {"user_code": "TEST-CODE", "message": "Go to ..."}
            mock_app.acquire_token_by_device_flow.return_value = {
                "access_token": "fake-bearer-token",
                "token_type": "Bearer",
            }

            from narrator.mcp_server.auth import get_token
            token = get_token(config_path=str(tmp_path / "narrator.config.yaml"))
            assert token == "fake-bearer-token"


class TestTokenCacheDisabled:
    def test_no_cache_file_written_when_disabled(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "narrator.config.yaml").write_text(
            "workspace_url: ''\ntoken_cache: false\nsimilarity_threshold: 0.85\ndemo_workspace: false\n",
            encoding="utf-8",
        )

        with patch("narrator.mcp_server.auth.msal") as mock_msal:
            mock_app = MagicMock()
            mock_msal.PublicClientApplication.return_value = mock_app
            mock_app.get_accounts.return_value = []
            mock_app.initiate_device_flow.return_value = {"user_code": "X", "message": "..."}
            mock_app.acquire_token_by_device_flow.return_value = {"access_token": "tok"}

            from narrator.mcp_server.auth import get_token
            get_token(config_path=str(tmp_path / "narrator.config.yaml"))

        cache_file = tmp_path / ".narrator-token-cache"
        assert not cache_file.exists(), ".narrator-token-cache must NOT be created when token_cache: false"


class TestTokenCacheEnabled:
    def test_cache_file_written_when_enabled(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "narrator.config.yaml"
        config_file.write_text(
            "workspace_url: ''\ntoken_cache: true\nsimilarity_threshold: 0.85\ndemo_workspace: false\n",
            encoding="utf-8",
        )

        with patch("narrator.mcp_server.auth.msal") as mock_msal:
            mock_cache = MagicMock()
            mock_cache.has_state_changed = True
            mock_cache.serialize.return_value = '{"AccessToken": {}}'
            mock_msal.SerializableTokenCache.return_value = mock_cache
            mock_app = MagicMock()
            mock_msal.PublicClientApplication.return_value = mock_app
            mock_app.get_accounts.return_value = []
            mock_app.initiate_device_flow.return_value = {"user_code": "X", "message": "..."}
            mock_app.acquire_token_by_device_flow.return_value = {"access_token": "cached-tok"}

            from narrator.mcp_server.auth import get_token
            get_token(config_path=str(config_file))

        cache_file = tmp_path / ".narrator-token-cache"
        assert cache_file.exists(), ".narrator-token-cache MUST be created when token_cache: true"
