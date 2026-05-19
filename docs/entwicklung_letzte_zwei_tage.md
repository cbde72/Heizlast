# Entwicklungsdokumentation der letzten zwei Tage

Stand: 18.05.2026

Diese Dokumentation fasst die zuletzt umgesetzten Erweiterungen am Heizlast-Tool zusammen. Schwerpunkt war die bessere DIN-orientierte Berechnung und Nachvollziehbarkeit, besonders für Transmission, Projektparameter, U-Werte, Report und Ladeverhalten.

Aktueller Stand:

- App-Version: `2.9.0`
- Interne Version: `Heizlast_V37-intern-01`
- Anzeige-Version: `37.0.0`
- Projekt-Schema: `PROJECT_SCHEMA_VERSION = 24`

Hinweis zur Schema-Version: Die GUI-/Workflow-Erweiterungen ab V34 bis V37 benötigen keine neuen gespeicherten Projektfelder. Deshalb bleibt die Projektdatei kompatibel mit Schema 24.

## 1. DIN-Konformität und Nachweislogik

Der bestehende DIN-orientierte Arbeitsstand wurde ausgebaut. Ziel war nicht, einen vollständigen rechtsverbindlichen Normnachweis zu behaupten, sondern die Berechnung prüffähiger und transparenter zu machen.

Umgesetzt:

- DIN-Ampel und Maßnahmenplan wurden erweitert.
- Fehlende Quellen für U-Werte werden jetzt als offener Punkt bewertet.
- U-Wert-Nachweise erscheinen als eigener Baustein in der Konformitätsbewertung.
- Report und Status unterscheiden weiterhin zwischen implementierter Rechnung und projektspezifisch zu prüfenden Annahmen.
- `docs/din_konformitaet.md` wurde aktualisiert, insbesondere zur Lüftungsbilanz und zu verbleibenden offenen Normbausteinen.

Wichtig: Die Ampel bleibt bewusst konservativ. Wenn Quellen oder normative Detailverfahren fehlen, wird das sichtbar gemacht.

## 2. Lüftung und WRG

Die Lüftungsrechnung wurde DIN-näher erweitert.

Vorher:

- Natürliche Lüftung über `c_air * n * V * dT`
- Mechanische Lüftung als einfacher Restwärmeverlust mit WRG

Jetzt:

- Mindestluftwechsel `n_min`
- Infiltration `n_inf`
- Mechanischer Raumvolumenstrom nach Volumenanteil
- Nicht gedeckter Mindestvolumenstrom
- WRG-Restanteil

Formel der neuen Bilanz:

```text
Vdot_eff = Vdot_infiltration
         + max(0, Vdot_min - Vdot_mech,room)
         + Vdot_mech,room * (1 - eta_WRG)

Q_vent = c_air * Vdot_eff * dT
```

Neue/erweiterte Ergebniswerte:

- `ventilation_n_min_1ph`
- `ventilation_n_infiltration_1ph`
- `ventilation_vdot_effective_m3h`
- `ventilation_vdot_mech_room_m3h`

Der Report weist diese Werte raumweise aus.

## 3. Decken, Fußböden und Dach-Transmission

Ein großer Schwerpunkt lag auf der sauberen Trennung und Nachweisbarkeit horizontaler und oberer thermischer Grenzen.

Umgesetzt:

- Transmissionszeilen erhalten jetzt eine Bauteilrolle:
  - `deck_basement`
  - `deck_interzone`
  - `deck_attic`
  - `floor_ground`
  - `wall_ground`
  - `roof`
- Bodenplatten/Fußböden gegen Erdreich bekommen:
  - Perimeter
  - charakteristisches Bodenplattenmaß `B'`
- Reportabschnitt erweitert zu:
  - Decken
  - Fußböden/Bodenplatte
  - erdberührte Wand
  - Dachflächen

Der Report zeigt je Gruppe:

- wirksame Fläche
- U-Wert
- Temperaturdifferenz
- Faktor
- Leistung
- Perimeter
- `B'`

## 4. Vermeidung doppelter Decken und Böden

Die Deduplizierung wurde erweitert.

Vorher:

- Doppelte automatische Decken wurden bereits weitgehend verhindert.

Jetzt zusätzlich:

