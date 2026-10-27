"""Exercise the real public extension and native tool schemas without a model."""

from types import SimpleNamespace

import pytest
from deerflow_extension_api import ExtensionRuntimeDeps
from eiqas_research import install
from eiqas_research.models import ResearchCreate
from eiqas_research.plugin import active_service
from eiqas_research.tools import eiqas_save_plan


@pytest.mark.asyncio
async def test_public_plugin_lifecycle_and_thread_context(tmp_path):
    contributions = {}
    registry = SimpleNamespace(
        service=lambda service: contributions.update(service=service),
        middlewares=lambda contributor: contributions.update(middlewares=contributor),
        routers=lambda routers: contributions.update(routers=routers),
    )
    install(registry, {"data_dir": str(tmp_path)})
    runtime = contributions["service"]
    await runtime.start(ExtensionRuntimeDeps())
    try:
        service = active_service()
        service.create(ResearchCreate(thread_id="owned-thread", question="测试研究问题"))
        middleware = contributions["middlewares"].contribute_middlewares(None, None)[0].middleware

        class Request:
            system_message = None
            runtime = SimpleNamespace(config={"configurable": {"thread_id": "owned-thread"}})

            def override(self, **kwargs):
                return SimpleNamespace(**kwargs)

        async def handler(request):
            return request.system_message

        message = await middleware.awrap_model_call(Request(), handler)
        assert "测试研究问题" in message.content
        assert "Never claim that a user confirmed" in message.content
        request = Request()
        request.runtime = SimpleNamespace(config={"configurable": {"thread_id": "other-thread"}})
        assert await middleware.awrap_model_call(request, handler) is None
    finally:
        await runtime.stop()
    with pytest.raises(RuntimeError):
        active_service()


def test_native_tool_hides_runtime_and_has_no_confirmation_tool():
    import eiqas_research.tools as tools

    schema = eiqas_save_plan.tool_call_schema.model_json_schema()
    assert set(schema["properties"]) == {"plan"}
    assert not any("confirm" in name for name in vars(tools))
