"""A native tool uses its existing DeerFlow sandbox; no second run scheduler."""

import asyncio
import hashlib
import json
import shlex
import threading
import uuid
from pathlib import Path

from . import worker


async def execute_job_async(sandbox, operation: str, data: bytes, media_type: str = "application/octet-stream") -> tuple[dict, str]:
    """Signal the real job on cancellation and drain it, including repeated stops."""
    cancel = threading.Event()
    job = asyncio.create_task(asyncio.to_thread(execute_job, sandbox, operation, data, media_type, cancel_event=cancel))
    try:
        return await asyncio.shield(job)
    except asyncio.CancelledError:
        cancel.set()
        while not job.done():
            try:
                await asyncio.wait({job})
            except asyncio.CancelledError:
                continue
        if not job.cancelled():
            job.exception()
        raise


def execute_job(sandbox, operation: str, data: bytes, media_type: str = "application/octet-stream", *, cancel_event: threading.Event | None = None) -> tuple[dict, str]:
    cancel = cancel_event if cancel_event is not None else threading.Event()

    def check_cancelled():
        if cancel.is_set():
            raise InterruptedError("EIQAS job cancelled")

    check_cancelled()
    execute = getattr(sandbox, "execute_command_cancellable", None)
    if not callable(execute):
        raise ValueError("本版解析与计算需要支持可取消任务的 AIO 沙箱，请更新 Gateway")
    directory = f"/mnt/user-data/workspace/eiqas/jobs/{uuid.uuid4().hex}"
    script = Path(worker.__file__).read_bytes()
    sandbox.execute_command(f"mkdir -p {shlex.quote(directory)}")
    check_cancelled()
    sandbox.update_file(f"{directory}/input.bin", data)
    check_cancelled()
    sandbox.update_file(f"{directory}/script.py", script)
    check_cancelled()
    command = shlex.join(["/opt/eiqas-venv/bin/python", f"{directory}/script.py", operation, "--input", f"{directory}/input.bin", "--output", f"{directory}/result.json", "--media-type", media_type])
    log = execute(command, cancel_event=cancel, timeout=600)
    check_cancelled()
    payload = sandbox.download_file(f"{directory}/result.json")
    check_cancelled()
    if len(payload) > 64 * 1024 * 1024:
        raise ValueError("解析或计算输出超过 64 MiB")
    result = json.loads(payload)
    if result.get("status") == "failed":
        return result, log
    if result.get("worker_sha256") != hashlib.sha256(script).hexdigest() or result.get("request_sha256") != hashlib.sha256(data).hexdigest():
        raise ValueError("沙箱输出的脚本或输入哈希不匹配")
    return result, log
