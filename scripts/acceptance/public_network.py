"""Live native search, public-original reading and AIO parsing diagnostics.

Run with the configured Gateway Python. This creates an isolated acceptance
research, simulates its plan confirmation explicitly, and destroys only its
own sandbox. It does not confirm or resume an operator's research.
"""

import argparse
import asyncio
import json
import shlex
import uuid
from pathlib import Path
from types import SimpleNamespace

from deerflow.community.ddg_search.tools import web_search_tool
from deerflow.sandbox import get_sandbox_provider
from eiqas_research.models import Plan, ResearchCreate
from eiqas_research.plugin import ResearchRuntime
from eiqas_research.tools import web_fetch_public


async def run(root: Path, world_bank: bool):
    thread = "network-acceptance-" + uuid.uuid4().hex[:12]
    plugin = ResearchRuntime({"data_dir": str(root / thread)})
    await plugin.start(None)
    runtime = SimpleNamespace(
        state={},
        context={"thread_id": thread, "user_id": "eiqas-acceptance"},
        config={"configurable": {"thread_id": thread}},
    )
    receipt = {
        "kind": "live-network-and-native-parser",
        "simulated_acceptance_confirmation": True,
        "checks": {},
        "pages": [],
    }
    try:
        service = plugin.service
        research = service.create(
            ResearchCreate(thread_id=thread, question="联网工具自检（非正式研究）")
        )
        plan = service.save_plan(
            research["id"],
            Plan(
                question=research["question"],
                methods=[
                    {
                        "name": "工具自检",
                        "rationale": "实际公网取得与沙箱解析",
                        "operation": "evidence_review",
                    }
                ],
                required_data=["公开网页"],
                outputs=["真实诊断回执"],
            ),
        )
        # Only this explicitly labelled acceptance fixture simulates confirmation.
        service.confirm_plan(research["id"], plan["hash"])
        search = json.loads(
            await asyncio.to_thread(
                web_search_tool.invoke,
                {"query": "site:haier.com 2025 半年报", "max_results": 5},
            )
        )
        receipt["search"] = {
            "query": search.get("query"),
            "hits": [
                {"title": row["title"], "url": row["url"]}
                for row in search.get("results", [])
            ],
            "error": search.get("error"),
        }
        receipt["checks"]["native_search"] = any(
            "haier.com/" in row["url"] for row in receipt["search"]["hits"]
        )
        urls = [
            "https://www.haier.com/about_haier/xinwen/20250829_270448.shtml",
            "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
        ]
        if world_bank:
            urls.append(
                "https://api.worldbank.org/v2/country/CHN/indicator/SP.URB.TOTL.IN.ZS?format=json&date=2020:2024&per_page=100"
            )
        for url in urls:
            result = await web_fetch_public.coroutine(url, runtime)
            receipt["pages"].append(
                {
                    key: result.get(key)
                    for key in [
                        "url",
                        "retrieved_url",
                        "status",
                        "reason",
                        "title",
                        "source_id",
                        "extraction_id",
                        "sha256",
                        "block_count",
                    ]
                }
            )
            receipt["checks"][url] = result["status"] == "acquired" and bool(
                result.get("blocks")
            )
        provider = get_sandbox_provider()
        sandbox = provider.get(runtime.state["sandbox"]["sandbox_id"])
        code = "import urllib.request; r=urllib.request.urlopen('https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf',timeout=20); print('EIQAS_PUBLIC_HTTPS='+str(r.status))"
        output = await asyncio.to_thread(
            sandbox.execute_command,
            shlex.join(["/opt/eiqas-venv/bin/python", "-c", code]),
            timeout=30,
        )
        receipt["checks"]["native_sandbox_https"] = "EIQAS_PUBLIC_HTTPS=200" in output
    except Exception as exc:
        receipt["error"] = type(exc).__name__ + ": " + str(exc)[:400]
    finally:
        sandbox_id = runtime.state.get("sandbox", {}).get("sandbox_id")
        if sandbox_id:
            await asyncio.to_thread(get_sandbox_provider().destroy, sandbox_id)
        await plugin.stop()
        receipt["passed"] = (
            bool(receipt["checks"])
            and all(receipt["checks"].values())
            and "error" not in receipt
        )
        root.mkdir(parents=True, exist_ok=True)
        (root / "public-network-receipt.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(receipt, ensure_ascii=False))
    return receipt["passed"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--world-bank", action="store_true")
    args = parser.parse_args()
    raise SystemExit(0 if asyncio.run(run(args.output, args.world_bank)) else 1)
