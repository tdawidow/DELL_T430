# core/workspace_manager.py
import os
import json
from datetime import datetime
import config

class WorkspaceManager:
    """Narzędzie do dynamicznego zarządzania środowiskiem i konfiguracją z poziomu GUI."""
    
    def __init__(self, init_system=True):
        self.config_file = config.MASTER_CONFIG_FILE
        if init_system:
            self.load_and_apply_master_config()

    def load_and_apply_master_config(self) -> dict:
        """Wczytuje konfigurację z dysku i wstrzykuje ścieżki bezpośrednio do config.py."""
        current_config = self._read_config_from_disk()
        
        # Wstrzykiwanie zmiennych do pamięci podręcznej modułu config
        config.BASE_DATA_DIR = current_config["output_workspace_dir"]
        config.OUTPUT_DIR = os.path.join(config.BASE_DATA_DIR, "results")
        config.LIBRARY_DIR = current_config["reference_library_dir"]
        config.LIBRARY_INDEX_FILE = os.path.join(config.LIBRARY_DIR, "library_index.json")
        config.DEFAULT_KRAKEN_DB = current_config["kraken_db_dir"]
        config.CURRENT_THREADS_LIMIT = int(current_config.get("threads_limit", config.MAX_THREADS_ALLOCATION))
        
        # NOWOŚĆ: Ładowanie i-węzła Torrent oraz bezpieczny fallback wewnątrz workspace
        default_torrent_dir = os.path.join(config.BASE_DATA_DIR, "torrent_downloads")
        config.TORRENT_DOWNLOAD_DIR = current_config.get("torrent_download_dir", default_torrent_dir).strip()
        
        # Tworzenie katalogów roboczych na wypadek gdyby użytkownik wskazał nowe ścieżki
        dirs_to_create = [config.BASE_DATA_DIR, config.OUTPUT_DIR, config.LIBRARY_DIR, config.TORRENT_DOWNLOAD_DIR]
        for d in dirs_to_create:
            if d:
                os.makedirs(d, exist_ok=True)
                
        return current_config

    def save_master_config(self, workspace_dir: str, kraken_dir: str, reference_dir: str, threads: int, torrent_dir: str) -> bool:
        """Trwale zapisuje ścieżki wskazane przez użytkownika w konfiguratorze GUI."""
        new_config = {
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "output_workspace_dir": os.path.abspath(workspace_dir.strip()),
            "kraken_db_dir": os.path.abspath(kraken_dir.strip()),
            "reference_library_dir": os.path.abspath(reference_dir.strip()),
            "threads_limit": int(threads),
            # NOWOŚĆ: Trwałe ryglowanie ścieżki pobrań Torrent w pliku JSON
            "torrent_download_dir": os.path.abspath(torrent_dir.strip())
        }
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(new_config, f, indent=4, ensure_ascii=False)
            # Natychmiastowe zaaplikowanie nowych ścieżek do pamięci programu
            self.load_and_apply_master_config()
            return True
        except Exception:
            return False

    def _read_config_from_disk(self) -> dict:
        """Pobiera konfigurację z pliku JSON lub tworzy bezpieczne wartości domyślne."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass

        # Jeśli plik nie istnieje lub jest uszkodzony, tworzymy domyślny kontener roboczy
        default_workspace = os.path.abspath(os.path.join(config.DEFAULT_APP_DIR, "kombajn_workspace"))
        return {
            "last_updated": "Pierwsze uruchomienie",
            "output_workspace_dir": default_workspace,
            "kraken_db_dir": os.path.join(default_workspace, "databases", "kraken2_standard"),
            "reference_library_dir": os.path.join(default_workspace, "references_library"),
            "threads_limit": config.MAX_THREADS_ALLOCATION
        }

    def create_new_project_container(self, custom_name="") -> str:
        """Tworzy czystą i posegregowaną strukturę folderów dla nowej analizy wewnątrz wybranego katalogu projects."""
        projects_root = os.path.join(config.BASE_DATA_DIR, "projects")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = f"_{custom_name.strip()}" if custom_name else ""
        project_id = f"PRJ_{timestamp}{suffix}"
        
        project_path = os.path.join(projects_root, project_id)
        
        subdirs = ["raw_input", "01_QC", "02_Taxonomy", "03_Assembly", "04_Comparative"]
        for subdir in subdirs:
            os.makedirs(os.path.join(project_path, subdir), exist_ok=True)
            
        return project_path
