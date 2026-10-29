"""Stopping research must stop its actual job before the native thread is reusable."""

import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from eiqas_research import sandbox_jobs


@pytest.fixture
def sandbox():
    from deerflow.community.aio_sandbox.aio_sandbox import AioSandbox

    with patch("deerflow.community.aio_sandbox.aio_sandbox.AioSandboxClient"):
        return AioSandbox(id="cancel-test", base_url="http://localhost:8080")


def response(status, output="", exit_code=None):
    return SimpleNamespace(data=SimpleNamespace(status=status, output=output, exit_code=exit_code))


def test_cancel_stops_only_its_explicit_session_and_releases_it(sandbox):
    cancel = threading.Event()
    shell = sandbox._client.shell

    def wait(**kwargs):
        cancel.set()
        return response("running")

    shell.exec_command.return_value = response("running")
    shell.wait_for_process.side_effect = wait
    with pytest.raises(InterruptedError):
        sandbox.execute_command_cancellable("python parse.py", cancel_event=cancel, timeout=600)
    session = shell.create_session.call_args.kwargs["id"]
    assert shell.exec_command.call_args.kwargs["id"] == session
    assert shell.exec_command.call_args.kwargs["async_mode"] is True
    assert shell.exec_command.call_args.kwargs["hard_timeout"] == 600
    assert shell.kill_process.call_args.kwargs["id"] == session
    assert shell.cleanup_session.call_args.args == (session,)
    assert not sandbox._scoped_shell_sessions
    # Cancellation does not close the shared client or affect another session.
    shell.cleanup_all_sessions.assert_not_called()
    sandbox._client.close.assert_not_called()


def test_pre_cancelled_job_never_starts(sandbox):
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(InterruptedError):
        sandbox.execute_command_cancellable("unused", cancel_event=cancel)
    sandbox._client.shell.exec_command.assert_not_called()


@pytest.mark.parametrize("status", ["hard_timeout", "terminated", "unexpected"])
def test_timeout_and_invalid_status_fail_and_clean_up(sandbox, status):
    shell = sandbox._client.shell
    shell.exec_command.return_value = response(status)
    with pytest.raises((TimeoutError, RuntimeError)):
        sandbox.execute_command_cancellable("unused", cancel_event=threading.Event(), timeout=5)
    shell.kill_process.assert_called_once()
    shell.cleanup_session.assert_called_once()
    assert not sandbox._scoped_shell_sessions


def test_completed_command_preserves_output_and_exit_code(sandbox):
    shell = sandbox._client.shell
    shell.exec_command.return_value = response("running")
    shell.wait_for_process.return_value = response("completed")
    shell.view.return_value = response("completed", "failed check", 2)
    assert sandbox.execute_command_cancellable("unused", cancel_event=threading.Event()) == "failed check\nExit Code: 2"
    shell.kill_process.assert_not_called()
    shell.cleanup_session.assert_called_once()


@pytest.mark.asyncio
async def test_repeated_cancellation_signals_and_drains_the_same_job(monkeypatch):
    started, signalled, release, finished = (threading.Event() for _ in range(4))

    def execute(*args, cancel_event, **kwargs):
        started.set()
        try:
            assert cancel_event.wait(3)
            signalled.set()
            assert release.wait(3)
            raise InterruptedError("remote job stopped")
        finally:
            finished.set()

    monkeypatch.setattr(sandbox_jobs, "execute_job", execute)
    task = asyncio.create_task(sandbox_jobs.execute_job_async(object(), "parse", b"synthetic"))
    try:
        assert await asyncio.to_thread(started.wait, 3)
        task.cancel()
        assert await asyncio.to_thread(signalled.wait, 3)
        task.cancel()
        await asyncio.sleep(0)  # Deliver the second cancellation, without a timing assumption.
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)
        assert finished.is_set()
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


def test_cancelled_queued_job_cannot_upload_or_launch():
    cancel = threading.Event()
    cancel.set()
    sandbox = MagicMock()
    with pytest.raises(InterruptedError):
        sandbox_jobs.execute_job(sandbox, "parse", b"synthetic", cancel_event=cancel)
    sandbox.execute_command.assert_not_called()
    sandbox.update_file.assert_not_called()
    sandbox.execute_command_cancellable.assert_not_called()


@pytest.mark.asyncio
async def test_native_thread_rejects_overlap_then_accepts_after_job_cancel(monkeypatch):
    from deerflow.extensions.registry import LoadedExtensions
    from deerflow.runtime.runs.manager import ConflictError, RunManager
    from deerflow.runtime.runs.schemas import RunStatus
    from deerflow.runtime.runs.worker import RunContext, run_agent

    started, signalled, release = (threading.Event() for _ in range(3))

    def execute(*args, cancel_event, **kwargs):
        started.set()
        assert cancel_event.wait(3)
        signalled.set()
        assert release.wait(3)
        raise InterruptedError("job stopped")

    monkeypatch.setattr(sandbox_jobs, "execute_job", execute)
    manager = RunManager()
    record = await manager.create_or_reject("cancel-resume-thread")
    bridge = SimpleNamespace(publish=AsyncMock(), publish_end=AsyncMock(), cleanup=AsyncMock())

    class Agent:
        async def astream(self, *args, **kwargs):
            await sandbox_jobs.execute_job_async(object(), "parse", b"synthetic")
            yield "unreachable"

    task = asyncio.create_task(run_agent(bridge, manager, record, ctx=RunContext(checkpointer=None, extensions=LoadedExtensions(app_store=MagicMock())), agent_factory=lambda **kwargs: Agent(), graph_input={}, config={}))
    record.task = task
    try:
        assert await asyncio.to_thread(started.wait, 3)
        await manager.cancel(record.run_id)
        assert await asyncio.to_thread(signalled.wait, 3)
        assert record.status == RunStatus.interrupted
        with pytest.raises(ConflictError, match="active run"):
            await manager.create_or_reject(record.thread_id)
        release.set()
        await asyncio.wait_for(task, 3)
        assert not record.finalizing
        bridge.publish_end.assert_awaited_once_with(record.run_id)
        replacement = await manager.create_or_reject(record.thread_id)
        assert replacement.run_id != record.run_id
    finally:
        release.set()
        await manager.cancel(record.run_id)
        await asyncio.gather(task, return_exceptions=True)
