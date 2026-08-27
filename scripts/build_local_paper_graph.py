"""Build a browser-safe literature graph from a user-owned local PDF inventory.

The script intentionally reads *only* PDF file names and their collection
directory names.  It never parses PDF text, exports an absolute path, reads
environment variables, or contacts a network service.  The resulting JSON is
intended to live under ``runs/`` (which is gitignored) and can be served by
the local preview or imported through the workbench.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


YEAR = re.compile(r"(?:^|\D)((?:19|20)\d{2})(?:\D|$)")


def _title(path: Path) -> str:
    title = re.sub(r"\s+", " ", path.stem.replace("_", " ")).strip()
    return title[:300] or "Untitled local PDF"


def _year(path: Path) -> int | None:
    match = YEAR.search(path.stem)
    return int(match.group(1)) if match else None


def _collection(root: Path, path: Path) -> str:
    relative = path.relative_to(root)
    return relative.parts[0] if len(relative.parts) > 1 else "Unfiled local papers"


def build_bundle(library_root: Path, maximum: int) -> dict[str, object]:
    files = sorted((path for path in library_root.rglob("*.pdf") if path.is_file()), key=lambda path: (str(path.parent).casefold(), path.name.casefold()))
    available: dict[str, list[Path]] = defaultdict(list)
    for path in files:
        available[_collection(library_root, path)].append(path)
    records: list[tuple[Path, str]] = []
    seen_titles: set[str] = set()
    round_index = 0
    while len(records) < maximum:
        added = False
        for collection in sorted(available):
            if round_index >= len(available[collection]):
                continue
            path = available[collection][round_index]
            title = _title(path)
            key = title.casefold()
            if key not in seen_titles:
                seen_titles.add(key)
                records.append((path, title))
                added = True
                if len(records) == maximum:
                    break
        if not added and all(round_index >= len(paths) for paths in available.values()):
            break
        round_index += 1
    collections: dict[str, list[tuple[Path, str]]] = defaultdict(list)
    for record in records:
        collections[_collection(library_root, record[0])].append(record)
    mission_id = "local_library_inventory"
    nodes: list[dict[str, object]] = [
        {
            "node_id": f"mission:{mission_id}",
            "kind": "mission",
            "label": "Local materials literature inventory",
            "trust_status": "local_filename_inventory_navigation_only",
        }
    ]
    edges: list[dict[str, str]] = []
    for index, (collection, items) in enumerate(sorted(collections.items()), start=1):
        collection_id = f"collection:{index}"
        nodes.append({
            "node_id": collection_id,
            "kind": "local_collection",
            "label": collection[:180],
            "trust_status": "local_filename_inventory_navigation_only",
            "source": "Local library collection",
        })
        edges.append({
            "source_id": f"mission:{mission_id}",
            "target_id": collection_id,
            "edge_type": "collection_scope",
            "relation_source": "Local filename inventory",
            "trust_status": "local_filename_inventory_navigation_only",
        })
        for path, title in items:
            paper_id = f"local-paper:{len(nodes):03d}"
            nodes.append({
                "node_id": paper_id,
                "kind": "candidate_paper",
                "label": title,
                "trust_status": "local_filename_inventory_not_scientific_evidence",
                "source": "Local PDF filename inventory",
                "publication_year": _year(path),
                "is_content_accessible": False,
            })
            edges.append({
                "source_id": collection_id,
                "target_id": paper_id,
                "edge_type": "collection_membership",
                "relation_source": "Local filename inventory",
                "trust_status": "local_filename_inventory_not_scientific_evidence",
            })
    return {
        "schema_version": "1.0",
        "mission": {
            "mission_id": mission_id,
            "question": "Which local material-science papers are available for a bounded review?",
            "material": "Local materials library",
            "property_name": "literature coverage",
            "scope": "PDF filename metadata only; no full text or automatic evidence extraction",
        },
        "fleet_assignment": {"display_name_en": "Local Library Survey Fleet", "mission_type": "library_inventory", "release_gate": "human_review"},
        "status": {"mission_state": "INVENTORY", "retry_count": 0, "retry_budget": 0, "return_reason": None},
        "stations": [{"station_type": "local_inventory", "status": "complete"}],
        "facilities": [],
        "evidence_cards": [],
        "condition_matrix": [],
        "timeline": [],
        "literature_graph": {
            "trust_status": "local_filename_inventory_navigation_only_not_scientific_evidence",
            "nodes": nodes,
            "edges": edges,
        },
        "coverage": {"scope": "local PDF filenames only", "empty_result_meaning": "No matching local filename does not establish that the literature is absent."},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library-root", type=Path, required=True, help="User-owned folder containing PDFs")
    parser.add_argument("--output", type=Path, required=True, help="Destination UI JSON, normally under runs/")
    parser.add_argument("--max-papers", type=int, default=90, help="Bounded number of distinct file-name records (1-250)")
    args = parser.parse_args()
    if not 1 <= args.max_papers <= 250:
        parser.error("--max-papers must be between 1 and 250")
    root = args.library_root.resolve()
    if not root.is_dir():
        parser.error("--library-root must be an existing directory")
    bundle = build_bundle(root, args.max_papers)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "papers": sum(1 for node in bundle["literature_graph"]["nodes"] if node["kind"] == "candidate_paper")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
