"""End-to-end validation (T055): generate deliverables from fixture and verify vocabulary."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

FIXTURES = Path(__file__).parent / "fixtures"

manifest = json.loads((FIXTURES / "manifest.json").read_text())
findings_data = json.loads((FIXTURES / "findings.json").read_text())
run_data = {
    "manifest": manifest,
    "findings": findings_data["findings"],
    "maturity_scores": findings_data["maturity_scores"],
    "unknown_fields": [],
}

run_id = manifest["run_id"]
print(f"Loaded artifact: run_id={run_id}")
print(f"  Findings: {len(run_data['findings'])}")
print(f"  Maturity scores: {len(run_data['maturity_scores'])}")

from narrator.mcp_server.deliverables import generate_deliverables

TEMPLATES = Path(__file__).parent.parent.parent / "templates"

with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp)
    files = generate_deliverables(run_data, output_dir=out, templates_dir=TEMPLATES)
    print(f"Deliverables generated: {len(files)} files")
    assert len(files) == 4, f"Expected 4 files, got {len(files)}"
    for f in files:
        size = f.stat().st_size
        content = f.read_text(encoding="utf-8")
        lower = content.lower()
        assert "canonical entity modeling" in lower, f"{f.name}: missing 'canonical entity modeling'"
        assert "field-level lineage" in lower, f"{f.name}: missing 'field-level lineage'"
        assert "layered modeling" in lower, f"{f.name}: missing 'layered modeling'"
        assert "steward-loop modeling" in lower, f"{f.name}: missing 'steward-loop modeling'"
        assert "not assessed in this version" in lower, f"{f.name}: missing scope honesty phrase"
        print(f"  {f.name}: {size} bytes — vocabulary OK")

print()
print("✅ End-to-end validation passed:")
print("   - Artifact loaded from fixture")
print("   - 4 deliverables rendered")
print("   - All 4 exact discipline names present in every deliverable")
print("   - Scope honesty phrase present in all deliverables")
