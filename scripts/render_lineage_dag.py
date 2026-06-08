#!/usr/bin/env python3
"""Render the dbt lineage DAG to docs/lineage_dag.png from target/manifest.json.

Run after `dbt docs generate`:
    python scripts/render_lineage_dag.py
Requires Graphviz (`dot`) on PATH.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "target" / "manifest.json"
OUT_PNG = ROOT / "docs" / "lineage_dag.png"

# layer -> (rank, fill colour)
LAYERS = {
    "source": (0, "#E5E7EB"),
    "seed": (1, "#DCFCE7"),
    "staging": (1, "#DBEAFE"),
    "intermediate": (2, "#CCFBF1"),
    "marts": (3, "#FCE7DD"),
    "exposure": (4, "#FEF3C7"),
}


def layer_of(node: dict, uid: str) -> str:
    if uid.startswith("source."):
        return "source"
    if uid.startswith("exposure."):
        return "exposure"
    rt = node.get("resource_type")
    if rt == "seed":
        return "seed"
    name = node.get("name", "")
    if name.startswith("stg_"):
        return "staging"
    if name.startswith("int_"):
        return "intermediate"
    return "marts"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    keep: dict[str, dict] = {}

    for uid, n in manifest.get("nodes", {}).items():
        if n.get("resource_type") in ("model", "seed"):
            keep[uid] = n
    for uid, n in manifest.get("sources", {}).items():
        keep[uid] = n
    for uid, n in manifest.get("exposures", {}).items():
        keep[uid] = n

    # edges from each node's parents (only between kept nodes)
    parent_map = manifest.get("parent_map", {})
    edges = []
    for uid in keep:
        for parent in parent_map.get(uid, []):
            if parent in keep:
                edges.append((parent, keep[parent], uid))

    def node_id(uid: str) -> str:
        return '"' + uid.split(".")[-1] + '"'

    lines = [
        "digraph lineage {",
        '  rankdir=LR; bgcolor="white"; pad=0.3; nodesep=0.28; ranksep=1.0;',
        '  node [shape=box style="filled,rounded" fontname="Helvetica" fontsize=11 '
        'penwidth=1.6 color="#111827" margin="0.12,0.07"];',
        '  edge [color="#9CA3AF" arrowsize=0.7 penwidth=1.1];',
    ]

    # group nodes by rank for a clean layered look + colour them
    ranks: dict[int, list[str]] = {}
    for uid, n in keep.items():
        layer = layer_of(n, uid)
        rank, fill = LAYERS[layer]
        ranks.setdefault(rank, []).append(node_id(uid))
        lines.append(f'  {node_id(uid)} [fillcolor="{fill}"];')

    for rank in sorted(ranks):
        lines.append(f'  {{ rank=same; {" ".join(ranks[rank])} }}')

    for parent, _pnode, child in edges:
        lines.append(f"  {node_id(parent)} -> {node_id(child)};")

    lines.append("}")
    dot = "\n".join(lines)

    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["dot", "-Tpng", "-Gdpi=150", "-o", str(OUT_PNG)],
        input=dot.encode("utf-8"), check=True,
    )
    print(f"wrote {OUT_PNG} ({len(keep)} nodes, {len(edges)} edges)")


if __name__ == "__main__":
    main()
