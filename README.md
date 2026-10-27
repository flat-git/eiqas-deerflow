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

Python 3.12+、Node.js 22+、**pnpm 10.26.2**、uv、Docker Desktop/Engine。基线运行命令沿用上游；EIQAS 标准配置与分析镜像正在开发，当前请以任务验收记录为准。

```sh
# 在各自目录安装锁定依赖，不使用系统中较旧的 pnpm：
cd backend
uv sync --frozen
cd ../frontend
npx --yes pnpm@10.26.2 install --frozen-lockfile
```

真实模型验证需要在本机配置凭据；CI 只运行不依赖密钥的测试。不要把密钥粘贴到 Issue、PR 或提交中。

## Contributing / English

EIQAS is an independent, early-stage quantitative business research product built on DeerFlow. It connects research questions, public evidence, executable analysis and interactive findings. See the roadmap for implemented and pending capabilities. Use issue-linked feature branches, small pull requests and Conventional Commits. Do not submit research data or credentials.

## License

MIT. Original DeerFlow copyright and third-party notices are retained. This independent project is not an official ByteDance release.
