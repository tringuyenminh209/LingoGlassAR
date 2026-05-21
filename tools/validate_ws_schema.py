"""Validate docs/api-contract/ws-events.samples.json against ws-events.schema.json.

Run:  py tools/validate_ws_schema.py
Exit: 0 if every sample passes, non-zero otherwise.

Dependencies: jsonschema (pip install --user jsonschema). Stdlib only otherwise.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ImportError:
    print("ERROR: install jsonschema first: py -m pip install --user jsonschema")
    sys.exit(2)


REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA = REPO_ROOT / "docs" / "api-contract" / "ws-events.schema.json"
SAMPLES = REPO_ROOT / "docs" / "api-contract" / "ws-events.samples.json"


def main() -> int:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    samples = json.loads(SAMPLES.read_text(encoding="utf-8"))["samples"]
    validator = Draft202012Validator(schema)

    fails = 0
    for i, sample in enumerate(samples):
        wire = {k: v for k, v in sample.items() if not k.startswith("_")}
        errors = sorted(validator.iter_errors(wire), key=lambda e: e.path)
        if errors:
            fails += 1
            print(f"[FAIL] sample #{i} type={sample.get('type')!r}")
            for err in errors:
                print(f"    -> {err.message} (at {list(err.path)})")
        else:
            print(f"[ok]   sample #{i} type={sample.get('type')!r}")

    if fails:
        print(f"\n{fails} sample(s) failed schema validation")
        return 1
    print(f"\nAll {len(samples)} samples valid against ws-events.schema.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
