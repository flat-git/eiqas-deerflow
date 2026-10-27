# EIQAS DeerFlow v0.1

## Goal and decisions

Independent public product on pinned DeerFlow v2.1.0. Single user, native model configuration, public-source research including Chinese/English OCR, real calculations, interactive reports and reproducible exports. Confirm a research plan once; ask again for material changes or unresolved evidence. No legacy EIQAS migration, drag/drop editor, shared-team deployment or public report hosting.

## Milestones

- [ ] M0 — repository, Project/Milestone/12 tasks, CI, runtime and real model/tool smoke.
- [ ] M1 — research records, plans, explicit confirmation and five-stage events.
- [ ] M2 — source acquisition, originals, PDF/OCR, datasets and correction.
- [ ] M3 — actual calculation, numerical validation, cancellation and partial results.
- [ ] M4 — workbench, interactive results/provenance, offline exports.
- [ ] M5 — real studies, OCR regression, reader trial and v0.1 release.

## Actual progress

2026-10-27: verified upstream commit; created the independent public repository, v0.1.0 Milestone, tasks #1–#12 and roadmap #13. Installed pinned backend dependencies; baseline tests are running. Docker is available. Frontend installation uses the pinned pnpm 10.26.2 because the host's pnpm 9 does not understand the lockfile configuration.

GitHub Projects 已授权。原生 DeepSeek 模型与实际领域工具往返已验证；密钥仅保留在忽略的本地环境文件。

## Evidence and acceptance

See [development notes](docs/eiqas-development.md) and the GitHub roadmap. Keep code completion, automated tests, real model calls, actual OCR and human trial separate. Close tasks only after their stated checks pass.


### 2026-10-27 implementation checkpoint

- Public repository and Project1 exist; all 12 issues plus roadmap are on the five-state board with Phase/Priority fields. Board layout/built-in automation still needs UI verification.
- PR #14 merged as b67a28b7 after all 11 remote CI checks passed (four full backend shards, default collection, frontend, blocking I/O, skill review, guidance and baseline).
- Native DeepSeek deepseek-flash adapter plus actual research tool round trip passed; secrets remain in ignored local .env. Full application startup still pending.
- M2 evidence preparation:10 tests; acquisition:3 tests. M3 methods:10 tests; combined runs/worker/evidence:29 tests passed. Actual Docker/OCR tests pending.
- Analysis image build encountered a missing context file, then a CPU index/requirements interaction. Dedicated minimal context now excludes all credentials/runtime data. CPU dependency lock is being repaired against official PyTorch/PyPI sources.
- Candidate correction, frozen datasets, run failure/cancellation/restart fences and read APIs are implemented. Native sandbox integration is in progress.
- Still required: actual OCR, structured results/export, full workbench, native browser flow, real case studies, reader trial, RC and final release. No stage exit is inferred from unit tests.

### 2026-10-27 — data, compute and reader integration

- 本地标准 Docker 应用已启动，用户已完成原生管理员创建。新 EIQAS 页面与扩展镜像正在部署。
- 68 项 EIQAS 后端测试通过，覆盖研究确认、资料、冻结数据、计算回执、失败/取消/中断、成果引用、物理页预检和四类导出。
- 真实 Docling2.143.0＋Tesseract OCR 回归通过：两页中英扫描表格的1200/1350/800/860、行列定位、中文字段、三页物理页码与原生文本分流。低清样例有实际解析记录；人工纠正路径仍需浏览器验收。
- 修复真实发现：Docling的CLI参数顺序使网格预处理被跳过；216DPI将860识别为260，改用已验证的288DPI。原件与定位坐标不变。
- 完整前端单元测试1632项通过（包含3项新增成果交互测试）；本机Node25需要禁用实验WebStorage以免与happy-dom冲突。生产使用Node22。类型/格式复查进行中。
- 五阶段工作台、原生对话、独立成果页、图表筛选、冻结数据依据、对话重算入口和离线HTML/MD/CSV/ZIP已实现。浏览器、离线断网与ZIP重跑验收未完成。
- 仍需：自定义Python方法、完整原生模型研究闭环、官方资料与世界银行案例、真实纠正操作、读者试读、Project布局/自动化核验、RC与发布。
