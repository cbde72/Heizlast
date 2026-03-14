import os
import zipfile
from pathlib import Path

def get_next_version_name(base_name, target_folder):
    """Sucht im Zielordner nach der nächsten freien Vxx-Nummer."""
    version = 1
    while True:
        current_name = target_folder / f"{base_name}_V{version:02d}.zip"
        if not current_name.exists():
            return current_name
        version += 1

def backup_multi_ext():
    # --- KONFIGURATION ---
    EBENEN_HOCH = 1  # Wie viele Ebenen über dem Skript liegt das Projekt-Root?

    # Hier einfach alle gewünschten Endungen eintragen:
    EXTENSIONS = ('.py', '.md', '.json', '.yaml', '.txt', '.html', '.css')

    IGNORE_DIRS = {'.git', '__pycache__', '.venv', 'venv', '.vscode', '.idea'}
    # ---------------------

    script_dir = Path.cwd()

    # Root-Verzeichnis bestimmen
    root_dir = script_dir
    for _ in range(EBENEN_HOCH):
        root_dir = root_dir.parent

    # Zielverzeichnis: "versionen" Ordner auf der gleichen Ebene wie root_dir
    versions_dir = root_dir.parent / "versionen"
    versions_dir.mkdir(exist_ok=True)

    folder_name = root_dir.name
    zip_path = get_next_version_name(folder_name, versions_dir)

    files_to_add = []

    print(f"--- Backup-Vorgang gestartet ---")
    print(f"Suche nach: {', '.join(EXTENSIONS)}")
    print(f"Projekt-Root: {root_dir}")

    # Dateien sammeln
    for root, dirs, files in os.walk(root_dir):
        # Verzeichnisse in-place filtern (überspringt ignorierte Ordner komplett)
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for file in files:
            if file.lower().endswith(EXTENSIONS):
                full_path = Path(root) / file
                files_to_add.append(full_path)

    if not files_to_add:
        print("\nKeine passenden Dateien zum Sichern gefunden.")
        return

    # Archiv erstellen
    print(f"\nErstelle: {zip_path.name} mit {len(files_to_add)} Dateien...")

    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in files_to_add:
                # Relativ zum root_dir speichern
                arcname = file.relative_to(root_dir)
                zipf.write(file, arcname=arcname)

        print(f"\nERFOLG!")
        print(f"Gespeichert in: {zip_path}")

    except Exception as e:
        print(f"\nFEHLER: {e}")

if __name__ == "__main__":
    backup_multi_ext()