# Implementation and validation log

## 2026-10-27 — M0

- Repository created: https://github.com/flat-git/eiqas-deerflow
- Roadmap #13 and twelve scoped tasks created; v0.1.0 Milestone exists.
- Verified upstream v2.1.0 commit `345f08be00c8a9495079b732a39b46aa9af1584e`.
- Official GitHub CLI 2.103.3 download SHA256 verified against official checksums; existing account authentication reused. CLI is a local development tool, not a product dependency.
- `uv sync --frozen` installed the backend baseline. Full offline tests started before backend feature changes.
- Initial frontend frozen install failed because the host uses pnpm 9.15.9. Retried with the repository-pinned pnpm 10.26.2 without editing the lockfile or weakening the security override.
- Docker Engine 29.6.1 is running. Container/image and OCR validation remain pending.
- System Python urllib certificate configuration failed during the CLI download; system curl with normal TLS verification and published SHA256 validation succeeded.
- GitHub Projects access and a real model configuration require operator action; no secrets were read, copied or committed.

No research execution, OCR acceptance, reader trial or release has passed yet.
