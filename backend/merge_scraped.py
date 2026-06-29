#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


MAX_AGE_DAYS = 90

BASE_DIR = Path(__file__).resolve().parent
SUPPLIERS_PATH = BASE_DIR / "data" / "suppliers.json"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


def load_suppliers(path: Path) -> list[dict[str, Any]]:
    data = load_json(path)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("suppliers"), list):
        return data["suppliers"]
    raise ValueError(f"{path} must contain a supplier array or an object with a suppliers array")


def company_key(supplier: dict[str, Any]) -> str:
    return str(supplier.get("name", "")).strip().casefold()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    raw_value = value.strip()
    if raw_value.endswith("Z"):
        raw_value = f"{raw_value[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(raw_value)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def supplier_id_for(name: str, existing_ids: set[str]) -> str:
    digest = hashlib.sha1(name.strip().casefold().encode("utf-8")).hexdigest()[:8]
    candidate = f"sup-{digest}"
    suffix = 2

    while candidate in existing_ids:
        candidate = f"sup-{digest}-{suffix}"
        suffix += 1

    existing_ids.add(candidate)
    return candidate


def merge_suppliers(
    existing_suppliers: list[dict[str, Any]],
    scraped_suppliers: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, int, int]:
    timestamp = now_iso()
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    existing_ids = {
        str(supplier["id"])
        for supplier in existing_suppliers
        if isinstance(supplier, dict) and supplier.get("id")
    }

    by_name: dict[str, dict[str, Any]] = {}
    for supplier in existing_suppliers:
        if not isinstance(supplier, dict):
            continue

        key = company_key(supplier)
        if not key:
            continue

        if key not in by_name:
            by_name[key] = supplier

    added = 0
    updated = 0

    for scraped in scraped_suppliers:
        if not isinstance(scraped, dict):
            continue

        key = company_key(scraped)
        if not key:
            continue

        if key in by_name:
            existing = by_name[key]
            merged = {**existing, **scraped}
            merged["id"] = existing.get("id") or scraped.get("id") or supplier_id_for(str(scraped["name"]), existing_ids)
            merged["updatedAt"] = timestamp
            by_name[key] = merged
            updated += 1
        else:
            new_supplier = dict(scraped)
            new_supplier["id"] = new_supplier.get("id") or supplier_id_for(str(new_supplier["name"]), existing_ids)
            new_supplier["matchScore"] = 70
            new_supplier["updatedAt"] = timestamp
            by_name[key] = new_supplier
            added += 1

    kept_suppliers: list[dict[str, Any]] = []
    for supplier in by_name.values():
        updated_at = parse_datetime(supplier.get("updatedAt"))
        if updated_at is not None and updated_at < cutoff:
            continue
        kept_suppliers.append(supplier)

    removed = len(existing_suppliers) + added - len(kept_suppliers)
    kept_suppliers.sort(key=lambda supplier: str(supplier.get("name", "")).casefold())
    return kept_suppliers, added, updated, removed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge scraped suppliers into backend/data/suppliers.json."
    )
    parser.add_argument(
        "scraped_json",
        type=Path,
        help="Path to the scraped supplier JSON file.",
    )
    parser.add_argument(
        "--suppliers-json",
        type=Path,
        default=SUPPLIERS_PATH,
        help=f"Path to existing suppliers JSON. Defaults to {SUPPLIERS_PATH}.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    scraped_path = args.scraped_json.expanduser().resolve()
    suppliers_path = args.suppliers_json.expanduser().resolve()

    scraped_suppliers = load_suppliers(scraped_path)
    existing_suppliers = load_suppliers(suppliers_path)

    merged_suppliers, added, updated, removed = merge_suppliers(
        existing_suppliers,
        scraped_suppliers,
    )
    save_json(suppliers_path, merged_suppliers)

    print(f"added {added}, updated {updated}, removed {removed}")


if __name__ == "__main__":
    main()
