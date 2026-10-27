"""Public DeerFlow extension entry point."""

from collections.abc import Mapping
from typing import Any

from deerflow_extension_api import ExtensionRegistry, extension


@extension(api="0.2.0", name="eiqas")
def install(registry: ExtensionRegistry, config: Mapping[str, Any]) -> None:
    from .plugin import ResearchRuntime, build_runtime_router

    runtime = ResearchRuntime(config)
    registry.service(runtime)
    registry.middlewares(runtime)
    registry.routers((build_runtime_router(runtime),))
