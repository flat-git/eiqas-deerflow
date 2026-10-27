# EIQAS 业务扩展

产品基于固定的 DeerFlow v2.1.0，在其原生线程、模型、流式事件和沙箱上运行。`backend/packages/eiqas-research` 是独立 Python workspace 包；插件通过公开 `deerflow-extension-api` 注册服务、路由与模型请求中间件，没有修改 Harness 循环。

## 研究与确认

一项研究绑定一个线程，数据库强制线程唯一。业务数据保存在独立 SQLite，资料目录按线程隔离。`/api/eiqas/research` 提供创建、读取和列表，研究下的 `question`、`plan`、`confirm`、`stage`、`scope` 与 `events` 提供相应操作。

方案包含问题、带理由的方法、所需数据、假设、预期产出及限制。规范 JSON 的 SHA-256 标识当前方案；工作台确认请求必须带上预览时的哈希。问题或方案变更后，执行门禁拒绝使用旧确认。完全相同的保存保留确认。确认只暴露为网页操作，Agent 工具没有该能力。

五个阶段可往返。执行状态、可以回答的问题和数据缺口分别保存，不计算总体研究完成百分比。每次业务更新与事件在同一 SQLite 事务提交；按序号读取事件可恢复刷新后的状态。Agent 会话、运行取消和 SSE 仍属于 DeerFlow。

## 依赖与运行

`config.eiqas.example.yaml` 使用原生模型适配和工具声明。模型 ID、地址及凭据由部署者在本地环境配置，不写入研究或 Git。`ResearchContext` 仅为关联研究的模型请求补充当前业务上下文，不创建新的 Agent 或调度器。

业务 I/O 使用同步领域方法；FastAPI 同步路由和原生同步工具在线程池执行。插件生命周期与异步模型钩子使用 `asyncio.to_thread`。单 Gateway worker、单用户为本版边界。

## 实施与验收状态

研究记录和确认的首批 14 项离线测试已通过。界面、实际模型推进、OCR、计算和交付分阶段实现与验收，不能从这些契约测试推定端到端完成。以 `docs/v0.1-acceptance.md` 和 GitHub Issue 中的实际证据为准。
