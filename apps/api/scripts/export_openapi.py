from __future__ import annotations

import json
from pathlib import Path

from atlas_api.main import create_app


def main() -> None:
    output = Path(__file__).resolve().parents[1] / "openapi.json"
    output.write_text(json.dumps(create_app().openapi(), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

