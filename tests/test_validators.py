"""Tests for URL validation and SSRF defenses."""

from unittest.mock import patch
import pytest
from app.utils.validators import (
    validate_and_sanitize_url,
    ValidationError,
    SSRFProtectionError
)


@patch("socket.getaddrinfo")
def test_valid_public_urls(mock_dns):
    """Test standard public web URLs pass validation."""
    mock_dns.return_value = [(2, 1, 0, "", ("93.184.216.34", 0))]

    assert validate_and_sanitize_url("https://example.com") == "https://example.com"
    assert validate_and_sanitize_url("http://example.com/test?page=1") == "http://example.com/test?page=1"
    # Auto-prepend https
    assert validate_and_sanitize_url("example.com") == "https://example.com"
    assert validate_and_sanitize_url("google.com") == "https://google.com"


def test_invalid_scheme():
    """Test disallowed protocols are rejected."""
    with pytest.raises(ValidationError, match="Unsupported protocol scheme"):
        validate_and_sanitize_url("ftp://example.com")

    with pytest.raises(ValidationError, match="Unsupported protocol scheme"):
        validate_and_sanitize_url("file:///etc/passwd")


def test_empty_or_non_string():
    """Test empty string raises ValidationError."""
    with pytest.raises(ValidationError):
        validate_and_sanitize_url("")

    with pytest.raises(ValidationError):
        validate_and_sanitize_url("   ")


def test_ssrf_blocked_hostnames():
    """Test loopback and internal hostname blocking."""
    with pytest.raises(SSRFProtectionError):
        validate_and_sanitize_url("http://localhost:8080")

    with pytest.raises(SSRFProtectionError):
        validate_and_sanitize_url("http://127.0.0.1")

    with pytest.raises(SSRFProtectionError):
        validate_and_sanitize_url("http://0.0.0.0")

    with pytest.raises(SSRFProtectionError):
        validate_and_sanitize_url("http://[::1]")


def test_ssrf_blocked_internal_suffixes():
    """Test internal domain suffixes (.local, .internal, etc.) are blocked."""
    with pytest.raises(SSRFProtectionError):
        validate_and_sanitize_url("http://my-service.local")

    with pytest.raises(SSRFProtectionError):
        validate_and_sanitize_url("https://database.internal")

    with pytest.raises(SSRFProtectionError):
        validate_and_sanitize_url("https://router.lan")


def test_ssrf_private_ip_literals():
    """Test explicit private IP addresses are blocked."""
    with pytest.raises(SSRFProtectionError):
        validate_and_sanitize_url("http://10.0.0.1")

    with pytest.raises(SSRFProtectionError):
        validate_and_sanitize_url("http://192.168.1.1")

    with pytest.raises(SSRFProtectionError):
        validate_and_sanitize_url("http://172.16.0.1")

    with pytest.raises(SSRFProtectionError):
        validate_and_sanitize_url("http://169.254.169.254")
