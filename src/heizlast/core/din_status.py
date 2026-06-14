from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..domain.models import ElementModel, RoomModel
from .config import VentilationCfg


ANNEX_DIN_CONFORMITY_ROWS = [
    ["Normbaustein", "DIN-Anforderung (Kurz)", "Tool-Umsetzung", "Status"],
    ["Raumweise Heizlast", "Phi_HL,Raum", "raumweise Q_sum_W", "✓"],
    ["Transmission", "Summe(U*A*dT*f)", "implementiert", "✓"],
    ["Öffnungsabzug", "A_eff = A_Wand - A_Öffnungen", "geometrisch", "✓"],
    ["Innen-/Außenmaß", "normativ definierte Maße", "Umschaltung A_trans", "△"],
    ["Lüftung", "Norm-Lüftungswärmeverlust", "raumweise n, Mindestluftwechsel und Infiltration als Volumenstrombilanz", "△"],
    ["Mechanische Lüftung", "Volumenströme, WRG", "mechanischer Restwärmeverlust mit WRG, Infiltration und ungedecktem Mindestvolumenstrom", "△"],
    ["Wärmebrücken", "Psi-Werte / Zuschläge", "optional via tb_cfg (dU/Psi/%), separat im Report", "△"],
    ["Erdreich/Boden", "Normverfahren", "vereinfachtes Erdreichmodell (Bodenplatte/Kellerwand, optional perimeter)", "△"],
    ["Aufheizzuschlag", "Phi_hu", "vereinfachtes q_hu*A_ref-Modul", "△"],
    ["Gewinne", "interne/solare Gewinne", "für Norm-Heizlast nicht als Lastminderung berücksichtigt", "△"],
]

ANNEX_DIN_VALIDATION_ROWS = [
    ["Prüfbereich", "Status", "Hinweis"],
    ["Temperaturzonen", "△", "Außenluft, Erdreich, unbeheizter Keller/Dachraum/Abseite und Interzone werden als Buckets ausgewiesen."],
    ["DIN/TS-Faktoren unbeheizt", "△", "strukturierte Default-Faktoren vorhanden; projektspezifische Prüfung bleibt erforderlich."],
    ["Transmissions-Buckets", "✓", "Rechenzeilen enthalten bucket, boundary_bucket und boundary_label."],
    ["Lüftung / WRG", "△", "Volumenstrombilanz mit Mindestluftwechsel, Infiltration und WRG-Rest vorhanden; Anlagen-/Normtabellenprüfung bleibt projektbezogen."],
    ["Aufheizzuschlag", "✗", "noch nicht implementiert."],
]

ANNEX_DIN_ACTION_ROWS = [
    ["Priorität", "Normbaustein", "Status", "Nächster Schritt"],
    ["1", "Aufheizzuschlag", "△", "Vereinfachtes q_hu-Modul gegen Normtabellen/Projektquelle absichern."],
    ["2", "Mechanische Lüftung / WRG", "△", "Anlagen-/Raumluftbilanz mit Projektquelle und Normtabellenwerten absichern."],
    ["3", "Erdreich", "△", "DIN/TS-Ersatzfaktoren gegen projektspezifischen Nachweis oder vollständiges Normverfahren absichern."],
    ["4", "Wärmebrücken", "△", "Psi-Werte je Anschluss/Element erfassen oder dU-Ansatz mit Quelle dokumentieren."],
    ["5", "Unbeheizte Bereiche", "△", "Default-Faktoren durch projektspezifische Temperatur-/Faktorwahl mit Quellenhinweis absichern."],
]

