# DIN-orientierte Heizlast: Umsetzungsstand

Dieses Projekt orientiert sich an DIN EN 12831-1:2017-09 und DIN/TS 12831-1:2020-04. Es ist bewusst als transparentes, parametrierbares Rechenwerkzeug umgesetzt und ersetzt keinen vollständigen Normnachweis durch eine qualifizierte Fachplanung.

## Umgesetzt

- Raumweise Transmissions- und Lüftungsanteile.
- Strukturierte Randbedingungen für Transmission:
  - `external` / Außenluft
  - `ground` / Erdreich
  - `basement` / unbeheizter Keller
  - `attic` / Dachboden oder Abseite
  - `unheated` / unbeheizter Bereich
  - `adjacent_heated` und `interzone`
- Detailnachweis im Report mit historischem Bucket, normnahem `boundary_bucket` und Klartext-Randbedingung.
- DIN/TS-nahe Default-Faktoren für unbeheizte Bereiche als zentrale Referenztabelle in `src/heizlast/core/din_boundary.py`; die Rechenzeile nutzt projektbezogene Nachbartemperaturen (`t_adj_c`, Keller-/Dachraumtemperatur) und den Bauteil-Faktor, damit Tabellenreferenz und wirksamer Rechenansatz nicht unbemerkt doppelt wirken.
- DG-Dachlogik mit Dachfenster-/Gaubenabzug und Randbedingung `outside` oder `attic_unheated`.
- Report-Anhang mit Validierungsgrad und Quellenliste.
- Projektbezogene DIN-Ampel im Report:
  - Grün = im Tool bewerteter Baustein erfüllt
  - Gelb = DIN-orientiert, aber projektspezifisch zu prüfen oder vereinfacht
  - Rot = fehlt oder verhindert eine prüffähige Konformitätsaussage
- Maßnahmenplan im Report für die offenen Normbausteine.
- Nachweis-Gates im Report, die vor einer belastbaren Konformitätsaussage geschlossen werden müssen.
- Zentrale Bewertungslogik in `src/heizlast/core/din_status.py`; Report und GUI nutzen denselben Prüfstatus.
- Projektparameter für Nachweisquellen:
  - Normausgabe
  - Außentemperatur-Quellendetail
  - Lüftung/WRG-Quelle
  - Erdreichquelle
  - Wärmebrückenquelle
  - Bearbeiter-/Prüfvermerk
- Aufheizzuschlag als eigenes vereinfachtes Rechenmodul:
  - optionaler Ansatz `Phi_hu = q_hu * A_ref`
  - herleitbarer Ansatz aus Wiederaufheizzeit, Temperaturabsenkung und Speicherkennwert
  - eigene Ergebniszeile `REHEAT`
  - separate Ausgabe `Q_reheat_W`
- Vorbereitete mechanische Lüftungsparameter für spätere WRG-Berechnung:
  - Lüftungsart `natural` / `mechanical`
  - Zuluft-/Abluft-Volumenstrom
  - WRG-Wirkungsgrad
- Mechanische Lüftung/WRG wirkt rechnerisch als DIN-orientierte Volumenstrombilanz:
  - `Vdot_eff = Vdot_infiltration + max(0, Vdot_min - Vdot_mech,room) + Vdot_mech,room * (1 - eta_WRG)`
  - `Q_vent = c_air * Vdot_eff * dT`
  - Verteilung mechanischer Volumenströme auf Räume nach Volumenanteil
  - Report weist `n_min`, `n_inf`, wirksamen Volumenstrom und WRG-Rest raumweise aus