- Pro Raum wird eine untere thermische Grenze nur einmal angesetzt.
- Manuelle Bodenplatte/Fußboden unterdrückt die automatische Kellerdecke desselben Raums.
- Doppelt importierte identische manuelle Bodenplatten werden nur einmal gezählt.
- Manuelle Decken schlagen automatische Decken.
- Unterschiedliche echte Bauteilsegmente bleiben möglich.

Abgedeckte Fälle:

- `Bodenplatte` plus automatische `Kellerdecke`
- doppelte `Bodenplatte`
- manuelle `Kellerdecke` statt Auto-Kellerdecke
- Speicherdecke und Geschossdecke getrennt nach Nachbarzone

## 5. Projektparameter für U-Werte

Die Projektparameter wurden deutlich erweitert. Ziel: typische Bauteil-U-Werte zentral eingeben und als Fallback nutzen, wenn einzelne Elemente keinen eigenen U-Wert haben.

Neu bzw. erweitert:

- `U Außenwand`
- `U Fenster`
- `U Tür`
- `U Kellerdecke`
- `U EG-Geschossdecke`
- `U DG-Geschossdecke`
- `U Bodenplatte`
- `U erdberührte Wand`
- `Quelle U-Werte`

Die Werte sind im Projektparameter-Dialog unter `Auto-Decken / Projekt-U-Werte` editierbar.

Fallback-Verhalten:

- Außenwand ohne eigenen U-Wert nutzt `u_aussenwand_w_m2k`.
- Fenster ohne eigenen U-Wert nutzt `u_fenster_w_m2k`.
- Tür ohne eigenen U-Wert nutzt `u_tuer_w_m2k`.
- Bodenplatte ohne eigenen U-Wert nutzt `u_bodenplatte_w_m2k`.
- Erdberührte Wand ohne eigenen U-Wert nutzt `u_erdberuehrte_wand_w_m2k`.

Schema-Versionen:

- `PROJECT_SCHEMA_VERSION = 21`: Lüftungsparameter `n_min` und `n_inf`
- `PROJECT_SCHEMA_VERSION = 22`: Bodenplatte und erdberührte Wand
- `PROJECT_SCHEMA_VERSION = 23`: Außenwand
- `PROJECT_SCHEMA_VERSION = 24`: Fenster, Tür und U-Wert-Quelle

## 5a. Normführung, Projekt-Dashboard und Assistent

Seit `Heizlast_V34-intern-01` wurde die Bedienführung deutlich erweitert. Mit `Heizlast_V35-intern-01` kamen die zentrale Arbeits-Checkliste und die raumweise Nachweis-Matrix hinzu. Mit `Heizlast_V36-intern-01` wurden Bauteilführung, Quellenstatus, Projektverwaltung und Reportstruktur ergänzt. Mit `Heizlast_V37-intern-01` kam der Heizlast-Audit für hohe Lasten und DG-Dach-/Giebelflächen hinzu.

Umgesetzt:

- Neues Dock `Projekt-Dashboard`:
  - Projektpfad
  - DIN-Status
  - Speicherstatus
  - Räume, Bauteile und Geschosse
  - offene Prüfpunkte aus der zentralen DIN-Bewertung
- Zentrale Arbeits-Checkliste im Dashboard:
  - Projektparameter vollständig
  - Räume geprüft
  - Bauteile plausibel
  - DIN-Report bereit
  - Klick auf einen Punkt springt zur passenden Eingabe oder Prüfung.
- Raumweise DIN-/Nachweis-Matrix:
  - Außenwand
  - Fenster
  - Dach
  - Decke
  - Boden
  - Wärmebrücken
  - Lüftung
  - Temperatur
  - Nachbarzonen
  - Klick auf einen Raum öffnet den Raum-Inspector.
- Bauteil-Assistent im Elemente-Dock:
  - Bauteiltyp
  - Randbedingung
  - Fläche
  - U-Wert
  - Temperaturfaktor
  - Quelle/Status und Quellenhinweis
  - Innenwände für Nachbarzone/Interzone
- Quellen-/Annahmenstatus je Bauteil:
  - `Projektwert`
  - `DIN/Normtabelle`
  - `Hersteller-/Bauteilnachweis`
  - `geschätzt`
  - `manuell`
  - Matrix bewertet Bauteile ohne Quelle konservativ gelb.
