# 模型与执行模式

模型 ID（例如 `deepseek-flash`）决定调用哪个服务端模型；输入框的闪速、思考、Pro、Ultra决定DeerFlow执行策略，两者是独立选项。选择Ultra不会自动把模型换成DeepSeek Pro。

| 模式 | 思考开关 | 原生计划 | 子代理 | 默认effort请求 |
| --- | --- | --- | --- | --- |
| 闪速 | 关闭 | 否 | 否 | minimal/默认 |
| 思考 | 开启 | 否 | 否 | low |
| Pro | 开启 | 是 | 否 | medium |
| Ultra | 开启 | 是 | 是 | high |

界面按`models[].supports_thinking`显示后面三个模式，未声明时默认为false。`supports_reasoning_effort`未声明时，后端也会移除effort参数。这些是部署配置的能力声明，不是运行时探测结果。仅设置能力声明还不够，应同时把原生思考开关映射到供应商实际参数。

## DeepSeek配置示例

保留本机已有model/base_url/api_key配置，在对应模型条目追加：

```yaml
supports_thinking: true
supports_reasoning_effort: true
when_thinking_enabled:
  extra_body:
    thinking:
      type: enabled
when_thinking_disabled:
  extra_body:
    thinking:
      type: disabled
```

适配器使用`deerflow.models.patched_deepseek:PatchedChatDeepSeek`，保留工具多轮所需的reasoning_content。不要把密钥写进配置模板或研究记录。

2026-10-28核对的[DeepSeek官方说明](https://api-docs.deepseek.com/guides/thinking_mode/)中，deepseek-flash支持思考和工具调用，API默认开启思考。若只配置模型ID、不显式发送开关，界面显示闪速也不能证明API已关闭思考。官方effort映射中medium和high均映射为high；因此原生Pro/Ultra在该供应商下不一定是不同推理深度，仍有计划/子代理组织方式的差异。原生Ultra也不自动等于供应商max档。

当前保持DeerFlow原生映射，未修改Harness循环。开启更深模式仍不能替代原件核对、口径审查、独立复算和实际读者判断。真实适配器验证与CI分开记录，CI不依赖密钥。
