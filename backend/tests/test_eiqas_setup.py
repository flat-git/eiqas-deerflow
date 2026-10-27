"""The native AIO provider takes absolute bind sources, not volume names."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location("eiqas_setup_script", Path(__file__).resolve().parents[2] / "scripts/eiqas_setup.py")
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


def test_ocr_volume_uses_verified_absolute_daemon_path(monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(stdout="/var/lib/docker/volumes/eiqas-ocr-cache/_data\n" if "inspect" in command else "")

    monkeypatch.setattr(setup.subprocess, "run", run)
    assert setup.prepare_ocr_cache() == "/var/lib/docker/volumes/eiqas-ocr-cache/_data"
    assert any(command[:3] == ["docker", "volume", "create"] for command in calls)
    assert any("type=volume,source=eiqas-ocr-cache,target=/cache" in command for command in calls)


def test_non_absolute_cache_path_is_rejected(monkeypatch):
    monkeypatch.setattr(setup.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(stdout="eiqas-ocr-cache\n"))
    with pytest.raises(ValueError):
        setup.prepare_ocr_cache()