- DIN-Ampel in der GUI-Statusleiste.
- Wärmebrücken-Plausibilisierung: ψ-Modus ohne Element-ψ oder Default-ψ wird rot bewertet.
- Erdreich-Zielmodus `din_ts` nutzt eigene Ersatzfaktoren für Bodenplatte und Kellerwand; ein vollständiges Normverfahren mit allen Zwischenwerten bleibt noch offen.
- Klimadaten-/Quellennachweis erweitert um Klimastation/Region und Höhenkorrektur.
- Projekt-Dashboard in der GUI:
  - zeigt DIN-Status, Speicherstatus, Räume, Bauteile, Geschosse und offene Prüfpunkte
  - nutzt dieselbe zentrale DIN-Bewertung wie Report und Export-Vorprüfung
  - führt über eine Arbeits-Checkliste durch Projektparameter, Raumprüfung, Bauteilplausibilität und Reportbereitschaft
  - zeigt eine raumweise Nachweis-Matrix für Außenwand, Fenster, Dach, Decke, Boden, Wärmebrücken, Lüftung, Temperatur und Nachbarzonen
- Bauteil-Assistent und Quellenstatus:
  - geführte Eingabe von Bauteiltyp, Randbedingung, Fläche, U-Wert, Faktor und Quelle/Annahme
  - Innenwände können als Nachbarzone/Interzone angelegt werden
  - Bauteile ohne dokumentierten Quellenstatus bleiben in der GUI-Prüfung konservativ gelb
  - Quellen-/Annahmenstatus wird im Report als eigene Übersicht ausgegeben
- Projektbewusste Auto-Decken:
  - automatische Kellerdecken, EG-Geschossdecken und DG-Speicherdecken sind einzeln abschaltbar
  - erzeugte Auto-Decken dokumentieren Randbedingung, Temperaturquelle, U-Wert-Quelle, Flächenherkunft und Bestätigungsstatus
  - unbestätigte Auto-Decken bleiben in der DIN-Prüfung gelb, auch wenn sie rechnerisch verwendet werden
- Projektverwaltung:
  - zuletzt verwendete Projekte, Versionen und Backups sind aus der GUI erreichbar
  - Versionen/Backups unterstützen prüfbare Variantenstände
- Reporting:
  - zusätzliche Nachweisübersicht bündelt Validierungsstatus, offene Punkte und Bauteilquellen vor den Detailanhängen
- Heizlast-Audit:
  - zeigt Top-Lasttreiber aus den letzten Rechenergebnissen direkt im Dashboard
  - markiert auffällige W/m²-Räume und große Fenster-/Dach-/Giebelanteile
  - prüft DG-Dach-/Giebelflächen auf auffällige Größenordnung und mögliche Doppelungen
- Geführter Normstart beim Anlegen neuer Projekte:
  - Normprüfung
  - U-Werte
  - Lüftung
  - Erdreich
  - anschließende Dashboard-Kontrolle
- Raum-Inspector mit Raumstatus und Nutzungspresets:
  - Nutzung, Solltemperatur und Luftwechsel werden direkt pflegbar
  - fehlende Raumdaten werden sichtbar markiert
- Export-Vorprüfung und Export-Auswahl:
  - rote DIN-Bausteine müssen bewusst bestätigt werden
  - Exportumfang ist auswählbar
  - vor Export wird ein Backup geschrieben, sofern ein Projektpfad vorhanden ist
- Versionsstand der GUI-/Workflow-Erweiterung:
  - App-Version `2.9.0`
  - interne Version `Heizlast_V37-intern-01`
  - Anzeige-Version `37.0.0`
  - Projekt-Schema `25`, da Auto-Decken jetzt eigene Nachweis- und Aktivierungsfelder besitzen

## Noch vereinfacht

