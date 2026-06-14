from __future__ import annotations

from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    ListFlowable,
    ListItem,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "Heizlast_Benutzerdokumentation.pdf"


def styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=26,
            leading=31,
            textColor=colors.HexColor("#153243"),
            alignment=TA_CENTER,
            spaceAfter=12,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#425466"),
            alignment=TA_CENTER,
            spaceAfter=16,
        ),
        "h1": ParagraphStyle(
            "Heading1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=21,
            textColor=colors.HexColor("#153243"),
            spaceBefore=12,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "Heading2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12.5,
            leading=16,
            textColor=colors.HexColor("#1d4e89"),
            spaceBefore=9,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.3,
            leading=13,
            textColor=colors.HexColor("#1f2933"),
            spaceAfter=5,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.1,
            leading=10.8,
            textColor=colors.HexColor("#334155"),
        ),
        "table_head": ParagraphStyle(
            "TableHead",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8.2,
            leading=10.5,
            textColor=colors.white,
        ),
        "table": ParagraphStyle(
            "Table",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.8,
            leading=10.2,
            textColor=colors.HexColor("#1f2933"),
        ),
        "note": ParagraphStyle(
            "Note",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.4,
            leading=11.5,
            textColor=colors.HexColor("#1f2933"),
            leftIndent=6,
            rightIndent=6,
            spaceBefore=4,
            spaceAfter=4,
        ),
    }


S = styles()


UMLAUT_NORMALIZATION = (
    ("Menue", "Menü"),
    ("menue", "menü"),
    ("fuer", "für"),
    ("Fue", "Fü"),
    ("fue", "fü"),
    ("Raeume", "Räume"),
    ("raeume", "räume"),
    ("Raume", "Räume"),
    ("Waende", "Wände"),
    ("waende", "wände"),
    ("Wanddicken", "Wanddicken"),
    ("Aussen", "Außen"),
    ("aussen", "außen"),
    ("Oeff", "Öff"),
    ("oeff", "öff"),
    ("Pruef", "Prüf"),
    ("pruef", "prüf"),
    ("Gruen", "Grün"),
    ("gruen", "grün"),
    ("Hoehe", "Höhe"),
    ("hoehe", "höhe"),
    ("Lueft", "Lüft"),
    ("lueft", "lüft"),
    ("Waerme", "Wärme"),
    ("waerme", "wärme"),
    ("Gebaeude", "Gebäude"),
    ("gebaeude", "gebäude"),
    ("Flaeche", "Fläche"),
    ("flaeche", "fläche"),
    ("Daemm", "Dämm"),
    ("Aufmass", "Aufmaß"),
    ("ueber", "über"),
    ("Ueber", "Über"),
    ("Rueck", "Rück"),
    ("rueck", "rück"),
    ("Aender", "Änder"),
    ("aender", "änder"),
    ("ergaenz", "ergänz"),
    ("Ergaenz", "Ergänz"),
    ("waehl", "wähl"),
    ("Waehl", "Wähl"),
    ("moeglich", "möglich"),
    ("Moeglich", "Möglich"),
    ("goess", "göss"),
    ("groess", "größ"),
    ("Groess", "Größ"),
    ("schliessen", "schließen"),
    ("gross", "groß"),
    ("Gross", "Groß"),
)


def de(text: str) -> str:
    for old, new in UMLAUT_NORMALIZATION:
        text = text.replace(old, new)
    return text


def p(text: str, style: str = "body") -> Paragraph:
    return Paragraph(de(text), S[style])


def heading(text: str, level: int = 1) -> Paragraph:
    return p(text, "h1" if level == 1 else "h2")


def bullets(items: list[str]) -> ListFlowable:
    return ListFlowable(
        [ListItem(p(item, "body"), leftIndent=9) for item in items],
        bulletType="bullet",
        leftIndent=12,
        bulletFontName="Helvetica",
        bulletFontSize=7,
        spaceAfter=5,
    )


def note(text: str) -> Table:
    tbl = Table([[p(text, "note")]], colWidths=[174 * mm])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eef6f7")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#7bb6bd")),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return tbl


def table(headers: list[str], rows: list[list[str]], widths: list[float]) -> Table:
    data = [[p(h, "table_head") for h in headers]]
    data.extend([[p(cell, "table") for cell in row] for row in rows])
    tbl = Table(data, colWidths=[w * mm for w in widths], repeatRows=1)
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d4e89")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#c9d6df")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f9fb")]),
            ]
        )
    )
    return tbl