- Heizlast-Audit im Dashboard:
  - Gesamtsumme nach Transmission, Lüftung und Wärmebrücken
  - Top-Räume nach Heizlast und W/m²
  - Top-Bauteilgruppen nach Transmissionslast
  - DG-Dachflächen mit auffälligem Verhältnis zur Raumfläche
  - DG-Giebelflächen mit auffälliger Größenordnung
  - mögliche Doppelungen von Dach-/Giebel-Rechenzeilen
- Direkte Projektmenü-/Toolbar-Zugriffe:
  - `Projektparameter`
  - `Normprüfung`
  - `U-Werte`
  - `Lüftung`
  - `Erdreich`
  - `Projekt-Dashboard`
- Neuer geführter Normstart im Projekt-Assistenten:
  - Normprüfung
  - Projekt-U-Werte
  - Lüftung
  - Erdreich
  - anschließend Dashboard-Kontrolle
- Raum-Inspector mit Raumstatus:
  - fehlende Nutzung
  - fehlende/ungültige Fläche
  - fehlende Höhe oder Volumen
  - auffällige Innentemperatur
  - auffälliger Luftwechsel
- Nutzungspresets im Raum-Inspector:
  - setzen `usage_type`
  - setzen passende Innentemperatur
  - setzen passenden Luftwechsel

## 5b. Projektverwaltung und Export-Workflow

Ebenfalls ab `Heizlast_V34-intern-01`:

- `Version speichern` erzeugt eine versionierte Kopie im Unterordner `Versionen`, ohne den aktuell geöffneten Projektpfad umzuschalten.
- Vor `Speichern unter...` wird, falls möglich, ein Backup im Ordner `_backups` geschrieben.
- Vor Export wird, falls möglich, ein Backup mit Marker `before_export` geschrieben.
- Der Export besitzt jetzt eine Umfangsauswahl:
  - PDF-Report mit DIN-Prüfstatus
  - DIN-12831-Formbericht
  - Heatload-CSV und Detail-CSV
  - Grundrisse PNG/PDF mit Heatmap
- Die bestehende rote DIN-Vorprüfung bleibt vor dem Export aktiv.
- Projektverwaltung:
  - zuletzt verwendete Projekte
  - Versionen aus dem Ordner `Versionen`
  - Backups aus `_backups`
  - direkte Öffnung der gewählten Datei
- Reportstruktur:
  - zusätzliche Nachweisübersicht vor den Anhängen
  - zentrale Status-/Validierungstabelle
  - Bauteilquellen und Annahmen als eigene Reporttabelle

Aktueller GUI-/Workflow-Stand:

- App-Version `2.9.0`
- interne Version `Heizlast_V37-intern-01`
- Anzeige-Version `37.0.0`
- Projekt-Schema weiterhin `24`, da Checkliste, Matrix, Projektverwaltung, Reportübersicht und Heizlast-Audit aus vorhandenen Projekt-, Raum-, Bauteil-, Ergebnis- und Metadaten berechnet werden.

## 6. Außenwände und Auto-Wände

Auto-Außenwände verwenden jetzt den projektweiten Außenwand-U-Wert.

Umgesetzt:

- Auto-Wand-Builder akzeptiert `u_aussenwand_w_m2k`.
- GUI-Autowände lesen den Wert aus den Projektparametern.
- Manuelle Außenwände behalten eigene U-Werte.
- Außenwände mit `U = 0` oder fehlendem U-Wert bekommen den Projektfallback.

Damit ist die automatische Wandableitung näher an den Projektparametern und weniger abhängig von hart codierten Defaults.

## 7. Erdreich/Bodenplatte

Das Erdreichmodell bleibt weiterhin DIN/TS-orientiert, aber noch kein vollständiges normatives Erdreichverfahren.

Verbessert wurde:

- getrennte U-Fallbacks für Bodenplatte und erdberührte Wand
- Perimeter- und `B'`-Nachweis bei Bodenplatten
- klarere Reportzeilen für Erdreich
- Quellenfelder für Erdreich und DIN/TS-Faktoren

Weiter offen für noch höhere DIN-Konformität:

- vollständiges DIN/TS-Erdreichverfahren
- Bodenleitfähigkeit
- Einbindetiefe
- detaillierte Randdämmung
- vollständige Keller-/Erdkontakt-Geometrie