ANNEX_DIN_PROOF_GATE_ROWS = [
    ["Gate", "Nachweisbedingung", "Tool-Status"],
    ["G1", "Normausgabe und nationale Ergänzung eindeutig benennen.", "teilweise: Quellenliste vorhanden, projektbezogene Normausgabe als Projektfeld vorbereitet"],
    ["G2", "Für jeden gelben/roten Baustein eine Quelle, Eingabe und Rechenzeile dokumentieren.", "teilweise: Quellenfelder und Rechenzeilen für Lüftung/WRG/Aufheizung vorhanden; Normtabellenbindung bleibt zu prüfen"],
    ["G3", "Erdreich, Lüftung/WRG und Aufheizzuschlag als eigene Normmodule ausweisen.", "teilweise: eigene Rechenzeilen vorhanden, Normtabellen-/Quellenbindung bleibt zu prüfen"],
    ["G4", "Wärmebrücken mit Anschlusswerten oder belegtem dU-Ansatz nachweisen.", "teilweise: Element-Psi-Werte werden geprüft, Anschlusskatalog/Quellenbindung bleibt projektbezogen"],
    ["G5", "Prüffähiger Report darf keine offene Rot-Bewertung enthalten.", "offen: Rot bleibt bewusst sichtbar, bis die Module umgesetzt sind"],
]

ANNEX_SOURCE_ROWS = [
    ["Quelle", "Verwendung im Tool"],
    ["DIN EN 12831-1:2017-09", "Grundverfahren Norm-Heizlast / raumweise Transmission und Lüftung"],
    ["DIN/TS 12831-1:2020-04", "deutsche Ergänzungen, Randbedingungen und unbeheizte Bereiche"],
    ["Handbuch ZUB Heizlast.pdf", "lokale Projektliteratur: raumweise Heizlast, Hüllflächen, Dachböden/Abseiten"],
    ["Heizlastberechnung_2019.pdf", "lokale Projektliteratur: Berechnungsschritte, Transmissionsflächen, Nachbarbereiche"],
]


@dataclass(frozen=True)
class DINStatus:
    conformity_rows: list[list[str]]
    validation_rows: list[list[str]]
    action_rows: list[list[str]]
    overall_status: str
    summary: str


def status_rank(status: str) -> int:
    return {"✓": 0, "△": 1, "✗": 2}.get(str(status).strip(), 1)


def status_label(status: str) -> str:
    if status == "✓":
        return "Grün"
    if status == "△":
        return "Gelb"
    return "Rot"


def result_has_positive(results: dict[str, dict[str, float]], *keys: str) -> bool:
    for rr in results.values():
        if not isinstance(rr, dict):
            continue
        for key in keys:
            try:
                if float(rr.get(key, 0.0) or 0.0) > 1e-9:
                    return True
            except Exception:
                continue
    return False


def _has_text(value: Any) -> bool:
    return bool(str(value or "").strip())


def _meta_has_any(elements: list[ElementModel] | None, *keys: str) -> bool:
    wanted = {k.strip() for k in keys}
    for e in elements or []:
        meta = str(getattr(e, "meta", "") or "")
        for chunk in meta.split("|"):
            if "=" not in chunk:
                continue
            key, value = chunk.split("=", 1)
            if key.strip() in wanted and str(value).strip():
                return True
    return False


def _has_deck_elements(elements: list[ElementModel] | None) -> bool:
    for e in elements or []:
        et = str(getattr(e, "element_type", "") or "").strip().lower()
        et = et.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
        if any(token in et for token in ("kellerdecke", "geschossdecke", "zwischendecke", "speicherdecke", "dachdecke")):
            return True
        if "decke" in et and any(token in et for token in ("keller", "geschoss", "zwischen", "speicher", "dach")):
            return True
    return False


