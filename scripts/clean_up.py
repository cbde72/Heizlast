# -*- coding: utf-8 -*-
"""
Created on Mon Mar 16 13:58:12 2026

@author: chris
"""

from pathlib import Path

def cleanup_pyc(directory_path):
    # Den Pfad in ein Path-Objekt umwandeln
    root_dir = Path(directory_path)

    if not root_dir.exists():
        print(f"Fehler: Das Verzeichnis '{directory_path}' existiert nicht.")
        return

    print(f"Suche nach .pyc-Dateien in: {root_dir.resolve()}...")

    count = 0
    # rglob('*') sucht rekursiv nach dem Muster
    for file in root_dir.rglob('*.pyc'):
        try:
            file.unlink()  # Löscht die Datei
            print(f"Gelöscht: {file}")
            count += 1
        except Exception as e:
            print(f"Fehler beim Löschen von {file}: {e}")

    print("-" * 30)
    print(f"Fertig! Insgesamt {count} Dateien gelöscht.")

if __name__ == "__main__":
    # Hier den Pfad anpassen ( '.' steht für das aktuelle Verzeichnis)
    target_directory = "."
    cleanup_pyc(target_directory)