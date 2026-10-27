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

## 研究契约实现

- 新包 `eiqas-research` 通过公开插件注册，无 Harness 核心循环修改。
- 首批流程测试：14 passed；证据链测试另属后续任务，尚未作为 M1 验收。
- 固定 pnpm 10.26.2 安装及前端基线 check 成功。Docker29.6.1就绪，AIO1.11.0 ARM 镜像已下载。
- 修改前完整后端：17002 passed、16 failed、188 skipped；15 项网页工具失败来自未隔离的 DNS 依赖，1 项来自产品化后工作流路径变更。局部修复后相关测试184 passed、1 skipped；完整复验进行中。生产 URL 防护保持原样。
- 修改前和修改后阻塞 IO 均143 passed。
- GitHub Project1已公开，含五个状态、阶段和优先级字段。真实模型和读者试读仍未完成。