def _meta_dict(e: ElementModel) -> dict[str, str]:
    out: dict[str, str] = {}
    for chunk in str(getattr(e, "meta", "") or "").split("|"):
        if "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def _deck_neighbor_zone_assessment(elements: list[ElementModel] | None) -> tuple[str, str]:
    deck_elements: list[ElementModel] = []
    for e in elements or []:
        if _has_deck_elements([e]):
            deck_elements.append(e)
    if not deck_elements:
        return "△", "keine Decken-Elemente im Prüfumfang erkannt; Projektaufbau prüfen"

    missing_required: list[str] = []
    missing_sources: list[str] = []
    unconfirmed_auto: list[str] = []
    missing_temperature: list[str] = []

    for e in deck_elements:
        meta = _meta_dict(e)
        ref = _element_ref(e)
        boundary = str(meta.get("boundary") or meta.get("boundary_condition") or "").strip()
        adj_floor = str(meta.get("adj_floor") or "").strip()
        deck_kind = str(meta.get("deck_kind") or "").strip()
        if not boundary and not adj_floor and not deck_kind:
            missing_required.append(ref)

        if not str(meta.get("u_source") or "").strip():
            missing_sources.append(ref)
        if not str(meta.get("area_source") or "").strip():
            missing_sources.append(ref)
        if not str(meta.get("t_source") or "").strip():
            missing_sources.append(ref)

        is_auto = "auto_deck=1" in str(getattr(e, "meta", "") or "") or str(getattr(e, "uid", "") or "").startswith("deck_")
        if is_auto and str(meta.get("assumptions_confirmed") or "").strip() not in {"1", "true", "True", "ja", "yes"}:
            unconfirmed_auto.append(ref)

        kind_text = (deck_kind + " " + adj_floor + " " + boundary + " " + _element_type_norm(e)).lower()
        if any(token in kind_text for token in ("keller", "speicher", "dach", "oben", "attic", "unheated")):
            if not (str(meta.get("t_adj_c") or "").strip() or str(meta.get("t_source") or "").strip()):
                missing_temperature.append(ref)

    if missing_required:
        return "✗", "Decken ohne eindeutige Nachbarzone/Randbedingung: " + ", ".join(missing_required[:5])
    if missing_temperature:
        return "✗", "Decken zu unbeheizten Bereichen ohne Temperaturbezug: " + ", ".join(missing_temperature[:5])

    issues: list[str] = []
    if missing_sources:
        issues.append("Quellen/Flächenherkunft fehlen bei: " + ", ".join(sorted(set(missing_sources))[:5]))
    if unconfirmed_auto:
        issues.append("Auto-Decken-Annahmen nicht bestätigt bei: " + ", ".join(unconfirmed_auto[:5]))
    if issues:
        return "△", "; ".join(issues)
    return "✓", "Decken mit Nachbarzone, Temperaturbezug, Flächen-/U-Wert-Quelle und bestätigten Auto-Annahmen dokumentiert"


def _interzone_temperature_assessment(elements: list[ElementModel] | None) -> tuple[str, str]:
    if elements is None:
        return "△", "Bauteilliste nicht an DIN-Prüfung übergeben"

    missing: list[str] = []
    checked = 0
    for e in elements or []:
        if not _is_transmission_element(e):
            continue
        meta = _meta_dict(e)
        boundary = str(meta.get("boundary") or meta.get("boundary_condition") or "").strip().lower()
        if boundary not in {"interzone", "adjacent_heated"}:
            continue
        checked += 1
        if not str(meta.get("t_adj_c") or "").strip():
            missing.append(_element_ref(e))

    if missing:
        return "△", "Interzone/Nachbarraum ohne t_adj_c; rechnerisch 0 K Fallback, fachlich prüfen: " + ", ".join(missing[:5])
    if checked:
        return "✓", "Interzone/Nachbarräume mit angrenzender Solltemperatur t_adj_c dokumentiert"
    return "✓", "keine expliziten Interzone-Bauteile im Prüfumfang"


def _element_ref(e: ElementModel) -> str:
    uid = str(getattr(e, "uid", "") or "").strip()
    et = str(getattr(e, "element_type", "") or "").strip()
    room_id = str(getattr(e, "room_id", "") or "").strip()
    return uid or f"{room_id}:{et}" or et or "Element"


def _element_type_norm(e: ElementModel) -> str:
    return (
        str(getattr(e, "element_type", "") or "")
        .strip()
        .lower()
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )


def _is_transmission_element(e: ElementModel) -> bool:
    et = _element_type_norm(e)
    return any(token in et for token in (
        "wand",
        "fenster",
        "tuer",
        "decke",
        "boden",
        "dach",
        "platte",
    ))


