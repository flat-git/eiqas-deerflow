"""Public originals, not search snippets, become computational evidence."""

import ipaddress
from urllib.parse import urljoin

import httpx

from deerflow.community import url_safety

from .evidence import EvidenceService


def resolve_public_doh(hostname: str) -> list:
    """Fixed public resolver used only for the synthetic 198.18/15 proxy range."""
    with httpx.Client(timeout=15, follow_redirects=False, trust_env=True) as resolver:
        response = resolver.get("https://cloudflare-dns.com/dns-query", params={"name": hostname, "type": "A"}, headers={"Accept": "application/dns-json"})
        response.raise_for_status()
        return [ipaddress.ip_address(answer["data"]) for answer in response.json().get("Answer", []) if answer.get("type") == 1]


def public_target(url: str) -> tuple[httpx.URL, dict, dict]:
    original = httpx.URL(url)
    hostname = original.raw_host.decode("ascii")
    try:
        candidates = [ipaddress.ip_address(hostname)]
    except ValueError:
        candidates = url_safety.resolve_host_addresses(hostname)
        if candidates and all(address in ipaddress.ip_network("198.18.0.0/15") for address in candidates):
            candidates = resolve_public_doh(hostname)
    error = url_safety.validate_public_http_url(url, resolver=lambda _hostname: candidates)
    if error:
        raise ValueError(error)
    if not candidates or any(url_safety.is_blocked_address(address) or not address.is_global for address in candidates):
        raise ValueError("来源没有可连接的公网地址")
    # Pin the connection address after screening, preserving Host and TLS SNI.
    # No private-address exception or hostname allowlist is introduced.
    return original.copy_with(host=str(candidates[0])), {"Host": original.netloc.decode("ascii")}, {"sni_hostname": hostname}


def acquire_source(evidence: EvidenceService, rid: str, url: str, title: str, organization: str, *, client: httpx.Client | None = None) -> dict:
    evidence._url(url)
    own_client = client is None
    client = client or httpx.Client(timeout=45, follow_redirects=False, trust_env=False)
    current, routes = url, []
    try:
        for _ in range(6):
            evidence._url(current)
            target, headers, extensions = public_target(current)
            with client.stream("GET", target, headers={**headers, "User-Agent": "EIQAS/0.1 public research"}, extensions=extensions) as response:
                routes.append({"url": current, "status": response.status_code})
                if response.is_redirect:
                    current = urljoin(current, response.headers.get("location", ""))
                    continue
                if response.status_code in {401, 403, 429}:
                    return evidence.record_source_failure(rid, url=url, title=title, organization=organization, status="restricted", reason=f"HTTP {response.status_code}")
                response.raise_for_status()
                parts, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > 64 * 1024 * 1024:
                        raise ValueError("原件超过 64 MiB")
                    parts.append(chunk)
                source = evidence.register_source(
                    rid, url=url, retrieved_url=current, title=title, organization=organization, content=b"".join(parts), media_type=response.headers.get("content-type", "application/octet-stream").split(";")[0]
                )
                # The requested URL stays canonical; retrieval routes are audit events.
                with evidence.research._connection() as db, db:
                    evidence.research._event(db, rid, "source.retrieved", {"id": source["id"], "routes": routes})
                return source
        raise ValueError("重定向次数超限")
    except (ValueError, httpx.HTTPError) as exc:
        if isinstance(exc, httpx.HTTPStatusError):
            reason = f"HTTP {exc.response.status_code}"
        else:
            reason = str(exc) if isinstance(exc, ValueError) else f"取得失败：{type(exc).__name__}"
        return evidence.record_source_failure(rid, url=url, title=title, organization=organization, reason=reason)
    finally:
        if own_client:
            client.close()
