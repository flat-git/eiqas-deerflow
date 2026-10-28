"""Compose container replacement must not leave nginx using stale backend IPs."""

from pathlib import Path


def test_proxy_reresolves_recreated_compose_services_and_preserves_api_prefix():
    config = (Path(__file__).resolve().parents[2] / "docker/eiqas/nginx.conf").read_text()
    assert "resolver 127.0.0.11" in config
    for service, port in [("gateway", 8001), ("frontend", 3000)]:
        assert f"server {service}:{port} resolve;" in config
        assert f"zone eiqas_{service} " in config
    assert "proxy_pass http://eiqas_gateway/api/;" in config
    assert "proxy_buffering off;" in config