def _room_data_assessment(
    rooms: list[RoomModel] | None,
    results: dict[str, dict[str, float]],
) -> tuple[str, str]:
    if rooms is None:
        return "△", "Raumliste nicht an DIN-Prüfung übergeben; nur Ergebnisdaten bewertet"
    if not rooms:
        return "✗", "keine Räume im Prüfumfang"

    missing_results: list[str] = []
    invalid_geometry: list[str] = []
    missing_usage: list[str] = []
    for room in rooms:
        rid = str(getattr(room, "id", "") or "").strip()
        label = rid or str(getattr(room, "name", "") or "Raum")
        try:
            area = float(room.area_m2())
        except Exception:
            area = 0.0
        height = float(getattr(room, "height_m", 0.0) or 0.0)
        volume = float(getattr(room, "volume_m3", 0.0) or 0.0)
        t_inside = float(getattr(room, "t_inside_c", 0.0) or 0.0)
        air_change = float(getattr(room, "air_change_1ph", 0.0) or 0.0)
        if area <= 0.0 or height <= 0.0 or volume <= 0.0 or not (5.0 <= t_inside <= 35.0) or air_change < 0.0:
            invalid_geometry.append(label)
        if rid and rid not in results:
            missing_results.append(label)
        if not _has_text(getattr(room, "usage_type", "")):
            missing_usage.append(label)

    if invalid_geometry:
        return "✗", "ungültige Raumdaten: " + ", ".join(invalid_geometry[:5])
    if missing_results:
        return "✗", "Räume ohne Heizlastergebnis: " + ", ".join(missing_results[:5])
    if missing_usage:
        return "△", "Nutzung/Solltemperatur fachlich prüfen; usage_type fehlt bei: " + ", ".join(missing_usage[:5])
    return "✓", "alle Räume haben Fläche, Höhe, Volumen, Solltemperatur, Lüftungswert und Ergebnis"


def _element_data_assessment(elements: list[ElementModel] | None) -> tuple[str, str]:
    if elements is None:
        return "△", "Bauteilliste nicht an DIN-Prüfung übergeben"
    transmission_elements = [e for e in elements if _is_transmission_element(e)]
    if not transmission_elements:
        return "✗", "keine transmissionsrelevanten Bauteile im Prüfumfang"

    invalid: list[str] = []
    weak_geometry: list[str] = []
    for e in transmission_elements:
        ref = _element_ref(e)
        area = float(getattr(e, "area_m2", 0.0) or 0.0)
        u_value = float(getattr(e, "u_w_m2k", 0.0) or 0.0)
        factor = float(getattr(e, "factor", 0.0) or 0.0)
        room_id = str(getattr(e, "room_id", "") or "").strip()
        if area <= 0.0 or u_value <= 0.0 or factor < 0.0 or not room_id:
            invalid.append(ref)
            continue
        et = _element_type_norm(e)
        if any(token in et for token in ("wand", "fenster", "tuer", "dach")):
            length = float(getattr(e, "length_m", 0.0) or 0.0)
            height = float(getattr(e, "height_m", 0.0) or 0.0)
            if length <= 0.0 or height <= 0.0:
                weak_geometry.append(ref)

    if invalid:
        return "✗", "Bauteile mit fehlender Fläche/U-Wert/Faktor/Raum: " + ", ".join(invalid[:5])
    if weak_geometry:
        return "△", "Bauteile ohne vollständige Längen-/Höhengeometrie: " + ", ".join(weak_geometry[:5])
    return "✓", "transmissionsrelevante Bauteile haben Fläche, U-Wert, Faktor, Raumbezug und Geometrie"


