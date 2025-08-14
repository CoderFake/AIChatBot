from typing import Optional
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
    # 1) Origin header
    origin = request.headers.get("origin")
    if origin:
        parsed = urlsplit(origin)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"

    # 2) Referer header
    referer = request.headers.get("referer")
    if referer:
        p = urlsplit(referer)
        if p.scheme and p.netloc:
            return f"{p.scheme}://{p.netloc}"

    # 3) Forwarded header (RFC 7239)
    fwd = request.headers.get("forwarded")
    if fwd:
        proto, host = _parse_forwarded_header(fwd)
        if host:
            scheme = proto or request.url.scheme
            return f"{scheme}://{host}"

    # 3b) X-Forwarded-* headers
    xf_proto = request.headers.get("x-forwarded-proto")
    xf_host = request.headers.get("x-forwarded-host")
    if xf_host:
        # In case of multiple values, use the first
        host = xf_host.split(",")[0].strip()
        scheme = (xf_proto.split(",")[0].strip() if xf_proto else request.url.scheme)
        return f"{scheme}://{host}"

    # 4) Fallback to request.url
    return f"{request.url.scheme}://{request.url.netloc}"


def get_request_netloc(request: Request) -> str:
    """
    Get only the netloc (host[:port]) of the frontend origin for this request.
    """
    origin = get_request_origin(request)
    return urlsplit(origin).netloc or request.url.netloc 