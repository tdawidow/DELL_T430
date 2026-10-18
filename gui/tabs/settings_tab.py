# gui/tabs/settings_tab.py
import os
import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QSlider,
    QMessageBox, QGridLayout, QFileDialog
)
from PyQt6.QtCore import Qt
import config

class SettingsTab(QWidget):
    """
    [RDZEŃ KONFIGURACYJNY MACIERZY V46 - GOLD BASELINE]:
    Zarządza globalnymi rejestrami środowiskowymi stacji roboczej Xeon.
    """
    def __init__(self, parent_main_window=None):
        super().__init__()
        self.main_window = parent_main_window
        self.ws = getattr(self.main_window, 'ws', None)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # --- SEKCJA 1: INTEGRACJA 4 ŚCIEŻEK LABORATORYJNYCH ---
        paths_group = QGroupBox("📁 INTEGRACJA ŚCIEŻEK SYSTEMOWYCH I WORKSPACE")
        paths_grid = QGridLayout(paths_group)
        paths_grid.setSpacing(8)

        # 1. Lokalny Workspace Diagnostyczny
        paths_grid.addWidget(QLabel("Lokalne Workspace Diagnostyczne:"), 0, 0)
        self.txt_workspace = QLineEdit()
        self.txt_workspace.setReadOnly(True)
        paths_grid.addWidget(self.txt_workspace, 0, 1)
        self.btn_browse_ws = QPushButton("Przeglądaj...")
        self.btn_browse_ws.clicked.connect(self._browse_workspace)
        paths_grid.addWidget(self.btn_browse_ws, 0, 2)

        # 2. Baza Danych Kraken2
        paths_grid.addWidget(QLabel("Baza danych Kraken2 (kraken_db_dir):"), 1, 0)
        self.txt_kraken_db = QLineEdit()
        self.txt_kraken_db.setReadOnly(True)
        paths_grid.addWidget(self.txt_kraken_db, 1, 1)
        self.btn_browse_kraken = QPushButton("Przeglądaj...")
        self.btn_browse_kraken.clicked.connect(lambda: self._browse_dir(self.txt_kraken_db, "Wybierz bazę Kraken2"))
        paths_grid.addWidget(self.btn_browse_kraken, 1, 2)

        self.paths_grid = paths_grid
        self.paths_group = paths_group
        layout.addWidget(paths_group)

        # 3. Biblioteka Referencyjna
        self.paths_grid.addWidget(QLabel("Biblioteka Referencyjna (reference_library_dir):"), 2, 0)
        self.txt_library_dir = QLineEdit()
        self.txt_library_dir.setReadOnly(True)
        self.paths_grid.addWidget(self.txt_library_dir, 2, 1)
        self.btn_browse_lib = QPushButton("Przeglądaj...")
        self.btn_browse_lib.clicked.connect(lambda: self._browse_dir(self.txt_library_dir, "Wybierz bibliotekę referencyjną"))
        self.paths_grid.addWidget(self.btn_browse_lib, 2, 2)

        # 4. Magazyn Kopii Zapasowych
        self.paths_grid.addWidget(QLabel("Magazyn Kopii Zapasowych (backup_repository_dir):"), 3, 0)
        self.txt_backup_dir = QLineEdit()
        self.txt_backup_dir.setReadOnly(True)
        self.paths_grid.addWidget(self.txt_backup_dir, 3, 1)
        self.btn_browse_backup = QPushButton("Przeglądaj...")
        self.btn_browse_backup.clicked.connect(lambda: self._browse_dir(self.txt_backup_dir, "Wybierz katalog kopii zapasowych"))
        self.paths_grid.addWidget(self.btn_browse_backup, 3, 2)

        # =====================================================================
        # 🛸 HORYZONTALNA REFORMA PRZESTRZENNA: SIDE-BY-SIDE (ZASADA SZEFA)
        # =====================================================================
        self.h_split_layout = QHBoxLayout()
        self.h_split_layout.setSpacing(15)

        # Zachowanie instancji kontenera dla layoutu głównego
        self.main_layout = layout

        # --- PANEL LEWY: FILTRY TAKSONOMICZNE I INTEGRACJA NCBI ---
        analysis_box = QGroupBox("🧬 ZAAWANSOWANE FILTRY I BAZA NCBI")
        a_lay = QVBoxLayout(analysis_box)
        a_lay.setSpacing(6)
        
        a_lay.addWidget(QLabel("Próg odcięcia szumu metagenomiki Kraken2 (%):"))
        self.txt_threshold = QLineEdit()
        a_lay.addWidget(self.txt_threshold)
        
        a_lay.addWidget(QLabel("🔑 Klucz autoryzacyjny NCBI API Key:"))
        self.txt_api_key = QLineEdit()
        self.txt_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_api_key.setPlaceholderText("Wklej token API (opcjonalnie)")
        a_lay.addWidget(self.txt_api_key)
        
        a_lay.addStretch()
        self.h_split_layout.addWidget(analysis_box)

        # --- PANEL PRAWY: PRODUKCYJNY TORRENT SERVER INTERLOCK ---
        torrent_group = QGroupBox("📡 INTEGRACJA SIECIOWA TORRENT SERVERA")
        t_lay = QVBoxLayout(torrent_group)
        t_lay.setSpacing(6)
        
        t_lay.addWidget(QLabel("Absolutny URL panelu Torrent Suite Software:"))
        self.txt_torrent_url = QLineEdit()
        self.txt_torrent_url.setPlaceholderText("Domyślnie: http://192.168.1.100")
        t_lay.addWidget(self.txt_torrent_url)
        
        t_lay.addWidget(QLabel("Login operatora sekwencera masowego:"))
        self.txt_torrent_user = QLineEdit()
        self.txt_torrent_user.setPlaceholderText("Domyślnie: ionadmin")
        t_lay.addWidget(self.txt_torrent_user)
        
        t_lay.addWidget(QLabel("Hasło dostępowe do serwera maszynowego:"))
        self.txt_torrent_pass = QLineEdit()
        self.txt_torrent_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_torrent_pass.setPlaceholderText("Wpisz hasło autoryzacji")
        t_lay.addWidget(self.txt_torrent_pass)

        # ✅ NOWOŚĆ: Dedykowana, sztywna lokalizacja pobrań dla maszyn Torrent ION
        t_lay.addWidget(QLabel("Katalog sterylnego zrzutu genomów z serwera ION:"))
        torrent_path_layout = QHBoxLayout()
        self.txt_torrent_download_dir = QLineEdit()
        self.txt_torrent_download_dir.setReadOnly(True)
        torrent_path_layout.addWidget(self.txt_torrent_download_dir)
        self.btn_browse_torrent_dir = QPushButton("Przeglądaj...")
        self.btn_browse_torrent_dir.clicked.connect(
            lambda: self._browse_dir(self.txt_torrent_download_dir, "Wybierz katalog pobrań z Torrent ION")
        )
        torrent_path_layout.addWidget(self.btn_browse_torrent_dir)
        t_lay.addLayout(torrent_path_layout)
        
        t_lay.addStretch()
        self.h_split_layout.addWidget(torrent_group)
        
        # Wstrzyknięcie zunifikowanego pasa Side-by-Side do layoutu głównego
        self.main_layout.addLayout(self.h_split_layout)

        # --- SEKCJA 3: RAM BUFFER ALLOCATION ---
        ram_group = QGroupBox("🧠 REZERWACJA PAMIĘCI OPERACYJNEJ DLA POTOKU (RAM Buffer)")
        ram_layout = QVBoxLayout(ram_group)
        self.lbl_ram = QLabel()
        self.slider_ram = QSlider(Qt.Orientation.Horizontal)
        self.slider_ram.setMinimum(8)
        self.slider_ram.setMaximum(config.MAX_RAM_ALLOCATION_GB)
        self.slider_ram.valueChanged.connect(self._update_ram_label)
        ram_layout.addWidget(self.lbl_ram)
        ram_layout.addWidget(self.slider_ram)
        self.main_layout.addWidget(ram_group)

        # --- SEKCJA 4: CORE CPU ALLOCATION ---
        cpu_group = QGroupBox("🎛 PRZYDZIAŁ RDZENI CPU DLA SILNIKÓW BATERII (Xeon Core Allocator)")
        cpu_layout = QVBoxLayout(cpu_group)
        self.lbl_cpu = QLabel()
        self.slider_cpu = QSlider(Qt.Orientation.Horizontal)
        self.slider_cpu.setMinimum(2)
        self.slider_cpu.setMaximum(config.MAX_THREADS_ALLOCATION)
        self.slider_cpu.valueChanged.connect(self._update_cpu_label)
        cpu_layout.addWidget(self.lbl_cpu)
        cpu_layout.addWidget(self.slider_cpu)
        self.main_layout.addWidget(cpu_group)

        # --- PRZYCISK ZAPISU I SYNCHRONIZACJI MASTERYCZNEJ ---
        self.btn_save_settings = QPushButton("💾 ZAPISZ I ZARYGLUJ NOWĄ KONFIGURACJĘ GLOBALNĄ")
        self.btn_save_settings.setStyleSheet("""
            QPushButton {
                background-color: #0d47a1; color: white; font-weight: bold;
                font-size: 13px; border-radius: 5px; padding: 10px;
            }
            QPushButton:hover { background-color: #1565c0; }
        """)
        self.btn_save_settings.clicked.connect(self._save_system_settings)
        self.main_layout.addWidget(self.btn_save_settings)

        # Automatyczne załadowanie danych przy podniesieniu instancji
        self.refresh_settings_fields()

    def _update_ram_label(self, val):
        self.lbl_ram.setText(f"Alokowany bufor pamięci RAM dla podprocesów: {val} GB (Zalecane: {config.MAX_RAM_ALLOCATION_GB} GB)")

    def _update_cpu_label(self, val):
        self.lbl_cpu.setText(f"Maksymalna pula wątków dla nucmer/blastn: {val} / {config.TOTAL_SYSTEM_CORES} Cores")

    def _browse_workspace(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Wybierz lokalne workspace diagnostyczne")
        if dir_path:
            self.txt_workspace.setText(os.path.abspath(dir_path))

    def _browse_dir(self, target_line_edit, title):
        dir_path = QFileDialog.getExistingDirectory(self, title)
        if dir_path:
            target_line_edit.setText(os.path.abspath(dir_path))

    def refresh_settings_fields(self):
        """
        [THE MASTER REFRESH ENGINE - V46]: Bezpiecznie ładuje konfigurację z dysku.
        Zasila kontrolki i synchronizuje globalną pamięć RAM modułu config.
        """
        if not self.ws:
            return
        current_cfg = self.ws._read_config_from_disk()

        # 1. Wczytanie 4 ścieżek laboratoryjnych (Zgodnie z plikiem JSON)
        saved_ws = current_cfg.get("output_workspace_dir", config.DEFAULT_APP_DIR).strip()
        saved_kraken = current_cfg.get("kraken_db_dir", "").strip()
        saved_lib = current_cfg.get("reference_library_dir", "").strip()
        saved_backup = current_cfg.get("backup_repository_dir", "").strip()

        self.txt_workspace.setText(saved_ws)
        self.txt_kraken_db.setText(saved_kraken)
        self.txt_library_dir.setText(saved_lib)
        self.txt_backup_dir.setText(saved_backup)

        # Synchronizacja pamięci jądra config.py
        config.BASE_DATA_DIR = saved_ws
        config.OUTPUT_DIR = saved_ws
        config.DEFAULT_KRAKEN_DB = saved_kraken
        config.LIBRARY_DIR = saved_lib
        config.BACKUP_DIR = saved_backup

        # 2. Wczytanie Zaawansowanych Filtrów i API (Uodpornione Atrybuty)
        saved_threshold = current_cfg.get("kraken_noise_threshold", 0.1)
        self.txt_threshold.setText(str(saved_threshold))
        config.KRAKEN_NOISE_THRESHOLD = float(saved_threshold)

        saved_api_key = current_cfg.get("ncbi_api_key", "").strip()
        self.txt_api_key.setText(saved_api_key)
        config.NCBI_API_KEY = saved_api_key

        # 3. Wczytanie Rejestrów Torrent Servera i Nowego Katalogu Pobierania
        saved_url = current_cfg.get("torrent_server_url", "").strip()
        saved_user = current_cfg.get("torrent_server_user", "ionadmin").strip()
        saved_pass = current_cfg.get("torrent_server_pass", "").strip()
        
        # ✅ Dynamiczny bezpieczny fallback podkatalogu wewnątrz workspace
        default_torrent_dir = os.path.join(saved_ws, "torrent_downloads")
        saved_torrent_dir = current_cfg.get("torrent_download_dir", default_torrent_dir).strip()

        self.txt_torrent_url.setText(saved_url)
        self.txt_torrent_user.setText(saved_user)
        self.txt_torrent_pass.setText(saved_pass)
        self.txt_torrent_download_dir.setText(saved_torrent_dir)

        config.TORRENT_SERVER_URL = saved_url
        config.TORRENT_SERVER_USER = saved_user
        config.TORRENT_SERVER_PASS = saved_pass
        config.TORRENT_DOWNLOAD_DIR = saved_torrent_dir

        # 4. Inicjalizacja suwaków sprzętowych
        saved_threads = current_cfg.get("threads_limit", config.MAX_THREADS_ALLOCATION)
        self.slider_cpu.setValue(int(saved_threads))
        config.CURRENT_THREADS_LIMIT = int(saved_threads)

        saved_ram = current_cfg.get("max_ram_allocation_gb", config.MAX_RAM_ALLOCATION_GB)
        self.slider_ram.setValue(int(saved_ram))

    def _save_system_settings(self):
        """Przekazuje nowe dane ścieżek, filtrów i RAM do rejestru głównego i zapisuje trwale."""
        workspace = self.txt_workspace.text().strip()
        kraken = self.txt_kraken_db.text().strip()
        reference = self.txt_library_dir.text().strip()
        backup = self.txt_backup_dir.text().strip()
        threads = self.slider_cpu.value()
        api_key_val = self.txt_api_key.text().strip()
        
        torrent_url_val = self.txt_torrent_url.text().strip()
        torrent_user_val = self.txt_torrent_user.text().strip()
        torrent_pass_val = self.txt_torrent_pass.text().strip()
        torrent_dir_val = self.txt_torrent_download_dir.text().strip()

        try:
            threshold = float(self.txt_threshold.text().strip())
            config.KRAKEN_NOISE_THRESHOLD = threshold
        except ValueError:
            QMessageBox.critical(self, "Błąd wartości", "Próg odcięcia szumu musi być liczbą (np. 0.1)!")
            return

        ram_gb = self.slider_ram.value()
        config.MAX_RAM_ALLOCATION_GB = ram_gb

        if not workspace or not kraken or not reference or not backup or not torrent_dir_val:
            QMessageBox.critical(self, "Błąd konfiguracji", "Wszystkie ścieżki do katalogów, w tym lokalizacja pobrań Torrent, muszą być uzupełnione!")
            return

        # Wywołanie rozszerzonej sygnatury zaryglowanego menedżera jądra (Krok 2B)
        success = self.ws.save_master_config(workspace, kraken, reference, threads, torrent_dir_val)
        if success:
            current_cfg = self.ws._read_config_from_disk()
            current_cfg["kraken_noise_threshold"] = threshold
            current_cfg["max_ram_allocation_gb"] = ram_gb
            current_cfg["backup_repository_dir"] = backup
            current_cfg["ncbi_api_key"] = api_key_val
            current_cfg["torrent_server_url"] = torrent_url_val
            current_cfg["torrent_server_user"] = torrent_user_val
            current_cfg["torrent_server_pass"] = torrent_pass_val

            try:
                with open(self.ws.config_file, "w", encoding="utf-8") as f:
                    json.dump(current_cfg, f, indent=4, ensure_ascii=False)
            except Exception:
                pass

            config.BACKUP_DIR = backup
            config.NCBI_API_KEY = api_key_val
            config.TORRENT_SERVER_URL = torrent_url_val
            config.TORRENT_SERVER_USER = torrent_user_val
            config.TORRENT_SERVER_PASS = torrent_pass_val
            config.TORRENT_DOWNLOAD_DIR = torrent_dir_val

            if hasattr(self.main_window, 'kraken_db_field'):
                self.main_window.kraken_db_field.setText(kraken)

            if self.main_window and hasattr(self.main_window, 'tab_backup'):
                self.main_window.tab_backup.update_backup_repo_field()

            QMessageBox.information(self, "Zapisano", "Wszystkie pięć ścieżek, progi, limity Xeon oraz parametry Torrent Servera zostały zaryglowane na dysku NVMe!")
        else:
            QMessageBox.critical(self, "Błąd", "Wystąpił twardy błąd zapisu pliku konfiguracyjnego.")
