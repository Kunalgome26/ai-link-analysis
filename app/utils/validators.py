"""URL validation and Server-Side Request Forgery (SSRF) defense."""

import ipaddress
import re
import socket
from urllib.parse import urlsplit


class ValidationError(Exception):
    """Raised when URL format is invalid."""
    pass


class SSRFProtectionError(Exception):
    """Raised when a URL attempts to resolve to private, loopback, or forbidden networks."""
    pass


# Reserved or dangerous TLDs / local hostnames
BLOCKED_HOSTNAMES = {
    "localhost",
    "loopback",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "metadata.google.internal",
    "instance-data",
}

# Regex for basic domain syntax check
DOMAIN_PATTERN = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
)


def validate_and_sanitize_url(raw_url: str) -> str:
    """Validate URL syntax, scheme, and perform SSRF safety checks against DNS resolution.

    Args:
        raw_url: The incoming string URL from user payload.

    Returns:
        Clean, normalized URL string.

    Raises:
        ValidationError: If the URL format or scheme is invalid.
        SSRFProtectionError: If the target domain resolves to private/internal IPs.
    """
    if not raw_url or not isinstance(raw_url, str):
        raise ValidationError("URL must be a non-empty string.")

    cleaned_url = raw_url.strip()

    # Prepend https:// if user provided a plain domain like "example.com"
    if not (cleaned_url.startswith("http://") or cleaned_url.startswith("https://")):
        if "://" in cleaned_url:
            scheme = cleaned_url.split("://")[0]
            raise ValidationError(f"Unsupported protocol scheme '{scheme}'. Only HTTP and HTTPS are permitted.")
        cleaned_url = "https://" + cleaned_url

    try:
        parsed = urlsplit(cleaned_url)
    except Exception as exc:
        raise ValidationError(f"Malformed URL string: {str(exc)}") from exc

    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise ValidationError(f"Invalid scheme '{scheme}'. Only HTTP and HTTPS are permitted.")

    hostname = parsed.hostname
    if not hostname:
        raise ValidationError("URL must include a valid hostname.")

    hostname_lower = hostname.lower()

    # 1. Direct hostname blocklist
    if hostname_lower in BLOCKED_HOSTNAMES:
        raise SSRFProtectionError(f"Access to host '{hostname}' is blocked for security (SSRF protection).")

    # Reject local/internal domain suffixes
    forbidden_suffixes = (".local", ".internal", ".lan", ".home", ".corp", ".intranet")
    if any(hostname_lower.endswith(suffix) for suffix in forbidden_suffixes):
        raise SSRFProtectionError(f"Access to internal domain suffix '{hostname}' is blocked (SSRF protection).")

    # 2. Check if hostname is directly an IP literal
    try:
        ip_obj = ipaddress.ip_address(hostname_lower)
        _verify_ip_is_public(ip_obj, hostname)
    except ValueError:
        # Hostname is a domain name, proceed to DNS resolution check
        _check_dns_resolution(hostname)

    return cleaned_url


def _check_dns_resolution(hostname: str) -> None:
    """Resolve DNS records for the hostname and ensure none point to internal IPs."""
    try:
        # Resolve both IPv4 and IPv6
        addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValidationError(f"Failed to resolve domain '{hostname}'. Website may not exist or DNS lookup failed.") from exc
    except Exception as exc:
        raise ValidationError(f"DNS lookup error for '{hostname}': {str(exc)}") from exc

    resolved_ips = set()
    for item in addr_info:
        sockaddr = item[4]
        ip_str = sockaddr[0]
        resolved_ips.add(ip_str)

    if not resolved_ips:
        raise ValidationError(f"No IP address found for domain '{hostname}'.")

    for ip_str in resolved_ips:
        try:
            ip_obj = ipaddress.ip_address(ip_str)
            _verify_ip_is_public(ip_obj, hostname)
        except ValueError:
            continue


def _verify_ip_is_public(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address, hostname: str) -> None:
    """Ensure IP address is globally reachable and not private/loopback/link-local/cloud-metadata."""
    if ip_obj.is_loopback:
        raise SSRFProtectionError(f"Resolved IP {ip_obj} for '{hostname}' is a loopback address (SSRF protection).")
    if ip_obj.is_private:
        raise SSRFProtectionError(f"Resolved IP {ip_obj} for '{hostname}' is within a private network (SSRF protection).")
    if ip_obj.is_link_local:
        raise SSRFProtectionError(f"Resolved IP {ip_obj} for '{hostname}' is a link-local address (SSRF protection).")
    if ip_obj.is_reserved:
        raise SSRFProtectionError(f"Resolved IP {ip_obj} for '{hostname}' is a reserved address (SSRF protection).")
    if ip_obj.is_multicast:
        raise SSRFProtectionError(f"Resolved IP {ip_obj} for '{hostname}' is a multicast address (SSRF protection).")
    if ip_obj.is_unspecified:
        raise SSRFProtectionError(f"Resolved IP {ip_obj} for '{hostname}' is an unspecified address (SSRF protection).")

    # AWS/GCP/Azure link-local metadata protection (169.254.169.254)
    if str(ip_obj) == "169.254.169.254":
        raise SSRFProtectionError("Access to cloud instance metadata service is forbidden (SSRF protection).")
