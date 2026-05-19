from __future__ import annotations

APP_NAME = "Heizlast Tool"
APP_INTERNAL_VERSION = "37.1.0"
APP_VERSION_LABEL = f"Version {APP_INTERNAL_VERSION}"

MAIN_FEATURES = [
    "2D-Grundrissbearbeitung für KG, EG und DG",
    "Heizlastberechnung mit Raum-, Flächen- und Elementauswertung",
    "Auto-Wände, Auto-Keller sowie DG-Dach-/Giebel-Ableitung",
    "Projektparameter für Randbedingungen, Geometrie, Erdreich und Wärmebrücken",
    "PDF-/CSV-/Grundriss-Export und integriertes Reporting",
    "3D-Hausansicht mit drehbarer Darstellung, Materialumschaltung, Dachmaterial und Dach-Profilparametern",
    "Winkel-/Kehldach für L-förmige Gebäudegrundrisse in der 3D-Ansicht",
    "Dachlinien-Editor für First-, Grat- und Kehllinien direkt in der Draufsicht",
    "Echte Dachfacetten-Zerlegung: Dachflächen zwischen First, Grat und Kehle werden als einzelne Polygone berechnet und in Vorschau/3D separat ausgewiesen",
    "Projekt-Dashboard, geführter Normstart, versionierte Projektkopien, Export-Auswahl und Raumdaten-Status",
    "Arbeits-Checkliste und raumweise DIN-Nachweis-Matrix für schnellere Projektprüfung",
    "Bauteil-Assistent, Projektverwaltung und strukturierte Nachweisübersicht im Report",
    "Heizlast-Audit im Dashboard mit Top-Lasttreibern und DG-Dach-/Giebelflächenprüfung",
    "Bauteil-Assistent unterstützt Innenwände für Nachbarzonen und Interzone",
]

DIN_CONFORMITY = [
    "DIN-nahe Auslegung und Reporting mit Bezug auf DIN EN 12831-1 und DIN/TS 12831-1",
    "Norm-Außentemperatur, Transmissions- und Lüftungsanteile parametrierbar",
    "Wärmebrücken-Ansätze über ΔU-, ψ- und Prozent-Modus verfügbar",
    "Erdreich- und Geschossdeckenansätze projektbezogen konfigurierbar",
    "DIN-Prüfung bewertet Raumdaten, Bauteildaten, Transmissionsdetails und fehlende Quellen konservativ",
    "Raum-Matrix zeigt Außenwand, Fenster, Dach, Decke, Boden, Wärmebrücken, Lüftung, Temperatur und Nachbarzonen",
    "Bauteile führen Quellen-/Annahmenstatus, der in GUI und Report sichtbar wird",
    "Audit markiert auffällige Raumlasten, hohe Fenster-/Dachanteile und mögliche Dach-/Giebel-Doppelungen",
]
