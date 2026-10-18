# gui/tabs/comparative_tab.py
import os
import re  # ✅ REWIZJA JĄDRA: Dołożenie modułu regex dla bezpiecznego oczyszczania nazw projektów
import config  # ✅ POPRAWKA NAMESPACE: Bezwzględny import monolitu konfiguracji dla metod CoreExplorer [2.4]

# ✅ ROZBUDOWANE IMPORTY WIDŻETÓW DLA PANELU KONTROLNEGO MATRYCY [INDEX]
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, QComboBox, 
                             QPushButton, QTableWidget, QTableWidgetItem, QLineEdit,
                             QGroupBox, QHeaderView, QMessageBox, QDialog, QCheckBox,
                             QRadioButton, QButtonGroup)

from PyQt6.QtCore import Qt, QModelIndex, pyqtSignal

from gui.dialogs.ncbi_search import NcbiSearchDialog  # type: ignore

# ✅ BEZPOŚREDNI IMPORT STAŁYCH ORAZ TOKENU Z JĄDRA KONFIGURACJI KATALOGU GŁÓWNEGO [INDEX]
from config import NCBI_ESEARCH_URL, NCBI_ESUMMARY_URL, NCBI_EUTILS_TEMPLATE_URL, NCBI_API_KEY

# ✅ INTEGRACJA MODUŁÓW RDZENIA OBLICZENIOWEHO JĄDRA [INDEX]
from core.download_manager import BatchDownloadManager  # Pancerne dławienie strumieni sieciowych (Max 3)
from core.matrix_queue_manager import MatrixQueueManager  # Centralny mózg procesowy matrycy (FIFO + DiskGuard)

