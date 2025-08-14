from typing import Optional, Tuple, List
import uuid
from fastapi import Request
from urllib.parse import urlsplit


def _parse_forwarded_header(header_value: str) -> tuple[Optional[str], Optional[str]]:
    """
    Parse RFC 7239 Forwarded header to extract proto and host.
    Example: Forwarded: for=192.0.2.60;proto=https;host=example.com
    Returns (proto, host)
    """
    try:
        parts = [p.strip() for p in header_value.split(";")]
        kv = {}
        for part in parts:
            if "=" in part:
                k, v = part.split("=", 1)
                kv[k.lower()] = v.strip().strip('"')
        return kv.get("proto"), kv.get("host")
    except Exception:
        return None, None


def get_request_origin(request: Request) -> str:
    """
    Get the frontend origin (scheme://host[:port]) for an incoming request.
    Priority:
    1) Origin header (preferred for CORSed requests)
    2) Referer header (fallback)
    3) Forwarded / X-Forwarded-Proto + X-Forwarded-Host (proxy aware)
    4) request.url scheme/netloc (last resort)
    """
    origin = request.headers.get("origin")
    if origin:
        parsed = urlsplit(origin)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"

    referer = request.headers.get("referer")
    if referer:
        p = urlsplit(referer)
        if p.scheme and p.netloc:
            return f"{p.scheme}://{p.netloc}"

    fwd = request.headers.get("forwarded")
    if fwd:
        proto, host = _parse_forwarded_header(fwd)
        if host:
            scheme = proto or request.url.scheme
            return f"{scheme}://{host}"

    xf_proto = request.headers.get("x-forwarded-proto")
    xf_host = request.headers.get("x-forwarded-host")
    if xf_host:
        host = xf_host.split(",")[0].strip()
        scheme = (xf_proto.split(",")[0].strip() if xf_proto else request.url.scheme)
        return f"{scheme}://{host}"

    return f"{request.url.scheme}://{request.url.netloc}"


def get_request_netloc(request: Request) -> str:
    """
    Get only the netloc (host[:port]) of the frontend origin for this request.
    """
    origin = get_request_origin(request)
    return urlsplit(origin).netloc or request.url.netloc 


def get_subdomain(request: Request) -> Optional[str]:
    """
    Extract subdomain from request host if present.
    - Ignore port
    - Ignore 'www' prefix
    - Return first label when netloc has >= 3 labels (e.g., sub.domain.tld)
    - Return None for IPs, localhost, or bare domains
    """
    try:
        netloc = get_request_netloc(request)
        host = netloc.split(":")[0]
        
        if host == "localhost" or host.replace(".", "").isdigit():
            return None
        labels: List[str] = host.split(".")
        if len(labels) < 3:
            return None
        first = labels[0].lower()
        if first == "www":
            return None
        return first
    except Exception:
        return None


def get_path_tenant_id(request: Request) -> Optional[str]:
    """
    Extract tenant_id from URL path by convention:
    - /api/v1/{tenant_id}/...
    - /{tenant_id}/api/v1/...
    - /{tenant_id}/...
    Returns None if not found.
    """
    try:
        def _is_uuid(s: str) -> bool:
            try:
                uuid.UUID(s)
                return True
            except Exception:
                return False
        parts = [p for p in request.url.path.split("/") if p]
        if not parts:
            return None
        if len(parts) >= 3 and parts[0] == "api" and parts[1].startswith("v"):
            return parts[2] if _is_uuid(parts[2]) else None
        
        if len(parts) >= 3 and parts[1] == "api" and parts[2].startswith("v"):
            return parts[0] if _is_uuid(parts[0]) else None
        return parts[0] if _is_uuid(parts[0]) else None
    except Exception:
        return None


def get_tenant_identifier_from_request(request: Request) -> Tuple[Optional[str], Optional[str]]:
    """
    Return (sub_domain, path_tenant_id) extracted from request.
    Caller can prefer sub_domain, then fallback to path_tenant_id.
    """
    return get_subdomain(request), get_path_tenant_id(request)