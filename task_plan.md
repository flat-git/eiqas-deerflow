# EIQAS DeerFlow v0.1

## 当前开发：2026-10-29 研究设计闭环

用户已授权 Git 备份后开发。基线68ec48b5已备份，分支 codex/research-design-loop，Issue #17。方法—数据可行性、分类缺口、可回答范围、重拟方案与最终确认已接入；修改前17128项后端和143项阻塞IO通过，当前前端1639项、断网容器与导出重跑通过。最终17156项后端、138项领域、1639项前端、12项浏览器、生产构建与断网容器通过；真实DeepSeek完成合成草稿自修复。完整无人代修研究与试读仍待验证；不合并、不发布，不把测试报告代修算作自主化验收。详见 docs/research-design-loop.md。

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

### 联网与真实数据准备复验

- 自定义Python计算及独立检查已实现并通过回归；断网容器计算、四类导出和ZIP实际重跑已通过。离线HTML浏览器交互仍待验收。
- 默认Jina正文服务实际返回401；已改为EIQAS直接取得公开原件，经原生AIO解析并保存定位。真实原生搜索、海尔网页、W3C PDF、世界银行JSON和沙箱内HTTPS五项均通过。脚本为 `scripts/acceptance/public_network.py`，回执在忽略的 `.deer-flow/acceptance/network-fixed`。
- 真实年报准备发现千元缺失、相邻增速百分号误报及Agent提前换算。已补单位归一化和回归，候选必须登记原值/原单位；Agent可审计撤回未核对错误登记，不能批准、改写或撤回已核对数据。
- 新增线程内记录读取工具，刷新或上下文压缩后可恢复已有来源、数据集与运行；提取元数据不会返回整个PDF文本。
- 独立无操作员配置检出：完整后端17099 passed、188 skipped、3 deselected；阻塞IO143 passed。当前扩展93 passed。最终变更的完整CI复验与真实研究成果仍在进行。
- 尚未通过实际读者试读，未创建RC或正式Release；所有需要实际验收的Issue保持开放。

### 真实成果、交付与试读候选

- 美的／海尔原生研究已经完成真实Python比率计算：26行、26项独立复算通过，产生6张图。文字复核纠正了分子/分母同时变化、区域费用口径及过时失败标记；没有将公司自报等同于AI能力或因果成效。
- 真实成果四类导出、显式包内文件哈希及断网容器重跑通过。ZIP按实际引用包含3份原件；所有4份原件仍保留在研究记录，不扩大打包范围。
- 自制合成成本收益/折现率情景已在断网容器通过，参数变化产生新运行，旧回执不变。原生页面参数重算仍待验收。
- 当前领域94项、前端完整1634项通过；桌面布局9项与离线浏览器3项通过，最新前端镜像已部署。干净检出c0a257de完整后端17111 passed；最新诊断修复的完整CI仍待复验。
- PR #15已建立并附到任务，未合并。草稿也将执行完整CI，不再跳过原生回归门禁。Project已切换并实际核对五列看板，入库/关闭自动化已启用。
- 已请求实际读者试读；世界银行修订方案v2等待本人工作台确认，不能将网络自检当作该研究已完成。其余明确未完成项见验收文档。没有RC或Release。
