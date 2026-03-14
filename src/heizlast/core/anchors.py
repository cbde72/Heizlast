from __future__ import annotations

import json
from typing import Dict, Iterable, Optional, Tuple


EPS = 1e-9


def parse_meta(meta: str | None) -> Dict[str, str]:
    s = (meta or "").strip()
    if not s:
        return {}
    if s.startswith("{") and s.endswith("}"):
        try:
            d = json.loads(s)
            if isinstance(d, dict):
                return {str(k): "" if v is None else str(v) for k, v in d.items()}
        except Exception:
            pass
    out: Dict[str, str] = {}
    for part in s.split("|"):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k:
            out[k] = v
    return out


def dump_meta(parts: Dict[str, object], *, prefer_json: bool = False) -> str:
    if prefer_json:
        try:
            return json.dumps(parts, ensure_ascii=False, sort_keys=True, indent=2)
        except Exception:
            pass
    out = []
    for k, v in parts.items():
        if v is None:
            continue
        ks = str(k).strip().replace("|", "/").replace("\n", " ").replace("\r", " ")
        vs = str(v).strip().replace("|", "/").replace("\n", " ").replace("\r", " ")
        if ks:
            out.append(f"{ks}={vs}")
    return "|".join(out)


def meta_rooms(meta: str | None) -> set[str]:
    raw = parse_meta(meta).get("rooms", "")
    return {x.strip() for x in raw.split(",") if x.strip()}


def _fmt3(x: float) -> str:
    return f"{float(x):.3f}"


def _fmt4(x: float) -> str:
    return f"{float(x):.4f}"


def edge_line_token(orient: str, c: float) -> str:
    return f"{str(orient).strip().upper()}:{float(c):.3f}"


def parse_line_token(raw: str | None) -> Tuple[Optional[str], Optional[float]]:
    s = (raw or "").strip()
    if not s or ":" not in s:
        return None, None
    orient, c = s.split(":", 1)
    orient = orient.strip().upper()[:1]
    try:
        return orient, float(c)
    except Exception:
        return orient, None


def build_edge_span_meta(*, kind: str, room_ids: Iterable[str], orient: str, c: float, a0: float, a1: float, uid: str) -> str:
    parts: Dict[str, object] = {
        kind: None,
        "rooms": ",".join(sorted({str(r) for r in room_ids if str(r)})),
        "line": edge_line_token(orient, c),
        "orient": str(orient).strip().upper()[:1],
        "c": _fmt3(c),
        "a0": _fmt3(min(a0, a1)),
        "a1": _fmt3(max(a0, a1)),
        "edge_uid": uid,
    }
    # token-only flag first
    out = []
    if kind:
        out.append(str(kind))
    for k in ("rooms", "line", "orient", "c", "a0", "a1", "edge_uid"):
        v = parts.get(k)
        if v is not None:
            out.append(f"{k}={v}")
    return "|".join(out)


def parse_edge_anchor(meta: str | None) -> Dict[str, object]:
    d = parse_meta(meta)
    orient = (d.get("orient") or "").strip().upper()[:1] or None
    c = _safe_float(d.get("c"))
    a0 = _safe_float(d.get("a0"))
    a1 = _safe_float(d.get("a1"))
    if (orient is None or c is None) and d.get("line"):
        o2, c2 = parse_line_token(d.get("line"))
        orient = orient or o2
        c = c if c is not None else c2
    out: Dict[str, object] = dict(d)
    out.update({
        "parent": d.get("parent"),
        "orient": orient,
        "c": c,
        "a0": a0,
        "a1": a1,
        "s": _safe_float(d.get("s")),
        "w": _safe_float(d.get("w")),
        "rooms": meta_rooms(meta),
    })
    return out


def update_edge_anchor_meta(meta: str | None, *, parent: str | None = None, orient: str | None = None, c: float | None = None,
                            a0: float | None = None, a1: float | None = None, s: float | None = None,
                            w: float | None = None, rooms: Iterable[str] | None = None) -> str:
    d = parse_meta(meta)
    if parent is not None:
        d["parent"] = str(parent)
    if orient is not None:
        d["orient"] = str(orient).strip().upper()[:1]
    if c is not None:
        d["c"] = _fmt3(c)
    if a0 is not None:
        d["a0"] = _fmt3(min(a0, a1 if a1 is not None else a0))
    if a1 is not None:
        d["a1"] = _fmt3(max(a1, a0 if a0 is not None else a1))
    if (orient is not None) and (c is not None):
        d["line"] = edge_line_token(str(orient), float(c))
    elif (d.get("orient") and d.get("c")):
        try:
            d["line"] = edge_line_token(str(d["orient"]), float(d["c"]))
        except Exception:
            pass
    if s is not None:
        d["s"] = _fmt4(s)
    if w is not None:
        d["w"] = _fmt4(w)
    if rooms is not None:
        d["rooms"] = ",".join(sorted({str(r) for r in rooms if str(r)}))
    return dump_meta(d)


def anchor_centerline_endpoints(*, orient: str, c: float, s: float, width: float) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    half = 0.5 * float(width)
    if str(orient).upper().startswith("H"):
        return (float(s) - half, float(c)), (float(s) + half, float(c))
    return (float(c), float(s) - half), (float(c), float(s) + half)


def clamp_anchor_s(*, span_len: float, s: float, width: float) -> float:
    L = float(span_len)
    width = max(0.0, float(width))
    half = 0.5 * width
    if L <= width + EPS:
        return 0.5 * L
    return max(half, min(float(s), L - half))


def project_point_to_edge_span(x: float, y: float, *, orient: str, c: float, a0: float, a1: float) -> float:
    a_min = min(float(a0), float(a1))
    a_max = max(float(a0), float(a1))
    coord = float(x) if str(orient).upper().startswith("H") else float(y)
    return max(a_min, min(coord, a_max))


def _safe_float(v: object) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except Exception:
        return None
