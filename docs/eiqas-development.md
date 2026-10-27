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

## 联网链路修复与复验

用户再次反馈检索问题。实际区分为搜索、原件下载、正文解析和沙箱HTTPS：原生DuckDuckGo可取得官网/年报链接；匿名Jina正文服务返回401；沙箱W3C HTTPS成功但首次世界银行请求20秒超时，不能据此判定整个沙箱断网。

默认正文读取改为 `eiqas_research.tools:web_fetch_public`：下载受保护的公开原件，保存请求URL/最终URL和SHA-256，经同一原生AIO解析路径保留文本与链接定位；相对链接以最终URL解析。不会自动执行网页内容或访问其中链接，私网/loopback/metadata与重定向仍检查。HTTP状态与限制继续保存，不伪造成功回执。

`scripts/acceptance/public_network.py` 真实执行通过五项：原生搜索命中海尔官网；海尔网页371个定位块；W3C PDF一页；世界银行接口56个JSON定位块；原生沙箱内部HTTPS200。测试建立独立、明确标注模拟确认的验收研究，只销毁自己的沙箱，不确认或恢复用户研究。原生模型完整研究仍另行验收。

定量数据准备另发现：模型把数值先转成万元导致与原文不符；原值千元未登记支持；同一表行的增速百分号误报为绝对值单位冲突。新增回归后修复。统一换算只在冻结数据集执行；错误候选登记可审计撤回，不能修改原值或变成人工确认，真正OCR与口径问题仍保留门禁。当前扩展93项通过。

无本地凭据/操作员配置的独立检出完整测试17099 passed、188 skipped、3 deselected；阻塞IO143 passed。此前全局配置变量引发的测试隔离干扰已通过干净检出消除，没有放宽生产校验。

另修复容器更新后的入口502：Nginx曾缓存被替换容器的旧IP，改用Docker内置DNS与带共享zone的动态upstream。实际 `nginx -t` 通过；工作台可重新加载、API返回预期401认证响应。原生API重写与SSE缓冲关闭保持原状。新增回归后领域测试93项通过。

## 真实成果与交付复核

定制检查脚本连续失败的根因是checks.json写成裸数组，工具说明不够明确。现在明确对象契约并给出可操作错误；失败也绑定本次输入/脚本哈希，不再误报成身份不匹配。新增实际子进程回归，领域94项通过。没有放宽逐个数值独立expected与冻结输入provenance要求。

美的／海尔研究随后产生26行、26项独立检查的真实Python运行，以及6张来源可追溯图表。复核修正了“分子变化而非分母变化”误读，以及把国内AI提效与集团整体费用率上升视为冲突的区域口径错误。过时失败保留在运行历史，不作为当前执行状态。每次文字修订产生新成果，旧稿没有覆盖。

公司研究HTML/Markdown/CSV/ZIP全部生成；包内每个文件哈希通过，断网分析容器重跑后26行与26项检查逐项一致。包内包含实际引用的3份原件，不遍历所有研究附件。合成成本收益场景亦通过实际容器、独立Decimal复算、参数新运行与旧回执不变检查，脚本为 `scripts/acceptance/synthetic_scenario.py`。

新增离线Chromium验收：真实file://打开自包含HTML，网络离线，图表实际画布、联动筛选、依据弹窗和CSV下载均正常；ZIP的index.html原件链接均解析到真实包内相对路径。1366/1440共3项通过。试读前修正百分号/百分点显示，次要限制可以展开，原限制信息保留；前端完整1634项、布局9项和类型/生产构建均通过。

干净检出c0a257de全后端17111 passed、188 skipped、3 deselected。最新跟进修复仍以对应提交的完整CI为准。草稿PR #15不再跳过完整原生测试。Project已保存为五列看板，公开浏览器实际显示Backlog/Ready/In progress/In review/Done，入库/关闭工作流启用。

实际读者试读、世界银行研究修订方案确认已提出请求；用户自建海尔舆情研究的暂停选择没有被覆盖。未完成实际人工/OCR纠正、完整原生浏览器路径、OCR模型revision锁定及RC/正式发布，不标记产品全部完成。