## 8. Wärmebrücken

Die vorhandene Wärmebrückenlogik wurde stärker in die DIN-Bewertung eingebunden.

Bereits vorhanden:

- `none`
- `delta_u`
- `psi`
- `percent`
- Element-ψ-Werte über Metadaten
- Default-ψ-Wert
- Quellenfeld `thermal_bridge_source`

Verbessert:

- DIN-Ampel bewertet fehlende ψ-Werte oder fehlende Quellen konservativ.
- Report weist Wärmebrücken separat aus.

Weiter offen:

- echter Anschlusskatalog
- Anschlusslängen je Detail
- Quellen je Anschlusswert

## 9. Aufheizzuschlag

Der Aufheizzuschlag bleibt als vereinfachtes Modul vorhanden.

Vorhanden:

- direkter Zuschlag `q_hu`
- alternativ Ableitung aus:
  - Wiederaufheizzeit
  - Temperaturabsenkung
  - Speicherkennwert
- Quellenfeld `reheat_source`
- Rechenzeile im Report

Weiter offen:

- normtabellenbasierter Zuschlag
- Gebäudeschwere nach Normtabellen
- belastbare Zuordnung zu Nutzungsprofilen

## 10. Report und Prüfbarkeit

Der PDF-/DIN-Report wurde mehrfach erweitert.

Neu oder verbessert:

- U-Werte für Außenwand, Fenster, Tür, Bodenplatte, erdberührte Wand
- Quelle U-Werte
- raumweise Lüftungsbilanz
- Decken/Fußboden/Dach-Abschnitt
- Perimeter und `B'`
- DIN-Ampel mit Quellenstatus
- Maßnahmenplan bei fehlenden Nachweisen

Der Report ist damit deutlich besser als Arbeits- und Prüfunterlage geeignet.

## 11. Schnelleres Laden

Das Laden wurde beschleunigt.

Änderung:

- Direkt nach dem Laden wird zuerst die Geometrie angezeigt.
- Die teurere Heizlast-/DIN-Neuberechnung läuft verzögert im bestehenden Nachlauf.

Dadurch fühlt sich das Öffnen größerer Projekte schneller an, ohne auf die Berechnung zu verzichten.

## 12. Tests und Qualitätssicherung

Die Änderungen wurden mit Regressionstests abgesichert.

Neue oder erweiterte Testbereiche:

- Lüftungsbilanz mit Infiltration, Mindestluftwechsel und WRG
- Bodenplatte unterdrückt Auto-Kellerdecke
- doppelte Bodenplatte zählt nur einmal
- Dachflächen werden getrennt von Speicherdecken klassifiziert
- U-Fallbacks für Außenwand, Fenster, Tür, Bodenplatte
- Auto-Wände übernehmen Projekt-U-Wert
- DIN-Ampel erkennt fehlende U-Wert-Quelle
- Projektsettings enthalten neue Eingaben

Letzter kompletter Testlauf:

```text
155 passed
```

## 13. Aktueller Stand

Das Tool ist jetzt deutlich stärker DIN-orientiert und prüffähiger:

- mehr projektbezogene Eingaben
- weniger harte Defaultwerte
- bessere Trennung der thermischen Grenzen
- konservativere DIN-Ampel
- mehr Nachweiswerte im Report
- weniger Doppelzählungen

Es bleibt aber ein DIN-orientiertes Berechnungswerkzeug und ersetzt ohne vollständige Quellen, Normtabellen und fachliche Prüfung noch keinen vollständig normkonformen Nachweis.

## 14. Empfohlene nächste Schritte

Für noch mehr DIN-Konformität sind als nächste Schritte sinnvoll:

1. Vollständigeres DIN/TS-Erdreichverfahren mit Bodenleitfähigkeit, Einbindetiefe und Randdämmung.
2. Wärmebrücken-Anschlusskatalog mit ψ-Werten und Anschlusslängen.
3. Normtabellenbasierter Aufheizzuschlag.
4. U-Wert-Nachweis je Bauteil oder Bauteilschichten.
5. Raumweise Anlagenbilanz für mechanische Lüftung mit Quellen je Volumenstrom.
6. Export eines Eingabedatenblatts zusätzlich zum Ergebnisreport.
