"""Real AIO cancellation probe with synthetic processes; no model key or study edits.

uv run --project backend python scripts/acceptance/cancellation.py --base-url http://127.0.0.1:8080
Run inside Gateway with host.docker.internal for a Docker-host sandbox.
"""

import argparse
import json
import shlex
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from deerflow.community.aio_sandbox.aio_sandbox import AioSandbox


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url", required=True, help="An already running test AIO sandbox API"
    )
    args = parser.parse_args()
    sandbox = AioSandbox(id="synthetic-cancel-probe", base_url=args.base_url)
    marker = f"/mnt/user-data/workspace/eiqas-cancel-probe-{uuid.uuid4().hex}.json"
    code = f"import os,subprocess,time,json; from pathlib import Path; child=subprocess.Popen(['sleep','120']); Path({marker!r}).write_text(json.dumps([os.getpid(),child.pid])); time.sleep(120)"
    cancel = threading.Event()
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                sandbox.execute_command_cancellable,
                shlex.join(["python3", "-c", code]),
                cancel_event=cancel,
                timeout=120,
            )
            try:
                pids = None
                for _ in range(100):
                    try:
                        pids = json.loads(sandbox.read_file(marker))
                        break
                    except Exception:
                        if future.done():
                            future.result()
                        time.sleep(0.1)
                assert pids, "synthetic process did not start"
                started = time.monotonic()
                cancel.set()
                try:
                    future.result(timeout=15)
                    raise AssertionError("cancelled job returned success")
                except InterruptedError:
                    pass
                elapsed = time.monotonic() - started
                check = (
                    "import os,json; print(json.dumps([p for p in "
                    + repr(pids)
                    + " if os.path.exists('/proc/'+str(p)) and open('/proc/'+str(p)+'/stat').read().split()[2]!='Z']))"
                )
                remaining = sandbox.execute_command_cancellable(
                    shlex.join(["python3", "-c", check]),
                    cancel_event=threading.Event(),
                    timeout=10,
                )
                assert json.loads(remaining) == [], remaining
                try:
                    sandbox.execute_command_cancellable(
                        "sleep 120", cancel_event=threading.Event(), timeout=2
                    )
                    raise AssertionError("hard timeout returned success")
                except TimeoutError:
                    pass
                resumed = sandbox.execute_command_cancellable(
                    "printf resumed", cancel_event=threading.Event(), timeout=10
                )
                assert resumed == "resumed", resumed
                print(
                    json.dumps(
                        {
                            "cancel_seconds": round(elapsed, 2),
                            "descendants_remaining": 0,
                            "hard_timeout": "passed",
                            "next_command": resumed,
                        }
                    )
                )
            finally:
                cancel.set()
    finally:
        try:
            sandbox.execute_command_cancellable(
                shlex.join(["rm", "-f", marker]),
                cancel_event=threading.Event(),
                timeout=10,
            )
        finally:
            sandbox.close()


if __name__ == "__main__":
    main()