def _transmission_detail_assessment(results: dict[str, dict[str, float]]) -> tuple[str, str]:
    detail_rows = []
    for rr in results.values():
        rows = rr.get("transmission_details") or rr.get("trans_details") or []
        if isinstance(rows, list):
            detail_rows.extend(row for row in rows if isinstance(row, dict))
    if not results:
        return "✗", "keine Ergebnisdaten vorhanden"
    if not detail_rows:
        return "△", "keine detaillierten Transmissions-Rechenzeilen im Ergebnis gefunden"

    missing: list[str] = []
    for row in detail_rows:
        ref = str(row.get("element_uid") or row.get("uid") or row.get("element_type") or "Rechenzeile")
        bucket = str(row.get("boundary_bucket", "") or row.get("bucket", "") or "").strip()
        label = str(row.get("boundary_label", "") or "").strip()
        role = str(row.get("surface_role", "") or "").strip()
        if not bucket or not label or not role:
            missing.append(ref)
    if missing:
        return "△", "Transmissionsdetails ohne Bucket/Label/Rolle: " + ", ".join(missing[:5])
    return "✓", "Transmissionsdetails enthalten boundary_bucket, boundary_label und surface_role"


def assess_din_status(
    *,
    results: dict[str, dict[str, float]],
    project_cfg: Any | None,
    vent_cfg: VentilationCfg,
    elements: list[ElementModel] | None = None,
    rooms: list[RoomModel] | None = None,
) -> DINStatus:
    """Build a conservative project-specific DIN status assessment."""
    has_results = bool(results)
    has_transmission = result_has_positive(
        results,
        "Q_trans_W",
        "Q_trans_out_W",
        "Q_trans_ground_W",
        "Q_trans_keller_W",
        "Q_trans_oben_W",
        "Q_trans_dachraum_W",
        "Q_trans_interzone_W",
    )
    has_ventilation = result_has_positive(results, "Q_vent_W")
    has_ground = result_has_positive(results, "A_env_ground_m2", "Q_trans_ground_W")

    floor_area_mode = str(getattr(project_cfg, "floor_area_mode", "") or "")
    c_air = float(getattr(project_cfg, "c_air", getattr(vent_cfg, "c_air", 0.34)) or 0.34)

    norm_edition = getattr(project_cfg, "norm_edition", "")
    t_source_detail = getattr(project_cfg, "t_out_source_detail", "")
    climate_station = getattr(project_cfg, "climate_station", "")
    climate_altitude = getattr(project_cfg, "climate_altitude_correction", "")
    tb_source = getattr(project_cfg, "thermal_bridge_source", "")
    ground_source = getattr(project_cfg, "ground_source", "")
    ventilation_source = getattr(project_cfg, "ventilation_source", "")
    reheat_source = getattr(project_cfg, "reheat_source", "")
    u_value_source = getattr(project_cfg, "u_value_source", "")

    tb = getattr(project_cfg, "tb", None)
    tb_mode = str(getattr(tb, "mode", "none") or "none")
    tb_status = "△"
    tb_text = "nicht angesetzt; für DIN-Nachweis projektspezifisch prüfen"
    if tb_mode == "psi":
        psi_default = float(getattr(tb, "psi_default_w_mk", 0.0) or 0.0)
        use_meta = bool(getattr(tb, "use_element_meta_psi", True))
        has_element_psi = _meta_has_any(elements, "psi_w_mk", "psi_L_m")
        if use_meta and not has_element_psi and psi_default <= 0.0:
            tb_status = "✗"
            tb_text = "Psi-Modus aktiv, aber keine Element-Psi-Werte und kein Default-Psi vorhanden"
        elif _has_text(tb_source):
            tb_text = "Psi-Modus aktiv; Quelle dokumentiert, Anschlussqualität projektbezogen prüfen"
        else:
            tb_text = "Psi-Modus aktiv; Quellen-/Anschlussnachweis fehlt noch"
    elif tb_mode == "delta_u":
        tb_text = "dU-Zuschlag aktiv; Quelle dokumentiert" if _has_text(tb_source) else "dU-Zuschlag aktiv; Quelle und Geltungsbereich dokumentieren"
    elif tb_mode == "percent":
        tb_text = "Prozent-Zuschlag aktiv; nur überschlägige Ersatzmethode"

    ground = getattr(project_cfg, "ground", None)
    ground_mode = str(getattr(ground, "mode", "simplified") or "simplified")
    ground_status = "△"
    ground_text = f"{ground_mode}; vereinfachtes Erdreichmodell"
    if ground_mode == "none" and has_ground:
        ground_status = "✗"
        ground_text = "Erdberührte Flächen vorhanden, Erdreichmodell deaktiviert"
    elif ground_mode == "perimeter":
        ground_text = "perimeter; zusätzlicher Psi-Perimeteransatz, weiter DIN/TS-orientiert"
    elif ground_mode == "din_ts":
        src = getattr(ground, "din_ts_source", "")
        ground_text = "DIN/TS-orientierter Ersatztemperaturansatz aktiv"
        if _has_text(src):
            ground_text += "; DIN/TS-Faktorquelle dokumentiert"
    if _has_text(ground_source) and ground_status != "✗":
        ground_text += "; Quelle dokumentiert"

    ventilation_mode = str(getattr(project_cfg, "ventilation_mode", "natural") or "natural")
    supply = float(getattr(project_cfg, "mech_supply_m3h", 0.0) or 0.0)
    exhaust = float(getattr(project_cfg, "mech_exhaust_m3h", 0.0) or 0.0)
    hrv = float(getattr(project_cfg, "heat_recovery_efficiency", 0.0) or 0.0)
    if ventilation_mode == "mechanical":
        if max(supply, exhaust) <= 0.0:
            mech_status = "✗"
            mech_text = "mechanisch gewählt, aber Volumenstrom fehlt"
        else:
            mech_status = "△"
            src_note = "; Quelle dokumentiert" if _has_text(ventilation_source) else "; Quellenhinweis fehlt"
            n_min = float(getattr(project_cfg, "min_air_change_1ph", 0.0) or 0.0)
            n_inf = float(getattr(project_cfg, "infiltration_air_change_1ph", 0.0) or 0.0)
            mech_text = f"mechanischer Restwärmeverlust aktiv; Volumenstrombilanz: V_sup={supply:.1f} m³/h, V_exh={exhaust:.1f} m³/h, WRG={hrv:.0%}, n_min={n_min:.3f} 1/h, n_inf={n_inf:.3f} 1/h{src_note}"
    else:
        mech_status = "△"
        mech_text = "natürliche Lüftung / Grundmodell; mechanische Lüftung nicht angesetzt"

    reheat_enabled = bool(getattr(project_cfg, "reheat_enabled", False))
    reheat_power = float(getattr(project_cfg, "reheat_power_w_m2", 0.0) or 0.0)
    reheat_duration = float(getattr(project_cfg, "reheat_duration_h", 0.0) or 0.0)
    reheat_drop = float(getattr(project_cfg, "reheat_temp_drop_k", 0.0) or 0.0)
    has_reheat_result = result_has_positive(results, "Q_reheat_W")
    if reheat_enabled and has_reheat_result and (reheat_power > 0.0 or (reheat_duration > 0.0 and reheat_drop > 0.0)):
        reheat_status = "△"
        reheat_text = (
            f"q_hu direkt aktiv: {reheat_power:.2f} W/m²"
            if reheat_power > 0.0
            else f"hergeleitet aus Dauer={reheat_duration:.2f} h und Absenkung={reheat_drop:.2f} K"
        )
        if _has_text(reheat_source):
            reheat_text += "; Quelle dokumentiert"
        else:
            reheat_text += "; Quellenhinweis fehlt"
    else:
        reheat_status = "✗"
        reheat_text = "nicht angesetzt; q_hu fehlt oder Aufheizzuschlag deaktiviert"

    measure_status = "✓" if floor_area_mode in {"inner", "outer"} else "△"
    vent_status = "△" if c_air > 0 and (has_ventilation or has_results) else "✗"
    trans_status = "✓" if has_transmission else "✗"
    room_status = "✓" if has_results else "✗"
    source_status = "△" if (_has_text(norm_edition) and _has_text(t_source_detail) and (_has_text(climate_station) or _has_text(climate_altitude))) else "✗"
    u_source_status = "△" if _has_text(u_value_source) else "✗"
    u_source_text = "U-Wert-Quelle dokumentiert" if _has_text(u_value_source) else "Quelle der Bauteil-U-Werte fehlt"
    deck_status, deck_text = _deck_neighbor_zone_assessment(elements)
    interzone_status, interzone_text = _interzone_temperature_assessment(elements)
    room_data_status, room_data_text = _room_data_assessment(rooms, results)
    element_data_status, element_data_text = _element_data_assessment(elements)
    detail_status, detail_text = _transmission_detail_assessment(results)

    conformity_rows = [
        ANNEX_DIN_CONFORMITY_ROWS[0],
        ["Norm-/Quellenbezug", "Normausgabe und lokale Randdaten", "Projektfelder für Normausgabe und Quellen", source_status],
        ["U-Werte / Bauteilnachweis", "U-Werte je Bauteil mit Quelle", u_source_text, u_source_status],
        ["Raumdaten", "Raumweise Nutzungs-, Geometrie- und Temperaturdaten", room_data_text, room_data_status],
        ["Bauteildaten", "Fläche, U-Wert, Faktor und Raumbezug je Hüllbauteil", element_data_text, element_data_status],
        ["Raumweise Heizlast", "Phi_HL,Raum", "raumweise Q_sum_W" if has_results else "keine Ergebnisse im Report", room_status],
        ["Transmission", "Summe(U*A*dT*f)", "implementiert und Ergebnisanteile vorhanden" if has_transmission else "keine Transmissionsanteile gefunden", trans_status],
        ["Transmissionsdetails", "Prüffähige Rechenzeilen mit Randbedingung und Bauteilrolle", detail_text, detail_status],
        ["Decken / Nachbarzonen", "Kellerdecke, Zwischendecke, Speicherdecke mit passender Nachbarzone", deck_text, deck_status],
        ["Interzone / Nachbarräume", "angrenzende Solltemperatur dokumentieren", interzone_text, interzone_status],
        ["Öffnungsabzug", "A_eff = A_Wand - A_Öffnungen", "geometrisch/ankerbasiert im Rechenkern", "✓"],
        ["Innen-/Außenmaß", "normativ definierte Maße", f"Projektmodus: {floor_area_mode or 'nicht gesetzt'}", measure_status],
        ["Lüftung", "Norm-Lüftungswärmeverlust", f"Grundmodell n*V*dT mit c_air={c_air:.3f}", vent_status],
        ["Mechanische Lüftung", "Volumenströme, WRG", mech_text, mech_status],
        ["Wärmebrücken", "Psi-Werte / Zuschläge", tb_text, tb_status],
        ["Erdreich/Boden", "Normverfahren", ground_text, ground_status],
        ["Aufheizzuschlag", "Phi_hu", reheat_text, reheat_status],
        ["Gewinne", "interne/solare Gewinne", "für Norm-Heizlast nicht als Lastminderung berücksichtigt", "△"],
    ]

    validation_rows = [
        ANNEX_DIN_VALIDATION_ROWS[0],
        ["Norm-/Quellenbezug", source_status, "Normausgabe, Außentemperaturquelle, Klimaregion/-station oder Höhenkorrektur müssen projektbezogen dokumentiert sein."],
        ["U-Wert-Quellen", u_source_status, u_source_text],
        ["Raumdaten", room_data_status, room_data_text],
        ["Bauteildaten", element_data_status, element_data_text],
        ["Temperaturzonen", "△", "Außenluft, Erdreich, unbeheizter Keller/Dachraum/Abseite und Interzone werden als Buckets ausgewiesen."],
        ["Decken / Nachbarzonen", deck_status, deck_text],
        ["Interzone / Nachbarräume", interzone_status, interzone_text],
        ["DIN/TS-Faktoren unbeheizt", "△", "Default-Faktoren vorhanden; projektspezifische Prüfung und Quellenhinweis bleiben erforderlich."],
        ["Transmissions-Buckets", detail_status if has_transmission else "✗", detail_text if has_transmission else "keine Transmissionsanteile gefunden."],
        ["Lüftung / WRG", mech_status if ventilation_mode == "mechanical" else vent_status, mech_text],
        ["Aufheizzuschlag", reheat_status, reheat_text],
        ["Erdreich", ground_status, ground_text],
        ["Wärmebrücken", tb_status, tb_text],
    ]

    action_rows = [ANNEX_DIN_ACTION_ROWS[0]]
    for row in ANNEX_DIN_ACTION_ROWS[1:]:
        action_rows.append(list(row))
    if source_status == "✗":
        action_rows.append(["1", "Norm-/Quellenbezug", "✗", "Normausgabe, Außentemperaturquelle und Quellenfelder in den Projektparametern ausfüllen."])
    if u_source_status == "✗":
        action_rows.append(["1", "U-Werte / Bauteile", "✗", "Quelle für Projekt-U-Werte hinterlegen oder U-Werte je Element mit Nachweis dokumentieren."])
    if trans_status == "✗":
        action_rows.append(["1", "Transmission", "✗", "Ergebnisdaten prüfen; ohne Transmissionsanteile kein belastbarer Heizlastnachweis."])
    if room_status == "✗":
        action_rows.append(["1", "Raumweise Ergebnisse", "✗", "Berechnung ausführen, bevor der Report als Nachweis verwendet wird."])
    if room_data_status == "✗":
        action_rows.append(["1", "Raumdaten", "✗", "Raumfläche, Raumhöhe, Volumen, Solltemperatur und Luftwechsel je Raum korrigieren."])
    elif room_data_status == "△":
        action_rows.append(["2", "Raumdaten", "△", "Nutzungstypen und Solltemperaturen je Raum dokumentieren."])
    if element_data_status == "✗":
        action_rows.append(["1", "Bauteildaten", "✗", "Fläche, U-Wert, Faktor und Raumbezug aller transmissionsrelevanten Bauteile prüfen."])
    elif element_data_status == "△":
        action_rows.append(["2", "Bauteildaten", "△", "Längen-/Höhengeometrie der Bauteile ergänzen, damit Öffnungen und Hüllflächen prüfbar bleiben."])
    if detail_status == "△":
        action_rows.append(["2", "Transmissionsdetails", "△", "Transmissions-Rechenzeilen mit boundary_bucket, boundary_label und surface_role ausweisen."])
    if interzone_status != "✓":
        action_rows.append(["2", "Interzone / Nachbarräume", interzone_status, interzone_text])
    if tb_status == "✗":
        action_rows.append(["2", "Wärmebrücken", "✗", "Im Psi-Modus Element-Psi-Werte oder einen dokumentierten Default-Psi hinterlegen."])

    worst = max(status_rank(row[-1]) for row in conformity_rows[1:])
    overall_status = "✓" if worst == 0 else "△" if worst == 1 else "✗"
    if overall_status == "✗":
        summary = "DIN-Ampel: Rot – DIN-orientierter Arbeitsstand, nicht als vollständiger Normnachweis einzustufen; offene Normbausteine sind im Maßnahmenplan aufgeführt."
    elif overall_status == "△":
        summary = "DIN-Ampel: Gelb – DIN-orientierter Nachweis mit projektspezifisch zu prüfenden Annahmen."
    else:
        summary = "DIN-Ampel: Grün – alle im Tool bewerteten Bausteine sind erfüllt; die fachliche Prüfung der Normquellen bleibt erforderlich."

    return DINStatus(conformity_rows, validation_rows, action_rows, overall_status, summary)


def din_status_summary(
    *,
    results: dict[str, dict[str, float]],
    project_cfg: Any | None,
    vent_cfg: VentilationCfg,
    elements: list[ElementModel] | None = None,
    rooms: list[RoomModel] | None = None,
) -> tuple[str, str]:
    status = assess_din_status(results=results, project_cfg=project_cfg, vent_cfg=vent_cfg, elements=elements, rooms=rooms)
    return status.overall_status, status.summary
