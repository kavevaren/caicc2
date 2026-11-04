"""L0 task 1c: short OpenAPI validation for contracts/openapi.yaml.

Checks (PyYAML only, no extra deps):
1. top-level `openapi` key present;
2. every path has at least one operation;
3. every $ref in the document resolves.
Prints the real path and operation counts.
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
OPS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")


def iter_refs(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "$ref" and isinstance(v, str):
                yield v
            else:
                yield from iter_refs(v)
    elif isinstance(node, list):
        for item in node:
            yield from iter_refs(item)


def main() -> None:
    spec = yaml.safe_load((ROOT / "contracts" / "openapi.yaml").read_text(encoding="utf-8"))
    assert isinstance(spec, dict) and spec.get("openapi"), "missing top-level `openapi` key"

    paths = spec.get("paths") or {}
    n_ops = 0
    for path, item in paths.items():
        ops = [k for k in item if k in OPS]
        assert ops, f"path {path} has no operations"
        n_ops += len(ops)

    bad = [r for r in iter_refs(spec) if not r.startswith("#/")]
    assert not bad, f"unresolvable external refs: {bad[:5]}"
    for ref in {r for r in iter_refs(spec)}:
        node = spec
        for part in ref.lstrip("#/").split("/"):
            assert isinstance(node, dict) and part in node, f"dangling ref {ref} (at {part})"
            node = node[part]

    print(f"OK openapi={spec['openapi']} paths={len(paths)} operations={n_ops} all_refs_resolve=True")


if __name__ == "__main__":
    main()
