"""Offline checks for the independent product's declared public baseline."""
from pathlib import Path

root = Path(__file__).resolve().parent.parent
provenance = (root / "UPSTREAM.md").read_text(encoding="utf-8")
assert "345f08be00c8a9495079b732a39b46aa9af1584e" in provenance
assert "flat-git/eiqas-deerflow" in provenance
license_text = (root / "LICENSE").read_text(encoding="utf-8")
assert "MIT License" in license_text and "Bytedance" in license_text
assert (root / "task_plan.md").is_file()
assert (root / "docs/eiqas-development.md").is_file()
workflows = list((root / ".github/workflows").glob("*"))
assert workflows and all(path.name.startswith("eiqas-") for path in workflows)
print("EIQAS baseline and public-workflow boundaries verified")
