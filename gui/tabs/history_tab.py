# gui/tabs/history_tab.py
import os
import sys
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QFileDialog, QMessageBox, QComboBox, QGroupBox, QDialog, QTextEdit)
from PyQt6.QtCore import Qt, QUrl, QThread, pyqtSignal
from PyQt6.QtWebEngineWidgets import QWebEngineView
from pipeline.parsers import KrakenParser
import config

class ExtractionWorkerThread(QThread):
    """Asynchroniczny wątek wykonujący pancerną ekstrakcję Krakentools i auto-GZIP."""
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, cmd_extract: list, cmd_gzip: list, final_gz_path: str):
        super().__init__()
        self.cmd_extract = cmd_extract
        self.cmd_gzip = cmd_gzip
        self.final_gz_path = final_gz_path

    def run(self):
        import subprocess
        try:
            self.log_signal.emit("[STATUS] Krok 1/2: Uruchamianie extract_kraken_reads.py...")
            p = subprocess.Popen(self.cmd_extract, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            stdout_data, _ = p.communicate()
            if p.returncode == 0:
                self.log_signal.emit("[STATUS] Krok 2/2: Błyskawiczne pakowanie gzip -f...")
                subprocess.run(self.cmd_gzip, check=True)
                if os.path.exists(self.final_gz_path) and os.path.getsize(self.final_gz_path) > 0:
                    lines = stdout_data.strip().split("\n")
                    summary = lines[-1] if lines else "Ekstrakcja ukończona."
                    self.log_signal.emit(f"[SUKCES] {summary}")
                    self.finished_signal.emit(True, os.path.basename(self.final_gz_path))
                else:
                    self.finished_signal.emit(False, "Błąd kompresji GZIP.")
            else:
                self.finished_signal.emit(False, "Błąd Krakentools.")
        except Exception as e:
            self.finished_signal.emit(False, str(e))

class AssemblyWorkerThread(QThread):
    """Asynchroniczny wątek dedykowanego składania wyizolowanego patogenu de novo, uodporniony na ostrzeżenia [INDEX]."""
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, cmd_list: list, final_fasta_dest: str, quast_cmd: list = None):
        super().__init__()
        self.cmd_list = cmd_list
        self.final_fasta_dest = final_fasta_dest
        self.quast_cmd = quast_cmd

    def run(self):
        import subprocess
        try:
            for cmd in self.cmd_list:
                self.log_signal.emit(f"[ASSEMBLER] Uruchamianie: {' '.join(cmd)}")
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                for line in p.stdout:
                    self.log_signal.emit(line.strip())
                p.wait()
                
                # ZMODYFIKOWANO: Wykrywamy ścieżkę wyjściową zapisaną w parametrach komendy, aby zrobić pre-weryfikację dysku [INDEX]
                try:
                    out_dir_idx = cmd.index("-o") if "-o" in cmd else (cmd.index("--out-dir") if "--out-dir" in cmd else -1)
                    if out_dir_idx != -1 and out_dir_idx + 1 < len(cmd):
                        out_dir = cmd[out_dir_idx + 1]
                        # Szukamy czy powstał jakikolwiek plik fasta [INDEX]
                        has_files = any(
                            os.path.exists(os.path.join(out_dir, f)) and os.path.getsize(os.path.join(out_dir, f)) > 0
                            for f in ["scaffolds.fasta", "contigs.fasta", "assembly.fasta"]
                        )
                        if has_files:
                            self.log_signal.emit("[ZABEZPIECZENIE]: Wykryto poprawne pliki FASTA na dysku. Ignoruję niezerowy kod ostrzeżeń jądra.")
                            continue # Pliki istnieją, przechodzimy dalej mimo ostrzeżeń bioinformatycznych [INDEX]
                except Exception:
                    pass

                if p.returncode != 0:
                    self.finished_signal.emit(False, "Krok składania nie powiódł się.")
                    return
                    
            if self.quast_cmd:
                self.log_signal.emit(f"[QUAST] Analiza jakości: {' '.join(self.quast_cmd)}")
                subprocess.run(self.quast_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                
            # Zwracamy True, właściwą weryfikację i atomowe przeniesienie wykona interfejs GUI [INDEX]
            self.finished_signal.emit(True, os.path.basename(self.final_fasta_dest))
        except Exception as e:
            self.finished_signal.emit(False, str(e))

class PassportWorkerThread(QThread):
    """[THE ASYNCHRONOUS PASSPORT ENGINE - BACKGROUND THREAD]: Wykonuje os.fsync i zapis JSON w tle stacji XEON [2.4]."""
    log_signal = pyqtSignal(str)

    def __init__(self, species_assembly_folder: str, label: str, platform: str, final_fasta_dest: str, metadata_snapshot: dict):
        super().__init__()
        self.species_assembly_folder = species_assembly_folder
        self.label = label
        self.platform = platform
        self.final_fasta_dest = final_fasta_dest
        self.metadata_snapshot = metadata_snapshot

    def run(self):
        import os
        import json
        try:
            # 🚀 HARDWARE SYNC TRIGGER W TLE: Zamrażamy odizolowany wątek, omijając główny interfejs GUI! [2.4]
            if os.path.exists(self.final_fasta_dest):
                with open(self.final_fasta_dest, "a") as f_sync:
                    f_sync.flush()
                    os.fsync(f_sync.fileno())

            # Bezbłędne wycinanie nagłówka z pierwszej linii zaryglowanego fizycznie pliku FASTA [2.4]
            fasta_header_id = "NODE_UNKNOWN"
            if os.path.exists(self.final_fasta_dest):
                try:
                    with open(self.final_fasta_dest, "r", encoding="utf-8", errors="ignore") as f_head:
                        first_line = f_head.readline()
                        if first_line and first_line.startswith(">"):
                            fasta_header_id = first_line.replace(">", "").strip()
                except Exception:
                    pass

            # Łączenie wstrzykniętej migawki RAM (Metadata Snapshot) ze stanem sprzętowym potoku [2.4]
            passport_data = {
                "organism_name": self.metadata_snapshot.get("val_name", "Unknown_Taxon"),
                "ncbi_taxid": self.metadata_snapshot.get("val_taxid", 0),
                "reads_count": self.metadata_snapshot.get("val_reads", 0),
                "abundance_percent": self.metadata_snapshot.get("val_percent", 0.0),
                "fasta_header_id": fasta_header_id,
                "assembly_platform": self.platform,
                "assembly_timestamp": self.metadata_snapshot.get("timestamp", "")
            }

            # Zrzut sterylnego paszportu JSON dokładnie w miejscu docelowym Double Commandera [2.4]
            passport_name = f"passport_{self.label}.json"
            passport_dest = os.path.join(self.species_assembly_folder, passport_name)
            
            with open(passport_dest, "w", encoding="utf-8") as f_json:
                json.dump(passport_data, f_json, indent=4, ensure_ascii=False)
                
            # Emitowanie sygnału zwrotnego z wątku pobocznego bezpośrednio do konsoli Monitora [2.4]
            self.log_signal.emit(f"[PASZPORT]: Asynchroniczny zrzut metadanych zakończony sukcesem: {passport_name}")
        except Exception as e:
            self.log_signal.emit(f"[BŁĄD PASZPORTU W TLE]: Przerwanie zapisu I/O: {str(e)}")

class HistoryTab(QWidget):
    """Karta Przeglądu Analiz Historycznych: Kompleksowe przeglądanie archiwalne z filtracją w locie."""
    
    def __init__(self):
        super().__init__()
        self.main_window = None
        self.worker = None
        self.asm_worker = None
        
        # Zmienne pamięci lokalnej instancji do zarządzania filtrem w locie
        self.active_report_txt = None
        self.local_override_threshold = None
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # 1. PANEL GÓRNY: WYBÓR FOLDERU
        top_header = QLabel("📁 MENEDŻER PRZEGLĄDU ARCHIWALNEGO I INTEGRACJI RAPORTÓW SKŁADANIA")
        top_header.setStyleSheet("font-weight: bold; color: #00FF66; font-size: 13px;")
        layout.addWidget(top_header)

        browse_layout = QHBoxLayout()
        self.txt_history_path = QLineEdit()
        self.txt_history_path.setPlaceholderText("Wskaż folder projektu (PRJ_...) na dysku NVMe...")
        
        btn_browse = QPushButton("Wybierz folder...")
        btn_browse.clicked.connect(self._handle_browse_history)
        
        btn_load = QPushButton("Załaduj dane 💾")
        btn_load.setStyleSheet("background-color: #004d99; font-weight: bold; color: white;")
        btn_load.clicked.connect(self._load_historical_analysis)

        browse_layout.addWidget(self.txt_history_path, stretch=7)
        browse_layout.addWidget(btn_browse, stretch=2)
        browse_layout.addWidget(btn_load, stretch=1)
        layout.addLayout(browse_layout)

        # 2. PANEL ŚRODKOWY: TABELA + KRONA (UKŁAD ERGONOMICZNY)
        data_layout = QHBoxLayout()
        data_layout.setSpacing(12)

        # LEWA STRONA: TABELA GATUNKÓW KRAKEN2
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        
        # Górny pasek kontrolny lewej strony: Tytuł, pole tekstowe i klawisz odświeżania w locie
        filter_control_layout = QHBoxLayout()
        
        start_threshold = getattr(config, 'KRAKEN_NOISE_THRESHOLD', 0.1)
        self.lbl_table_header = QLabel(f"🦠 WYKRYTE TAKSONY (> {start_threshold}%):")
        self.lbl_table_header.setStyleSheet("font-weight: bold; color: #00FF66; font-size: 13px;")
        filter_control_layout.addWidget(self.lbl_table_header)
        
        self.txt_local_threshold = QLineEdit(str(start_threshold))
        self.txt_local_threshold.setFixedWidth(50)
        self.txt_local_threshold.setPlaceholderText("%")
        filter_control_layout.addWidget(self.txt_local_threshold)
        
        self.btn_apply_local_filter = QPushButton("Zastosuj 🔄")
        self.btn_apply_local_filter.setFixedWidth(80)
        self.btn_apply_local_filter.setStyleSheet("""
            QPushButton { background-color: #1A1A1A; color: #00FF66; border: 1px solid #00FF66; font-weight: bold; font-size: 11px; padding: 3px; }
            QPushButton:hover { background-color: #006622; color: white; }
        """)
        self.btn_apply_local_filter.clicked.connect(self._handle_apply_local_filter)
        filter_control_layout.addWidget(self.btn_apply_local_filter)
        
        left_layout.addLayout(filter_control_layout)

        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(4)
        self.table_widget.setHorizontalHeaderLabels(["Udział (%)", "L.odcz.", "NCBI TaxID", "Nazwa organizmu"])
        self.table_widget.setStyleSheet("""
            QTableWidget { background-color: #1E1E1E; gridline-color: #2C2C2C; color: #FFFFFF; border: 1px solid #2C2C2C; }
            QHeaderView::section { background-color: #2D2D2D; color: #00FF66; padding: 5px; font-weight: bold; border: 1px solid #2C2C2C; }
        """)
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        from PyQt6.QtWidgets import QSizePolicy
        self.table_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table_widget.setMinimumHeight(450)
        self.table_widget.itemSelectionChanged.connect(self._handle_table_selection_changed)
        
        left_layout.addWidget(self.table_widget)
        data_layout.addWidget(left_container, stretch=4)

        # PRAWA STRONA: RAPORT KRONA HTML ORAZ PRZYCISK MONTAŻU IZOLATU
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        
        krona_title = QLabel("📊 RAPORT METAGENOMICZNY KRONA HTML:")
        krona_title.setStyleSheet("font-weight: bold; color: #00FF66; font-size: 14px;")
        right_layout.addWidget(krona_title)

        self.krona_view = QWebEngineView()
        self.krona_view.setStyleSheet("border: 1px solid #2C2C2C; border-radius: 4px;")
        
        settings = self.krona_view.settings()
        settings.setAttribute(settings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(settings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(settings.WebAttribute.LocalContentCanAccessFileUrls, True)
        
        self.krona_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.krona_view.setMinimumHeight(450)
        right_layout.addWidget(self.krona_view)

        self.btn_direct_asm_row = QPushButton("Buduj Genom z wiersza (de Novo) 🧬")
        self.btn_direct_asm_row.setEnabled(False)
        self.btn_direct_asm_row.setStyleSheet("""
            QPushButton { background-color: #1A1A1A; color: #00FF66; border: 1px solid #00FF66; font-weight: bold; padding: 6px; font-size: 12px; }
            QPushButton:hover { background-color: #006622; color: white; }
            QPushButton:disabled { background-color: #2D2D2D; color: #666666; border: 1px solid #444444; }
        """)
        self.btn_direct_asm_row.clicked.connect(self._handle_direct_assembly_from_row)
        right_layout.addWidget(self.btn_direct_asm_row)

        right_layout.addStretch()
        data_layout.addWidget(right_container, stretch=6)
        layout.addLayout(data_layout)

        # 3. PANEL DOLNY: OPERACJE EKSTRAKCJI I RAPORTY MONTAŻU
        extract_box = QGroupBox("🎯 CENTRUM OPERACJI NA PROJEKCIE HISTORYCZNYM")
        extract_layout = QVBoxLayout(extract_box)
        extract_layout.setContentsMargins(10, 6, 10, 6)
        extract_layout.setSpacing(4)

        group_row = QHBoxLayout()
        group_row.addWidget(QLabel("1. Izolacja Królestwa/Grup:"), stretch=2)
        self.combo_groups = QComboBox()
        self.combo_groups.addItem("Wczytaj projekt, aby załadować grupy...")
        self.combo_groups.setEnabled(False)
        self.btn_ext_group = QPushButton("Wyodrębnij Grupę 🧬")
        self.btn_ext_group.setEnabled(False)
        self.btn_ext_group.setStyleSheet("background-color: #2b6cb0; font-weight: bold; color: white; padding: 3px;")
        self.btn_ext_group.clicked.connect(self._handle_group_extraction)
        group_row.addWidget(self.combo_groups, stretch=5)
        group_row.addWidget(self.btn_ext_group, stretch=3)
        extract_layout.addLayout(group_row)

        species_row = QHBoxLayout()
        species_row.addWidget(QLabel("2. Celowana Izolacja Gatunku:"), stretch=2)
        self.combo_species = QComboBox()
        self.combo_species.addItem("Wczytaj projekt, aby załadować patogeny...")
        self.combo_species.setEnabled(False)
        self.btn_ext_species = QPushButton("Wyodrębnij Gatunek 🦠")
        self.btn_ext_species.setEnabled(False)
        self.btn_ext_species.setStyleSheet("background-color: #2b6cb0; font-weight: bold; color: white; padding: 3px;")
        self.btn_ext_species.clicked.connect(self._handle_species_extraction)
        species_row.addWidget(self.combo_species, stretch=5)
        species_row.addWidget(self.btn_ext_species, stretch=3)
        extract_layout.addLayout(species_row)

        buttons_row = QHBoxLayout()
        self.btn_hist_quast = QPushButton("📊 Zobacz Archiwalny Raport Jakości QUAST (HTML)")
        self.btn_hist_quast.setEnabled(False)
        self.btn_hist_quast.setStyleSheet("background-color: #4a5568; font-weight: bold; color: white; padding: 3px;")
        self.btn_hist_quast.clicked.connect(self._open_quast_report_local)

        self.btn_hist_fasta = QPushButton("🧬 Szybki Podgląd Zmontowanego Genomu (FASTA)")
        self.btn_hist_fasta.setEnabled(False)
        self.btn_hist_fasta.setStyleSheet("background-color: #4a5568; font-weight: bold; color: white; padding: 3px;")
        self.btn_hist_fasta.clicked.connect(self._preview_fasta_sequence_local)

        buttons_row.addWidget(self.btn_hist_quast)
        buttons_row.addWidget(self.btn_hist_fasta)
        extract_layout.addLayout(buttons_row)

        self.lbl_extract_status = QLineEdit("Stan menedżera: Oczekiwanie na wczytanie projektu...")
        self.lbl_extract_status.setReadOnly(True)
        self.lbl_extract_status.setStyleSheet("background-color: #1A202C; color: #48BB78; font-family: 'DejaVu Sans Mono', monospace; font-size: 11px; padding: 2px;")
        extract_layout.addWidget(self.lbl_extract_status)

        layout.addWidget(extract_box)
        self.active_quast_html = None
        self.active_fasta_path = None
        # PANCERNY STANDARD DEWELOPERSKI: Jednorazowe podpięcie sygnału w konstruktorze chroni pamięć RAM [INDEX]!
        self.table_widget.cellClicked.connect(self._handle_cell_clicked_preview)

    def _handle_browse_history(self):
        """[THE SECURE HISTORY BROWSER - DYNAMIC FALLBACK]: Wymusza start w podfolderze projects z kaskadą awaryjną [2.4]."""
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
                self.txt_history_path.setText(dir_path)

    def _handle_table_selection_changed(self):
        """
        Włącza przycisk składania genomu z wiersza po wybraniu taksonu, 
        a jeśli genom już istnieje — dynamicznie podepnie ścieżki i odblokuje dolne przyciski podglądu [INDEX].
        """
        selected_ranges = self.table_widget.selectedRanges()
        if not selected_ranges or len(selected_ranges) == 0:
            self.btn_direct_asm_row.setEnabled(False)
            return

        # Prawidłowe pobranie wiersza za pomocą poprawki indeksowania [INDEX]
        first_range = selected_ranges[0]
        row_idx = first_range.topRow()

        taxid_item = self.table_widget.item(row_idx, 2)
        name_item = self.table_widget.item(row_idx, 3)
        
        if taxid_item and name_item:
            self.btn_direct_asm_row.setEnabled(True)
            
            # Dynamiczne wyliczenie ścieżek dla klikniętego gatunku [INDEX]
            label = KrakenParser.sanitize_linux_name(name_item.text().strip()).lower()
            target_dir = self.txt_history_path.text().strip()
            
            species_assembly_folder = os.path.join(target_dir, "03_Assembly", label)
            final_fasta_name = f"assembly_{label}.fasta"
            potential_fasta = os.path.join(species_assembly_folder, final_fasta_name)
            potential_quast = os.path.join(species_assembly_folder, "quast_report", "report.html")

            # =====================================================================
            # NOWOŚĆ: INTEGRACJA AUTODETEKCJI ARCHIWALNEJ W LOCIE KLIKNIĘCIA [INDEX]
            # =====================================================================
            if os.path.exists(potential_fasta) and os.path.getsize(potential_fasta) > 0:
                # Genom istnieje — natychmiastowo mapujemy ścieżki do lokalnego podglądu [INDEX]
                self.active_fasta_path = potential_fasta
                self.btn_hist_fasta.setEnabled(True)
                self.btn_hist_fasta.setStyleSheet("background-color: #004d99; font-weight: bold; color: white; padding: 3px;")
                
                if os.path.exists(potential_quast):
                    self.active_quast_html = potential_quast
                    self.btn_hist_quast.setEnabled(True)
                    self.btn_hist_quast.setStyleSheet("background-color: #22863a; font-weight: bold; color: white; padding: 3px;")
                else:
                    self.btn_hist_quast.setEnabled(False)
                    self.btn_hist_quast.setStyleSheet("background-color: #4a5568; font-weight: bold; color: #a0aec0; padding: 3px;")
            else:
                # Genom nie istnieje dla tej pozycji — wygaszamy dolne przyciski archiwalne [INDEX]
                self.btn_hist_fasta.setEnabled(False)
                self.btn_hist_fasta.setStyleSheet("background-color: #4a5568; font-weight: bold; color: #a0aec0; padding: 3px;")
                self.btn_hist_quast.setEnabled(False)
                self.btn_hist_quast.setStyleSheet("background-color: #4a5568; font-weight: bold; color: #a0aec0; padding: 3px;")
                self.active_fasta_path = None
                self.active_quast_html = None
        else:
            self.btn_direct_asm_row.setEnabled(False)

    def get_active_threshold(self) -> float:
        """Bezpiecznie zwraca próg wpisany przez użytkownika w lokalnym okienku historii."""
        try:
            return float(self.txt_local_threshold.text().strip())
        except ValueError:
            return getattr(config, 'KRAKEN_NOISE_THRESHOLD', 0.1)

    def _load_historical_analysis(self):
        """Dynamicznie skanuje folder, zasila widżety i synchronizuje tymczasowe filtry odcięcia szumu [INDEX]."""
        target_dir = self.txt_history_path.text().strip()
        if not target_dir or not os.path.exists(target_dir):
            QMessageBox.warning(self, "Błąd ścieżki", "Wskazany folder projektu nie istnieje!")
            return

        active_threshold = self.get_active_threshold()
        self.lbl_table_header.setText(f"🦠 WYKRYTE TAKSONY (> {active_threshold}%):")
        self.txt_local_threshold.setText(str(active_threshold))

        # ZGODNOŚĆ ARCHITEKTONICZNA: Domyślnie wygaszamy przyciski lokalnego podglądu przy starcie.
        # Aktywują się one precyzyjnie dopiero po kliknięciu wybranego wiersza w tabeli [INDEX].
        self.active_quast_html, self.active_fasta_path = None, None
        self.btn_hist_quast.setEnabled(False)
        self.btn_hist_quast.setStyleSheet("background-color: #4a5568; font-weight: bold; color: #a0aec0; padding: 3px;")
        self.btn_hist_fasta.setEnabled(False)
        self.btn_hist_fasta.setStyleSheet("background-color: #4a5568; font-weight: bold; color: #a0aec0; padding: 3px;")

        report_txt = os.path.join(target_dir, "02_Taxonomy", "kraken_report.txt")
        report_html = os.path.join(target_dir, "02_Taxonomy", "krona_report.html")
        if not os.path.exists(report_txt):
            report_txt = os.path.join(target_dir, "kraken_report.txt")
            report_html = os.path.join(target_dir, "krona_chart.html")

        if os.path.exists(report_txt):
            self.active_report_txt = report_txt
            filtered_rows = KrakenParser.parse_kraken_report(report_txt, threshold=active_threshold)
            self._populate_history_table(filtered_rows)
            self._parse_report_for_comboboxes(report_txt)
        else:
            self.active_report_txt = None
            self._reset_comboboxes()
            self.table_widget.setRowCount(0)

        if os.path.exists(report_html):
            self.krona_view.setUrl(QUrl.fromLocalFile(os.path.abspath(report_html)))
        else:
            base_dir = os.path.dirname(report_html) if os.path.dirname(report_html) else target_dir
            alt_name = "krona_chart.html" if "krona_report.html" in report_html else "krona_report.html"
            actual_html = os.path.join(base_dir, alt_name)
            if os.path.exists(actual_html):
                self.krona_view.setUrl(QUrl.fromLocalFile(os.path.abspath(actual_html)))
            else:
                self.krona_view.setHtml("<h3 style='color:red; text-align:center;'>Nie znaleziono Krona HTML.</h3>")
 
    def _handle_apply_local_filter(self):
        """Pobiera chwilowy próg i odświeża tabelę archiwalną zarówno przed, jak i po załadowaniu folderu."""
        try:
            local_val = float(self.txt_local_threshold.text().strip())
        except ValueError:
            QMessageBox.critical(self, "Niepoprawny format", "Wpisany próg musi być liczbą zmiennoprzecinkową (np. 0.05)!")
            return           
        self.local_override_threshold = local_val
        self.lbl_table_header.setText(f"🦠 WYKRYTE TAKSONY (> {local_val}%):")        
        if not self.active_report_txt or not os.path.exists(self.active_report_txt):
            return           
        refiltered_rows = KrakenParser.parse_kraken_report(self.active_report_txt, threshold=local_val)
        self._populate_history_table(refiltered_rows)

    def _populate_history_table(self, filtered_rows: list):
        """Zasila komórki tabeli odfiltrowanymi danymi historycznymi [INDEX]."""
        self.table_widget.setRowCount(0)
        self.table_widget.setRowCount(len(filtered_rows))
        for row_idx, data in enumerate(filtered_rows):
            item_percent = QTableWidgetItem(f"{data['percent']}%")
            item_reads = QTableWidgetItem(str(data['reads']))
            item_taxid = QTableWidgetItem(str(data['taxid']))
            item_name = QTableWidgetItem(data['name'])       
            
            for item in [item_percent, item_reads, item_taxid, item_name]: 
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            
            item_percent.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_reads.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_taxid.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)            
            
            self.table_widget.setItem(row_idx, 0, item_percent)
            self.table_widget.setItem(row_idx, 1, item_reads)
            self.table_widget.setItem(row_idx, 2, item_taxid)
            self.table_widget.setItem(row_idx, 3, item_name)

    def _handle_direct_assembly_from_row(self):
        """
        [SANDBOX ASSEMBLY ENGINE + INTERLOCK S-1]: Uruchamia asynchroniczny montaż de Novo szczepu z wiersza.
        Weryfikuje zajętość Xeona i twardo rygruje pasek boczny oraz karty peryferyjne przed startem.
        """
        import shutil
        
        # ⚔️ BEZPIECZNIK KRZYŻOWY: Odrzucamy start, jeśli w oknie głównym leci już analiza potoku!
        if self.main_window and self.main_window.current_pipeline_thread and self.main_window.current_pipeline_thread.isRunning():
            QMessageBox.critical(
                self, 
                "Xeon jest zajęty", 
                "Nie można uruchomić celowanego montażu szczepu! W tle trwa przetwarzanie potoku głównego na rdzeniach Xeona."
            )
            return

        selected_ranges = self.table_widget.selectedRanges()
        if not selected_ranges or len(selected_ranges) == 0: 
            return
            
        first_range = selected_ranges[0]
        row_idx = first_range.topRow()
        
        taxid_item = self.table_widget.item(row_idx, 2)
        name_item = self.table_widget.item(row_idx, 3)
        if not taxid_item or not name_item: 
            return
        
        taxid = str(taxid_item.text()).strip()
        raw_name = str(name_item.text()).strip()
        label = KrakenParser.sanitize_linux_name(raw_name).lower()
        target_dir = self.txt_history_path.text().strip()
        
        species_assembly_folder = os.path.join(target_dir, "03_Assembly", label)
        final_fasta_name = f"assembly_{label}.fasta"
        final_fasta_dest = os.path.join(species_assembly_folder, final_fasta_name)
        
        if os.path.exists(final_fasta_dest) and os.path.getsize(final_fasta_dest) > 0:
            QMessageBox.information(
                self,
                "🧬 Genom już istnieje",
                f"Dla pozycji \"{raw_name}\" wykryto już pomyślnie zmontowany genom de Novo w:\n"
                f"03_Assembly/{label}/{final_fasta_name}"
            )
            return

        # AUTONOMNA DETEKCJA PLATFORMY: Skanujemy fizyczną obecność folderów na dysku
        platform = "ION_TORRENT"
        if os.path.exists(os.path.join(target_dir, "03_Assembly", "flye_output")) or os.path.exists(os.path.join(target_dir, "assembly.fasta")): 
            platform = "NANOPORE"

        try:
            total, used, free = shutil.disk_usage(target_dir)
            free_gb = free / (1024 ** 3)
        except Exception:
            free_gb = 0.0

        required_gb = 25.0 if platform == "NANOPORE" else 10.0
        if free_gb < required_gb:
            QMessageBox.critical(self, "🛑 Brak przestrzeni", f"Celowany montaż wymaga {required_gb:.1f} GB. Wolne: {free_gb:.1f} GB.")
            return

        expected_folder = os.path.join(target_dir, "02_Taxonomy") if os.path.exists(os.path.join(target_dir, "02_Taxonomy")) else target_dir
        extracted_fastq_gz = os.path.join(expected_folder, f"extracted_{label}.fastq.gz")
        
        bin_prefix = "/home/ionadmin/miniforge3/envs/ion_analysis/bin/"
        threads = getattr(config, 'CURRENT_THREADS_LIMIT', 16)
        ram_limit = str(int(float(config.MAX_RAM_ALLOCATION_GB))) 
        
        tmp_asm_out = os.path.join(target_dir, f"tmp_asm_{label}")
        spades_output_dir = os.path.join(tmp_asm_out, "spades_output" if platform == "ION_TORRENT" else "flye_output")
        
        cmd_list = []
        if platform == "ION_TORRENT":
            cmd_list.append([os.path.join(bin_prefix, "spades.py"), "--iontorrent", "-s", extracted_fastq_gz, "-o", spades_output_dir, "-m", ram_limit, "-t", str(threads)])
        else:
            cmd_list.append([os.path.join(bin_prefix, "flye"), "--nano-hq", extracted_fastq_gz, "--out-dir", spades_output_dir, "--threads", str(threads)])

        if os.path.exists(extracted_fastq_gz):
            self.btn_direct_asm_row.setEnabled(False)
            
            # 🚨 INTERLOCK DWUKIERUNKOWY S-1: Paraliżujemy cały panel boczny i karty okna głównego!
            if self.main_window and hasattr(self.main_window, '_set_peripheral_tabs_enabled'):
                self.main_window._set_peripheral_tabs_enabled(False)
            
            # Okno dialogowe statusu montażu szczepu
            self._status_dialog = QDialog(self)
            self._status_dialog.setWindowTitle("Proces Składania Genomu Szczepu")
            self._status_dialog.setMinimumSize(500, 150)
            sd_layout = QVBoxLayout(self._status_dialog)
            sd_lbl = QLabel(f"🧬 Trwa celowana budowa genomu de Novo dla szczepu: {label}\nProcesor Xeon uruchamia wątki silnika obliczeniowego...")
            sd_lbl.setStyleSheet("color: #00FF66; font-weight: bold;")
            sd_layout.addWidget(sd_lbl)
            self._status_dialog.show()
            
            self.asm_worker = AssemblyWorkerThread(cmd_list, final_fasta_dest, quast_cmd=None)
            self.asm_worker.finished_signal.connect(
                lambda success, fname: self._handle_row_assembly_completed(success, fname, target_dir, platform, tmp_asm_out, final_fasta_dest, species_assembly_folder, label)
            )
            self.asm_worker.start()
            return

        # SCENARIUSZ B: OKNO DECYZYJNE I POTOK DWUETAPOWY
        reply = QMessageBox.question(
            self, "Brak odczytów szczepu",
            f"Nie odnaleziono pliku {os.path.basename(extracted_fastq_gz)}.\n\nCzy automatycznie dokonać ekstrakcji i montażu?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.No:
            return 
            
        output_text = os.path.join(target_dir, "02_Taxonomy", "kraken_output.txt")
        report_text = os.path.join(target_dir, "02_Taxonomy", "kraken_report.txt")
        if not os.path.exists(output_text):
            output_text = os.path.join(target_dir, "kraken_output.txt")
            report_text = os.path.join(target_dir, "kraken_report.txt")
            
        fastp_r1 = os.path.join(target_dir, "01_QC", "cleaned_reads.fastq.gz")
        if not os.path.exists(fastp_r1):
            fastp_r1 = os.path.join(target_dir, "clean_R1.fastq.gz")
            if not os.path.exists(fastp_r1): 
                fastp_r1 = os.path.join(target_dir, "clean_R1.fastq")
                
        if not os.path.exists(output_text) or not os.path.exists(fastp_r1):
            QMessageBox.critical(self, "Błąd struktur", "Brakuje krytycznych plików kraken_output.txt lub cleaned_reads.fastq!")
            return

        mamba_python = os.path.join(bin_prefix, "python3")
        file_temp_fastq = os.path.join(expected_folder, f"extracted_{label}.fastq")
        cmd_extract = [mamba_python, os.path.join(bin_prefix, "extract_kraken_reads.py"), "-k", output_text, "-r", report_text, "-s", fastp_r1, "-o", file_temp_fastq, "--taxid", taxid, "--fastq-output", "--include-children"]
        cmd_gzip = ["gzip", "-f", file_temp_fastq]
        
        self.btn_direct_asm_row.setEnabled(False)
        
        # INTERLOCK DWUKIERUNKOWY S-1: Paraliżujemy pasek boczny main_window przed startem sztafety!
        if self.main_window and hasattr(self.main_window, '_set_peripheral_tabs_enabled'):
            self.main_window._set_peripheral_tabs_enabled(False)
        
        # Inicjalizacja okna progresu dla sztafety dwuetapowej
        self._status_dialog = QDialog(self)
        self._status_dialog.setWindowTitle("Automatyczny Dwustopniowy Potok Izolatu")
        self._status_dialog.setMinimumSize(500, 150)
        sd_layout = QVBoxLayout(self._status_dialog)
        self._sd_lbl = QLabel(f"🦠 Krok 1/2: Trwa automatyczna izolacja odczytów Krakentools...")
        self._sd_lbl.setStyleSheet("color: #0099FF; font-weight: bold;")
        sd_layout.addWidget(self._sd_lbl)
        self._status_dialog.show()
            
        self.worker = ExtractionWorkerThread(cmd_extract, cmd_gzip, extracted_fastq_gz)
        
        # ✅ FIX STRUMIENIA LOGÓW: Przekierowujemy asynchroniczne logi Krakentools bezpośrednio do konsoli Monitora!
        if self.main_window and hasattr(self.main_window, 'tab_monitor'):
            self.worker.log_signal.connect(self.main_window.tab_monitor.append_log)
            # Przerzucamy użytkownika na zakładkę monitora, aby na żywo widział logowanie binarne Krakentools
            if hasattr(self.main_window, 'tabs'):
                self.main_window.tabs.setCurrentIndex(0)
                
        self.worker.finished_signal.connect(
            lambda success, fname: self._trigger_chained_assembly_flow_updated(success, fname, cmd_list, final_fasta_dest, target_dir, platform, label, tmp_asm_out, species_assembly_folder)
        )
        self.worker.start()

    def _trigger_chained_assembly_flow_updated(self, success, filename, cmd_list, final_fasta_dest, target_dir, platform, label, tmp_asm_out, species_assembly_folder):
        """Wewnętrzny łącznik sztafetowy: automatycznie zamyka okno-widmo i bezbłędnie przekazuje potok do assemblera [INDEX]."""
        # JAWNY I ATOMOWY ZAMKNIĘCIE OKNA DIALOGOWEGO: Likwidujemy wiszący dialog progresu z ekranu operatora!
        if hasattr(self, '_status_dialog') and self._status_dialog:
            try:
                self._status_dialog.accept()
                self._status_dialog.close()
            except Exception:
                pass
            self._status_dialog = None

        if not success:
            # W razie awarii pierwszego kroku, bezwzględnie uwalniamy pasek boczny okna głównego
            if self.main_window and hasattr(self.main_window, '_set_peripheral_tabs_enabled'):
                self.main_window._set_peripheral_tabs_enabled(True)
            self.btn_direct_asm_row.setEnabled(True)
            return

        if self.main_window and hasattr(self.main_window, 'tab_monitor'):
            self.main_window.tab_monitor.append_log(f"\n[Krok 2/2]: Ekstrakcja zakończona pomyślnie. Plik {filename} zabezpieczony na NVMe.")
            self.main_window.tab_monitor.append_log(f"[Kombajn T430]: Uruchamiam automatyczny montaż de novo dla wyizolowanego szczepu: {label}...")

        # Wybudzamy nowe, dedykowane okno progresu wyłącznie dla Kroku 2/2 (Montażu assemblerem)
        self._status_dialog = QDialog(self)
        self._status_dialog.setWindowTitle("Krok 2/2: Składanie Genomu Szczepu")
        self._status_dialog.setMinimumSize(500, 150)
        sd_layout = QVBoxLayout(self._status_dialog)
        sd_lbl = QLabel(f"🧬 Trwa celowana budowa genomu de Novo dla szczepu: {label}\nSilniki SPAdes/Flye alokują zasoby procesora Xeon...")
        sd_lbl.setStyleSheet("color: #b83280; font-weight: bold;")
        sd_layout.addWidget(sd_lbl)
        self._status_dialog.show()

        self.asm_worker = AssemblyWorkerThread(cmd_list, final_fasta_dest, quast_cmd=None)
        self.asm_worker.finished_signal.connect(
            lambda succ, fname: self._handle_row_assembly_completed(succ, fname, target_dir, platform, tmp_asm_out, final_fasta_dest, species_assembly_folder, label)
        )
        self.asm_worker.start()

    def _handle_row_assembly_completed(self, success, filename, target_dir, platform, tmp_asm_out, final_fasta_dest, species_assembly_folder, label):
        """[THE ORIGINAL FAILSAFE ENGINE - ASYNC TRIGGER]: Kopiuje FASTA i asynchronicznie odpala paszport w tle [2.4]."""
        import shutil
        import subprocess
        from datetime import datetime

        # ✅ ATOMOWE NISZCZENIE OKIENKA: Likwidujemy wiszący dialog Krok 2/2 z ekranu operatora
        if hasattr(self, '_status_dialog') and self._status_dialog:
            try:
                self._status_dialog.accept()
                self._status_dialog.close()
            except Exception:
                pass
            self._status_dialog = None

        # UWOLNIENIE RYGLA PASKA BOCZNEGO: Przywracamy sterowność i jasność main_window
        if self.main_window and hasattr(self.main_window, '_set_peripheral_tabs_enabled'):
            self.main_window._set_peripheral_tabs_enabled(True)
            
        self.btn_direct_asm_row.setEnabled(True)
        
        # Wyznaczanie podfolderów wewnątrz tymczasowej struktury
        sub_folder = "spades_output" if platform == "ION_TORRENT" else "flye_output"
        spades_output_dir = os.path.join(tmp_asm_out, sub_folder)
        
        # TWARDA WERYFIKACJA DYSKOWA: Szukamy czy pliki fizycznie istnieją
        scaffolds_name = "scaffolds.fasta" if platform == "ION_TORRENT" else "assembly.fasta"
        check_path_1 = os.path.join(spades_output_dir, scaffolds_name)
        check_path_2 = os.path.join(spades_output_dir, "contigs.fasta")
        
        disk_success = (os.path.exists(check_path_1) and os.path.getsize(check_path_1) > 0) or \
                       (os.path.exists(check_path_2) and os.path.getsize(check_path_2) > 0)
                       
        if disk_success:
            if self.main_window and hasattr(self.main_window, 'tab_monitor'):
                self.main_window.tab_monitor.append_log(f"[SUKCES LOGICZNY]: Wykryto pliki wynikowe szczepu. Przechodzę do atomowego przenoszenia.")
            
            # KROK 1: ATOMOWE PRZENIESIENIE I ZMIANA NAZWY CAŁEGO KATALOGU SZCZEPU
            try:
                if os.path.exists(tmp_asm_out):
                    if os.path.exists(species_assembly_folder):
                        shutil.rmtree(species_assembly_folder, ignore_errors=True)
                        
                    shutil.move(tmp_asm_out, species_assembly_folder)
                    
                    if self.main_window and hasattr(self.main_window, 'tab_monitor'):
                        self.main_window.tab_monitor.append_log(f"[DYSK Kingston]: Katalog roboczy przesunięty atomowo do: 03_Assembly/{label}/")
                else:
                    raise FileNotFoundError(f"Nie odnaleziono katalogu tymczasowego: {tmp_asm_out}")
            except Exception as e:
                QMessageBox.critical(self, "Błąd systemowy I/O", f"Nie udało się atomowo przenieść struktur katalogu szczepu:\n{str(e)}")
                return

            # KROK 2: DYNAMICZNE MAPOWANIE PLIKU FASTA I WYWOŁANIE SHUTIL.COPY
            current_fasta_source = os.path.join(species_assembly_folder, sub_folder, scaffolds_name)
            if platform == "ION_TORRENT" and not os.path.exists(current_fasta_source):
                current_fasta_source = os.path.join(species_assembly_folder, sub_folder, "contigs.fasta")

            if os.path.exists(current_fasta_source) and os.path.getsize(current_fasta_source) > 0:
                try:
                    shutil.copy(current_fasta_source, final_fasta_dest)
                    self.active_fasta_path = final_fasta_dest
                except Exception:
                    self.active_fasta_path = current_fasta_source
                    final_fasta_dest = current_fasta_source

                # =====================================================================
                # 🚀 METADATA SNAPSHOT: Pobieranie danych z RAM przed startem wątku tła [2.4]
                # =====================================================================
                val_percent, val_reads, val_taxid, val_name = "0.0", "0", "0", "Unknown_Taxon"
                selected_ranges = self.table_widget.selectedRanges()
                if selected_ranges and len(selected_ranges) > 0:
                    row_idx = selected_ranges[0].topRow()
                    item_pct = self.table_widget.item(row_idx, 0)
                    item_rds = self.table_widget.item(row_idx, 1)
                    item_tid = self.table_widget.item(row_idx, 2)
                    item_nam = self.table_widget.item(row_idx, 3)
                    
                    if item_pct: val_percent = item_pct.text().replace("%", "").strip()
                    if item_rds: val_reads = item_rds.text().strip()
                    if item_tid: val_taxid = item_tid.text().strip()
                    if item_nam: val_name = item_nam.text().strip()

                snapshot = {
                    "val_name": val_name,
                    "val_taxid": int(val_taxid) if val_taxid.isdigit() else 0,
                    "val_reads": int(val_reads) if val_reads.isdigit() else 0,
                    "val_percent": float(val_percent) if val_percent.replace('.', '', 1).isdigit() else 0.0,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }

                # 🚀 ASYNCHRONICZNY WYZWOLACZ PASZPORTU: Inicjalizacja i rozruch wątku w tle [2.4]
                self.passport_thread = PassportWorkerThread(species_assembly_folder, label, platform, final_fasta_dest, snapshot)
                if self.main_window and hasattr(self.main_window, 'tab_monitor'):
                    self.passport_thread.log_signal.connect(self.main_window.tab_monitor.append_log)
                self.passport_thread.start()

                # CIĄG DALSZY ORYGINALNEGO POTOKU WALIDACJI QUAST (0ms opóźnienia logów!)
                bin_prefix = "/home/ionadmin/miniforge3/envs/ion_analysis/bin/"
                mamba_python = os.path.join(bin_prefix, "python3")
                threads = str(config.CURRENT_THREADS_LIMIT) if self.main_window else "16"
                final_quast_out = os.path.join(species_assembly_folder, "quast_report")
                
                quast_cmd = [mamba_python, os.path.join(bin_prefix, "quast.py"), final_fasta_dest, "-o", final_quast_out, "--threads", threads]
                
                if self.main_window and hasattr(self.main_window, 'tab_monitor'):
                    self.main_window.tab_monitor.append_log(f"[QUAST]: Uruchamiam ocenę jakościową zmontowanego szczepu {label}...")
                
                subprocess.run(quast_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                
                potential_quast_html = os.path.join(final_quast_out, "report.html")
                if os.path.exists(potential_quast_html):
                    self.active_quast_html = potential_quast_html

                if self.main_window and hasattr(self.main_window, 'tabs'):
                    self.main_window.tabs.setCurrentIndex(2)

            else:
                QMessageBox.critical(self, "Błąd struktur", "Montaż ukończony, ale nie wykryto plików FASTA szczepu w przeniesionym katalogu!")
                return

            self.btn_hist_quast.setEnabled(True)
            self.btn_hist_quast.setStyleSheet("background-color: #22863a; font-weight: bold; color: white; padding: 3px;")
            self.btn_hist_fasta.setEnabled(True)
            self.btn_hist_fasta.setStyleSheet("background-color: #004d99; font-weight: bold; color: white; padding: 3px;")

            status_msg = f"[SUKCES]: Kompletny potok celowany dla szczepu {label} zamknięty w 03_Assembly."
            if hasattr(self, 'lbl_extract_status') and self.lbl_extract_status:
                self.lbl_extract_status.setText(status_msg)

            QMessageBox.information(
                self, 
                "Sukces automatyzacji atomowej", 
                f"Zestaw wynikowy dla szczepu został pomyślnie zmontowany i poukładany!\n\n"
                f"Wyniki znajdują się w lokalizacji:\n"
                f"03_Assembly/{label}/\n\n"
                f"Katalog główny próbki pozostał w nieskazitelnej czystości."
            )
            
        else:
            err_msg = "[BŁĄD] Składanie patogenu lub analiza nie powiodła się."
            if hasattr(self, 'lbl_extract_status') and self.lbl_extract_status:
                self.lbl_extract_status.setText(err_msg)
            QMessageBox.critical(self, "Błąd montażu szczepu", "Wystąpił krytyczny problem podczas pracy silnika. Nie odnaleziono plików FASTA.")

    def _open_quast_report_local(self):
        """Otwiera archiwalny raport jakości QUAST HTML w dedykowanym oknie dialogowym [INDEX]."""
        if self.active_quast_html and os.path.exists(self.active_quast_html):
            dialog = QDialog(self)
            dialog.setWindowTitle("Archiwalny Raport Jakości QUAST")
            dialog.setMinimumSize(900, 650)
            dialog_layout = QVBoxLayout(dialog)
            dialog_layout.setContentsMargins(0, 0, 0, 0)
            web_browser = QWebEngineView()
            web_browser.settings().setAttribute(web_browser.settings().WebAttribute.JavascriptEnabled, True)
            web_browser.setUrl(QUrl.fromLocalFile(os.path.abspath(self.active_quast_html)))
            dialog_layout.addWidget(web_browser)
            dialog.exec()

    def _preview_fasta_sequence_local(self):
        """Wczytuje pierwsze 100 linii pliku FASTA i wyświetla w ciemnym oknie tekstowym [INDEX]."""
        if self.active_fasta_path and os.path.exists(self.active_fasta_path):
            try:
                preview_lines = []
                with open(self.active_fasta_path, "r", encoding="utf-8") as f:
                    for _ in range(100):
                        line = f.readline()
                        if not line: break
                        preview_lines.append(line)
                dialog = QDialog(self)
                dialog.setWindowTitle(f"Archiwalny Podgląd FASTA")
                dialog.setMinimumSize(700, 500)
                dialog_layout = QVBoxLayout(dialog)
                text_area = QTextEdit()
                text_area.setReadOnly(True)
                text_area.setPlainText("".join(preview_lines))
                text_area.setStyleSheet("background-color: #1A1A1A; color: #48BB78; font-family: 'DejaVu Sans Mono', monospace;")
                dialog_layout.addWidget(text_area)
                dialog.exec()
            except Exception: pass

    def _handle_group_extraction(self):
        """Wywoływana po kliknięciu niebieskiego przycisku grupy [INDEX]."""
        selected = self.combo_groups.currentText()
        if "[ID: " not in selected: return
        taxid = selected.split("[ID: ")[1].split("]")[0].strip()
        label = selected.split(" [ID:")[0].replace(" ", "_").lower()
        include_children = False if taxid == "0" else True
        self._execute_krakentools_engine(taxid, label, include_children)

    def _handle_species_extraction(self):
        """Wywoływana po kliknięciu niebieskiego przycisku gatunku [INDEX]."""
        selected = self.combo_species.currentText()
        if "[ID: " not in selected: return
        taxid = selected.split("[ID: ")[1].split("]")[0].strip()
        label = selected.split(" (")[0].replace(" ", "_").replace("(", "").replace(")", "").strip().lower()
        self._execute_krakentools_engine(taxid, label, include_children=True)

    def _parse_report_for_comboboxes(self, report_path):
        """Dynamicznie zasila listy rozwijane na podstawie aktualnego progu z konfiguracji [INDEX]."""
        target_groups = {"2": "Bakterie (Bacteria)", "10239": "Wirusy (Viruses)", "4751": "Grzyby (Fungi)"}
        detected_groups, detected_species = [], []
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split("\t")
                    if len(parts) < 6: continue
                    percent_str, rank, taxid, name = parts[0].strip(), parts[3].strip(), parts[4].strip(), parts[5].strip()
                    if taxid in target_groups: detected_groups.append(f"{target_groups[taxid]} [ID: {taxid}]")
                    if rank in ["G", "S"]:
                        try:
                            # Bezpieczne oczyszczenie i rzutowanie z wymuszonym fallbackiem typu float
                            current_percent = float(percent_str.replace(",", ".").strip())
                            current_threshold = float(getattr(config, 'KRAKEN_NOISE_THRESHOLD', 0.1))

                            if current_percent >= current_threshold:
                                rank_label = "Rodzaj" if rank == "G" else "Gatunek"
                                detected_species.append(f"{name.strip()} ({rank_label}) [ID: {taxid}] - {percent_str}%")
                        except (ValueError, TypeError):
                            continue

            detected_groups.append("Niesklasyfikowane (Unclassified) [ID: 0]")
            self.combo_groups.clear()
            self.combo_groups.addItems(detected_groups)
            self.combo_groups.setEnabled(True)
            self.btn_ext_group.setEnabled(True)
            self.combo_species.clear()
            if detected_species:
                self.combo_species.addItems(detected_species)
                self.combo_species.setEnabled(True)
                self.btn_ext_species.setEnabled(True)
        except Exception: 
            pass

    def _reset_comboboxes(self):
        """Przywraca stan początkowy list rozwijanych po czyszczeniu lub braku pliku [INDEX]."""
        self.combo_groups.clear()
        self.combo_groups.addItem("Wczytaj projekt...")
        self.combo_groups.setEnabled(False)
        self.btn_ext_group.setEnabled(False)
        self.combo_species.clear()
        self.combo_species.addItem("Wczytaj projekt...")
        self.combo_species.setEnabled(False)
        self.btn_ext_species.setEnabled(False)

    def _execute_krakentools_engine(self, taxid, label, include_children):
        """[SANDBOX ENGINE + EXCEPTION INTERLOCK]: Wykonuje izolację odczytów i twardo rygluje panel boczny main_window omijając indeks 2."""
        target_dir = self.txt_history_path.text().strip()
        output_text = os.path.join(target_dir, "02_Taxonomy", "kraken_output.txt")
        report_text = os.path.join(target_dir, "02_Taxonomy", "kraken_report.txt")
        if not os.path.exists(output_text):
            output_text = os.path.join(target_dir, "kraken_output.txt")
            report_text = os.path.join(target_dir, "kraken_report.txt")
            
        fastp_r1 = os.path.join(target_dir, "01_QC", "cleaned_reads.fastq.gz")
        if not os.path.exists(fastp_r1):
            fastp_r1 = os.path.join(target_dir, "clean_R1.fastq.gz")
            if not os.path.exists(fastp_r1): 
                fastp_r1 = os.path.join(target_dir, "clean_R1.fastq")
                
        if not os.path.exists(output_text) or not os.path.exists(fastp_r1): 
            QMessageBox.warning(self, "Brak struktur", "Nie odnaleziono wymaganych plików Kraken/FASTQ w projekcie!")
            return
            
        file_temp_fastq = os.path.join(target_dir, "02_Taxonomy" if os.path.exists(os.path.join(target_dir, "02_Taxonomy")) else target_dir, f"extracted_{label}.fastq")
        file_final_gz = file_temp_fastq + ".gz"
        
        bin_prefix = "/home/ionadmin/miniforge3/envs/ion_analysis/bin/"
        cmd_extract = [os.path.join(bin_prefix, "python3"), os.path.join(bin_prefix, "extract_kraken_reads.py"), "-k", output_text, "-r", report_text, "-s", fastp_r1, "-o", file_temp_fastq, "--taxid", taxid, "--fastq-output"]
        if include_children: 
            cmd_extract.append("--include-children")
            
        cmd_gzip = ["gzip", "-f", file_temp_fastq]
        
        self.btn_ext_group.setEnabled(False)
        self.btn_ext_species.setEnabled(False)
        
        # 🚨 MASKOWANIE WYJĄTKU RYGLA S-1.5: Unieruchamiamy lewy panel paska bocznego, zachowując indeks 2 (Historię) aktywny!
        if self.main_window and hasattr(self.main_window, '_set_peripheral_tabs_enabled'):
            self.main_window._set_peripheral_tabs_enabled(False, exclude_idx=2)
        
        # Autonomiczne okno statusu wyodrębniania
        self._status_dialog = QDialog(self)
        self._status_dialog.setWindowTitle("Izolacja Krakentools")
        self._status_dialog.setMinimumSize(450, 120)
        sd_layout = QVBoxLayout(self._status_dialog)
        sd_lbl = QLabel(f"🧬 Trwa filtrowanie binarne odczytów dla TaxID {taxid}...\nWynik zostanie skompresowany automatycznie do .fastq.gz")
        sd_lbl.setStyleSheet("color: #0099FF; font-weight: bold;")
        sd_layout.addWidget(sd_lbl)
        self._status_dialog.show()

        self.worker = ExtractionWorkerThread(cmd_extract, cmd_gzip, file_final_gz)
        self.worker.finished_signal.connect(self._handle_extraction_completed)
        self.worker.start()

    def _handle_extraction_completed(self, success, filename):
        """Obsługuje zakończenie samodzielnej izolacji Krakentools i czyści interfejs z okien dialogowych [INDEX]."""
        # JAWNY ZAMKNIĘCIE OKNA DIALOGOWEGO: Likwidujemy wiszący dialog izolacji z ekranu
        if hasattr(self, '_status_dialog') and self._status_dialog:
            try:
                self._status_dialog.accept()
                self._status_dialog.close()
            except Exception:
                pass
            self._status_dialog = None

        # 🚨 UWOLNIENIE RYGLA S-1: Odblokowujemy pasek boczny i zakładki okna głównego
        if self.main_window and hasattr(self.main_window, '_set_peripheral_tabs_enabled'):
            self.main_window._set_peripheral_tabs_enabled(True)
            
        self.btn_ext_group.setEnabled(True)
        self.btn_ext_species.setEnabled(True)
        if success: 
            QMessageBox.information(self, "Sukces", f"Wyodrębniono: {filename}")

    def _handle_cell_clicked_preview(self, row, column):
        """Pasywne okno modalne: wyświetla pełną nazwę patogenu z archiwum. 100% stabilności [INDEX]."""
        if column != 3:
            return
            
        item = self.table_widget.item(row, column)
        if not item or not item.text():
            return
            
        full_organism_name = item.text().strip()

        dialog = QDialog(self)
        dialog.setWindowTitle("Archiwalna pełna nazwa taksonomiczna")
        dialog.setMinimumSize(500, 160)
        dialog.setStyleSheet("background-color: #1A1A1A; border: 1px solid #00FF66; border-radius: 4px;")
        
        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.setContentsMargins(20, 20, 20, 20)
        dialog_layout.setSpacing(15)
        
        lbl_name = QLabel(full_organism_name)
        lbl_name.setWordWrap(True) 
        lbl_name.setStyleSheet("color: #00FF66; font-size: 14px; font-weight: bold; font-family: 'Segoe UI', Arial;")
        lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dialog_layout.addWidget(lbl_name)
        
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
