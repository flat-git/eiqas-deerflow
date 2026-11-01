# 构建与本地空间管理

## 构建契约

前端先复制 package.json、pnpm-lock.yaml 和 pnpm-workspace.yaml，再安装固定版本的依赖，最后复制源码。dev 保留开发方式；prod 使用 Next.js standalone，只带生成的服务器、追踪到的依赖、public 和 .next/static。Node 以 server.js 启动，无需生产容器中运行 pnpm；环境变量由 Compose 在启动时注入。标准入口仍为 Nginx，API 和 SSE 路由不变。

Gateway 首层仅使用根 pyproject.toml 和 uv.lock 安装外部生产依赖。使用 uv 的 --frozen/--no-install-workspace，在暂缺 workspace 源码时复用锁文件；暂不安装 extensions 组。源码复制后，--locked --no-dev 同步会验证所有 workspace 元数据，并安装已登记的 extensions 组。redis 与经过字符校验的 UV_EXTRAS 在所有阶段保留；dev target 额外安装开发依赖。生产镜像保留 app、packages、extensions、虚拟环境及必要项目元数据，排除测试、样例及开发脚本。扩展源码快照仍完整进入构建上下文。

这会减少代码迭代带来的依赖安装层重复。本地类型检查缓存、测试产物和开发指引不进入构建上下文。生成输出仍会产生构建缓存，需要定期维护；不保证 Docker 总占用不会增长。

## 安全迭代

1. 给当前容器引用的镜像 ID 加回退标签，保留至少一个已验证版本。
2. 用候选标签构建；不要用 --no-cache 做日常迭代。标准 Compose 构建方式不变。
3. 用临时目录、独立 Compose 项目及仅监听本机的端口验证，避免挂载真实研究目录或生产密钥。
4. 普通源码改动后再构建，确认依赖安装步骤为 CACHED；依赖清单变动时应正常重建。
5. 检查通过后再更新服务。用户研究运行期间不得通过重启强行结束任务。

## 定向缓存维护

先用 `docker system df` 和 `docker buildx du --format json` 查看实际占用与记录。镜像与缓存共享层，数值不能相加；保留当前、候选和回退镜像后，才移除已确认无用的构建记录。

共享 Docker Desktop builder 不属于单一仓库。不要执行全局 system prune、volume prune 或改动其他项目的保留策略。对本仓库已核对的缓存 ID，可逐个执行：

```sh
docker buildx prune --filter id=已核对的缓存记录ID --force
```

定期维护时可先查看包含 /app/frontend、/app/backend 的构建描述，核对项目归属后再按 ID 清理长期未用记录。新依赖层和可复用构建层保留；不用把清理加入每次构建命令，也不清理研究文件、数据库、模型/OCR 缓存或卷。

Docker Desktop 的虚拟磁盘文件尺寸不会总是立即缩小。记录 BuildKit 实际回收量，同时观察宿主可用空间；不要把镜像标称缩减量当成额外回收空间。

参考：[Docker 缓存分层](https://docs.docker.com/build/cache/optimize/)、[uv workspace 容器安装](https://docs.astral.sh/uv/guides/integration/docker/)、[Next.js standalone](https://nextjs.org/docs/app/api-reference/config/next-config-js/output)、[定向缓存清理](https://docs.docker.com/reference/cli/docker/buildx/prune/)。

## 验证状态

2026-11-01 在 Apple Silicon / Docker Desktop 实测：

| 对象 | 原镜像 | 新候选镜像 |
| --- | ---: | ---: |
| Frontend | 2.85 GB | 478 MB |
| Gateway | 1.98 GB | 1.70 GB |

以上为 `docker image ls` / `docker system df` 的同一磁盘口径，不与 manifest 压缩大小混用。回退标签为 `rollback-8554e96a`，已验证候选为 `storage-candidate`；旧容器仍处于停止状态。未更改分析镜像。

已验证：两个生产镜像实际构建；源码变化后前端 pnpm 安装及后端外部依赖安装命中 CACHED；dev target 可用测试工具。Gateway readiness、扩展导入、redis、Lark/Docker CLI 可用，生产环境不含 pytest、ruff、SciPy、后端测试与开发脚本。前端不含 .next/cache 或完整源码树。

使用独立临时数据库、合成账号及研究记录，Chrome 验证首次设置、注册/登录、1440/1366 五阶段研究页、中文 MDX 文档和静态资源，无页面脚本错误或资源失败。原生 SSE 的 metadata、updates、end 正常返回；无真实模型配置的合成运行正确记录为 error。这只证明事件和失败状态通道，不代表完成真实模型/研究质量验收。

清理前重新确认缓存归属和非共享状态，按精确 ID 删除历史 EIQAS 缓存，CLI 合计回收约 **12.40 GB**。构建缓存总量从初始 48.43 GB，经新构建增至 51.34 GB，清理即时为 38.94 GB；构建收尾后的最终记录为 41.23 GB，其中独占可回收为 8.195 GB（共享缓存计数会随构建产物登记变化）。当前/回退/候选镜像、所有卷及真实数据库保留；镜像缩减量不另计为空间回收。其他项目的缓存保持原状。

修改前后均完成仓库规定的完整离线与 blocking-io 检查：修改前17165通过，修改后17172通过，均188跳过/3取消选择；blocking-io前后均143通过。相关构建部署回归27通过，前端pnpm check通过。详见[Issue #21](https://github.com/flat-git/eiqas-deerflow/issues/21)。测试不调用真实模型，不代替用户方案确认。检查点和研究历史治理、分析/OCR 镜像瘦身不在本批范围。