def footer(canvas, doc):
    canvas.saveState()
    width, _height = A4
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#667085"))
    canvas.drawString(18 * mm, 10 * mm, "Heizlast Tool - Benutzerdokumentation")
    canvas.drawRightString(width - 18 * mm, 10 * mm, f"Seite {doc.page}")
    canvas.restoreState()


def cover(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(colors.HexColor("#153243"))
    canvas.rect(0, height - 48 * mm, width, 48 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#cce6f4"))
    canvas.rect(0, height - 50 * mm, width, 2 * mm, fill=1, stroke=0)
    canvas.restoreState()
    footer(canvas, doc)


def menu_rows() -> list[list[str]]:
    return [
        ["Datei > Neues Projekt > Neues leeres Projekt", "Legt ein leeres Projekt mit Standardwerten an.", "Start fuer einfache Varianten oder schnelle Tests."],
        ["Datei > Neues Projekt > Neues Projekt mit Projektparametern", "Erstellt ein Projekt und oeffnet danach direkt die Projektparameter.", "Empfohlener Einstieg, wenn Randbedingungen bekannt sind."],
        ["Datei > Neues Projekt > Neues Projekt-Assistent", "Fuehrt durch Projektanlage, Normpruefung, U-Werte, Lueftung und Erdreich.", "Bester Start fuer eine nachvollziehbare Heizlastberechnung."],
        ["Datei > Zuletzt verwendet", "Oeffnet zuletzt genutzte Projektdateien.", "Praktisch fuer laufende Bearbeitungsstaende."],
        ["Datei > Projekt laden", "Laedt Raum- und Elementdaten eines Projekts.", "Vorhandene CSV/JSON-Projekte weiterbearbeiten."],
        ["Datei > Projekt speichern", "Speichert den aktuellen Projektstand.", "Regelmaessig nutzen, besonders vor Export oder groesseren Auto-Aktionen."],
        ["Datei > Projekt speichern unter", "Speichert das Projekt unter neuem Namen.", "Varianten, Pruefstaende oder Sicherungskopien anlegen."],
        ["Datei > Report & Grundrisse exportieren", "Exportiert PDF-Report, DIN-Formbericht, CSVs und Grundrisse je nach Auswahl.", "Abschluss einer Berechnung oder Zwischenstand fuer Pruefung."],
        ["Projekt > Projektparameter", "Oeffnet alle zentralen Randbedingungen: Projektinfo, Klima, Geometrie, U-Werte, Lueftung, Erdreich, Dach und Normpruefung.", "Zentrale Stelle fuer fachliche Annahmen."],
        ["Projekt > Normpruefung", "Springt direkt zur DIN-Pruefliste und zu fehlenden Quellen.", "Gelbe/rote Tool-Gates gezielt abarbeiten."],
        ["Projekt > Projekt-Dashboard", "Zeigt DIN-Ampel, Speicherstatus, Raum-Matrix, offene Punkte und Heizlast-Audit.", "Kontrollzentrum waehrend der Bearbeitung."],
        ["Projekt > Projektverwaltung", "Zeigt zuletzt verwendete Projekte, Versionen und Backups.", "Projektstaende nachvollziehen und Varianten finden."],
        ["Projekt > U-Werte", "Oeffnet Projekt-U-Werte fuer typische Bauteile.", "Fallbackwerte fuer Auto-Waende, Decken, Boden und Dach pflegen."],
        ["Projekt > Lueftung", "Oeffnet Lueftung, Infiltration, WRG und Aufheizzuschlag.", "Lueftungsverluste und Zuschlaege dokumentieren."],
        ["Projekt > Erdreich", "Oeffnet Bodenplatte, erdberuehrte Bauteile und DIN/TS-Faktoren.", "Erdreichansatz mit Quelle und Zwischenwerten pflegen."],
        ["Projekt > Auto-Waende neu", "Erzeugt Aussen- und Innenwaende aus der Raumgeometrie neu.", "Nach Geometrieaenderungen verwenden; danach Plausibilitaet pruefen."],
        ["Projekt > Auto Keller", "Erzeugt Kellergeometrie aus EG-Aussenflaechen.", "Schneller Ansatz fuer unbeheizten Keller oder Kellerdecke."],
        ["Projekt > 3D Raum/Geschoss/Haus", "Oeffnet 3D-Ansichten fuer Raum, Geschoss oder gesamtes Haus.", "Geometrie und Dach visuell plausibilisieren."],
        ["Projekt > Dach/Giebel 0", "Pruefschalter, der Transmission von Dach- und Giebelelementen auf 0 setzen kann.", "Nur zur Fehlersuche bei moeglichen Doppelungen verwenden."],
        ["Projekt > 2D Gebaeudehuelle+ / Haus Seitenansicht / 3D Gebaeudehuelle+", "Zeigt Huelle, Wanddicken, Oeffnungen, Seitenansicht und OpenGL-Huelle.", "Kontrolle von Huelle, Dachlinien und Oeffnungen."],
        ["Bearbeiten > Auswahl loeschen", "Loescht die aktuelle Auswahl.", "Schnelles Entfernen einzelner Objekte."],
        ["Bearbeiten > Fenster/Tueren loeschen", "Loescht ausgewaehlte Fenster/Tueren.", "Oeffnungen gezielt bereinigen."],
        ["Bearbeiten > Raum-Operation rueckgaengig/wiederholen", "Macht Raumoperationen rueckgaengig oder wiederholt sie.", "Fuer Zeichen-, Teil- und Merge-Aktionen."],
        ["Bearbeiten > Aenderung rueckgaengig/wiederholen", "Snapshot-basierte Projekt-Aenderung rueckgaengig machen oder wiederholen.", "Breiterer Sicherheitsanker fuer Projektarbeit."],
        ["Bearbeiten > Auswahlmodus", "Selektiert und verschiebt Objekte, ohne neue Raeume zu zeichnen.", "Normaler Arbeitsmodus."],
        ["Bearbeiten > Grundriss/Rechteck/L-Raum/Polygon zeichnen", "Aktiviert die jeweiligen Zeichenwerkzeuge.", "Raeume aus Plan oder Aufmass erfassen."],
        ["Bearbeiten > Raum teilen / Raeume verschmelzen / Raeume subtrahieren", "Bearbeitet bestehende Raumgeometrien.", "Feinmodellierung der Grundrissstruktur."],
        ["Bearbeiten > Raum loeschen", "Loescht ausgewaehlte Raeume.", "Nur nach Pruefung, da zugehoerige Bauteile betroffen sein koennen."],
        ["Ansicht > Beschriftungen regenerieren", "Baut Labels und Leader-Lines neu auf.", "Nach groesseren Geometrieaenderungen oder bei ueberlappenden Labels."],
        ["Ansicht > Aktuelle Skizze einpassen", "Zentriert und zoomt die aktive Geschossansicht.", "Schnell zurueck zur Gesamtansicht."],
        ["Ansicht > Heatmap anzeigen", "Schaltet die Heizlast-/Intensitaetsdarstellung ein oder aus.", "Lastschwerpunkte visuell erkennen."],
        ["Ansicht > Auto-Waende aktiv", "Schaltet automatische Aussen- und Innenwaende ein oder aus.", "Bei manueller Bauteilpflege bewusst setzen."],
        ["Ansicht > Fenster/Tuer einfuegen", "Aktiviert das Einfuegen von Oeffnungen.", "Fenster und Tueren auf Wandsegmenten platzieren."],
        ["Ansicht > Beschriftung Aussenwaende/Fenster/Innenwaende", "Blendet Beschriftungen getrennt ein oder aus.", "Uebersichtlichkeit im Plan steuern."],
        ["Ansicht > Debug-Overlay / Auto-DG-Markierungen / W/m2 Aussenflaeche", "Zeigt technische Flaechenreferenzen, DG-Markierungen und alternative Bezugsflaeche.", "Pruefung und Diagnose."],
        ["Dach > Dach-Editor", "Oeffnet den Dialog fuer Dachform, Geometrie, Linien, Gauben und Vorschau.", "DG-Dach systematisch modellieren."],
        ["Dach > Dachprofil waehlen", "Setzt Sattel-, Pult-, Walm-, Krueppelwalm-, Flach- oder Winkel-/Kehldach.", "Grundtyp vor Detailbearbeitung festlegen."],
        ["Dach > 3D-/Dachmaterial waehlen", "Waehlt Fassaden- und Dachmaterial fuer die 3D-Ansicht.", "Reine Visualisierung, keine Heizlastwirkung."],
        ["Dach > DG-Dachparameter / Zum Dachgeschoss / DG-Skizze aktualisieren", "Oeffnet Dachparameter, wechselt in DG-Ansicht oder aktualisiert die Skizze.", "Workflow rund um Dachgeschoss und Auto-DG."],
        ["Dach > DG-Dock anzeigen / Auto-DG-Markierungen", "Blendet das Dach-Dock und DG-Markierungen ein oder aus.", "Eingaben und Ableitungen sichtbar halten."],
        ["Hilfe > Info / Version / DIN", "Zeigt Versionen, Hauptfunktionen und DIN-Hinweise.", "Schnelle Orientierung zum Softwarestand."],
    ]


def workflow_rows() -> list[list[str]]:
    return [
        ["1", "Projekt anlegen", "Am besten Datei > Neues Projekt-Assistent verwenden. Projektname, Ordner und gefuehrten Normstart setzen.", "Projektdatei ist angelegt; Projektparameter wurden geoeffnet."],
        ["2", "Norm- und Klimadaten setzen", "Normausgabe, Aussentemperatur, Quelle/Region, Bearbeiter und Pruefvermerk dokumentieren.", "Projekt > Normpruefung zeigt keine roten Basisdaten."],
        ["3", "Geometrie erfassen", "Geschosse KG, EG und DG bearbeiten; Raeume zeichnen, teilen, verschmelzen oder aus Bestand ableiten.", "Alle Raeume haben plausible Flaechen und Raumhoehen."],
        ["4", "Raeume bedaten", "Nutzung, Solltemperatur, Luftwechsel und Raumhoehe im Raum-Inspector oder per Geschoss-Assistent setzen.", "Raumstatus ist fuer alle Raeume plausibel."],
        ["5", "Huelle erzeugen", "Auto-Waende neu ausfuehren und bei Bedarf Fenster, Tueren, Innenwaende, Decken, Boden und Dachbauteile pflegen.", "Elementliste enthaelt alle relevanten Huellelemente."],
        ["6", "U-Werte und Quellen pflegen", "Projekt-U-Werte setzen; Bauteile mit U-Wert, Flaechenherkunft, Randbedingung und Quellenstatus versehen.", "Bauteildialog zeigt keine offene Live-DIN-Warnung fuer wichtige Huellelemente."],
        ["7", "Sondermodule ergaenzen", "Lueftung/WRG, Erdreich, Waermebruecken, Aufheizzuschlag und Dachparameter eintragen.", "Dashboard zeigt diese Module nicht mehr als ungeprueft."],
        ["8", "Berechnung plausibilisieren", "Projekt-Dashboard, Raum-Matrix, Heizlast-Audit, Heatmap und 3D/2D-Huelle pruefen.", "Auffaellige W/m2-Werte, Fensteranteile oder DG-Doppelungen sind geklaert."],
        ["9", "Nachweise schliessen", "Normpruefung und Massnahmenplan abarbeiten; gelbe/rote Punkte mit Quelle oder fachlicher Entscheidung klaeren.", "Bei Prueffassung sind alle Tool-Gates gruen."],
        ["10", "Exportieren", "Datei > Report & Grundrisse exportieren. Umfang waehlen: PDF-Report, DIN-Formbericht, CSVs, Grundrisse.", "Exportordner enthaelt nachvollziehbare Ergebnisunterlagen."],
    ]


def build_story():
    today = date.today().strftime("%d.%m.%Y")
    story = [
        Spacer(1, 28 * mm),
        p("Heizlast Tool", "title"),
        p("Benutzerdokumentation fuer Bedienung, Menuebefehle und Aufbau einer Heizlastberechnung", "subtitle"),
        Spacer(1, 10 * mm),
        note(
            "Stand: 14.06.2026 | App-Version 2.11.0 | Anzeige-Version 39.0.0 | "
            "interne Version Heizlast_V39-intern-01. Diese Dokumentation beschreibt den aktuellen Arbeitsstand "
            "des Tools und ersetzt keine fachliche Pruefung durch eine qualifizierte Planung."
        ),
        Spacer(1, 8 * mm),
        table(
            ["Kapitel", "Inhalt"],
            [
                ["1. Schnellstart", "Wie ein Projekt sicher begonnen wird."],
                ["2. Programmoberflaeche", "Aufbau der Fenster, Docks, Geschosse und Statusanzeigen."],
                ["3. Menuebefehle", "Alle relevanten Menues mit Zweck und typischer Anwendung."],
                ["4. Aufbau der Heizlastberechnung", "Schrittfolge vom Projektstart bis zum Export."],
                ["5. DIN-orientierte Nachweisfuehrung", "Tool-Ampel, Quellen, Prueffassung und offene Normbausteine."],
                ["6. Checklisten und Glossar", "Praktische Kontrolle vor Report und Begriffe."],
            ],
            [45, 129],
        ),
        NextPageTemplate("Normal"),
        PageBreak(),
        heading("1. Schnellstart"),
        p(
            "Der sicherste Einstieg ist der gefuehrte Projekt-Assistent. Er legt den Projektstand an und fuehrt direkt "
            "durch die wichtigsten Randbedingungen, bevor Raeume und Bauteile detailliert bedatet werden."
        ),
        bullets(
            [
                "Datei > Neues Projekt-Assistent waehlen.",
                "Projektname und Speicherort festlegen.",
                "Normstart aktivieren und mindestens Normpruefung, U-Werte, Lueftung und Erdreich durchgehen.",
                "Grundriss geschossweise erfassen: KG, EG und DG getrennt bearbeiten.",
                "Projekt > Auto-Waende neu nach Geometrieaenderungen ausfuehren.",
                "Raeume, Bauteile, Quellen und Sondermodule im Projekt-Dashboard kontrollieren.",
                "Erst exportieren, wenn rote Punkte bewusst geklaert sind; fuer eine Prueffassung muessen die Tool-Gates gruen sein.",
            ]
        ),
        note(
            "Praxisregel: Geometrie zuerst, dann Raeume bedaten, dann Bauteile und Quellen, danach erst Export. "
            "So bleiben automatische Flaechen und Nachweise nachvollziehbar."
        ),
        heading("2. Programmoberflaeche"),
        table(
            ["Bereich", "Beschreibung", "Wichtig fuer"],
            [
                ["Menueleiste", "Datei, Projekt, Bearbeiten, Ansicht, Dach und Hilfe.", "Alle Hauptfunktionen und Exporte."],
                ["Toolbar", "Schnelle Symbole fuer Projekt, Speichern, Werkzeuge, Ansichten und Export.", "Wiederkehrende Bedienung ohne Menuesuche."],
                ["Geschossansichten", "KG, EG und DG werden getrennt modelliert und angezeigt.", "Saubere Zuordnung von Raeumen und Bauteilen."],
                ["Zeichenflaeche", "Hier werden Raeume, Waende, Oeffnungen und Dachbezug dargestellt.", "Geometrische Eingabe und Sichtpruefung."],
                ["Eigenschaften-Dock", "Raumdaten: Nutzung, Solltemperatur, Luftwechsel, Flaeche und Hoehe.", "Raumweise Bedatung und Status."],
                ["Elemente-Dock", "Bauteile des aktiven Raums mit Filter, Assistent und Massenbearbeitung.", "U-Werte, Randbedingungen, Quellen."],
                ["Projekt-Dashboard", "DIN-Ampel, Arbeits-Checkliste, Raum-Matrix und Heizlast-Audit.", "Projektfuehrung und Qualitaetskontrolle."],
                ["DG-Dach/Giebel-Dock", "Dachparameter, Dachlinien, Giebel- und Dachflaechenkontrolle.", "Dachgeschoss und Auto-DG."],
                ["Statusleiste", "Projektpfad, Raumanzahl, Gesamt-Heizlast und DIN-Status.", "Schnelle Rueckmeldung waehrend der Arbeit."],
            ],
            [34, 88, 52],
        ),
        heading("3. Menuebefehle"),
        p("Die folgende Tabelle fasst die Menuebefehle mit Zweck und typischer Anwendung zusammen."),
        table(["Menuebefehl", "Funktion", "Typische Anwendung"], menu_rows(), [54, 67, 53]),
        PageBreak(),
        heading("4. Aufbau einer Heizlastberechnung"),
        p(
            "Eine belastbare Berechnung entsteht aus drei Ebenen: Projektweite Randbedingungen, raumweise Nutzung "
            "und bauteilweise Transmission. Das Tool fuehrt diese Daten im Report und in den CSV-Ausgaben zusammen."
        ),
        table(["Schritt", "Arbeitspaket", "Was tun?", "Kontrolle"], workflow_rows(), [13, 35, 73, 53]),
        heading("4.1 Projektweite Randbedingungen", 2),
        bullets(
            [
                "Normausgabe und nationale Ergaenzung festlegen.",
                "Norm-Aussentemperatur, Klimaregion und Quelle dokumentieren.",
                "Geometriemodus und Bezugsflaechen bewusst waehlen.",
                "Projekt-U-Werte als Fallback fuer automatische Bauteile eintragen.",
                "Lueftung, Infiltration, WRG, Erdreich, Waermebruecken und Aufheizzuschlag mit Quelle pflegen.",
            ]
        ),
        heading("4.2 Raumdaten", 2),
        bullets(
            [
                "Jeder Raum braucht Geschoss, Geometrie, Nutzung, Solltemperatur, Luftwechsel und Raumhoehe.",
                "Nutzungspresets beschleunigen typische Wohn-, Neben-, Technik- und unbeheizte Raeume.",
                "Der Geschoss-Assistent setzt gemeinsame Daten wie Nutzung oder Raumhoehe fuer mehrere Raeume.",
                "Die Raum-Matrix im Dashboard zeigt fehlende Daten fuer Aussenwand, Fenster, Dach, Decke, Boden, Lueftung, Temperatur und Nachbarzonen.",
            ]
        ),
        heading("4.3 Bauteile und Transmission", 2),
        bullets(
            [
                "Aussenwaende, Fenster, Tueren, Dach, Decken und Boden bilden die Transmissionsflaechen.",
                "Innenwaende koennen als Nachbarzone oder Interzone genutzt werden, wenn Temperaturdifferenzen relevant sind.",
                "Jedes Huellelement sollte U-Wert, Flaeche, Randbedingung, Faktor, Quellenstatus und Flaechenherkunft besitzen.",
                "Auto-Waende und Auto-Decken sind Modellierungshilfen; fuer Nachweise muessen die Annahmen bestaetigt und dokumentiert werden.",
            ]
        ),
        heading("4.4 Lueftung, Erdreich, Waermebruecken und Aufheizzuschlag", 2),
        bullets(
            [
                "Lueftung trennt Infiltration, Mindestluftwechsel, mechanische Volumenstroeme und WRG-Restanteil.",
                "Erdreich nutzt projektbezogene Faktoren und Zwischenwerte; der DIN/TS-orientierte Ansatz braucht Quelle und Eingaben.",
                "Waermebruecken koennen ueber Delta-U, Prozentansatz oder psi-Werte erfasst werden.",
                "Aufheizzuschlag kann als Flaechenzuschlag oder herleitbarer Ansatz dokumentiert werden.",
            ]
        ),
        heading("5. DIN-orientierte Nachweisfuehrung"),
        p(
            "Das Tool ist DIN-orientiert aufgebaut und bezieht sich auf DIN EN 12831-1:2017-09 sowie DIN/TS 12831-1:2020-04. "
            "Die Pruefung ist eine Tool-interne Bewertungs- und Dokumentationshilfe."
        ),
        table(
            ["Status", "Bedeutung", "Folge"],
            [
                ["Gruen", "Der im Tool bewertete Baustein ist vollstaendig genug dokumentiert.", "Berechnung kann im Report nachvollziehbar ausgegeben werden."],
                ["Gelb", "Der Baustein ist DIN-orientiert, aber vereinfacht oder projektspezifisch zu pruefen.", "Quelle, Annahme oder fachliche Entscheidung ergaenzen."],
                ["Rot", "Ein Pflichtbaustein fehlt oder verhindert eine prueffaehige Aussage.", "Vor Export klaeren; Prueffassung wird blockiert."],
            ],
            [24, 86, 64],
        ),
        heading("5.1 Wichtige Nachweis-Gates", 2),
        bullets(
            [
                "Normausgabe, Aussentemperatur und Klimadatenquelle sind dokumentiert.",
                "Alle Huellelemente haben U-Wert, Flaechenherkunft, Randbedingung und Quellenstatus.",
                "Erdreich, Lueftung/WRG und Aufheizzuschlag enthalten Quelle und Zwischenwerte.",
                "Waermebruecken sind bewusst deaktiviert oder mit Ansatz/Quelle belegt.",
                "Auto-Decken, Auto-DG und Nachbarzonen sind bestaetigt und plausibilisiert.",
                "Der Report enthaelt keine offene Rot-Bewertung, wenn eine belastbare Prueffassung erzeugt werden soll.",
            ]
        ),
        heading("5.2 Export und Prueffassung", 2),
        p(
            "Beim Export kann der Umfang gewaehlt werden: PDF-Report mit DIN-Pruefstatus, DIN-12831-Formbericht, "
            "Heatload-CSV und Detail-CSV sowie Grundrisse als PNG/PDF mit Heatmap. Wenn die DIN-Prueffassung aktiv ist, "
            "blockiert der Export, solange zentrale Tool-Gates nicht gruen sind."
        ),
        note(
            "Ein roter DIN-Status kann fuer Arbeitsstaende bewusst uebersteuert werden. Fuer eine Prueffassung ist das nicht vorgesehen: "
            "Hier muessen die offenen Punkte vorher geklaert werden."
        ),
        heading("6. Checklisten"),
        heading("6.1 Vor der Berechnung", 2),
        bullets(
            [
                "Alle Geschosse sind angelegt und Raeume liegen im richtigen Geschoss.",
                "Raumhoehen, Nutzungen, Solltemperaturen und Luftwechsel sind gepflegt.",
                "Auto-Waende wurden nach der letzten Geometrieaenderung neu erzeugt.",
                "Fenster und Tueren liegen auf passenden Wandsegmenten und haben plausible Flaechen.",
                "Projekt-U-Werte und Bauteilquellen sind eingetragen.",
            ]
        ),
        heading("6.2 Vor dem Export", 2),
        bullets(
            [
                "Projekt speichern und Dashboard oeffnen.",
                "Raum-Nachweis-Matrix pruefen.",
                "Heizlast-Audit auf auffaellige W/m2-Werte und grosse Fenster-/Dachanteile pruefen.",
                "Normpruefung oeffnen und rote Punkte abarbeiten.",
                "Bei Prueffassung: alle Tool-Gates muessen gruen sein.",
                "Exportumfang bewusst waehlen und Exportordner dokumentieren.",
            ]
        ),
        heading("7. Glossar"),
        table(
            ["Begriff", "Erklaerung"],
            [
                ["Bedatung", "Das Fuellen eines Modells mit fachlichen Daten: Nutzung, Temperaturen, U-Werte, Quellen, Randbedingungen und Flaechenherkunft."],
                ["Randbedingung", "Thermische Grenze eines Bauteils, z. B. Aussenluft, Erdreich, unbeheizter Keller, Dachraum oder beheizte Nachbarzone."],
                ["U-Wert", "Waermedurchgangskoeffizient eines Bauteils in W/(m2K). Je kleiner, desto besser die Daemmwirkung."],
                ["Flaechenherkunft", "Dokumentation, ob eine Flaeche automatisch, manuell, aus Plan, Bestand oder Nachweis stammt."],
                ["WRG", "Waermerueckgewinnung in einer mechanischen Lueftungsanlage."],
                ["Tool-Gate", "Interner Pruefpunkt, der fuer DIN-orientierte Dokumentation gruen, gelb oder rot bewertet wird."],
                ["Prueffassung", "Strenger Exportmodus, der nur freigibt, wenn zentrale Tool-Gates gruen sind."],
                ["Auto-DG", "Automatische Ableitung von Dach-/Giebelflaechen fuer das Dachgeschoss aus Dachparametern und Geometrie."],
            ],
            [43, 131],
        ),
    ]
    story.append(Spacer(1, 5 * mm))
    story.append(p(f"Erzeugt am {today} aus dem Projektstand des Heizlast Tools.", "small"))
    return story


def build_pdf() -> Path:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=17 * mm,
        bottomMargin=16 * mm,
        title="Heizlast Tool Benutzerdokumentation",
        author="Heizlast Tool",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates(
        [
            PageTemplate(id="Cover", frames=frame, onPage=cover),
            PageTemplate(id="Normal", frames=frame, onPage=footer),
        ]
    )
    doc.build(build_story())
    return OUT


if __name__ == "__main__":
    print(build_pdf())
