"""Guard costly build-cache boundaries and the production image contract.

Real image startup and source-edit cache checks are recorded separately; these
checks catch accidental full-tree copies before downloading/building images.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_frontend_dependencies_precede_source():
    dockerfile = (ROOT / "frontend/Dockerfile").read_text(encoding="utf-8")
    assert dockerfile.index("pnpm install --frozen-lockfile") < dockerfile.index("COPY frontend ./frontend")


def test_frontend_production_uses_traced_output():
    dockerfile = (ROOT / "frontend/Dockerfile").read_text(encoding="utf-8")
    assert "NEXT_CONFIG_BUILD_OUTPUT=standalone" in dockerfile
    runtime = dockerfile.split(" AS prod\n", 1)[1]
    assert ".next/standalone" in runtime
    assert ".next/static" in runtime
    assert "/public" in runtime
    assert '"node", "server.js"' in runtime
    assert "pnpm install" not in runtime
    assert "COPY --from=builder /app/frontend ./frontend" not in runtime


def test_backend_external_dependencies_precede_source_and_runtime_excludes_tests():
    dockerfile = (ROOT / "backend/Dockerfile").read_text(encoding="utf-8")
    assert dockerfile.index("uv sync") < dockerfile.index("COPY backend ./backend")
    assert "--no-install-workspace" in dockerfile
    assert "--no-dev" in dockerfile
    runtime = dockerfile.split("# ── Stage 3: Runtime", 1)[1]
    assert "COPY --from=builder /app/backend ./backend" not in runtime
    assert "/app/backend/.venv" in runtime
    assert "/app/backend/extensions" in runtime
