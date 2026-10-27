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

## 2026-10-27 — 可验证的纵向实现

- 模型：原生 `PatchedChatDeepSeek` 使用用户选择的 deepseek-flash，完成实际工具请求→领域服务→模型答复。该项通过不等于完整 Agent 研究闭环。
- OCR：实际分析镜像通过自制中英扫描表格与原生文本混合PDF回归；全部11项检查通过。只对扫描页做OCR；扫描表格输入仍进入人工核对队列。
- 计算：DuckDB/Pandas/Scipy真实运算，Decimal/numpy独立复核。每次保留输入、脚本、日志、JSON、CSV与哈希；未确认方法、未执行、失败检查和迟到取消结果均不能成为已校验成果。
- 数据：保留原始文字、单位、修饰词、来源/提取哈希、物理页或表格定位。已核对的自定义单位可原样使用；上限/下限/区间不能伪装成精确值。
- 交付：同一成果快照生成HTML/Markdown/CSV/ZIP；ECharts6.1.0固定资产及许可证随包。ZIP显式列出被引用原件、提取记录、冻结输入和计算材料，不遍历运行目录。
- 前端：中文五阶段工作台复用原生线程、模型和流；独立成果保留当前结果标识，新运行需读者主动打开。新增交互组件测试3项，完整单元测试1632项通过。

本次证据位于忽略目录 `.eiqas/acceptance/ocr` 与 `.deer-flow/acceptance`。公开仓库只提交合成样例生成器、检查程序和汇总验收记录，不提交原始研究运行资料。全后端回归、桌面浏览器、独立重算和真实案例仍在推进。

## 用户试用发现：工作台滚动被裁切

在真实研究页面量测到外层网格高度742px，但隐式行被长方案撑至约4196px；正文自身高度等于内容高度，因此滚轮没有独立滚动区，外层hidden反而会被输入框聚焦带动跳转。修复为外层网格显式 `minmax(0,1fr)` 行、workspace/main的 `min-height:0` 与嵌套滚动边界。

修复前两个workbench浏览器回归在1366/1440失败；修复后workbench/reader四项真实wheel输入测试通过，验证正文/对话互不带动、页头稳定、输入框可见、文档不超出视口。这是布局回归，完整真实研究与实际读者验收仍独立保留。

补充真实页面回查：正文高度680px、内容约2995px；滚动后正文scrollTop=680、外层scrollTop=0、顶部top=0、输入框底边665px（视口742px）。随后覆盖980px紧凑窗口，移除全局最小宽度，并避免输入框样式覆盖原生隐藏文件选择器；980/1366/1440下共6项浏览器回归通过。

确认门禁另发现：计划分析问题可能是原始请求的合理重述，不能用两段文字逐字相等判断目标变化。改为在保存时绑定原始研究问题SHA-256，确认同时核对方案hash与问题hash；实际问题变化仍撤销确认。新增回归后EIQAS后端77项通过。

完整本机后端复验曾受本地操作员插件影响4项通用原生假设；全局配置路径又干扰16项自行建立配置的子进程测试。已恢复测试写入的示例demo条目，将在不含本地凭据/配置的独立Git检出复验，与CI保持一致，不放宽生产门禁。

## 真实闭环发现与修复

- 用户反馈AI追问卡片长选项互相重叠。原因是原生固定按钮高度与多行中文不匹配；在EIQAS作用域改为内容自适应高度。300/332/368px对话栏回归3项通过，加上滚动共9项。真实页面选项高度76/96/96/56px，标签均在自身边界内。
- 本机代理将公网域名解析为198.18/15合成地址，取得工具按既有规则拒绝。仅对该合成地址范围使用固定TLS校验的公共DoH解析，并将连接固定到重新校验的公网IP，保留原始Host/TLS SNI；私网、loopback、metadata与每次重定向仍被拒绝，不增加私网例外。
- 原生AIO绑定源必须为绝对路径。设置脚本创建独立OCR卷、读取Docker守护进程的Mountpoint，并通过部署环境传入配置。缓存初始化只挂载公开模型卷，赋予AIO用户写权限。
- 对应新增4项回归，EIQAS测试总计81项通过；前端类型与lint通过。实际模型重试后已下载原件并产生4份PDF提取记录，定量计算与报告仍在进行。
