"""Rewrite internal package-proxy hosts in uv.lock / package-lock.json to the public registries.

Local machines resolve through Databricks-internal proxies; the Databricks Apps runtime installs from the
public registries. The proxies mirror the public path layout and serve identical artefacts (same hashes),
so a host rewrite is sufficient. Run after every `uv lock` / `npm install`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES = {
    "uv.lock": [
        (r"https://pypi-proxy\.(?:cloud|dev)\.databricks\.com/simple/?", "https://pypi.org/simple"),
        (r"https://pypi-proxy\.(?:cloud|dev)\.databricks\.com/packages/", "https://files.pythonhosted.org/packages/"),
    ],
    "package-lock.json": [
        (r"https://npm-proxy\.(?:cloud|dev)\.databricks\.com/", "https://registry.npmjs.org/"),
    ],
}


def main() -> int:
    leftovers = 0
    for name, rules in RULES.items():
        path = ROOT / name
        if not path.exists():
            continue
        text = path.read_text()
        for pattern, repl in rules:
            text = re.sub(pattern, repl, text)
        path.write_text(text)
        remaining = len(re.findall(r"(?:pypi|npm)-proxy\.[a-z]+\.databricks\.com", text))
        leftovers += remaining
        print(f"{name}: normalised ({remaining} internal URLs left)")
    return 1 if leftovers else 0


if __name__ == "__main__":
    sys.exit(main())