class ComparativeTab(QWidget):
    """
    Karta 3 [REFORMACJA MATRYCOWA - ZADANIE A]: Matryca Porównawcza N x M.
    Czysty, ergonomiczny panel wejściowy konfiguracji krzyżowej całogenomowych analiz.
    """
    matrix_relay_log_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.main_window = None
        self.compare_thread = None
        self.active_compare_project_dir = None
        
        # 📘 1. PANCERNY MANAGER KOLEJKOWANIA SIECIOWEGO: Throttled Pool (Max 3 parallel) [INDEX]
        self.download_manager = BatchDownloadManager(self)
        self.download_manager.task_started_signal.connect(self._handle_manager_task_started_callback)
        self.download_manager.task_progress_signal.connect(self._handle_manager_task_progress_callback)
        self.download_manager.task_finished_signal.connect(self._handle_manager_task_finished_callback)

        # =====================================================================
        # [Wycinek z konstruktora __init__ w gui/tabs/comparative_tab.py]
        # =====================================================================
        # 📘 2. CENTRALNY MANAGER MULTI-CPU: (FIFO + DiskGuard) [INDEX]
        self.matrix_manager = MatrixQueueManager(self)
        
        # ✅ ULTRA-PŁYNNA MAGISTRALA TELEMETRYCZNA QPROCESS [INDEX]
        self.matrix_manager.matrix_cli_log_signal.connect(self.matrix_relay_log_signal)
        self.matrix_relay_log_signal.connect(self._safe_log_relay)
        
        # ✅ SYGNAŁY ZABEZPIECZAJĄCE INTERFEJS GŁÓWNY (ZARYGLOWANE PRZECIWKO DUBELOM) [INDEX]
        self.matrix_manager.grid_started_signal.connect(self._handle_grid_started)
        self.matrix_manager.grid_completed_signal.connect(self._handle_grid_completed)
        
        # ✅ PANCERNE SPROSTOWANIE POŁĄCZENIA: Sygnał finiszu pary steruje wyłącznie widokiem komórek!
        # Zapobiega to asynchronicznemu wyścigowi i-węzłów w locie masowej serii 2x30! [INDEX]
        self.matrix_manager.grid_task_finished_signal.connect(self._handle_grid_task_finished)
        self.matrix_manager.grid_task_progress_signal.connect(self._handle_grid_task_progress_callback)
        
        # PANCERNY SEJF WĄTKÓW INTERNETOWYCH
        self._active_downloads = {}
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # =====================================================================
        # PANEL GÓRNY: PARAMETRY STRUKTURY PROJEKTU I ŚCIEŻKI WYBORU
        # =====================================================================
        top_box = QGroupBox("📁 PARAMETRY WEJŚCIOWE URUCHOMIENIA MATRYCY")
        top_layout = QVBoxLayout(top_box)
        top_layout.setSpacing(8)

        top_layout.addWidget(QLabel("🧬 Wskaż katalog zbiorczy ze złożonymi genomami (Źródło osi N):"))
        path_layout = QHBoxLayout()
        self.txt_matrix_query_path = QLineEdit()
        self.txt_matrix_query_path.setPlaceholderText("Wskaż folder 03_Assembly lub nadrzędny folder serii...")
        self.txt_matrix_query_path.textChanged.connect(self._handle_path_text_changed)
        
        self.btn_browse_matrix_query = QPushButton("...")
        self.btn_browse_matrix_query.setFixedWidth(40)
        self.btn_browse_matrix_query.clicked.connect(self._handle_browse_matrix_source)
        path_layout.addWidget(self.txt_matrix_query_path)
        path_layout.addWidget(self.btn_browse_matrix_query)
        top_layout.addLayout(path_layout)

        top_layout.addWidget(QLabel("   Własna nazwa projektu porównawczego (Opcjonalna - spacje zostaną zamienione na '_'):"))
        self.txt_custom_comp_name = QLineEdit()
        self.txt_custom_comp_name.setPlaceholderText("Np. Wybuch_Epidemii_Grypa_2026...")
        
        # ✅ ROZWIĄZANIE BEZPIECZEŃSTWA: Twardy limit 30 znaków na poziomie klawiatury operatora! [INDEX]
        self.txt_custom_comp_name.setMaxLength(30)
        
        self.txt_custom_comp_name.textChanged.connect(
            lambda text: self.txt_custom_comp_name.setText(text.replace(" ", "_")) if " " in text else None
        )
        top_layout.addWidget(self.txt_custom_comp_name)

        # =====================================================================
        # ⚙️ REWIZJA: PROTOKOŁY WALIDACJI GATUNKOWEJ I HYBRYDOWEGO POTOKU FIFO [INDEX]
        # =====================================================================
        advanced_box = QGroupBox("⚙️ PROTOKOŁY WALIDACJI GATUNKOWEJ I PARAMETRY FILTRÓW OBLICZENIOWYCH")
        advanced_box_layout = QVBoxLayout(advanced_box)
        advanced_box_layout.setSpacing(10)

        # 1. Brama Taksonomiczna (Zgodność z rygorem: "Sprawdzenie, żeby nie porównywać różnych gatunków") [INDEX]
        self.chk_species_interlock = QCheckBox("Włącz automatyczną bramę taksonomiczną (Species Interlock Guard)")
        self.chk_species_interlock.setChecked(True)  # Domyślnie włączony rygor biologiczny
        self.chk_species_interlock.setToolTip("Blokuje krzyżowanie próbek z referencjami o odmiennych kodach NCBI TaxID.")
        advanced_box_layout.addWidget(self.chk_species_interlock)

        # 2. Pola Filtrów Akceptacji Wyników — ZKORYGOWANA POZYCJA GEOMETRII (Dociśnięte do lewej) [INDEX]
        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)
        
        filter_row.addWidget(QLabel("Minimalne pokrycie genomu referencyjnego (%):"))
        self.txt_min_coverage = QLineEdit("90.0")
        self.txt_min_coverage.setFixedWidth(55)
        self.txt_min_coverage.setAlignment(Qt.AlignmentFlag.AlignRight)
        filter_row.addWidget(self.txt_min_coverage)

        filter_row.addWidget(QLabel("   Minimalna tożsamość nukleotydowa (Identity %):"))
        self.txt_min_identity = QLineEdit("95.0")
        self.txt_min_identity.setFixedWidth(55)
        self.txt_min_identity.setAlignment(Qt.AlignmentFlag.AlignRight)
        filter_row.addWidget(self.txt_min_identity)
        
        # Sprężyna pneumatyczna na samym końcu spycha pustą przestrzeń w prawo, wyrównując pola do lewej! [INDEX]
        filter_row.addStretch()
        advanced_box_layout.addLayout(filter_row)

        # 3. Wybór Silników Obliczeniowych — PRZEJŚCIE NA PANCERNY HYBRYDOWY STANDARD SEKWENCYJNY [INDEX]
        engine_row = QHBoxLayout()
        engine_row.addWidget(QLabel("Aktywne silniki dopasowań w kolejce sekwencyjnej (Rdzeń Miniforge3):"))
        
        # Zamiana radiobuttonów na niezależne checkboxy pozwala operatorowi wybrać OBA programy jednocześnie! [INDEX]
        self.chk_engine_mummer = QCheckBox("MUMmer (Całogenomowy nucmer + DotPlot)")
        self.chk_engine_blast = QCheckBox("BLASTn (Lokalne dopasowania celowane)")
        
        # Domyślnie zaznaczamy oba programy, aby kolejka FIFO wykonała pełną sztafetę analityczną [INDEX]
        self.chk_engine_mummer.setChecked(True)
        self.chk_engine_blast.setChecked(True)

        engine_row.addWidget(self.chk_engine_mummer)
        engine_row.addWidget(self.chk_engine_blast)
        engine_row.addStretch()
        advanced_box_layout.addLayout(engine_row)

        # Wpychamy zaawansowany boks bezpośrednio do kontenera parametrów wejściowych [INDEX]
        top_layout.addWidget(advanced_box)

        layout.addWidget(top_box)

        # =====================================================================
        # PANEL ŚRODKOWY: DWUKOLUMNOWA MATRYCA WYBORU (N x M GRID)
        # =====================================================================
        grid_layout = QHBoxLayout()
        grid_layout.setSpacing(15)

        # LEWA KOLUMNA: Lista Genomów Pacjentów / Query (Oś N)
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("📋 SEKWENCJE BADANE (Oś N):"))
        
        self.table_matrix_query = QTableWidget()
        self.table_matrix_query.setColumnCount(4)
        self.table_matrix_query.setHorizontalHeaderLabels(["Akcja", "ID Projektu / Pacjent", "Nazwa pliku/Szczepu", "Rozmiar (Mbp)"])
        self.table_matrix_query.setStyleSheet("background-color: #1E1E1E; gridline-color: #2C2C2C; color: #FFFFFF; border: 1px solid #2C2C2C;")
        
        self.table_matrix_query.setColumnWidth(0, 75)   
        self.table_matrix_query.setColumnWidth(1, 220)  
        self.table_matrix_query.setColumnWidth(3, 100)  
        self.table_matrix_query.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch) 
        
        left_layout.addWidget(self.table_matrix_query)
        grid_layout.addWidget(left_container, stretch=6)

        # =====================================================================
        # 📘 REWIZJA: STRUKTURA PRZYCISKÓW OSI M (NCBI + BAZA LOKALNA + GENOMU) [2.4]
        # =====================================================================
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        ref_header_layout = QHBoxLayout()
        ref_header_layout.addWidget(QLabel("📘 SEKWENCJE REFERENCYJNE (Oś M):"))
        
        # ✅ SPROSTOWANIE GEOMETRII: Sprężyna pneumatyczna spycha przyciski do prawej krawędzi! [2.4]
        ref_header_layout.addStretch()
        
        # Nowy, jaskrawozielony przycisk menedżera lokalnych wzorców NVMe [2.4]
        self.btn_local_db = QPushButton("Baza lokalna 💾")
        self.btn_local_db.setFixedWidth(115)
        self.btn_local_db.setStyleSheet("background-color: #1E252F; color: #48BB78; font-weight: bold; border: 1px solid #48BB78; padding: 2px; font-size: 11px;")
        self.btn_local_db.clicked.connect(self._open_local_reference_db_dialog)
        ref_header_layout.addWidget(self.btn_local_db)

        # Istniejący przycisk wyszukiwania przez standardowe API NCBI [2.4]
        self.btn_ncbi_search = QPushButton("Szukaj NCBI 🔍")
        self.btn_ncbi_search.setFixedWidth(115)
        self.btn_ncbi_search.setStyleSheet("background-color: #1E2D2F; color: #0099FF; font-weight: bold; border: 1px solid #0099FF; padding: 2px; font-size: 11px;")
        self.btn_ncbi_search.clicked.connect(self._open_ncbi_dialog)
        ref_header_layout.addWidget(self.btn_ncbi_search)
        
        # ✅ NOWOŚĆ [WSTRZYKNIĘCIE V46.5 - NCBI DATASETS GENOME]: Obejście limitów analitycznych API [2.4]
        self.btn_search_genome = QPushButton("Szukaj GENOMU 🧬")
        self.btn_search_genome.setFixedWidth(115)
        self.btn_search_genome.setStyleSheet("background-color: #1E1E1E; color: #E2E8F0; font-weight: bold; border: 1px solid #A0AEC0; padding: 2px; font-size: 11px;")
        self.btn_search_genome.clicked.connect(self._open_ncbi_genome_datasets_browser)
        ref_header_layout.addWidget(self.btn_search_genome)
        
        right_layout.addLayout(ref_header_layout)

        self.table_matrix_reference = QTableWidget()
        self.table_matrix_reference.setColumnCount(4)
        self.table_matrix_reference.setHorizontalHeaderLabels(["Akcja", "Accession ID / Szczep", "Rozmiar (Mbp)", "Status"])
        self.table_matrix_reference.setStyleSheet("background-color: #1E1E1E; gridline-color: #2C2C2C; color: #FFFFFF; border: 1px solid #2C2C2C;")
        
        self.table_matrix_reference.setColumnWidth(0, 75)   
        self.table_matrix_reference.setColumnWidth(2, 100)  
        self.table_matrix_reference.setColumnWidth(3, 120)  
        self.table_matrix_reference.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch) 
        
        right_layout.addWidget(self.table_matrix_reference)
        grid_layout.addWidget(right_container, stretch=6)

        layout.addLayout(grid_layout)

        # =====================================================================
        # PANEL DOLNY: CENTRALNY KLAWISZ URUCHOMIENIA MATRYCOWEGO
        # =====================================================================
        self.btn_run_compare = QPushButton("URUCHOM MAPOWANIE KRZYŻOWE MATRYCY N x M (ETAP 2) 🚀")
        self.btn_run_compare.setStyleSheet("""
            QPushButton { background-color: #004d99; color: #FFFFFF; font-weight: bold; padding: 12px; border: 1px solid #0099FF; border-radius: 4px; font-size: 13px; }
            QPushButton:hover { background-color: #0066cc; }
        """)
        self.btn_run_compare.clicked.connect(self._start_matrix_comparison)
        layout.addWidget(self.btn_run_compare)

        self.table_matrix_query.cellClicked.connect(self._handle_query_cell_clicked)
        # ✅ NOWOŚĆ: Rejestracja kliknięć komórek prawej tabeli Osi M [INDEX]
        self.table_matrix_reference.cellClicked.connect(self._handle_reference_cell_clicked)

    def _safe_log_relay(self, text: str):
        """
        [THE CLI LOG MUTING GUARD V48.7]: Odcina spóźnione logi jądra po finiszu.
        Gwarantuje trwałe zachowanie focusu graficznego na Menedżerze Wyników [2.4].
        """
        # ✅ KROK 14: Jeśli potok masowy został ukończony, odcinamy logi chroniąc przed odskokiem focusu! [2.4]
        if hasattr(self, 'matrix_manager') and getattr(self.matrix_manager, '_matrix_is_done', False):
            return

        if self.main_window and hasattr(self.main_window, 'tab_monitor') and self.main_window.tab_monitor:
            self.main_window.tab_monitor.append_log(text)

    def _handle_browse_matrix_source(self):
        """[THE SECURE MATRIX BROWSER - DYNAMIC FALLBACK]: Wymusza start w podfolderze projects z kaskadą awaryjną [2.4]."""
        from core.explorer import CoreExplorer, ExplorerMode, FilterProfile

        # KROK 1: Dynamiczne wyznaczenie ścieżki głównej przestrzeni roboczej z modułu konfiguratora [2.4]
        base_workspace = getattr(config, 'BASE_DATA_DIR', '')
        start_dir = None

        if base_workspace and os.path.exists(base_workspace):
            # KROK 2: Próba budowy i-węzła celowanego dla podfolderu projektów archiwalnych [2.4]
            potential_projects_path = os.path.join(base_workspace, "projects")
            
            # ✅ KASKADA AWARYJNA: Sprawdzamy czy podfolder istnieje, jeśli nie - otwieramy output_workspace_dir
            if os.path.exists(potential_projects_path) and os.path.isdir(potential_projects_path):
                start_dir = potential_projects_path
            else:
                start_dir = base_workspace

        # Awaryjny bezpiecznik krańcowy w przypadku całkowitego braku struktur roboczych na dysku
        if not start_dir or not os.path.exists(start_dir):
            start_dir = os.path.expanduser("~")

        absolute_start_path = os.path.abspath(start_dir)
        
        # INICJALIZACJA AUTONOMICZNEGO INTERFEJSU JĄDRA (TRYB DIRECTORY_SELECT)
        explorer = CoreExplorer(
            parent=self, 
            mode=ExplorerMode.DIRECTORY_SELECT, 
            filter_profile=FilterProfile.RAW_DATA, 
            start_dir=absolute_start_path
        )
        
        # WYWOŁANIE MODALNE: Korzenie przepinają się w locie RAM z zachowaniem blokad systemowych
        if explorer.exec():
            dir_path = explorer.get_selected_path()
            if dir_path:
                self.txt_matrix_query_path.setText(dir_path)

    def _handle_path_text_changed(self, text: str):
        """Sygnał dynamicznego odświeżania: automatycznie przelicza i zasila tabelę osi N po zmianie ścieżki."""
        self._populate_matrix_query_table(text.strip())

    def _populate_matrix_query_table(self, base_path: str):
        """
        [PANCERNY SENSING MATRYCOWY V2 - FULL GZIP SUPPORT]: Skanuje rekurencyjnie NVMe.
        Akceptuje pliki .gz, przelicza w locie RAM realną wielkość genomu w Mbp ze strumienia
        oraz automatycznie oczyszcza widok z technicznych rozszerzeń archiwalnych [INDEX].
        """
        if not base_path or not os.path.exists(base_path):
            return

        search_target = base_path
        if os.path.exists(os.path.join(base_path, "03_Assembly")):
            search_target = os.path.join(base_path, "03_Assembly")

        detected_isolated_genomes = []
        # ✅ ROZSZERZENIE JĄDRA: Dołączamy pancerne maski skompresowane GZIP [INDEX]
        valid_extensions = (".fasta", ".fa", ".fna", ".fasta.gz", ".fa.gz", ".fna.gz")

        try:
            for root, dirs, files in os.walk(search_target):
                if os.path.abspath(root) == os.path.abspath(search_target):
                    continue
                    
                for file in files:
                    if file.lower().endswith(valid_extensions) and file.lower().startswith("assembly_"):
                        full_fp = os.path.join(root, file)
                        if os.path.isfile(full_fp) and os.path.getsize(full_fp) > 0:
                            project_id = "Nieznany Projekt"
                            current_dir = root
                            for _ in range(5):
                                base_dir_name = os.path.basename(current_dir)
                                if base_dir_name.startswith("PRJ_"):
                                    project_id = base_dir_name
                                    break
                                next_parent = os.path.dirname(current_dir)
                                if next_parent == current_dir: break
                                current_dir = next_parent

                            detected_isolated_genomes.append((file, full_fp, project_id))
        except Exception:
            return

        existing_paths = set()
        for r in range(self.table_matrix_query.rowCount()):
            item = self.table_matrix_query.item(r, 1)
            if item:
                saved_path = item.data(Qt.ItemDataRole.UserRole)
                if saved_path:
                    existing_paths.add(os.path.abspath(str(saved_path)))

        for filename, full_path, project_id in detected_isolated_genomes:
            abs_fp = os.path.abspath(full_path)
            if abs_fp in existing_paths:
                continue

            row_idx = self.table_matrix_query.rowCount()
            self.table_matrix_query.insertRow(row_idx)

            btn_delete = QPushButton("Usuń")
            btn_delete.setStyleSheet("""
                QPushButton { background-color: #500000; color: #FFFFFF; font-weight: bold; border: 1px solid #FF0000; padding: 2px; font-size: 11px; }
                QPushButton:hover { background-color: #880000; }
            """)
            btn_delete.clicked.connect(lambda checked, r_path=full_path: self._handle_delete_row_by_path(r_path))
            
            btn_container = QWidget()
            btn_layout = QHBoxLayout(btn_container)
            btn_layout.addWidget(btn_delete)
            btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            btn_layout.setContentsMargins(4, 2, 4, 2)
            self.table_matrix_query.setCellWidget(row_idx, 0, btn_container)

            item_prj = QTableWidgetItem(project_id)
            item_prj.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item_prj.setData(Qt.ItemDataRole.UserRole, full_path)
            self.table_matrix_query.setItem(row_idx, 1, item_prj)

            # Oczyszczanie nazwy wyświetlanej z technicznego sufixu archiwalnego dla estetyki GUI
            display_name = filename
            if display_name.lower().endswith(".gz"):
                display_name = display_name[:-3]

            item_name = QTableWidgetItem(display_name)
            item_name.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table_matrix_query.setItem(row_idx, 2, item_name)

            # ✅ OPTYMALIZACJA 0 MS: Likwidacja dekompresji w locie wątku głównego GUI [2.4]
            try:
                size_bytes = os.path.getsize(full_path)
                if full_path.lower().endswith(".gz"):
                    size_mbp = (size_bytes * 3.3) / 1000000.0
                else:
                    size_mbp = size_bytes / 1000000.0
                size_str = f"{size_mbp:.2f}"
            except Exception:
                size_str = "0.00"

            item_size = QTableWidgetItem(size_str)
            item_size.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item_size.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table_matrix_query.setItem(row_idx, 3, item_size)

    def _handle_delete_row_by_path(self, target_path: str):
        """[PANCERNY DESTRUKTOR WIERSZA]: Kasuje wiersz z tabeli osi N po akceptacji."""
        target_row = -1
        for row in range(self.table_matrix_query.rowCount()):
            item = self.table_matrix_query.item(row, 1)
            if item and item.data(Qt.ItemDataRole.UserRole) == target_path:
                target_row = row
                break

        if target_row == -1: return
        filename = self.table_matrix_query.item(target_row, 2).text()

        reply = QMessageBox.question(
            self, "Potwierdzenie usunięcia",
            f"Czy na pewno usunąć genom szczepu:\n\"{filename}\"\nz koszyka aktywnej matrycy porównawczej?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.table_matrix_query.removeRow(target_row)

    def _get_verified_local_reference_path(self, accession_id: str, library_dir: str) -> str:
        """
        [THE PATH INTERLOCK GUARD - V16]: Rozbija Accession, odcina kropkę wersji
        i sprawdza kompletną tablicę dopuszczalnych masek rozszerzeń na dysku NVMe [INDEX].
        """
        if not accession_id or not library_dir or not os.path.exists(library_dir):
            return ""
            
        # Sterylizacja identyfikatora przed kropką wersji (np. NC_026011.1 -> NC_026011) [INDEX]
        clean_acc = accession_id.split(".")[0].strip() if "." in accession_id else accession_id.strip()
        
        # Uniwersalna tablica bioinformatycznych masek rozszerzeń plików [INDEX]
        possible_extensions = [".fasta.gz", ".fasta", ".fa.gz", ".fa", ".fna.gz", ".fna"]
        
        for ext in possible_extensions:
            potential_path = os.path.join(library_dir, f"{clean_acc}{ext}")
            if os.path.exists(potential_path) and os.path.getsize(potential_path) > 0:
                return os.path.abspath(potential_path) # Zwraca pierwszą istniejącą ścieżkę fizyczną [INDEX]
        return ""

    def _open_ncbi_dialog(self):
        """
        [THROTTLED BATCH NETWORK ENGINE V4 - AMENDMENT V16]: Pobiera paczkę danych online.
        Implementuje multi-sprawdzian masek, odcinając ponowne ściąganie i nadpisywanie zasobów [INDEX].
        """
        from gui.dialogs.ncbi_search import NcbiSearchDialog
        from PyQt6.QtGui import QColor
        import config
        
        dialog = NcbiSearchDialog(self)
        if dialog.exec() != NcbiSearchDialog.DialogCode.Accepted:
            return

        genomes_list = getattr(dialog, 'selected_genomes_list', [])
        if not genomes_list:
            return

        target_library_dir = None
        current_api_key = ""
        
        if self.main_window and hasattr(self.main_window, 'ws'):
            try:
                current_cfg = self.main_window.ws._read_config_from_disk()
                if "reference_library_dir" in current_cfg:
                    target_library_dir = current_cfg.get("reference_library_dir", "").strip()
                elif "references_library_dir" in current_cfg:
                    target_library_dir = current_cfg.get("references_library_dir", "").strip()
                current_api_key = current_cfg.get("ncbi_api_key", "").strip()
            except Exception: pass

        if not target_library_dir and self.main_window and hasattr(self.main_window, 'ws'):
            target_library_dir = getattr(self.main_window.ws, 'reference_library_dir', None)

        if not target_library_dir:
            target_library_dir = "/home/ionadmin/kombajn_workspace/references_library"

        absolute_library_path = os.path.abspath(target_library_dir)
        if not current_api_key:
            current_api_key = getattr(config, 'NCBI_API_KEY', "").strip()

        download_batch = []

        for data in genomes_list:
            if "accession" not in data: continue

            raw_accession = data["accession"].strip()
            accession = raw_accession.split(".")[0].strip() if "." in raw_accession else raw_accession
            organism_name = data.get("name", "Unknown Organism").strip()
            display_label = f"{accession} - {organism_name}"
            
            # Domyślny docelowy i-węzeł zapisu dla nowych plików pobieranych z sieci [INDEX]
            expected_fasta_file = os.path.join(absolute_library_path, f"{accession}.fasta")

            is_duplicate = False
            for r in range(self.table_matrix_reference.rowCount()):
                item = self.table_matrix_reference.item(r, 1)
                if item and item.text().startswith(accession):
                    is_duplicate = True
                    break
            if is_duplicate: continue 

            row_idx = self.table_matrix_reference.rowCount()
            self.table_matrix_reference.insertRow(row_idx)

            btn_del = QPushButton("Usuń")
            btn_del.setStyleSheet("""
                QPushButton { background-color: #500000; color: #FFFFFF; font-weight: bold; border: 1px solid #FF0000; padding: 2px; font-size: 11px; }
                QPushButton:hover { background-color: #880000; }
            """)
            btn_del.clicked.connect(self._handle_delete_reference_row_dynamic)
            
            btn_container = QWidget()
            btn_layout = QHBoxLayout(btn_container)
            btn_layout.addWidget(btn_del)
            btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            btn_layout.setContentsMargins(4, 2, 4, 2)
            self.table_matrix_reference.setCellWidget(row_idx, 0, btn_container)

            # ✅ ŚRUBA 2: Odpytujemy pancerny multi-sprawdzian masek przed podjęciem decyzji o pobieraniu! [INDEX]
            verified_local_path = self._get_verified_local_reference_path(accession, absolute_library_path)

            item_name = QTableWidgetItem(display_label)
            item_name.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            
            try:
                raw_bp = float(data.get("size_bp", 0)) if data.get("size_bp") else 0.0
                size_mbp = raw_bp / 1000000.0 if raw_bp > 0 else 0.0
                size_str = f"{size_mbp:.2f}" if size_mbp > 0 else "N/A"
            except Exception: size_str = "N/A"

            item_size = QTableWidgetItem(size_str)
            item_size.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item_size.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table_matrix_reference.setItem(row_idx, 2, item_size)

            item_status = QTableWidgetItem()
            item_status.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            if verified_local_path:
                # 🟢 Plik autentycznie istnieje pod jedną z masek na dysku NVMe! Blokujemy sieć! [INDEX]
                item_name.setData(Qt.ItemDataRole.UserRole, verified_local_path)
                item_status.setText("🟢 GOTOWY")
                item_status.setBackground(QColor("#003311"))
                item_status.setForeground(QColor("#00FF66"))
            else:
                # 🔵 Brak pliku na dysku pod jakąkolwiek maską - zakleszczamy zadanie w kolejce sieciowej [INDEX]
                item_name.setData(Qt.ItemDataRole.UserRole, expected_fasta_file) # Fallback ścieżki surowej
                item_status.setText("🔵 W KOLEJCE (Oczekuje)")
                item_status.setBackground(QColor("#1A2634"))
                item_status.setForeground(QColor("#0099FF"))
                
                ncbi_eutils_url = config.NCBI_EUTILS_TEMPLATE_URL.format(accession)
                if current_api_key:
                    ncbi_eutils_url = f"{ncbi_eutils_url}&api_key={current_api_key}"

                append_log_method = None
                if self.main_window and hasattr(self.main_window, 'tab_monitor'):
                    append_log_method = self.main_window.tab_monitor.append_log
                    append_log_method(f"[NCBI BATCH QUEUE]: Dodano do koszyka seryjnego: {accession}")

                task_data = {
                    "url": ncbi_eutils_url,
                    "target": expected_fasta_file,
                    "monitor_log": append_log_method
                }
                download_batch.append(task_data)

            self.table_matrix_reference.setItem(row_idx, 1, item_name)
            self.table_matrix_reference.setItem(row_idx, 3, item_status)

        if download_batch:
            if self.main_window and hasattr(self.main_window, 'tab_monitor'):
                self.main_window.tab_monitor.append_log(
                    f"\n[MANAGER SIECIOWY]: Przekazano paczkę {len(download_batch)} genomów do Throttled Pool..."
                )
            self.download_manager.add_batch_to_queue(download_batch)

    def _open_local_reference_db_dialog(self):
        """
        [OFFLINE COUPLING - AUTENTIC PATH LOCK V16]: Wywołuje edytor bazy lokalnej,
        wyciąga oryginalną nazwę pliku z krotki i rygruje bezbłędne ścieżki .gz w UserRole [INDEX].
        """
        from PyQt6.QtGui import QColor
        import config
        
        target_library_dir = None
        if self.main_window and hasattr(self.main_window, 'ws'):
            try:
                current_cfg = self.main_window.ws._read_config_from_disk()
                if "reference_library_dir" in current_cfg:
                    target_library_dir = current_cfg.get("reference_library_dir", "").strip()
                elif "references_library_dir" in current_cfg:
                    target_library_dir = current_cfg.get("references_library_dir", "").strip()
            except Exception: pass

        if not target_library_dir:
            target_library_dir = getattr(config, 'DEFAULT_REFERENCE_LIBRARY_DIR', "/home/ionadmin/kombajn_workspace/references_library")

        absolute_library_path = os.path.abspath(target_library_dir)

        dialog = LocalReferenceDbDialog(absolute_library_path, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        new_references = dialog.selected_references
        if not new_references:
            return

        # Seryjne masowe wstrzykiwanie pozycji do siatki widoku Osi M [INDEX]
        for accession, full_name, size_str, raw_filename in new_references:
            display_label = f"{accession} - {full_name}"

            is_duplicate = False
            for r in range(self.table_matrix_reference.rowCount()):
                item = self.table_matrix_reference.item(r, 1)
                if item and item.text().startswith(accession):
                    is_duplicate = True
                    break
            if is_duplicate:
                continue

            row_idx = self.table_matrix_reference.rowCount()
            self.table_matrix_reference.insertRow(row_idx)

            btn_del = QPushButton("Usuń")
            btn_del.setStyleSheet("""
                QPushButton { background-color: #500000; color: #FFFFFF; font-weight: bold; border: 1px solid #FF0000; padding: 2px; font-size: 11px; }
                QPushButton:hover { background-color: #880000; }
            """)
            btn_del.clicked.connect(self._handle_delete_reference_row_dynamic)
            
            btn_container = QWidget()
            btn_layout = QHBoxLayout(btn_container)
            btn_layout.addWidget(btn_del)
            btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            btn_layout.setContentsMargins(4, 2, 4, 2)
            self.table_matrix_reference.setCellWidget(row_idx, 0, btn_container)

            # ✅ PANCERNY STANDARD REALIZMU: Brak zgadywania! Składamy ścieżkę z oryginalnej nazwy pliku na NVMe! [INDEX]
            real_ref_file_path = os.path.join(absolute_library_path, raw_filename)

            item_name = QTableWidgetItem(display_label)
            item_name.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            # Rygrujemy prawdziwy, dyskowy i-węzeł do UserRole komórki [INDEX]
            item_name.setData(Qt.ItemDataRole.UserRole, real_ref_file_path)
            self.table_matrix_reference.setItem(row_idx, 1, item_name)

            item_size = QTableWidgetItem(size_str)
            item_size.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item_size.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table_matrix_reference.setItem(row_idx, 2, item_size)

            item_status = QTableWidgetItem("🟢 GOTOWY")
            item_status.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_status.setBackground(QColor("#003311"))
            item_status.setForeground(QColor("#00FF66"))
            self.table_matrix_reference.setItem(row_idx, 3, item_status)

    def _handle_delete_reference_row_dynamic(self):
        """[DYNAMICZNY DESTRUKTOR]: Wykrywa dokładną pozycję przycisku Usuń w locie kliknięcia [INDEX]."""
        button = self.sender()
        if not button: return
        point = button.parent().pos()
        index = self.table_matrix_reference.indexAt(point)
        target_row = index.row()

        if target_row < 0 or target_row >= self.table_matrix_reference.rowCount(): return
        ref_label = self.table_matrix_reference.item(target_row, 1).text()

        reply = QMessageBox.question(
            self, "Potwierdzenie usunięcia",
            f"Czy na pewno usunąć genom referencyjny:\n\"{ref_label}\"\nz koszyka aktywnej matrycy?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.table_matrix_reference.removeRow(target_row)

    def _handle_download_finished_callback_dynamic(self, success: bool, message: str, fasta_path: str):
        """
        [DYNAMICZNY ŁĄCZNIK STATUSÓW - BEZBŁĘDNY PARSER V3]: Pobiera pierwszy element 
        z listy rozbicia tekstowego, zapobiegając IndexError i stabilizując serię Batch [INDEX].
        """
        from PyQt6.QtGui import QColor
        target_row = -1
        target_filename = os.path.basename(fasta_path).strip()
        
        for r in range(self.table_matrix_reference.rowCount()):
            item_name = self.table_matrix_reference.item(r, 1)
            if item_name and item_name.text():
                # ✅ PANCERNE ROZBICIE SPLITU: Zapobiega IndexError przy braku separatora " - " [INDEX]
                parts = item_name.text().split(" - ")
                acc_id = parts[0].strip() if parts else "N/A"
                
                if acc_id != "N/A" and acc_id in target_filename:
                    target_row = r
                    break

        if target_row == -1: 
            return
            
        item_status = self.table_matrix_reference.item(target_row, 3)
        if not item_status: 
            return

        if success:
            item_status.setText("🟢 GOTOWY")
            item_status.setBackground(QColor("#003311"))
            item_status.setForeground(QColor("#00FF66"))
        else:
            item_status.setText("🔴 BŁĄD")
            item_status.setBackground(QColor("#4d0000"))
            item_status.setForeground(QColor("#FF3333"))

        if hasattr(self, '_active_downloads') and fasta_path in self._active_downloads:
            worker = self._active_downloads[fasta_path]
            if worker:
                worker.deleteLater()

    def _handle_grid_task_finished(self, success: bool, pair_key: str, eval_status: str):
        """[GRID CALLBACK - FINAL FAKTY V51.3]: Pełna izolacja koszyka Osi M przed wyciekiem danych [2.4]."""
        from PyQt6.QtWidgets import QMessageBox
        
        # 🕒 KROK 1: Bezwarunkowa obsługa awaryjnego rygla i-węzła przestrzeni dyskowej DiskGuard
        if pair_key == "GLOBAL_PROJ" and eval_status.startswith("ABORT:"):
            self._set_controls_enabled_state(True)
            self.btn_run_compare.setEnabled(True)
            self.btn_run_compare.setText("URUCHOM MAPOWANIE KRZYŻOWE MATRYCY N x M (ETAP 2) 🚀")
            self.btn_run_compare.setStyleSheet("")
            QMessageBox.critical(self, "Błąd krytyczny DiskGuard", f"🚨 ROZRUCH ANULOWANY!\n\n{eval_status}")
            return

        return

    def _handle_manager_task_started_callback(self, target_path: str):
        """
        [POOL CALLBACK - STAN ODPALONY]: Wywoływany, gdy zadanie opuszcza kolejkę FIFO
        i przechodzi w tryb aktywnego pobierania. Zmienia kolor na dynamiczny żółty [INDEX].
        """
        from PyQt6.QtGui import QColor
        target_row = -1
        target_filename = os.path.basename(target_path).strip()
        
        # Namierzamy wiersz w tabeli Osi M po Accession ID zakodowanym w ścieżce
        for r in range(self.table_matrix_reference.rowCount()):
            item_name = self.table_matrix_reference.item(r, 1)
            if item_name and item_name.text():
                acc_id = item_name.text().split(" - ")[0].strip()
                if acc_id and acc_id in target_filename:
                    target_row = r
                    break

        if target_row == -1:
            return

        item_status = self.table_matrix_reference.item(target_row, 3)
        if item_status:
            item_status.setText("🟡 POBIERANIE...")
            item_status.setBackground(QColor("#332200"))
            item_status.setForeground(QColor("#ECC94B"))

    def _handle_manager_task_progress_callback(self, percent: int, target_path: str):
        """
        [POOL CALLBACK - STAN LICZNIKA]: Dynamicznie aktualizuje licznik procentowy
        w locie RAM wyłącznie dla wątków znajdujących się w 3 aktywnych slotach [INDEX].
        """
        target_row = -1
        target_filename = os.path.basename(target_path).strip()
        
        for r in range(self.table_matrix_reference.rowCount()):
            item_name = self.table_matrix_reference.item(r, 1)
            if item_name and item_name.text():
                acc_id = item_name.text().split(" - ")[0].strip()
                if acc_id and acc_id in target_filename:
                    target_row = r
                    break

        if target_row == -1:
            return

        item_status = self.table_matrix_reference.item(target_row, 3)
        if item_status and item_status.text().startswith("🟡"):
            item_status.setText(f"🟡 POBIERANIE {percent}%")

    def _handle_manager_task_finished_callback(self, success: bool, final_path_or_msg: str, original_target_path: str):
        """
        [POOL CALLBACK - STAN KOŃCOWY]: Przechwytuje finał operacji dyskowej.
        Zmienia barwę na pancerną zieleń sukcesu lub czerwień awarii sieciowej [INDEX].
        """
        from PyQt6.QtGui import QColor
        target_row = -1
        target_filename = os.path.basename(original_target_path).strip()
        
        for r in range(self.table_matrix_reference.rowCount()):
            item_name = self.table_matrix_reference.item(r, 1)
            if item_name and item_name.text():
                acc_id = item_name.text().split(" - ")[0].strip()
                if acc_id and acc_id in target_filename:
                    target_row = r
                    break

        if target_row == -1:
            return

        item_status = self.table_matrix_reference.item(target_row, 3)
        if not item_status:
            return

        if success:
            item_status.setText("🟢 GOTOWY")
            item_status.setBackground(QColor("#003311"))
            item_status.setForeground(QColor("#00FF66"))
            
            # Wstrzykujemy zaktualizowaną przez GZIP ścieżkę .gz bezpośrednio do logów Monitora
            if self.main_window and hasattr(self.main_window, 'tab_monitor'):
                self.main_window.tab_monitor.append_log(
                    f"[NCBI SUCCESS]: Genom referencyjny zaryglowany pomyślnie w .gz:\n -> {final_path_or_msg}"
                )
        else:
            item_status.setText("🔴 BŁĄD SIECOWY")
            item_status.setBackground(QColor("#4d0000"))
            item_status.setForeground(QColor("#FF3333"))
            
            if self.main_window and hasattr(self.main_window, 'tab_monitor'):
                self.main_window.tab_monitor.append_log(
                    f"[NCBI KATASTROFA]: Awaria pobierania dla ścieżki: {original_target_path}\n -> Powód: {final_path_or_msg}"
                )

    def _handle_download_progress_callback_dynamic(self, percent: int, fasta_path: str):
        """[PANCERNY LOKALIZATOR POSTĘPU]: Dynamicznie aktualizuje licznik procentowy w locie RAM [INDEX]."""
        target_row = -1
        for r in range(self.table_matrix_reference.rowCount()):
            item_name = self.table_matrix_reference.item(r, 1)
            if item_name:
                acc_id = item_name.text().split(" - ")[0].strip()
                if acc_id in fasta_path:
                    target_row = r
                    break

        if target_row == -1: return
        item_status = self.table_matrix_reference.item(target_row, 3)
        if item_status and item_status.text().startswith("🟡"):
            item_status.setText(f"🟡 POBIERANIE {percent}%")

    def _handle_grid_started(self, project_id: str):
        """
        [GRID CALLBACK - START]: Reaguje na pomyślne zaryglowanie manifestu JSON.
        Wprowadza informację o oficjalnym rozruchu super-projektu do Monitora [INDEX].
        """
        if self.main_window and hasattr(self.main_window, 'tab_monitor'):
            self.main_window.tab_monitor.append_log(
                f"\n[MATRYCA RUNTIME]: Super-projekt {project_id} przeszedł bramkę przestrzenną.\n"
                f" -> Rozpoczynam asynchroniczne przetwarzanie kolejki FIFO..."
            )

    def _handle_grid_task_progress_callback(self, pair_key: str, percent: int):
        """[GRID CALLBACK - PROGRESS V51.3]: Pełna izolacja Osi M od asynchronicznego szumu runtime [2.4]."""
        # 🕒 KROK 1: Bezwarunkowa i natychmiastowa amputacja spóźnionych sygnałów-duchów po finiszu serii
        if hasattr(self, 'matrix_manager') and getattr(self.matrix_manager, '_matrix_is_done', False):
            return

        # 📊 KROK 2: Przekierowanie globalnej telemetrii matrycy na pasek MonitorTab
        if pair_key == "GLOBAL_MATRIX":
            if self.main_window and hasattr(self.main_window, 'tab_monitor') and self.main_window.tab_monitor:
                self.main_window.tab_monitor.update_sample_progress(percent, "Przetwarzanie matrycy całogenomowej...")
            return

        return

    def _handle_grid_task_started(self, pair_key: str, phase_label: str):
        """
        [GRID CALLBACK - STERILIZED INTERFACE]: Pasywne reagowanie na błędy krytyczne przestrzeni dyskowej.
        Całkowite odcięcie tabeli Osi M od zaśmiecania komunikatami operacyjnymi runtime [INDEX].
        """
        # Zachowujemy wyłącznie nadrzędny, panoramiczny komunikat o zatrzymaniu kolejki z DiskGuarda
        if pair_key == "GLOBAL_QUEUE" and phase_label.startswith("PAUSED:"):
            QMessageBox.critical(self, "Krytyczny brak przestrzeni", f"⚠️ POTOK WSTRZYMANY!\n\n{phase_label}")

    def _set_controls_enabled_state(self, enabled: bool):
        """Pomocniczy uniwersalny przełącznik blokad kontrolek wejściowych GUI [INDEX]."""
        self.txt_matrix_query_path.setEnabled(enabled)
        self.btn_browse_matrix_query.setEnabled(enabled)
        self.txt_custom_comp_name.setEnabled(enabled)
        self.btn_local_db.setEnabled(enabled)
        self.btn_ncbi_search.setEnabled(enabled)
        self.chk_species_interlock.setEnabled(enabled)
        self.txt_min_coverage.setEnabled(enabled)
        self.txt_min_identity.setEnabled(enabled)
        self.chk_engine_mummer.setEnabled(enabled)
        self.chk_engine_blast.setEnabled(enabled)

    def _handle_query_cell_clicked(self, row, column):
        """[PANCERNY PODGLĄD ŚCIEŻKI]: Wybudza panoramiczne okno modalne 1100 px."""
        if column != 1: return
        item = self.table_matrix_query.item(row, column)
        if not item: return
        full_fasta_path = item.data(Qt.ItemDataRole.UserRole)
        if not full_fasta_path: return

        dialog = QDialog(self)
        dialog.setWindowTitle("Pełna archiwalna ścieżka genomu badanego")
        dialog.setMinimumSize(1100, 150)
        dialog.setStyleSheet("background-color: #1A1A1A; border: 1px solid #00FF66; border-radius: 4px;")
        
        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.setContentsMargins(20, 20, 20, 20)
        dialog_layout.setSpacing(15)
        
        lbl_path = QLabel(str(full_fasta_path))
        lbl_path.setWordWrap(True)
        lbl_path.setStyleSheet("color: #00FF66; font-size: 13px; font-family: 'DejaVu Sans Mono', monospace; font-weight: bold;")
        lbl_path.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dialog_layout.addWidget(lbl_path)
        
        btn_close = QPushButton("Zamknij")
        btn_close.setFixedWidth(100)
        btn_close.setStyleSheet("""
            QPushButton { background-color: #2D2D2D; color: #FFFFFF; font-weight: bold; border: 1px solid #3A3A3A; padding: 5px; }
            QPushButton:hover { background-color: #3D3D3D; border: 1px solid #00FF66; }
        """)
        btn_close.clicked.connect(dialog.accept)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        btn_layout.addStretch()
        dialog_layout.addLayout(btn_layout)
        dialog.exec()

    def _handle_reference_cell_clicked(self, row: int, column: int):
        """
        [PANCERNY PODGLĄD REFERENCJI]: Przechwytuje kliknięcie w kolumnie Accession ID (Oś M).
        Wybudza panoramiczne okno modalne, pokazując pełną, nieuciętą nazwę szczepu NCBI [INDEX].
        """
        # Sprawdzamy, czy operator kliknął w kolumnę numer 1 (Accession ID / Szczep)
        if column != 1: 
            return
            
        item = self.table_matrix_reference.item(row, column)
        if not item or not item.text(): 
            return
            
        full_reference_label = item.text().strip()

        # Budowa panoramicznego okna modalnego identycznego z lewym panelem
        dialog = QDialog(self)
        dialog.setWindowTitle("Pełna archiwalna nazwa genomu referencyjnego NCBI")
        dialog.setMinimumSize(1100, 150)
        dialog.setStyleSheet("background-color: #1A1A1A; border: 1px solid #0099FF; border-radius: 4px;")
        
        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.setContentsMargins(20, 20, 20, 20)
        dialog_layout.setSpacing(15)
        
        lbl_path = QLabel(str(full_reference_label))
        lbl_path.setWordWrap(True)
        lbl_path.setStyleSheet("color: #0099FF; font-size: 13px; font-family: 'DejaVu Sans Mono', monospace; font-weight: bold;")
        lbl_path.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dialog_layout.addWidget(lbl_path)
        
        btn_close = QPushButton("Zamknij")
        btn_close.setFixedWidth(100)
        btn_close.setStyleSheet("""
            QPushButton { background-color: #2D2D2D; color: #FFFFFF; font-weight: bold; border: 1px solid #3A3A3A; padding: 5px; }
            QPushButton:hover { background-color: #3D3D3D; border: 1px solid #0099FF; }
        """)
        btn_close.clicked.connect(dialog.accept)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        btn_layout.addStretch()
        dialog_layout.addLayout(btn_layout)
        
        dialog.exec()

    def _start_matrix_comparison(self):
        """
        [ACTIVE HYBRID MATRIX DISPATCHER V51.0]: Pobiera parametry z GUI.
        Uwalnia 78 wątków oraz stosuje rygor izolacji peryferyjnej z HistoryTab [2.4].
        """
        import config
        import os
        import re

        # 1. POBRANIE I AGREGACJA WEKTORA OSI N (Lewa tabela)
        query_tasks_batch = []
        for row in range(self.table_matrix_query.rowCount()):
            item_prj = self.table_matrix_query.item(row, 1)
            item_file = self.table_matrix_query.item(row, 2)
            if item_prj and item_file:
                path_in_ram = item_prj.data(Qt.ItemDataRole.UserRole)
                if path_in_ram:
                    query_tasks_batch.append((
                        item_file.text().strip(),
                        str(path_in_ram),
                        item_prj.text().strip()
                    ))
        if not query_tasks_batch:
            QMessageBox.warning(self, "Błąd rozruchu", "Koszyk sekwencji badanych (Oś N) jest pusty!"); return
        # Dynamiczny odczyt aktywnego katalogu biblioteki z dysku [INDEX]
        try:
            current_cfg = self.main_window.ws._read_config_from_disk() if self.main_window and hasattr(self.main_window, 'ws') else {}
            if "reference_library_dir" in current_cfg:
                lib_dir = current_cfg.get("reference_library_dir", "").strip()
            else:
                lib_dir = current_cfg.get("references_library_dir", "").strip()
        except Exception:
            lib_dir = ""
            
        if not lib_dir:
            lib_dir = "/home/ionadmin/kombajn_workspace/references_library"
        absolute_library_path = os.path.abspath(lib_dir)

        # 2. POBRANIE I AGREGACJA WEKTORA OSI M (Prawa tabela)
        reference_tasks_batch = []
        for row in range(self.table_matrix_reference.rowCount()):
            item_acc_name = self.table_matrix_reference.item(row, 1)
            item_size = self.table_matrix_reference.item(row, 2)
            item_status = self.table_matrix_reference.item(row, 3)
            if item_acc_name and item_size and item_status:
                raw_text = item_acc_name.text().strip()
                parts = raw_text.split(" - ", maxsplit=1)
                raw_acc = parts[0].strip() if parts else "N/A"
                accession = raw_acc.split(".")[0].strip() if "." in raw_acc else raw_acc
                full_name = parts[1].strip() if len(parts) > 1 else "Unknown Organism"
                
                real_ref_path_in_ram = item_acc_name.data(Qt.ItemDataRole.UserRole)
                if not real_ref_path_in_ram or not os.path.exists(str(real_ref_path_in_ram)):
                    verified_path = self._get_verified_local_reference_path(accession, absolute_library_path)
                    if verified_path: real_ref_path_in_ram = verified_path
                    else: real_ref_path_in_ram = os.path.join(absolute_library_path, f"{accession}.fasta")

                reference_tasks_batch.append((accession, full_name, item_size.text().strip(), str(real_ref_path_in_ram)))

        if not reference_tasks_batch:
            QMessageBox.warning(self, "Błąd rozruchu", "Koszyk sekwencji referencyjnych (Oś M) jest pusty!"); return

        # 3. ODCZYT PARAMETRÓW FILTRÓW I SILNIKÓW Z KONTROLEK
        run_mummer = self.chk_engine_mummer.isChecked()
        run_blast = self.chk_engine_blast.isChecked()
        species_interlock = self.chk_species_interlock.isChecked()
        if not run_mummer and not run_blast:
            QMessageBox.warning(self, "Błąd rozruchu", "Musisz zaznaczyć przynajmniej jeden silnik!"); return
        try:
            min_cov = float(self.txt_min_coverage.text().strip())
            min_id = float(self.txt_min_identity.text().strip())
        except ValueError:
            QMessageBox.critical(self, "Błąd wartości", "Progi muszą być liczbami zmiennoprzecinkowymi!"); return

        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        custom_suffix = self.txt_custom_comp_name.text().strip()[:30]
        custom_suffix_clean = re.sub(r'[^a-zA-Z0-9_]', '_', custom_suffix) if custom_suffix else ""
        generated_project_id = f"COMP_{timestamp}_{custom_suffix_clean}" if custom_suffix_clean else f"COMP_{timestamp}"

        allocated_threads = 76  
        try:
            current_cfg = self.main_window.ws._read_config_from_disk() if self.main_window and hasattr(self.main_window, 'ws') else {}
            allocated_threads = int(current_cfg.get("threads_limit", 76))
            base_workspace_dir = current_cfg.get("output_workspace_dir", "/home/ionadmin/kombajn_workspace").strip()
        except Exception:
            base_workspace_dir = "/home/ionadmin/kombajn_workspace"
        base_workspace_dir = os.path.join(base_workspace_dir, "projects")

        # 🕒 KROK 1: Blokada kontrolek lokalnych i-węzłów na Karcie 3 przed ucieczką widoku
        self._set_controls_enabled_state(False)
        self.btn_run_compare.setEnabled(False)
        
        # 🚨 KROK 2: MASKOWANIE WYJĄTKU RYGLA S-1.5 - Unieruchamiamy peryferia, omijając Karta ID 3!
        if self.main_window and hasattr(self.main_window, '_set_peripheral_tabs_enabled'):
            self.main_window._set_peripheral_tabs_enabled(False, exclude_idx=3)

        # 🚨 KROK 3: PRE-FLIGHTOWY SKOK UCIEKIERA - Wymuszamy indeks 0 i opróżniamy bufor PRZED dławieniem I/O! [2.4]
        if self.main_window and hasattr(self.main_window, 'tabs'):
            from PyQt6.QtWidgets import QApplication
            self.main_window.tabs.setCurrentIndex(0)  # Natychmiastowy przeskok na MonitorTab
            self.main_window.tab_monitor.repaint()   # Sterylne przerysowanie pikseli monitora
            QApplication.processEvents()              # Wypchnięcie geometrii przed uderzeniem OpenMP [2.4]

        # 🚨 KROK 4: ROZRUCH BACKENDU - 78 wątków stacji XEON rusza na zwalidowanym i wyrenderowanym Monitorze!
        self.matrix_manager.initialize_matrix_project(
            project_id=generated_project_id, base_workspace=base_workspace_dir,
            query_tasks=query_tasks_batch, reference_tasks=reference_tasks_batch,
            min_cov=min_cov, min_id=min_id, max_threads=allocated_threads,
            run_mummer=run_mummer, run_blast=run_blast, enable_species_interlock=species_interlock
        )

    def _handle_grid_completed(self, project_id: str, tsv_report_path: str):
        """[GRID CALLBACK - FINAL SUCCESS V51.0]: Adaptacja manualnego standardu Historii bez skoków automatycznych [2.4]."""
        from PyQt6.QtWidgets import QApplication, QMessageBox
        import os

        # 🕒 KROK 1: Bezwarunkowy zrzut logu końcowego na monitorze operatora
        self.main_window.tab_monitor.append_log(f"\n[MATRYCA COMPLETED]: Wszystkie pary zwalidowane.\n -> Raport zbiorczy: {tsv_report_path}")

        # 🕒 KROK 2: Pełne przywrócenie sterowności i odblokowanie paska peryferii przez okno główne
        self.main_window._set_peripheral_tabs_enabled(True)

        # 🕒 KROK 3: Pętla interlocku dyskowego - system czeka w RAM na glejt synchronizacji os.fsync [2.4]
        while not getattr(self.matrix_manager, '_matrix_is_done', False):
            QApplication.processEvents()

        # 🕒 KROK 4: SPROSTOWANIE CHRONOLOGII SZEFA - Przywrócenie klikalności kontrolek na Karcie 3 [2.4]
        self.main_window.tabs.setCurrentIndex(3)
        self._set_controls_enabled_state(True)
        self.btn_run_compare.setEnabled(True)
        self.repaint()

        # KROK 5: Sterylna bramka decyzyjna na gruncie aktywnej Karty 3 [2.4]
        reply = QMessageBox.question(
            self, "Sukces Matrycy",
            "Analiza zakończona pomyślnie!\nCzy chcesz przejść teraz do widoku Menedżera Wyników?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Wykonujemy bezpieczne ładowanie i kontenerowy skok na Kartę 4
            project_path = self.matrix_manager.output_project_dir
            self.main_window.tab_view_manager.load_completed_project(project_path)
            self.main_window.tab_view_manager.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.main_window.tabs.setCurrentIndex(4)
            self.main_window.tab_view_manager.setFocus()
            self.main_window.tab_view_manager.repaint()

    def _open_ncbi_genome_datasets_browser(self):
        """
        [THE REFERENCE DOWNLOAD INTERLOCK V46.5]: Wywołuje dedykowane okno pobierania genomów.
        Wymusza absolutny, nienaruszalny adres URL portalu NCBI Datasets Genome w locie RAM.
        """
        import config
        from core.chromium_engine import ChromiumBrowserWindow
        
        # Pobranie nienaruszalnej ścieżki magazynu referencji z globalnej bazy config.py
        reference_dir = getattr(config, 'LIBRARY_DIR', '')
        
        if not reference_dir:
            if self.main_window and hasattr(self.main_window, 'tab_monitor'):
                self.main_window.tab_monitor.append_log("[BŁĄD REFERENCJI]: Brak zdefiniowanego katalogu biblioteki referencyjnej!")
            return

        # Pancerne wstrzyknięcie poprawnego, twardego adresu bezpośrednio do konstruktora okna
        self.ncbi_datasets_browser = ChromiumBrowserWindow(
            "https://www.ncbi.nlm.nih.gov/datasets/genome/", 
            reference_dir, 
            parent=self.main_window
        )
        
        if self.main_window and hasattr(self.main_window, 'tab_monitor') and self.main_window.tab_monitor:
            self.main_window.tab_monitor.append_log(
                f"[SYSTEM]: Uruchomienie portalu NCBI Datasets Genome pod prawidłowym adresem. Cel: {reference_dir}"
            )

class LocalReferenceDbDialog(QDialog):
    """
    [OFFLINE REFERENCE MANAGER - V1.0]: Autonomiczne okno modalne o szerokości 1150 px [INDEX].
    Skanuje archiwum FASTA/GZIP, parsuje nagłówki w RAM i implementuje wyszukiwanie w locie.
    """
    def __init__(self, library_dir: str, parent=None):
        super().__init__(parent)
        self.library_dir = library_dir
        self.selected_references = [] # Lista krotek wyjściowych (accession, full_name, file_size_mbp)
        
        self.setWindowTitle("Lokalne Repozytorium Genomów Referencyjnych NVMe Kingston")
        self.setMinimumSize(1150, 600)
        self.setStyleSheet("""
            QDialog { background-color: #121212; border: 2px solid #48BB78; }
            QWidget { background-color: #121212; color: #E0E0E0; font-family: 'Segoe UI', Arial; font-size: 13px; }
            QTableWidget { background-color: #1A1A1A; gridline-color: #2C2C2C; color: #FFFFFF; border: 1px solid #2C2C2C; }
            QHeaderView::section { background-color: #2D2D2D; color: #48BB78; padding: 5px; font-weight: bold; border: 1px solid #2C2C2C; }
            QLineEdit { background-color: #1E1E1E; border: 1px solid #48BB78; border-radius: 4px; padding: 4px; color: #FFFFFF; font-weight: bold; }
            QPushButton { background-color: #2D2D2D; border: 1px solid #3A3A3A; border-radius: 4px; padding: 6px 15px; font-weight: bold; }
            QPushButton:hover { background-color: #3D3D3D; border: 1px solid #48BB78; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # 1. PASZPORT WYSZUKIWANIA W CZASIE RZECZYWISTYM
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("🔍 Szukaj w bazie lokalnej (wpisz fragment nazwy lub ID):"))
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Wpisz np. Salmonella, Enterococcus, NC_003... ")
        self.txt_search.textChanged.connect(self._handle_live_search_filter)
        search_layout.addWidget(self.txt_search, stretch=8)
        layout.addLayout(search_layout)

        # 2. PANORAMICZNA TABELA WZORCÓW
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Nazwa gatunku / Szczep laboratoryjny (Alfabetycznie)", "Accession ID", "Rozmiar pliku (Mbp)"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(1, 150)
        self.table.setColumnWidth(2, 130)
        
        # Aktywacja rygoru masowej selekcji (ExtendedSelection) oraz blokady edycji komórek
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.doubleClicked.connect(self._handle_double_click_accept)
        layout.addWidget(self.table)

        # 3. PASEK KONTROLNY AKCJI
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_cancel = QPushButton("Anuluj ❌")
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_accept = QPushButton("Załaduj zaznaczone do Matrycy ✅")
        self.btn_accept.setStyleSheet("background-color: #006622; color: #FFFFFF; border: 1px solid #48BB78;")
        self.btn_accept.clicked.connect(self._accept_selected_rows)
        
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_accept)
        layout.addLayout(btn_layout)

        # Rozruch pancernego skanera w locie otwierania okna
        self._scan_and_populate_local_library()

    def _scan_and_populate_local_library(self):
        """[FAST-HEADER SENSING V48.3]: Skanuje bazę lokalną NVMe w 0ms bez GUI Freeze [2.4]."""
        import gzip
        import re
        if not os.path.exists(self.library_dir):
            return

        valid_ext = (".fasta", ".fa", ".fna", ".fasta.gz", ".fa.gz", ".fna.gz")
        raw_records = []

        try:
            for file in os.listdir(self.library_dir):
                if not file.lower().endswith(valid_ext):
                    continue
                full_path = os.path.join(self.library_dir, file)
                if not os.path.isfile(full_path) or os.path.getsize(full_path) == 0:
                    continue

                # Szybkie wyciągnięcie wiersza nagłówka z natychmiastowym zamknieciem pliku [2.4]
                first_line = ""
                try:
                    if file.lower().endswith(".gz"):
                        with gzip.open(full_path, "rt", encoding="utf-8", errors="ignore") as f:
                            first_line = f.readline()
                    else:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            first_line = f.readline()
                except Exception:
                    continue

                if first_line.startswith(">"):
                    raw_header = first_line[1:].strip()
                    raw_header = re.sub(r', whole genome shotgun.*$', '', raw_header, flags=re.IGNORECASE)
                    raw_header = re.sub(r' chromosome, complete genome.*$', ' complete genome', raw_header, flags=re.IGNORECASE)
                    
                    parts = raw_header.split(maxsplit=1)
                    accession = parts[0].strip() if parts else file
                    if "." in accession:
                        accession = accession.split(".")[0].strip()
                    
                    full_name = parts[1].strip() if len(parts) > 1 else "Unknown Organism"
                    if full_name.startswith(accession):
                        full_name = full_name[len(accession):].strip().lstrip("-_").strip()
                else:
                    accession = file.split(".")[0]
                    if "." in accession:
                        accession = accession.split(".")[0].strip()
                    full_name = "Unknown Organism"

                if not full_name or full_name == "Unknown Organism":
                    clean_bname = file
                    for ext in valid_ext:
                        if clean_bname.lower().endswith(ext):
                            clean_bname = clean_bname[:-len(ext)]
                            break
                    full_name = clean_bname.replace("assembly_", "").replace("_", " ").strip()
                    if not full_name:
                        full_name = f"Reference Strain ({accession})"

                # ✅ POPRAWKA DANYCH: Pancerny interlock szacowania rozmiaru pliku skompresowanego [2.4]
                size_bytes = os.path.getsize(full_path)
                if file.lower().endswith(".gz"):
                    size_mbp = (size_bytes * 3.3) / 1000000.0
                else:
                    size_mbp = size_bytes / 1000000.0

                raw_records.append((full_name, accession, size_mbp, file))
        except Exception:
            return

        raw_records.sort(key=lambda x: x[0].lower())
        self.table.setRowCount(0)
        self.table.setRowCount(len(raw_records))
        
        for row_idx, (name, acc, size, raw_file) in enumerate(raw_records):
            item_name = QTableWidgetItem(name)
            item_acc = QTableWidgetItem(acc)
            item_acc.setData(Qt.ItemDataRole.UserRole, raw_file)
            
            display_size = size if size >= 0.01 else 0.05
            item_size = QTableWidgetItem(f"{display_size:.2f}")
            
            for item in [item_name, item_acc, item_size]:
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item_size.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            
            self.table.setItem(row_idx, 0, item_name)
            self.table.setItem(row_idx, 1, item_acc)
            self.table.setItem(row_idx, 2, item_size)

    def _accept_selected_rows(self):
        """Zgrupowany ekstraktor: pakuje podświetlone rzędy Batch wraz z ich oryginalną nazwą pliku [INDEX]."""
        selected_ranges = self.table.selectedRanges()
        if not selected_ranges:
            return
            
        rows_to_process = set()
        for r_range in selected_ranges:
            for r in range(r_range.topRow(), r_range.bottomRow() + 1):
                if not self.table.isRowHidden(r):
                    rows_to_process.add(r)
                    
        for row in sorted(rows_to_process):
            item_name = self.table.item(row, 0)
            item_acc = self.table.item(row, 1)
            item_size = self.table.item(row, 2)
            if item_name and item_acc and item_size:
                # ✅ REFORMA: Wyciągamy surową nazwę pliku z UserRole i dołączamy do krotki [INDEX]
                raw_filename = item_acc.data(Qt.ItemDataRole.UserRole)
                self.selected_references.append((
                    item_acc.text().strip(),
                    item_name.text().strip(),
                    item_size.text().strip(),
                    str(raw_filename)
                ))
                
        if self.selected_references:
            self.accept()

    def _extract_row_data_and_close(self, row: int):
        """Szybki ekstraktor dla dwukliku [INDEX]."""
        item_name = self.table.item(row, 0)
        item_acc = self.table.item(row, 1)
        item_size = self.table.item(row, 2)
        if item_name and item_acc and item_size:
            raw_filename = item_acc.data(Qt.ItemDataRole.UserRole)
            self.selected_references = [(
                item_acc.text().strip(),
                item_name.text().strip(),
                item_size.text().strip(),
                str(raw_filename)
            )]
            self.accept()

    def _handle_live_search_filter(self, text: str):
        """[DYNAMIC FILTRATION]: Ukrywa niedopasowane wiersze w locie RAM [INDEX]."""
        query = text.lower().strip()
        for row in range(self.table.rowCount()):
            item_name = self.table.item(row, 0)
            item_acc = self.table.item(row, 1)
            
            name_txt = item_name.text().lower() if item_name else ""
            acc_txt = item_acc.text().lower() if item_acc else ""
            
            is_match = (query in name_txt) or (query in acc_txt)
            self.table.setRowHidden(row, not is_match)

    def _handle_double_click_accept(self, index: QModelIndex):
        """[FAST ACCEPT]: Dwuklik od razu ładuje jeden genom wzorcowy [INDEX]."""
        row = index.row()
        self._extract_row_data_and_close(row)
