# Heizlast – Building Heat Load & Geometry Tool

Engineering-Tool zur **Heizlastberechnung und Gebäudegeometrie-Analyse** nach **DIN EN 12831** mit integrierter **2D-Planung, 3D-Gebäudemodell und Dachgeometrie-Simulation**.

Das Programm erlaubt es, Gebäudegeometrien interaktiv zu erstellen, Bauteile zu definieren und daraus automatisch Heizlasten sowie geometrische Ableitungen (z. B. Dachflächen, Giebel, Wandflächen) zu berechnen.

---

# Features

## Gebäudeplanung

* Interaktiver **2D-Grundrisseditor**
* Wände, Räume und Öffnungen (Fenster/Türen)
* automatische Flächen- und Umfangsermittlung
* Raumzuordnung für Heizlastberechnung

---

## 3D-Gebäudeansicht

* drehbares **3D-Gebäudemodell**
* Visualisierung von:

  * Wandmaterialien
  * Dachformen
  * Gebäudegeometrie
* Materialauswahl

Fassade:

* Klinker
* Putz
* Holz
* Beton

Dachmaterial:

* Ziegel (erste implementierte Variante)

---

## Dachmodellierung

Unterstützte Dachprofile:

* Satteldach
* Pultdach
* Walmdach
* Flachdach

Parametrisierbar:

* Firstrichtung
* Dachüberstand
* Firstversatz (asymmetrisches Dach)
* Pultdach-Neigungsrichtung

Automatische Ableitung von:

* Dachflächen
* Giebelflächen
* Walmdach-Geometrie
* DG-Flächen

---

## Automatische DG- und Dachflächenberechnung

Die Software berechnet automatisch:

* Dachflächen
* Giebelgeometrie
* Attic-Flächen
* Dachlaufweiten

Parameter berücksichtigt:

* Firstrichtung
* Dachneigung
* Firstversatz
* Walmdach-Geometrie

---

## Wand-2D-Ansicht (Kontextmenü)

Rechtsklick auf eine Wand öffnet ein Kontextmenü.

Menüpunkt:

```
Ansicht
```

öffnet eine **2D-Wandansicht** mit:

* Wandbreite
* Wandhöhe
* Fensterpositionen
* Türpositionen

Darstellung enthält:

* Fensterhöhe
* Brüstungshöhe
* Öffnungsbreite
* Wandabstände

Bemaßungen:

* Abstand links
* Fensterbreite
* Abstand rechts
* Brüstungshöhe
* Öffnungshöhe

---

## Projekteinstellungen

Modernisierte UI mit **linker Navigationsspalte**.

Bereiche:

* Projektinfo
* Randbedingungen
* Geometrie
* Lüftung
* Auto-Decken
* Wärmebrücken
* Erdreich
* DG-Dach

Eigenschaften:

* Gruppenbox-Layout
* dynamische Felder
* Engineering-Struktur

---

# Architektur

Projektstruktur:

```
heizlast/
│
├─ core/
│  ├─ geometry
│  ├─ attic
│  ├─ wall_openings
│  └─ heatload
│
├─ gui/
│  ├─ main_window
│  ├─ plan_view
│  ├─ project_settings
│  ├─ wall_view_dialog
│  └─ 3d_view
│
├─ config/
│
└─ tests/
```

Technologien:

* Python
* PySide6 / Qt
* Matplotlib / Qt Graphics
* JSON Projektdateien

---

# Installation

## Voraussetzungen

Python ≥ 3.10

Installation:

```bash
pip install -r requirements.txt
```

oder minimal:

```bash
pip install PySide6 matplotlib numpy
```

---

# Start

Programm starten:

```bash
python main.py
```

oder

```bash
python -m heizlast
```

---

# Projektdateien

Projektdateien werden als JSON gespeichert.

Schema enthält u. a.:

* Gebäudegeometrie
* Dachparameter
* Materialwahl
* Raumdefinitionen
* Heizlastparameter

---

# Roadmap

Geplante Erweiterungen:

* interaktive **3D-Gebäudeeditor**
* Fenster direkt in der **Wandansicht verschiebbar**
* **Dachmaterialien erweitern**

  * Blech
  * Bitumen
  * Gründach
* **IFC / BIM-Import**
* **Heizlastbericht PDF**
* **U-Wert Datenbank**

---

# Beispiel

Typischer Workflow:

1. Grundriss zeichnen
2. Räume definieren
3. Fenster und Türen hinzufügen
4. Dachprofil auswählen
5. 3D-Gebäude prüfen
6. Heizlast berechnen

---

# Lizenz

MIT License

---

# Autor

Chris Bühring

Engineering Tools
Building Physics / HVAC Simulation

---

Wenn du möchtest, kann ich dir zusätzlich noch:

* ein **richtig professionelles GitHub README mit Bildern**
* ein **Architekturdiagramm**
* ein **README-Badge-System**
* eine **GitHub-Landingpage mit Screenshots**

bauen. Das macht das Projekt deutlich professioneller auf GitHub.
