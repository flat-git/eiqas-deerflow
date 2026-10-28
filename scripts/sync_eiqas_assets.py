"""Vendor fixed chart assets and licenses for Python-side offline exports."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source = ROOT / "frontend/node_modules/echarts"
    if json.loads((source / "package.json").read_text())["version"] != "6.1.0":
        raise SystemExit("EIQAS requires ECharts 6.1.0")
    assets = ROOT / "backend/packages/eiqas-research/eiqas_research/assets"
    pairs = [
        (source / "dist/echarts.min.js", assets / "echarts.min.js"),
        (source / "LICENSE", assets / "ECHARTS-LICENSE"),
        (source / "NOTICE", assets / "ECHARTS-NOTICE"),
        (source / "licenses/LICENSE-d3", assets / "D3-LICENSE"),
        (source.resolve().parent / "zrender/LICENSE", assets / "ZRENDER-LICENSE"),
        (source.resolve().parent / "tslib/LICENSE.txt", assets / "TSLIB-LICENSE"),
        (source.resolve().parent / "tslib/CopyrightNotice.txt", assets / "TSLIB-COPYRIGHT"),
        (ROOT / "docker/analysis/requirements.lock", assets / "analysis-requirements.lock"),
    ]
    manifest = {"echarts": "6.1.0", "files": {}}
    for original, target in pairs:
        sha = hashlib.sha256(original.read_bytes()).hexdigest()
        manifest["files"][target.name] = sha
        if args.check:
            if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != sha:
                raise SystemExit(f"Export asset missing or stale: {target.name}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, target)
    path = assets / "manifest.json"
    if args.check:
        if json.loads(path.read_text()) != manifest:
            raise SystemExit("Export asset manifest is stale")
    else:
        path.write_text(json.dumps(manifest, indent=2) + "\n")
    print("Verified fixed ECharts assets, licenses and analysis dependency lock.")


if __name__ == "__main__":
    main()
