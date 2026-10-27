"""A native tool uses its existing DeerFlow sandbox; no second run scheduler."""

import hashlib
import json
import shlex
import uuid
from pathlib import Path

from . import worker


def execute_job(sandbox, operation: str, data: bytes, media_type: str = "application/octet-stream") -> tuple[dict, str]:
    directory = f"/mnt/user-data/workspace/eiqas/jobs/{uuid.uuid4().hex}"
    script = Path(worker.__file__).read_bytes()
    sandbox.execute_command(f"mkdir -p {shlex.quote(directory)}")
    sandbox.update_file(f"{directory}/input.bin", data)
    sandbox.update_file(f"{directory}/script.py", script)
    command = shlex.join(["/opt/eiqas-venv/bin/python", f"{directory}/script.py", operation, "--input", f"{directory}/input.bin", "--output", f"{directory}/result.json", "--media-type", media_type])
    log = sandbox.execute_command(command, timeout=600)
    payload = sandbox.download_file(f"{directory}/result.json")
    if len(payload) > 64 * 1024 * 1024:
        raise ValueError("解析或计算输出超过 64 MiB")
    result = json.loads(payload)
    if result.get("status") == "failed":
        return result, log
    if result.get("worker_sha256") != hashlib.sha256(script).hexdigest() or result.get("request_sha256") != hashlib.sha256(data).hexdigest():
        raise ValueError("沙箱输出的脚本或输入哈希不匹配")
    return result, log
