"""Tests for UrlTokenAuthManager."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests
from solentlabs.cable_modem_monitor_core.auth.url_token import UrlTokenAuthManager
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import UrlTokenAuth
from solentlabs.cable_modem_monitor_core.test_harness import HARMockServer

from .conftest import load_auth_fixture


class TestUrlTokenAuthManager:
    """UrlTokenAuthManager encodes credentials in URL."""

    def test_basic_login(self, session: requests.Session) -> None:
        """Successful login sets session cookie."""
        entries, _ = load_auth_fixture("har_url_token_login.json")
        with HARMockServer(entries) as server:
            config = UrlTokenAuth(
                strategy="url_token",
                login_page="/login.html",
                success_indicator="Downstream Bonded Channels",
            )
            manager = UrlTokenAuthManager(config)
            manager.configure_session(session, {})

            result = manager.authenticate(session, server.base_url, "admin", "password")
            assert result.success is True

    def test_session_cookie_set_after_login(self, session: requests.Session) -> None:
        """Session cookie is set after successful login for runner to extract."""
        entries, _ = load_auth_fixture("har_url_token_login.json")
        with HARMockServer(entries) as server:
            config = UrlTokenAuth(
                strategy="url_token",
                login_page="/login.html",
            )
            manager = UrlTokenAuthManager(config)
            manager.configure_session(session, {})

            result = manager.authenticate(session, server.base_url, "admin", "password")
            assert result.success is True
            # Runner extracts URL token from session cookies, not auth_context
            assert session.cookies.get("sessionId") == "tok_abc123"

    def test_login_prefix_in_url(self, session: requests.Session) -> None:
        """Login prefix is prepended to base64 credential."""
        entries, _ = load_auth_fixture("har_url_token_login.json")
        with HARMockServer(entries) as server:
            config = UrlTokenAuth(
                strategy="url_token",
                login_page="/login.html",
                login_prefix="login_",
            )
            manager = UrlTokenAuthManager(config)
            manager.configure_session(session, {})

            result = manager.authenticate(session, server.base_url, "admin", "password")
            assert result.success is True

    def test_success_indicator_absent_extracts_body_as_token(self, session: requests.Session) -> None:
        """Body without success_indicator is treated as session token.

        success_indicator is a response type discriminator:
        - Present → body is data page
        - Absent → body is the token string
        """
        entries, _ = load_auth_fixture("har_url_token_login_error.json")
        with HARMockServer(entries) as server:
            config = UrlTokenAuth(
                strategy="url_token",
                login_page="/login.html",
                success_indicator="Downstream Bonded Channels",
            )
            manager = UrlTokenAuthManager(config)
            manager.configure_session(session, {})

            result = manager.authenticate(session, server.base_url, "admin", "password")
            # New behavior: body without indicator = token extraction (not failure)
            assert result.success is True
            assert result.auth_context.url_token == "Error: bad credentials"

    def test_ajax_login_header(self, session: requests.Session) -> None:
        """AJAX login adds X-Requested-With header."""
        entries, _ = load_auth_fixture("har_url_token_login.json")
        with HARMockServer(entries) as server:
            config = UrlTokenAuth(
                strategy="url_token",
                login_page="/login.html",
                ajax_login=True,
            )
            manager = UrlTokenAuthManager(config)
            manager.configure_session(session, {})

            result = manager.authenticate(session, server.base_url, "admin", "password")
            assert result.success is True

    def test_auth_header_data_sets_basic_auth(self, session: requests.Session) -> None:
        """auth_header_data sets Basic auth on the session."""
        entries, _ = load_auth_fixture("har_url_token_login.json")
        with HARMockServer(entries) as server:
            config = UrlTokenAuth(
                strategy="url_token",
                login_page="/login.html",
                auth_header_data=True,
            )
            manager = UrlTokenAuthManager(config)
            manager.configure_session(session, {})

            result = manager.authenticate(session, server.base_url, "admin", "password")
            assert result.success is True
            assert session.auth == ("admin", "password")

    def test_response_url_captured(self, session: requests.Session) -> None:
        """Response URL path is captured for auth response reuse."""
        entries, _ = load_auth_fixture("har_url_token_login.json")
        with HARMockServer(entries) as server:
            config = UrlTokenAuth(
                strategy="url_token",
                login_page="/login.html",
            )
            manager = UrlTokenAuthManager(config)
            manager.configure_session(session, {})

            result = manager.authenticate(session, server.base_url, "admin", "password")
            assert result.success is True
            assert result.response_url == "/login.html"

    def test_cookies_available_for_runner(self, session: requests.Session) -> None:
        """Session cookies are available for runner to extract url_token."""
        entries, _ = load_auth_fixture("har_url_token_login.json")
        with HARMockServer(entries) as server:
            config = UrlTokenAuth(
                strategy="url_token",
                login_page="/login.html",
            )
            manager = UrlTokenAuthManager(config)
            manager.configure_session(session, {})

            result = manager.authenticate(session, server.base_url, "admin", "password")
            assert result.success is True
            # Cookies are on the session — runner reads them via cookie_name
            assert len(session.cookies) > 0

    def test_login_non_200(self, session: requests.Session) -> None:
        """Reports error when login GET returns non-200, attaches response."""
        config = UrlTokenAuth(strategy="url_token", login_page="/login.html")
        manager = UrlTokenAuthManager(config)
        manager.configure_session(session, {})

        resp = MagicMock()
        resp.status_code = 500
        with patch.object(session, "get", return_value=resp):
            result = manager.authenticate(session, "http://192.168.100.1", "admin", "password")

        assert result.success is False
        assert "500" in result.error
        assert result.response is resp

    def test_login_request_exception(self, session: requests.Session) -> None:
        """Non-connectivity RequestException returns AuthResult; ConnectionError propagates."""
        config = UrlTokenAuth(strategy="url_token", login_page="/login.html")
        manager = UrlTokenAuthManager(config)
        manager.configure_session(session, {})

        with patch.object(session, "get", side_effect=requests.RequestException("redirects")):
            result = manager.authenticate(session, "http://192.168.100.1", "admin", "password")

        assert result.success is False
        assert "URL token login failed" in result.error

    def test_login_connection_error_propagates(self, session: requests.Session) -> None:
        """ConnectionError on login GET propagates for collector to classify."""
        config = UrlTokenAuth(strategy="url_token", login_page="/login.html")
        manager = UrlTokenAuthManager(config)
        manager.configure_session(session, {})

        with (
            patch.object(session, "get", side_effect=requests.ConnectionError("refused")),
            pytest.raises(requests.ConnectionError),
        ):
            manager.authenticate(session, "http://127.0.0.1:1", "admin", "password")
