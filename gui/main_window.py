# gui/main_window.py
import sys
import os
from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
                             QTabWidget, QMessageBox, QFileDialog, QCheckBox)
from PyQt6.QtCore import Qt
import config
from gui.tabs.monitor_tab import MonitorTab  # type: ignore
from gui.tabs.taxonomy_tab import TaxonomyTab  # type: ignore
from gui.tabs.history_tab import HistoryTab  # type: ignore
from gui.tabs.comparative_tab import ComparativeTab  # type: ignore
from gui.tabs.view_manager_tab import ViewManagerTab  # type: ignore  <-- NOWOŚĆ: Import karty B!
from gui.tabs.settings_tab import SettingsTab  # type: ignore
from gui.tabs.backup_tab import BackupTab  # type: ignore
from core.workspace_manager import WorkspaceManager

class KombajnMainWindow(QMainWindow):
    """Część 1: Inicjalizacja rejestru kart, style Dark Mode oraz managerów."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kombajn T430 - Zintegrowany Potok Bioinformatyczny")
        
        self.ws = WorkspaceManager(init_system=True)
        self.showMaximized()
        
        self.setStyleSheet("""
            QMainWindow { background-color: #121212; }
            QWidget { background-color: #121212; color: #E0E0E0; font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; }
            QGroupBox { border: 2px solid #2C2C2C; border-radius: 6px; margin-top: 12px; font-weight: bold; color: #00FF66; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px 0 3px; }
            QLineEdit { background-color: #1E1E1E; border: 1px solid #3A3A3A; border-radius: 4px; padding: 4px; color: #FFFFFF; }
            QPushButton { background-color: #2D2D2D; border: 1px solid #3A3A3A; border-radius: 4px; padding: 5px 12px; font-weight: bold; }
            QPushButton:hover { background-color: #3D3D3D; border: 1px solid #00FF66; }
            QSlider::handle:horizontal { background: #00FF66; width: 14px; margin: -5px 0; border-radius: 7px; }
            QSlider::groove:horizontal { border: 1px solid #3A3A3A; height: 4px; background: #2D2D2D; }
            QTabWidget::pane { border: 1px solid #2C2C2C; background-color: #1E1E1E; }
            QTabBar::tab { background: #2D2D2D; border: 1px solid #2C2C2C; padding: 8px 20px; color: #AAAAAA; }
            QTabBar::tab:selected { background: #1E1E1E; border-bottom-color: #1E1E1E; color: #00FF66; font-weight: bold; }
            QCheckBox { color: #E0E0E0; font-weight: bold; }
            QCheckBox::indicator { border: 1px solid #3A3A3A; width: 14px; height: 14px; background: #1E1E1E; border-radius: 3px; }
            QCheckBox::indicator:checked { background: #00FF66; border: 1px solid #00FF66; }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        sidebar_widget = QWidget()
        sidebar_widget.setFixedWidth(350)
        self.sidebar_layout = QVBoxLayout(sidebar_widget)
        self.sidebar_layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar_layout.setSpacing(10)
        main_layout.addWidget(sidebar_widget)

        # =====================================================================
        # SEKCJA REJESTRACJI I ALOKACJI WIDŻETÓW KART W PAMIĘCI RAM
        # =====================================================================
        self.tabs = QTabWidget()
        self.tab_monitor = MonitorTab()
        self.tab_taxonomy = TaxonomyTab()
        self.tab_history = HistoryTab()
        self.tab_compare = ComparativeTab()       # Karta A — Gotowa do rozbudowy matrixa
        self.tab_view_manager = ViewManagerTab()   # Karta B — Nowa instancja makiety wyników!
        self.tab_settings = SettingsTab(parent_main_window=self)
        self.tab_backup = BackupTab() 
        
        # Powiązania referencyjne wsteczne dla zachowania interlocku bezawaryjnego
        self.tab_compare.main_window = self
        self.tab_history.main_window = self
        self.tab_view_manager.main_window = self   # Powiązanie nowej karty B
        self.tab_backup.main_window = self   

        # Oficjalne dodanie kart do widżetu tabulatora Qt w ergonomicznej sekwencji
        self.tabs.addTab(self.tab_monitor, "📡 Monitor Procesu")
        self.tabs.addTab(self.tab_taxonomy, "🦠 Analiza Taksonomiczna")
        self.tabs.addTab(self.tab_history, "📁 Przegląd Analiz")
        self.tabs.addTab(self.tab_compare, "🧬 Matryca Porównawcza N x M")  # <-- Zmieniony nagłówek zadania A!
        self.tabs.addTab(self.tab_view_manager, "🖥️ Menedżer Wyników i Logów") # <-- Nowa zakładka zadania B!
        self.tabs.addTab(self.tab_settings, "🔧 Konfiguracja")
        self.tabs.addTab(self.tab_backup, "🗄️ Magazyn HDD / Backup")
        main_layout.addWidget(self.tabs)

        self.current_pipeline_thread = None
        self.current_project_path = None
        
        self._build_sidebar(self.sidebar_layout)

    def _build_sidebar(self, layout):
        """Część 2: Konstruuje elementy kontrolne paska bocznego w oparciu o cztery jasne scenariusze pracy [AG1]."""
        from PyQt6.QtWidgets import QGroupBox, QRadioButton, QLineEdit, QPushButton, QLabel, QButtonGroup

        # 1. SEKCJA DANYCH WEJŚCIOWYCH
        input_box = QGroupBox("1. DANE WEJŚCIOWE")
        input_layout = QVBoxLayout(input_box)
        
        self.mode_single = QRadioButton("Pojedyncza próbka")
        self.mode_batch = QRadioButton("Cały katalog (Batch)")
        self.mode_single.setChecked(True)
        
        self.input_group = QButtonGroup(self)
        self.input_group.addButton(self.mode_single)
        self.input_group.addButton(self.mode_batch)
        
        path_layout = QHBoxLayout()
        self.input_path_field = QLineEdit()
        self.input_path_field.setPlaceholderText("Wskaż surowy FASTQ lub wyciąg .fastq.gz...")
        
        self.btn_browse_input = QPushButton("...")
        self.btn_browse_input.setFixedWidth(40)
        self.btn_browse_input.clicked.connect(self._handle_browse_input)
        path_layout.addWidget(self.input_path_field)
        path_layout.addWidget(self.btn_browse_input)
        
        self.txt_custom_project_name = QLineEdit()
        self.txt_custom_project_name.setPlaceholderText("Nazwa własna projektu (opcjonalnie)...")
        self.txt_custom_project_name.setToolTip("Wpisz opcjonalny sufix identyfikacyjny. Spacje zostaną automatycznie zamienione na '_'")
        
        self.txt_custom_project_name.textChanged.connect(
            lambda text: self.txt_custom_project_name.setText(text.replace(" ", "_")) if " " in text else None
        )
        
        # [WSTRZYKNIĘCIE V46]: Fizyczny klawisz pobierania ION
        self.btn_fetch_ion = QPushButton("📡 Pobierz Wyniki ION")
        self.btn_fetch_ion.setStyleSheet("""
            QPushButton { background-color: #1E1E1E; color: #00FF66; border: 1px solid #00FF66; border-radius: 4px; padding: 6px; font-weight: bold; margin-top: 6px; }
            QPushButton:hover { background-color: #006622; color: #FFFFFF; }
            QPushButton:disabled { background-color: #121212; color: #444444; border-color: #2C2C2C; }
        """)
        self.btn_fetch_ion.clicked.connect(self._open_torrent_browser_window)

        # ✅ NOWOŚĆ [WSTRZYKNIĘCIE V46.1 - GOOGLE INTERNET TESTER]: Przycisk diagnostyczny sieci zewnętrznej
        self.btn_fetch_google = QPushButton("🌐 Testuj Połączenie (Google)")
        self.btn_fetch_google.setStyleSheet("""
            QPushButton { background-color: #1E1E1E; color: #0099FF; border: 1px solid #0099FF; border-radius: 4px; padding: 6px; font-weight: bold; margin-top: 4px; }
            QPushButton:hover { background-color: #0044CC; color: #FFFFFF; }
            QPushButton:disabled { background-color: #121212; color: #444444; border-color: #2C2C2C; }
        """)
        self.btn_fetch_google.clicked.connect(self._open_google_browser_window)

        # Sekwencja geometryczna układu kaskadowego od góry do dołu
        input_layout.addWidget(self.mode_single)
        input_layout.addWidget(self.mode_batch)
        input_layout.addLayout(path_layout)
        input_layout.addWidget(self.txt_custom_project_name)
        input_layout.addWidget(self.btn_fetch_ion)
        input_layout.addWidget(self.btn_fetch_google) # Zamyka sterylnie dół ramki wejściowej
        layout.addWidget(input_box)

        self.mode_single.clicked.connect(lambda: self.tab_monitor.set_batch_mode_active(False))
        self.mode_batch.clicked.connect(lambda: self.tab_monitor.set_batch_mode_active(True, total_samples=0))

        # 2. SEKCJA PLATFORMY
        tech_box = QGroupBox("2. PLATFORMA SEKWENCJONOWANIA")
        tech_layout = QVBoxLayout(tech_box)
        self.tech_ion = QRadioButton("Ion Torrent (Ion S5)")
        self.tech_nano = QRadioButton("Oxford Nanopore (MinION)")
        self.tech_ion.setChecked(True)
        
        self.tech_group = QButtonGroup(self)
        self.tech_group.addButton(self.tech_ion)
        self.tech_group.addButton(self.tech_nano)
        
        tech_layout.addWidget(self.tech_ion)
        tech_layout.addWidget(self.tech_nano)
        layout.addWidget(tech_box)

        # =====================================================================
        # 3. SEKCJA TRYBU PRACY I SCENARIUSZE POTOKU - ERGONOMIA V17 [INDEX]
        # Układ odwrócony: od najszybszego skriningu do najcięższego pełnego potoku.
        # =====================================================================
        mode_box = QGroupBox("3. TRYB PRACY I SCENARIUSZE POTOKU")
        mode_layout = QVBoxLayout(mode_box)
        
        # Inicjalizacja przycisków radiowych w nowej, operacyjnej kolejności hierarchicznej [INDEX]
        self.rad_mode_tax = QRadioButton("Szybki Skrining (Tylko Taksonomia)")
        self.rad_mode_skip_qc = QRadioButton("Pomiń QC (Direct-to-Kraken)")
        self.rad_mode_asm = QRadioButton("Tylko składanie (Direct Assembly)")
        self.rad_mode_full = QRadioButton("Pełny Potok Standardowy")
        
        # ✅ REFORMA: Szybki Skrining staje się domyślnym profilem rozruchu laboratorium! [INDEX]
        self.rad_mode_tax.setChecked(True) 
        
        # Przypisanie sterylnych, jaskrawych kodów kolorystycznych dla szybkiej identyfikacji wizualnej
        self.rad_mode_tax.setStyleSheet("color: #ECC94B;")      # Żółty - Szybki Skrining
        self.rad_mode_skip_qc.setStyleSheet("color: #0099FF;")   # Niebieski - Direct-to-Kraken
        self.rad_mode_asm.setStyleSheet("color: #b83280;")       # Fuksja - Direct Assembly
        self.rad_mode_full.setStyleSheet("color: #00FF66;")      # Zielony - Pełny Potok
        
        self.workflow_group = QButtonGroup(self)
        self.workflow_group.addButton(self.rad_mode_tax)
        self.workflow_group.addButton(self.rad_mode_skip_qc)
        self.workflow_group.addButton(self.rad_mode_asm)
        self.workflow_group.addButton(self.rad_mode_full)
        
        # Bezwzględne wstrzyknięcie do layoutu w nowej sekwencji geometrycznej [INDEX]
        mode_layout.addWidget(self.rad_mode_tax)
        mode_layout.addWidget(self.rad_mode_skip_qc)
        mode_layout.addWidget(self.rad_mode_asm)
        mode_layout.addWidget(self.rad_mode_full)
        layout.addWidget(mode_box)

        # 4. SEKCJA BAZY DANYCH
        db_box = QGroupBox("4. BAZA METAGENOMIKI")
        db_layout = QVBoxLayout(db_box)
        kraken_path_layout = QHBoxLayout()
        self.kraken_db_field = QLineEdit(config.DEFAULT_KRAKEN_DB)
        
        # ✅ REJESTRACJA INSTANCJI: Przekształcenie drugiego wielokropka w zmienną klasy słuchającą rygru
        self.btn_browse_db_path = QPushButton("...")
        self.btn_browse_db_path.setFixedWidth(40)
        self.btn_browse_db_path.clicked.connect(self._handle_browse_db)
        kraken_path_layout.addWidget(self.kraken_db_field)
        kraken_path_layout.addWidget(self.btn_browse_db_path)
        db_layout.addLayout(kraken_path_layout)
        layout.addWidget(db_box)

        layout.addStretch()

        # 5. PANEL PRE-WERYFIKACJI
        self.status_disk_label = QLabel("Status dysku Kingston: Obliczanie...")
        self.status_disk_label.setStyleSheet("color: #ECC94B; font-weight: bold; font-size: 11px;")
        
        self.btn_run_pipeline = QPushButton("URUCHOM POTOK (ETAP 1)")
        self.btn_run_pipeline.setStyleSheet("""
            QPushButton { background-color: #1A1A1A; color: #666666; font-size: 14px; padding: 10px; border: 1px solid #444444; }
            QPushButton:hover { background-color: #2D2D2D; }
        """)
        self.btn_run_pipeline.setEnabled(False)
        self.btn_run_pipeline.clicked.connect(self._start_pipeline_execution)
        
        self.btn_stop_pipeline = QPushButton("ZATRZYMAJ (STOP/KILL)")
        self.btn_stop_pipeline.setStyleSheet("""
            QPushButton { background-color: #660000; color: #FFFFFF; padding: 6px; border: 1px solid #FF0000; }
            QPushButton:hover { background-color: #880000; }
        """)
        self.btn_stop_pipeline.clicked.connect(self._kill_pipeline_execution)

        layout.addWidget(self.status_disk_label)
        layout.addWidget(self.btn_run_pipeline)
        layout.addWidget(self.btn_stop_pipeline)

        self.input_path_field.textChanged.connect(self._update_storage_safety_guard)
        self.tech_ion.clicked.connect(self._update_storage_safety_guard)
        self.tech_nano.clicked.connect(self._update_storage_safety_guard)
        self.rad_mode_full.clicked.connect(self._update_storage_safety_guard)
        self.rad_mode_tax.clicked.connect(self._update_storage_safety_guard)
        self.rad_mode_skip_qc.clicked.connect(self._update_storage_safety_guard)
        self.rad_mode_asm.clicked.connect(self._update_storage_safety_guard)
        
        self._update_storage_safety_guard()

    def _handle_browse_input(self):
        """[THE SECURE INPUT BROWSER - FALLBACK ROUTING]: Wymusza start w torrent_download_dir z kaskadą awaryjną [2.4]."""
        from core.explorer import CoreExplorer, ExplorerMode, FilterProfile

        # Rygorowanie punktu startowego na bazie konfiguracji pobrań maszynowych Ion Torrent [2.4]
        target_torrent_dir = getattr(config, 'TORRENT_DOWNLOAD_DIR', '')
        
        # Kaskada awaryjna: jeśli dedykowany folder został skasowany, uderzamy w output_workspace_dir [2.4]
        if target_torrent_dir and os.path.exists(target_torrent_dir):
            start_dir = target_torrent_dir
        else:
            start_dir = getattr(config, 'BASE_DATA_DIR', None)

        if self.mode_single.isChecked():
            explorer = CoreExplorer(
                parent=self,
                mode=ExplorerMode.FILE_SELECT,
                filter_profile=FilterProfile.RAW_DATA,
                start_dir=start_dir
            )
            if explorer.exec():
                file_path = explorer.get_selected_path()
                if file_path:
                    self.input_path_field.setText(file_path)
        else:
            explorer = CoreExplorer(
                parent=self,
                mode=ExplorerMode.DIRECTORY_SELECT,
                filter_profile=FilterProfile.RAW_DATA,
                start_dir=start_dir
            )
            if explorer.exec():
                dir_path = explorer.get_selected_path()
                if dir_path:
                    self.input_path_field.setText(dir_path)
                
        self._update_storage_safety_guard()    

    def _handle_browse_db(self):
        """[THE RELATIONAL DB BROWSER - FALLBACK ROUTING]: Wymusza start w folderze nadrzędnym baz z kaskadą awaryjną [2.4]."""
        from core.explorer import CoreExplorer, ExplorerMode, FilterProfile

        # Pobranie oficjalnej ścieżki bazy zaryglowanej w pamięci konfiguratora globalnego [2.4]
        active_db_path = getattr(config, 'DEFAULT_KRAKEN_DB', '')
        start_dir = None

        if active_db_path:
            # Obliczenie ścieżki nadrzędnej (o jeden poziom wyżej) nad aktualnym folderem Kraken2 [2.4]
            parent_dir = os.path.dirname(os.path.abspath(active_db_path))
            if os.path.exists(parent_dir):
                start_dir = parent_dir

        # Kaskada awaryjna: jeśli katalog nadrzędny baz nie istnieje, skaczemy do output_workspace_dir [2.4]
        if not start_dir or not os.path.exists(start_dir):
            start_dir = getattr(config, 'BASE_DATA_DIR', None)

        explorer = CoreExplorer(
            parent=self,
            mode=ExplorerMode.DIRECTORY_SELECT,
            filter_profile=FilterProfile.RAW_DATA,
            start_dir=start_dir
        )
        
        if explorer.exec():
            dir_path = explorer.get_selected_path()
            if dir_path:
                self.kraken_db_field.setText(dir_path)
                # JAWNY INTERLOCK: Dynamiczna aktualizacja stałej w locie RAM na potrzeby kolejnych wywołań
                config.DEFAULT_KRAKEN_DB = dir_path

    def _update_storage_safety_guard(self):
        """Autonomiczny system pre-weryfikacji: skanuje foldery Batch i oblicza zapotrzebowanie NVMe [INDEX]."""
        # ✅ KROK 14: Bezwzględne odcięcie i wyciszenie zmian paska bocznego podczas finiszu matrycy [2.4]
        if hasattr(self, 'tab_compare') and hasattr(self.tab_compare, 'matrix_manager') and getattr(self.tab_compare.matrix_manager, '_matrix_is_done', False):
            return

        import shutil
        
        input_file = str(self.input_path_field.text()).strip()
        if not input_file or not os.path.exists(input_file):
            self.status_disk_label.setText("⚠️ [STATUS]: Oczekiwanie na dane wejściowe...")
            self.status_disk_label.setStyleSheet("color: #ECC94B; font-weight: bold; font-size: 11px;")
            self.btn_run_pipeline.setEnabled(False)
            self.btn_run_pipeline.setStyleSheet("""
                QPushButton { background-color: #1A1A1A; color: #666666; font-size: 14px; padding: 10px; border: 1px solid #444444; }
                QPushButton:disabled { background-color: #1A1A1A; color: #666666; }
            """)
            return

        sample_count = 1
        if self.mode_batch.isChecked() and os.path.isdir(input_file):
            try:
                valid_extensions = (".fastq", ".fastq.gz", ".bam")
                detected_files = [f for f in os.listdir(input_file) if f.lower().endswith(valid_extensions) and os.path.isfile(os.path.join(input_file, f))]
                sample_count = len(detected_files)
            except Exception:
                sample_count = 0
        target_dir = getattr(config, 'DEFAULT_OUTPUT_DIR', os.path.expanduser("~"))
        if not os.path.exists(target_dir):
            target_dir = os.path.expanduser("~")
            
        try:
            total, used, free = shutil.disk_usage(target_dir)
            free_gb = free / (1024 ** 3)
        except Exception:
            free_gb = 0.0

        is_nanopore = self.tech_nano.isChecked()
        is_only_taxonomy = self.rad_mode_tax.isChecked()
        is_skip_qc = self.rad_mode_skip_qc.isChecked()
        is_only_assembly = self.rad_mode_asm.isChecked()

        if is_nanopore:
            base_required = 50.0
        else:
            base_required = 20.0

        # ✅ DYNAMICZNA KOREKTA WAG: Pełna, 4-stopniowa segmentacja zapotrzebowania pamięci [INDEX]
        if is_only_taxonomy:
            base_required = 2.0
        elif is_skip_qc:
            base_required = 5.0  # Profil Direct-to-Kraken odcina ciężkie assemblery, wymagane stałe 5 GB
        elif is_only_assembly:
            base_required = base_required / 2.0

        required_gb = base_required * sample_count
        if sample_count == 0 and self.mode_batch.isChecked():
            self.status_disk_label.setText("⚠️ [BŁĄD BATCH]: Brak prawidłowych plików (FASTQ/BAM) w folderze!")
            self.status_disk_label.setStyleSheet("color: #F56565; font-weight: bold; font-size: 11px;")
            self.btn_run_pipeline.setEnabled(False)
        elif free_gb < required_gb:
            self.status_disk_label.setText(f"🛑 [BRAK MIEJSCA]: Seria ({sample_count} prób) wymaga {required_gb:.1f} GB, wolne {free_gb:.1f} GB!")
            self.status_disk_label.setStyleSheet("color: #F56565; font-weight: bold; font-size: 11px;")
            self.btn_run_pipeline.setEnabled(False)
            self.btn_run_pipeline.setStyleSheet("""
                QPushButton { background-color: #1A1A1A; color: #666666; font-size: 14px; padding: 10px; border: 1px solid #444444; }
                QPushButton:disabled { background-color: #1A1A1A; color: #666666; }
            """)
        else:
            batch_prefix = f"Seria ({sample_count} prób) - " if self.mode_batch.isChecked() else ""
            self.status_disk_label.setText(f"✅ [GOTOWY]: {batch_prefix}Wolne {free_gb:.1f} GB (Wymagane {required_gb:.1f} GB)")
            self.status_disk_label.setStyleSheet("color: #00FF66; font-weight: bold; font-size: 11px;")
            self.btn_run_pipeline.setEnabled(True)
            self.btn_run_pipeline.setStyleSheet("""
                QPushButton { background-color: #006622; color: #FFFFFF; font-size: 14px; padding: 10px; border: 1px solid #00FF66; font-weight: bold; }
                QPushButton:hover { background-color: #008833; }
            """)

    def _start_pipeline_execution(self):
        """Pobiera parametry z GUI, oficjalnie inicjuje projekt przez WorkspaceManager i automatycznie oczyszcza Master Container [INDEX]."""
        input_path = str(self.input_path_field.text()).strip()
        kraken_db = str(self.kraken_db_field.text()).strip()
        
        if not input_path or not os.path.exists(input_path):
            QMessageBox.warning(self, "Błąd wejścia", "Wskazany plik wejściowy nie istnieje!")
            return

        platform = "ION_TORRENT" if self.tech_ion.isChecked() else "NANOPORE"
        
        if not self.rad_mode_asm.isChecked() and (not kraken_db or not os.path.exists(kraken_db)):
            QMessageBox.warning(self, "Błąd bazy danych", "Wskazana baza danych Kraken2 nie istnieje!")
            return

        # ✅ DYNAMICZNA INTEGRACJA PRZYROSTKÓW: Bezbłędna segmentacja nazw folderów super-projektu [INDEX]
        if self.rad_mode_tax.isChecked():
            base_suffix = "QuickSkrining"
        elif self.rad_mode_skip_qc.isChecked():
            base_suffix = "DirectToKraken"  # Sprostowanie ślepego punktu dla pominięcia QC
        elif self.rad_mode_asm.isChecked():
            base_suffix = "DirectAsm"
        else:
            base_suffix = "LiveRun"

        custom_suffix = str(self.txt_custom_project_name.text()).strip().replace(" ", "_")
        final_container_label = f"{base_suffix}_{custom_suffix}" if custom_suffix else base_suffix

        ws = WorkspaceManager(init_system=False)
        self.current_project_path = ws.create_new_project_container(custom_name=final_container_label)
        
        self.tab_monitor.reset_controls_for_new_run()
        self.tab_taxonomy.reset_tab_for_new_run()

        self._set_peripheral_tabs_enabled(False)
        if hasattr(self, 'tabs'):
            self.tabs.setCurrentIndex(1)

        self.batch_files_queue = []
        self.batch_current_index = 0

        if self.mode_batch.isChecked() and os.path.isdir(input_path):
            for folder_name in ["01_QC", "02_Taxonomy", "03_Assembly", "04_Comparative", "raw_input"]:
                target_to_remove = os.path.join(self.current_project_path, folder_name)
                if os.path.exists(target_to_remove):
                    try: os.rmdir(target_to_remove)
                    except Exception: pass

            valid_extensions = (".fastq", ".fastq.gz", ".bam")
            try:
                all_items = os.listdir(input_path)
                for item in all_items:
                    full_item_path = os.path.join(input_path, item)
                    if os.path.isfile(full_item_path) and item.lower().endswith(valid_extensions):
                        self.batch_files_queue.append(full_item_path)
                self.batch_files_queue.sort()
            except Exception as e:
                QMessageBox.critical(self, "Błąd odczytu Batch", f"Nie udało się przeskanować katalogu:\n{str(e)}")
                self._set_peripheral_tabs_enabled(True)
                return

            if not self.batch_files_queue:
                QMessageBox.warning(self, "Brak danych", "Nie odnaleziono żadnych plików FASTQ lub BAM we wskazanym folderze!")
                self._set_peripheral_tabs_enabled(True)
                return
                
            self.tab_monitor.set_batch_mode_active(True, total_samples=len(self.batch_files_queue))
            self.tab_monitor.append_log(f"[BATCH MODE]: Wykryto {len(self.batch_files_queue)} plików do przetworzenia w serii.")
        else:
            self.batch_files_queue = [input_path]
            self.tab_monitor.set_batch_mode_active(False)

        self._execute_single_batch_item_from_queue()

    def _set_peripheral_tabs_enabled(self, enabled: bool, exclude_idx: int = None):
        """[PANCERNE API INTERLOCKU V49.9]: Odblokowanie instancji obiektowych w RAM stacji XEON [2.4]."""
        # 🕒 KROK 1: Bezpieczna iteracja po indeksach z odizolowaną ochroną przed crashami
        for idx in range(self.tabs.count()):
            try:
                widget = self.tabs.widget(idx)
                if not widget: 
                    continue
                    
                # 🚨 FIX WYSZARZONEJ KARTY: Bezpośrednie porównanie wskaźników RAM zamiast stringów typu [2.4]
                if widget == self.tab_monitor: 
                    continue
                    
                if exclude_idx is not None and idx == exclude_idx: 
                    continue
                    
                # Sterylna aktywacja i-węzła karty w strukturze QTabWidget
                self.tabs.setTabEnabled(idx, enabled)
            except Exception as e:
                if hasattr(self, 'tab_monitor') and self.tab_monitor:
                    self.tab_monitor.append_log(f"[BŁĄD I-WĘZŁA KARTY {idx}]: {str(e)}")

        # 🕒 KROK 2: Bezpieczne przywrócenie sterowności głównego przycisku potoku Etapu 1
        if hasattr(self, 'btn_run_pipeline') and self.btn_run_pipeline:
            self.btn_run_pipeline.setEnabled(enabled)
            style = "background-color: #006622; color: #FFFFFF;" if enabled else "background-color: #1A1A1A; color: #666666;"
            self.btn_run_pipeline.setStyleSheet(style + " font-size: 14px; padding: 10px; border: 1px solid #444444;")

        # 🕒 KROK 3: Masowa pętla uwalniania lub ryglowania wszystkich kontrolek wejściowych paska bocznego
        for widget in [self.input_path_field, self.mode_single, self.mode_batch, self.tech_ion, 
                       self.tech_nano, self.rad_mode_full, self.rad_mode_tax, self.rad_mode_skip_qc, 
                       self.rad_mode_asm, self.txt_custom_project_name, self.kraken_db_field, 
                       self.btn_fetch_ion, self.btn_fetch_google]:
            if widget: 
                widget.setEnabled(enabled)
            
        if hasattr(self, 'btn_browse_input') and self.btn_browse_input: 
            self.btn_browse_input.setEnabled(enabled)
        if hasattr(self, 'btn_browse_db_path') and self.btn_browse_db_path: 
            self.btn_browse_db_path.setEnabled(enabled)

    def _open_torrent_browser_window(self):
        """
        [THE TORRENT LAUNCH TRIGGER V46]: Wywołuje autonomiczne okno przeglądarki.
        Inicjalizuje OTR Chromium i przekazuje zaryglowane stałe jądra [▲2].
        """
        from core.chromium_engine import ChromiumBrowserWindow
        
        # Pobranie bezpiecznych parametrów z globalnego monolitu config.py [▲2]
        url = getattr(config, 'TORRENT_SERVER_URL', 'http://10.0.1.245')
        download_dir = getattr(config, 'TORRENT_DOWNLOAD_DIR', '')
        
        if not download_dir:
            if hasattr(self, 'tab_monitor') and self.tab_monitor:
                self.tab_monitor.append_log("[BŁĄD PRZEGLĄDARKI]: Brak zdefiniowanego katalogu pobrań w config.py! [▲2]")
            return

        # Powołanie do życia zmaksymalizowanego okna incognito sesji laboratoryjnej [▲2]
        self.torrent_browser = ChromiumBrowserWindow(url, download_dir, parent=self)
        if hasattr(self, 'tab_monitor') and self.tab_monitor:
            self.tab_monitor.append_log(f"[SYSTEM]: Inicjalizacja sterylnej sesji OTR Torrent Server pod adresem: {url} [▲2]")

    def _open_google_browser_window(self):
        """
        [THE GOOGLE LAUNCH TRIGGER V46.2]: Sterylne przekierowanie pobrań diagnostycznych.
        Dynamicznie wyznacza ścieżkę domową użytkownika systemu Lubuntu (~/Downloads).
        """
        from core.chromium_engine import ChromiumBrowserWindow
        import os
        
        url = "https://google.com"
        
        # Dynamiczne wyznaczenie ścieżki do domowego katalogu downloads użytkownika ionadmin
        user_home_downloads = os.path.expanduser("~/Downloads")
        
        # Weryfikacja awaryjna: jeśli angielski folder nie istnieje, uderzamy w polskie 'Pobrane'
        if not os.path.exists(user_home_downloads):
            user_home_downloads = os.path.expanduser("~/Pobrane")
            
        # Bezwarunkowe fizyczne utworzenie katalogu w locie, jeśli system go nie posiada
        os.makedirs(user_home_downloads, exist_ok=True)

        # Powołanie do życia okna Chromium z odizolowaną ścieżką systemową
        self.google_browser = ChromiumBrowserWindow(url, user_home_downloads, parent=self)
        if hasattr(self, 'tab_monitor') and self.tab_monitor:
            self.tab_monitor.append_log(f"[SYSTEM]: Uruchomienie okna diagnostycznego. Pobrane elementy trafią do: {user_home_downloads}")

    def _execute_single_batch_item_from_queue(self):
        """Pomocnicza metoda wewnętrzna: izoluje ścieżki próbek w RAM, mapuje 4 tryby i zasila oryginalny kalkulator step1_auto [AG1]."""
        import re
        if self.batch_current_index >= len(self.batch_files_queue):
            return

        current_file = self.batch_files_queue[self.batch_current_index]
        kraken_db = str(self.kraken_db_field.text()).strip()
        platform = "ION_TORRENT" if self.tech_ion.isChecked() else "NANOPORE"
        ram_gb = config.MAX_RAM_ALLOCATION_GB
        
        # PANCERNE MAPOWANIE PRZYCISKÓW RADIO NA NATIVE FLAGI SILNIKA OBLICZENIOWEGO
        skip_qc = True if (self.rad_mode_skip_qc.isChecked() or self.rad_mode_asm.isChecked()) else False
        force_only_asm = self.rad_mode_asm.isChecked()

        # UNIFIKACJA ŚCIEŻEK DLA LINUXA: Izolujemy foldery robocze próbek bezpośrednio w warstwie GUI
        if self.mode_batch.isChecked():
            raw_filename = os.path.basename(current_file)
            base_name = raw_filename.replace(".fastq.gz", "").replace(".fastq", "").replace(".bam", "").replace(".BAM", "")
            
            # Zamieniamy każdy ciąg spacji na jedno bezpieczne podkreślenie '_'
            clean_sample_name = re.sub(r'\s+', '_', base_name).strip('_')
            sample_output_dir = os.path.join(self.current_project_path, clean_sample_name)
            
            self.tab_monitor.append_log(f"\n=====================================================================")
            self.tab_monitor.append_log(f"[BATCH] URUCHAMIANIE PRÓBKI {self.batch_current_index + 1}/{len(self.batch_files_queue)}: {clean_sample_name}")
            self.tab_monitor.append_log(f"=====================================================================")
        else:
            sample_output_dir = self.current_project_path

        # Zgodnie z wytycznymi: fizyczne katalogi powstają w kontrolowanym momencie z poziomu GUI
        os.makedirs(sample_output_dir, exist_ok=True)

        from pipeline.step1_auto import AutoPipelineStep1
        pipeline_builder = AutoPipelineStep1(sample_output_dir)
        
        # GENEROWANIE KOMEND PRZEZ ZAMROŻONY SILNIK
        commands = pipeline_builder.build_pipeline_commands(
            input_fastq=current_file,
            platform=platform,
            kraken_db=kraken_db,
            allocated_ram_gb=ram_gb,
            skip_qc=skip_qc,
            force_only_assembly=force_only_asm
        )

        # CHIRURGICZNY FILTR SCENARIUSZA "SZYBKI SKRINIG" W LOCIE PAMIĘCI RAM INTERFEJSU
        if self.rad_mode_tax.isChecked():
            filtered_commands = []
            for cmd in commands:
                if isinstance(cmd, dict) and "args" in cmd and cmd["args"]:
                    binary_path = str(cmd["args"]).lower()
                    if "spades.py" in binary_path or "flye" in binary_path or "quast.py" in binary_path:
                        continue
                filtered_commands.append(cmd)
            
            commands = filtered_commands
            self.tab_monitor.append_log("[Kombajn T430]: Aktywowano scenariusz Szybkiego Skriningu. Sekcja assemblera została wycięta w RAM [AG1].")

        # AUTOMATYCZNY SEKWENCYJNY ZAPIS LOGU
        try:
            log_file_path = os.path.join(sample_output_dir, "pipeline.log")
            with open(log_file_path, "a", encoding="utf-8") as f:
                f.write(f"--- ROZPOCZĘTO ANALIZĘ PRÓBKI: {os.path.basename(current_file)} ---\n")
                f.write(f"Platforma: {platform} | Scenariusz: {'Tylko_Taksonomia' if self.rad_mode_tax.isChecked() else ('Tylko_Asm' if force_only_asm else ('Pomin_QC' if self.rad_mode_skip_qc.isChecked() else 'Pelny_Potok'))}\n")
            AutoPipelineStep1.commit_nvme_buffer(log_file_path)
        except Exception:
            pass

        self.btn_run_pipeline.setEnabled(False)
        self.tabs.setCurrentIndex(0)

        miniforge_env = os.environ.copy()

        from core.thread_manager import PipelineExecutionThread  # type: ignore
        self.current_pipeline_thread = PipelineExecutionThread(commands, env_vars=miniforge_env)
        
        self.current_pipeline_thread.log_signal.connect(self.tab_monitor.append_log)
        self.current_pipeline_thread.progress_signal.connect(self.tab_monitor.update_sample_progress)
        self.current_pipeline_thread.finished_signal.connect(self._handle_pipeline_finished)
        
        self.current_pipeline_thread.start()

    def _handle_pipeline_finished(self, status: str):
        """
        [PROCEDURA C - SANDBOX SZTAFETA]: Obsługuje zakończenie wątku roboczego.
        W pełni zsynchronizowana z kartą Monitora i Taksonomii. 
        Bezwarunkowo uwalnia zaryglowane peryferia po zakończeniu serii lub pojedynczej próbki.
        """
        import gc
        from PyQt6.QtCore import QTimer

        # 1. ZAPIS PRZYROSTOWEGO LOGU ANALIZY DO FOLDERU AKTYWNEJ PRÓBKI
        if self.batch_current_index < len(self.batch_files_queue):
            try:
                import re
                current_file = self.batch_files_queue[self.batch_current_index]
                raw_filename = os.path.basename(current_file)
                base_name = raw_filename.replace(".fastq.gz", "").replace(".fastq", "").replace(".bam", "").replace(".BAM", "")
                clean_sample_name = re.sub(r'\s+', '_', base_name).strip('_')
                
                target_log_dir = os.path.join(self.current_project_path, clean_sample_name) if self.mode_batch.isChecked() else self.current_project_path
                
                log_file_path = os.path.join(target_log_dir, "pipeline.log")
                if os.path.exists(target_log_dir):
                    with open(log_file_path, "a", encoding="utf-8") as f:
                        f.write(f"\n--- STAN KOŃCOWY ETAPU (STATUS: {status}) ---\n")
                        f.write(self.tab_monitor.log_viewer.toPlainText())
                        f.write(f"\n----------------------------------------------------\n")
                    from pipeline.step1_auto import AutoPipelineStep1
                    AutoPipelineStep1.commit_nvme_buffer(log_file_path)
            except Exception:
                pass

        if status == "KILLED":
            # [INTERLOCK S-1]: Przy twardym zabiciu potoku natychmiast uwalniamy zaryglowany interfejs
            self._set_peripheral_tabs_enabled(True)
            self.btn_run_pipeline.setEnabled(True)
            self.tab_monitor.append_log("\n[!!!] SERIA PRZERWANA PRZEZ UŻYTKOWNIKA [!!!]")
            QMessageBox.warning(self, "Przerwano", "Przetwarzanie serii zostało zatrzymane.")
            return
            
        if status == "FAILED":
            self.tab_monitor.append_log(f"\n[BŁĄD] Przetwarzanie bieżącej próbki zakończyło się awarią. Idę dalej...")

        # =====================================================================
        # WARUNEK ROZGRYWKI SERYJNEJ (TRYB BATCH) - MODEL ZDARZENIOWY [AG1]
        # =====================================================================
        if self.mode_batch.isChecked():
            self.batch_current_index += 1
            
            if self.batch_current_index < len(self.batch_files_queue):
                try:
                    current_percent = int((self.batch_current_index / len(self.batch_files_queue)) * 100)
                    self.tab_monitor.progress_bar.setValue(current_percent)
                    self.tab_monitor.lbl_task_status.setText(f"Stan systemu: Przetwarzanie serii Batch... Próbka {self.batch_current_index + 1}/{len(self.batch_files_queue)}")
                except Exception:
                    pass
                
                if self.current_pipeline_thread:
                    try:
                        self.current_pipeline_thread.disconnect()
                        # JAWNY TRIGGER ROZRUCHU: Kolejna próbka ruszy DOPIERO po pełnym usunięciu starej z RAM [AG1]
                        self.current_pipeline_thread.destroyed.connect(self._execute_single_batch_item_from_queue)
                        self.current_pipeline_thread.deleteLater() # Niskopoziomowy destruktor Qt C++ [AG1]
                    except Exception:
                        QTimer.singleShot(500, self._execute_single_batch_item_from_queue)
                    self.current_pipeline_thread = None
                
                gc.collect() # Wymuszenie odśmiecenia pamięci operacyjnej [AG1]
                return
            else:
                # OSTATECZNY FINAŁ SERII BATCH - WSZYSTKIE PRÓBKI UKOŃCZONE [AG1]
                # [INTERLOCK S-1]: Uwalniamy wszystkie zaryglowane zakładki archiwalne i konfiguracyjne na koniec serii
                self._set_peripheral_tabs_enabled(True)
                self.btn_run_pipeline.setEnabled(True)
                try:
                    self.tab_monitor.progress_bar.setValue(100)
                    self.tab_monitor.lbl_task_status.setText("Stan systemu: Wszystkie zadania serii Batch zostały pomyślnie przetworzone.")
                except Exception:
                    pass
                    
                self.tab_monitor.append_log("\n[SUKCES BATCH]: WSZYSTKIE PRÓBKI Z SERII ZOSTAŁY POMYŚLNIE PRZETWORZONE.")
                
                if self.current_pipeline_thread:
                    try:
                        self.current_pipeline_thread.disconnect()
                        self.current_pipeline_thread.deleteLater()
                    except Exception:
                        pass
                    self.current_pipeline_thread = None
                gc.collect()
                
                QMessageBox.information(
                    self, 
                    "Analiza seryjna Batch ukończona", 
                    "Proces seryjny został pomyślnie zakończony dla wszystkich znalezionych plików!\n\n"
                    f"Wyniki znajdują się w lokalizacji:\n"
                    f"{self.current_project_path}"
                )
                return

        # =====================================================================
        # WORKFLOW POJEDYNCZY (100% CIĄGŁOŚCI WSTECZNEJ DLA JEDNEGO FASTQ/BAM) [AG1]
        # =====================================================================
        # [INTERLOCK S-1]: Uwalniamy zaryglowany interfejs dla potoku pojedynczego
        self._set_peripheral_tabs_enabled(True)
        self.btn_run_pipeline.setEnabled(True)
        self.tab_monitor.append_log("\n[Kombajn T430]: PROCES ZAKOŃCZONY. ŁADOWANIE DOSTĘPNYCH RAPORTÓW...")
        
        if self.current_pipeline_thread:
            try:
                self.current_pipeline_thread.disconnect()
                self.current_pipeline_thread.deleteLater()
            except Exception:
                pass
            self.current_pipeline_thread = None
        gc.collect()

        if not self.rad_mode_asm.isChecked():
            from pipeline.step1_auto import AutoPipelineStep1
            report_txt = os.path.join(self.current_project_path, "02_Taxonomy", "kraken_report.txt")
            report_html = os.path.join(self.current_project_path, "02_Taxonomy", "krona_report.html")
            AutoPipelineStep1.commit_nvme_buffer(report_txt)
            AutoPipelineStep1.commit_nvme_buffer(report_html)

            from pipeline.parsers import KrakenParser
            if os.path.exists(report_txt):
                filtered_rows = KrakenParser.parse_kraken_report(report_txt, threshold=config.KRAKEN_NOISE_THRESHOLD)
                self.tab_taxonomy.populate_kraken_table(filtered_rows)
                
            if os.path.exists(report_html):
                self.tab_taxonomy.load_krona_chart(report_html)
            
        self.tab_monitor.activate_results_preview(self.current_project_path)
        QMessageBox.information(self, "Potok zakończony", "Zadanie bioinformatyczne zostało pomyślnie przetworzone!")

    def _kill_pipeline_execution(self):
        """Wymusza twarde i bezwzględne zatrzymanie aktualnie wykonywanych podprocesów CLI."""
        if self.current_pipeline_thread and self.current_pipeline_thread.isRunning():
            self.current_pipeline_thread.kill_process()
            self.tab_monitor.append_log("\n[!!!] WYMUSZONO ZATRZYMANIE PROCESÓW PRZEZ UŻYTKOWNIKA [!!!]")