- Lüftung/WRG ist rechnerisch wirksam inklusive Infiltrations-/Mindestluftwechseltrennung; vollständige Anlagen-/Normtabellenlogik und Quellenbindung bleiben projektbezogen zu prüfen.
- Aufheizzuschlag ist als flächenbezogener bzw. herleitbarer Zuschlag implementiert; ein vollständiges Normtabellenverfahren ist noch offen.
- Erdreichmodell ist weiterhin ein Ersatztemperaturmodell; `din_ts` nutzt separate Ersatzfaktoren, aber noch kein vollständiges DIN/TS-Rechenverfahren.
- Wärmebrücken sind optional über Zuschläge oder ψ-Werte modelliert; ein vollständiger Anschlusskatalog ist nicht enthalten.
- Der Projekt-Assistent führt durch die wichtigsten Projektparameter, ersetzt aber keine fachliche Vollständigkeitsprüfung aller projektspezifischen Normtabellen und Quellen.
- Die Raum-Nachweis-Matrix ist eine GUI-Prüfhilfe; sie ersetzt keine detaillierte normative Einzelnachweisprüfung je Bauteilanschluss.
- Auto-Decken sind weiterhin eine Modellierungshilfe. Für einen vollständigen Normnachweis müssen reale Nachbarzone, Temperatur, U-Wert-Quelle und Flächenherkunft projektbezogen bestätigt werden.
- Die Faktoren für unbeheizte Bereiche sind im Report als Referenzwerte gekennzeichnet. Wirksam wird rechnerisch die dokumentierte Nachbartemperatur beziehungsweise der explizite Element-Faktor.

## Nächste Normbausteine

Für eine belastbarere spätere Konformitätsaussage werden die offenen Punkte in dieser Reihenfolge geschlossen:

1. Aufheizzuschlag vom vereinfachten `q_hu * A_ref`-Ansatz auf ein projektspezifisch belegtes Normtabellenverfahren erweitern, inklusive Quelle, Raum-/Nutzungsbezug und eigener Rechenzeile.
2. Mechanische Lüftung mit Anlagen-/Normtabellenlogik absichern: Zuluft/Abluft je Raum, WRG-Randbedingung, Infiltration/Mindestluftwechsel und Quellenbezug getrennt dokumentieren.
3. Erdreichmodell vom vereinfachten Ansatz auf ein DIN/TS-nahes Nachweisverfahren erweitern: Bodenplatte, Kellerwand, Perimeter/B'-Wert, Temperatur-/Faktorquelle und Berechnungsweg getrennt ausweisen.
4. Wärmebrücken über dokumentierte ψ-Werte je Anschluss oder belegten ΔU-Ansatz absichern; globale Ersatzansätze müssen im Report als solche markiert bleiben.
5. Unbeheizte Bereiche projektspezifisch auswählbar machen: Keller, Dachraum/Abseite und sonstige Nebenräume benötigen eigene Temperatur, Quelle, Randbedingung und optionalen Faktor.
6. Bauteilquellen verschärfen: U-Werte, Flächenherkunft, Nachbarzone und Temperaturquelle sollten je Hüllbauteil vollständig sein, bevor der Status grün wird.
7. Report-Gate ergänzen, das grüne DIN-Bewertung nur erlaubt, wenn keine automatische Modellannahme unbestätigt und keine Interzone ohne `t_adj_c` vorhanden ist.

## Nachweis-Gates für eine spätere Konformitätsaussage

Eine grüne Tool-Ampel allein soll nicht als rechtliche oder fachliche Konformitätsbestätigung verstanden werden. Vor einer belastbaren Aussage müssen zusätzlich diese Gates erfüllt sein:

1. Normausgabe und nationale Ergänzung werden projektbezogen eindeutig festgelegt.
2. Jeder gelbe oder rote Baustein hat eine dokumentierte Quelle, Eingabe und Rechenzeile.
3. Erdreich, Lüftung/WRG und Aufheizzuschlag sind als eigene Normmodule im Report ausweisbar.
4. Wärmebrücken werden mit Anschlusswerten oder einem belegten ΔU-Ansatz nachgewiesen.
5. Der prüffähige Report enthält keine offene Rot-Bewertung.

## Lokale Literaturbasis

Die lokale Literatur unter `C:\Users\chris\Desktop\programming\Heizlast\Heizlast` wurde für die fachliche Ausrichtung verwendet, insbesondere:

- `Handbuch ZUB Heizlast.pdf`
- `Heizlastberechnung_2019.pdf`
- `itg-manuskript.pdf`
- `preview-9783410292890_A40391712.pdf`

Im PDF-Report werden diese Quellen zusammen mit DIN EN 12831-1 und DIN/TS 12831-1 als Bezugsrahmen genannt.
