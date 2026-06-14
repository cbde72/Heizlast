from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class BoundaryCondition:
    key: str
    bucket: str
    label: str
    factor: float
    source: str


DIN_BOUNDARY_CONDITIONS: dict[str, BoundaryCondition] = {
    "outside": BoundaryCondition("outside", "external", "Außenluft", 1.00, "DIN EN 12831-1: Außenklima"),
    "ground": BoundaryCondition("ground", "ground", "Erdreich", 1.00, "vereinfachtes Erdreichmodell"),
    "basement_unheated": BoundaryCondition("basement_unheated", "basement", "unbeheizter Keller", 1.00, "Projekt-Temperatur Keller"),
    "attic_unheated": BoundaryCondition("attic_unheated", "attic", "Dachboden/Abseite unbeheizt", 0.80, "DIN/TS-nahe Tabelle unbeheizte Bereiche"),
    "unheated": BoundaryCondition("unheated", "unheated", "unbeheizter Bereich", 0.80, "DIN/TS-nahe Tabelle unbeheizte Bereiche"),
    "adjacent_heated": BoundaryCondition("adjacent_heated", "adjacent_heated", "beheizter Nachbarbereich", 0.00, "Interzone / angrenzend beheizt"),
    "interzone": BoundaryCondition("interzone", "interzone", "Interzone", 0.00, "Interzone mit t_adj_c"),
}

BOUNDARY_KEY_ALIASES = {
    "basement": "basement_unheated",
    "keller": "basement_unheated",
    "unheated_basement": "basement_unheated",
    "attic": "attic_unheated",
    "dachraum": "attic_unheated",
    "speicher": "attic_unheated",
}


BUCKET_TO_CANONICAL = {
    "out": "external",
    "outside": "external",
    "external": "external",
    "ground": "ground",
    "keller": "basement",
    "basement": "basement",
    "oben": "upper",
    "dachraum": "attic",
    "speicher": "attic",
    "attic": "attic",
    "unheated": "unheated",
    "interzone": "interzone",
    "adjacent_heated": "adjacent_heated",
}


def parse_meta(meta: Optional[str]) -> dict[str, str]:
    parts: dict[str, str] = {}
    for chunk in str(meta or "").split("|"):
        if "=" in chunk:
            key, value = chunk.split("=", 1)
            parts[key.strip()] = value.strip()
    return parts


def boundary_from_meta(meta: Optional[str]) -> BoundaryCondition | None:
    parts = parse_meta(meta)
    key = (parts.get("boundary") or parts.get("boundary_condition") or "").strip().lower()
    key = BOUNDARY_KEY_ALIASES.get(key, key)
    return DIN_BOUNDARY_CONDITIONS.get(key) if key else None


def canonical_bucket(bucket: str) -> str:
    return BUCKET_TO_CANONICAL.get(str(bucket or "").strip().lower(), str(bucket or "").strip().lower() or "external")


def boundary_label_for_bucket(bucket: str) -> str:
    canonical = canonical_bucket(bucket)
    for bc in DIN_BOUNDARY_CONDITIONS.values():
        if bc.bucket == canonical:
            return bc.label
    return canonical
