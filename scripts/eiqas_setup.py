"""Prepare local single-user deployment without printing or overwriting secrets."""

import json
import os
import secrets
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def prepare_ocr_cache() -> str:
    subprocess.run(["docker", "volume", "create", "eiqas-ocr-cache"], check=True, capture_output=True, text=True)
    cache = subprocess.run(["docker", "volume", "inspect", "eiqas-ocr-cache", "--format", "{{.Mountpoint}}"], check=True, capture_output=True, text=True).stdout.strip()
    if not cache.startswith("/") or cache == "/" or any(character in cache for character in ["\n", "\r", ","]):
        raise ValueError("Docker OCR cache needs an absolute daemon mount path")
    # Only public model-cache files are mounted in this one-off initializer.
    subprocess.run(
        ["docker", "run", "--rm", "--network", "none", "--entrypoint", "/bin/sh", "--mount", "type=volume,source=eiqas-ocr-cache,target=/cache", "nginx:1.28.0-alpine", "-c", "chown -R 1000:1000 /cache"],
        check=True,
        capture_output=True,
        text=True,
    )
    return cache


def main():
    local = ROOT / ".eiqas"
    local.mkdir(exist_ok=True)
    (ROOT / ".deer-flow").mkdir(exist_ok=True)
    env = ROOT / ".env"
    if not env.exists():
        with env.open("x") as handle:
            handle.write(f"EIQAS_MODEL_ID=your-model-id\nOPENAI_BASE_URL=https://api.openai.com/v1\nOPENAI_API_KEY=\nBETTER_AUTH_SECRET={secrets.token_urlsafe(32)}\nDEER_FLOW_INTERNAL_AUTH_TOKEN={secrets.token_urlsafe(32)}\n")
        env.chmod(0o600)
    config = ROOT / "config.yaml"
    if not config.exists():
        config.write_bytes((ROOT / "config.eiqas.example.yaml").read_bytes())
    extensions = local / "extensions_config.json"
    if not extensions.exists():
        extensions.write_text(json.dumps({"mcpServers": {}, "skills": {}}))
    socket = os.environ.get("DEER_FLOW_DOCKER_SOCKET", "/var/run/docker.sock")
    context = subprocess.run(["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"], capture_output=True, text=True, check=True).stdout.strip()
    if context.startswith("unix://"):
        socket = context.removeprefix("unix://")
    cache = prepare_ocr_cache()
    (local / "deploy.env").write_text(f"EIQAS_OCR_CACHE_PATH={cache}\nEIQAS_HOST_STATE={ROOT / '.deer-flow'}\nDEER_FLOW_DOCKER_SOCKET={socket}\n")
    print("Prepared ignored .env, config.yaml and .eiqas/deploy.env. Configure your native model before starting.")


if __name__ == "__main__":
    main()
