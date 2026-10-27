# EIQAS · DeerFlow Edition

围绕问题组织、以真实定量分析为依据的开源商业研究工作台。

本项目基于 DeerFlow v2.1.0 独立开发，当前处于 **v0.1 实施阶段**，尚未通过完整产品验收。计划能力与已验证能力分开记录，不将原版 DeerFlow 的功能演示作为 EIQAS 验收。

- [路线图与实际进度](https://github.com/flat-git/eiqas-deerflow/issues/13)
- [v0.1 里程碑](https://github.com/flat-git/eiqas-deerflow/milestone/1)
- [实施计划](task_plan.md)
- [上游基线与许可证](UPSTREAM.md)

## 产品方向

研究路径按问题组合，不按竞品或长短期分类。默认流程为：明确问题 → 设计方案 → 准备数据 → 计算分析 → 复核交付，可回看、迭代和补充资料。

v0.1 的目标是：公开资料检索与原件保存、中英文 PDF/扫描 OCR、数据与口径核对、真实 Python/SQL 计算、图表交互和可回查的报告。方案确认一次后自动推进，关键缺口或口径变化再询问。

本机单用户，使用部署者自己的模型配置。原始资料、凭据和生成的研究保存在运行目录，不提交到本仓库。不迁移其他版本 EIQAS 的资料或历史。

## 开发基线

Python 3.12+、Node.js 22+、**pnpm 10.26.2**、uv、Docker Desktop/Engine。标准运行使用独立 Compose 与 CPU 分析镜像，默认仅监听本机。仍在进行真实研究、桌面试用及完整交付验收。

```sh
# 在各自目录安装锁定依赖，不使用系统中较旧的 pnpm：
cd backend
uv sync --frozen
cd ../frontend
npx --yes pnpm@10.26.2 install --frozen-lockfile
```

真实模型验证需要在本机配置凭据；CI 只运行不依赖密钥的测试。不要把密钥粘贴到 Issue、PR 或提交中。

## 本地启动

```sh
python3 scripts/eiqas_setup.py
# 在忽略的 .env 中配置模型ID、地址与密钥；如有需要，调整 config.yaml 原生适配器。
docker compose --env-file .env --env-file .eiqas/deploy.env -f compose.eiqas.yaml --profile build build
docker compose --env-file .env --env-file .eiqas/deploy.env -f compose.eiqas.yaml up -d --wait nginx frontend gateway
```

打开 [研究工作台](http://127.0.0.1:2026/research)，首次由本人创建本地管理员。创建问题、讨论并确认方案后自动推进；在数据核对队列处理关键冲突和OCR存疑值。成果页提供图表、来源、参数重算及离线交付。具体运行与验证说明见 [English Quickstart](docs/quickstart-en.md)。

默认搜索复用原生 DuckDuckGo；默认正文读取由 EIQAS 直接下载公开原件并在原生 AIO 沙箱解析，无需第三方正文读取服务的密钥。网页保留哈希、文本定位及原文链接；重定向逐次检查公网地址，访问受限、超时和解析失败分别保留记录。搜索摘要仅作为线索。

## Contributing / English

EIQAS is an independent, early-stage quantitative business research product built on DeerFlow. It connects research questions, public evidence, executable analysis and interactive findings. See the roadmap for implemented and pending capabilities. Use issue-linked feature branches, small pull requests and Conventional Commits. Do not submit research data or credentials.

## License

MIT. Original DeerFlow copyright and third-party notices are retained. This independent project is not an official ByteDance release.

## 当前可验证实现

独立业务扩展已贯通研究确认、原件保存、定位提取、数据核对、冻结数据集、真实计算回执、交互成果和HTML/Markdown/CSV/ZIP导出；五阶段页面复用原生模型、线程和对话。生成的Python方法在分析沙箱执行，并由第二个程序独立复核每个数值单元格。

已通过原生模型/工具往返、自制中英扫描OCR、94项EIQAS后端测试、1634项完整前端单元测试、九项桌面滚动与追问布局测试、三项断网HTML浏览器测试，以及实际容器计算与ZIP重跑。美的／海尔案例已生成6张图和26项逐格复算；合成成本收益情景亦通过。真实联网自检覆盖原生搜索、海尔网页、公开PDF、世界银行JSON与沙箱内HTTPS。跨主题真实研究、完整浏览器交互与读者试读仍待验收。参见[架构与接口](docs/architecture-eiqas.md)、[实际验收记录](docs/v0.1-acceptance.md)和[第三方声明](THIRD_PARTY_NOTICES.md)。

[公开进度看板](https://github.com/users/flat-git/projects/1)按M0—M5跟踪实际验收，未完成的验收任务保持开放。
