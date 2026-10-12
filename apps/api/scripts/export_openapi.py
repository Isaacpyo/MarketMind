"""Write the API's OpenAPI schema to packages/api-contract/openapi.json.

The web app generates its TypeScript types from this file (`npm run gen:api`), and CI
fails if it is stale, so the frontend and backend can't drift apart silently.

Usage (from apps/api):  uv run python scripts/export_openapi.py [--check]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from marketmind.config import Settings  # noqa: E402
from marketmind.main import create_app  # noqa: E402

TARGET = ROOT.parents[1] / "packages" / "api-contract" / "openapi.json"


def main() -> int:
    app = create_app(Settings(app_env="test"))
    rendered = json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"
    if "--check" in sys.argv:
        current = TARGET.read_text("utf-8") if TARGET.exists() else ""
        if current != rendered:
            print(f"{TARGET} is out of date; run scripts/export_openapi.py", file=sys.stderr)
            return 1
        print("OpenAPI contract is up to date")
        return 0
    TARGET.write_text(rendered, "utf-8")
    print(f"wrote {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
