# gui/tabs/view_manager_tab.py
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QGroupBox, QLineEdit)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

# Integracja silników analityczno-obliczeniowych backendu z warstwy core/
from core.comparative_engine import ComparativeEngine
from core.detail_analysis_provider import DetailAnalysisProvider

class ViewManagerTab(QWidget):
    """
    [MASTER-DETAIL HEATMAP DISPLAYER V46.7]: Menedżer wizualizacji matrycy.
    Centralny Hub przeglądu wygenerowanych map ciepła i wyzwalacz szczegółów [2.4].
    """
    def __init__(self):
        super().__init__()
        self.main_window = None
        self.engine = None
        self.current_project_path = None
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)

        # =====================================================================
        # PANEL GÓRNY: SELEKTOR I REJESTR PROJEKTÓW COMP_... (SEKCJA 2B) [2.4]
        # =====================================================================
        top_box = QGroupBox("🖥️ MENEDŻER WYŚWIETLANIA WYNIKÓW MATRYCY KRZYŻOWEJ")
        top_layout = QHBoxLayout(top_box)
        top_layout.setSpacing(10)
        
        top_layout.addWidget(QLabel("📊 Ścieżka aktywnego projektu super-matrycy:"))
        
        self.txt_project_path = QLineEdit()
        self.txt_project_path.setPlaceholderText("Wskaż katalog projektu COMP_YYYYMMDD_HHMMSS...")
        self.txt_project_path.setReadOnly(True)
        self.txt_project_path.setStyleSheet("background-color: #1E1E1E; padding: 4px; color: #00FF66; border: 1px solid #3A3A3A; font-weight: bold;")
        top_layout.addWidget(self.txt_project_path, stretch=8)
        
        self.btn_browse_project = QPushButton("Otwórz Projekt 📁")
        self.btn_browse_project.setStyleSheet("background-color: #2D2D2D; color: #FFFFFF; font-weight: bold; padding: 4px 12px; border: 1px solid #444444;")
        self.btn_browse_project.clicked.connect(self._handle_browse_project_folder)
        top_layout.addWidget(self.btn_browse_project, stretch=2)
        
        main_layout.addWidget(top_box)

        # =====================================================================
        # PANEL ŚRODKOWY: SZKIELET DWUKOLUMNOWY (SEKCJA 2C) [2.4]
        # =====================================================================
        grid_layout = QHBoxLayout()
        grid_layout.setSpacing(15)

        # LEWA KOLUMNA: Lista Próbek Badanych (Oś N)
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("📋 SEKWENCJE BADANE (Oś N):"))

        self.table_samples_n = QTableWidget()
        self.table_samples_n.setColumnCount(3)
        self.table_samples_n.setHorizontalHeaderLabels(["ID Próbki", "Nazwa Szczepu / Projekt", "Gatunek"])
        self.table_samples_n.setStyleSheet("background-color: #1A1A1A; gridline-color: #2C2C2C; color: #FFFFFF; border: 1px solid #2C2C2C;")
        self.table_samples_n.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_samples_n.cellClicked.connect(self._handle_sample_n_cell_clicked)
        
        left_layout.addWidget(self.table_samples_n)
        grid_layout.addWidget(left_container, stretch=4)

        # PRAWA KOLUMNA: Wyniki Dopasowań Referencyjnych (Oś M - Heatmap) [2.4]
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("📊 MATRYCA HOMOLOGII REFERENCYJNEJ (Oś M - Mapa Ciepła):"))

        self.table_results_m = QTableWidget()
        self.table_results_m.setColumnCount(5)
        self.table_results_m.setHorizontalHeaderLabels(["Accession ID", "Organizm / Szczep", "Pokrycie (%)", "Identity (%)", "Ocena Jądra"])
        self.table_results_m.setStyleSheet("background-color: #1A1A1A; gridline-color: #2C2C2C; color: #FFFFFF; border: 1px solid #2C2C2C;")
        self.table_results_m.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_results_m.cellDoubleClicked.connect(self._handle_result_m_cell_double_clicked)
        
        right_layout.addWidget(self.table_results_m)
        grid_layout.addWidget(right_container, stretch=6)
        
        main_layout.addLayout(grid_layout)

        # ✅ WIECZYSTA INSTANCJA BACKENDU: Żyje tak długo jak karta główna
        from core.detail_analysis_provider import DetailAnalysisProvider
        self.detail_provider = DetailAnalysisProvider()

    def _handle_browse_project_folder(self):
        """[THE SECURE VIEW BROWSER - DYNAMIC FALLBACK]: Wymusza start w podfolderze projects z kaskadą awaryjną [INDEX]."""
        from core.explorer import CoreExplorer, ExplorerMode, FilterProfile
        import config

        # KROK 1: Dynamiczne wyznaczenie ścieżki głównej przestrzeni roboczej z modułu konfiguratora [INDEX]
        base_workspace = getattr(config, 'BASE_DATA_DIR', '')
        start_dir = None

        if base_workspace and os.path.exists(base_workspace):
            # KROK 2: Próba budowy i-węzła celowanego dla podfolderu projektów archiwalnych i matryc [INDEX]
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
            folder_path = explorer.get_selected_path()
            if folder_path:
                # Oficjalne wstrzyknięcie zwalidowanej ścieżki do silnika ładowania projektów krzyżowych
                self.load_completed_project(folder_path)

    def load_completed_project(self, project_path: str):
        """[THE CORE PROJECT LOAD TRIGGER]: Inicjuje silnik analityczny matrycy [2.4]."""
        self.current_project_path = project_path
        self.txt_project_path.setText(project_path)
        
        # Powołanie do życia bezwizualnego procesora danych manifestu
        self.engine = ComparativeEngine(project_path)
        
        self.table_samples_n.setRowCount(0)
        self.table_results_m.setRowCount(0)
        self._populate_samples_table()

    def _populate_samples_table(self):
        """[THE SAMPLES AXIS POPULATOR]: Zrzuca wektor próbek pacjentów do lewej tabeli [2.4]."""
        if not self.engine: return
        samples = self.engine.get_samples_axis_n()
        
        self.table_samples_n.setRowCount(len(samples))
        for row_idx, sample in enumerate(samples):
            self.table_samples_n.setItem(row_idx, 0, QTableWidgetItem(sample["sample_id"]))
            self.table_samples_n.setItem(row_idx, 1, QTableWidgetItem(sample["display_label"]))
            self.table_samples_n.setItem(row_idx, 2, QTableWidgetItem(sample["species"]))

    def _handle_sample_n_cell_clicked(self, row, column):
        """[THE DETAILS TRIGGER]: Przechwytuje wybór próbki i inicjuje filtrowanie Osi M [2.4]."""
        if not self.engine: return
        sample_id = self.table_samples_n.item(row, 0).text()
        
        # Pobranie przefiltrowanych dopasowań referencyjnych dla pacjenta
        ref_data = self.engine.get_reference_axis_m_for_sample(sample_id)
        
        self.table_results_m.setRowCount(0)
        self._populate_results_heatmap(ref_data)

    def _populate_results_heatmap(self, ref_data: list):
        """[THE HEATMAP ENGINE V46.7]: Dynamicznie barwi kafelki osi M w locie RAM [2.4]."""
        self.table_results_m.setRowCount(len(ref_data))
        
        for row_idx, item in enumerate(ref_data):
            # Inicjalizacja sterylnych komórek tabeli tekstowej [2.4]
            self.table_results_m.setItem(row_idx, 0, QTableWidgetItem(item["accession_id"]))
            self.table_results_m.setItem(row_idx, 1, QTableWidgetItem(item["organism_name"]))
            self.table_results_m.setItem(row_idx, 2, QTableWidgetItem(item["coverage"]))
            self.table_results_m.setItem(row_idx, 3, QTableWidgetItem(item["identity"]))
            
            # Wstrzyknięcie pełnego kodu oceny i sparowanie linku szczegółowego raportu
            rating_item = QTableWidgetItem(item["rating"])
            rating_item.setData(Qt.ItemDataRole.UserRole, item["results_link"])
            self.table_results_m.setItem(row_idx, 4, rating_item)
            
            # 🎨 STERYLNY INTERLOCK BARWNY: Aplikacja kolorów odziedziczonych z jądra [2.4]
            bg = QColor(item["bg_color"])
            fg = QColor(item["fg_color"])
            for col_idx in range(5):
                cell = self.table_results_m.item(row_idx, col_idx)
                cell.setBackground(bg)
                cell.setForeground(fg)

    def _handle_result_m_cell_double_clicked(self, row, column):
        """[THE FULLSCREEN DIAGNOSTIC INTERLOCK]: Wyciąga jawny powód awarii binaru [INDEX]."""
        rating_item = self.table_results_m.item(row, 4)
        if not rating_item:
            return
        
        pair_metrics_json = rating_item.data(Qt.ItemDataRole.UserRole)
        if not pair_metrics_json or not os.path.exists(pair_metrics_json):
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Błąd wejścia/wyjścia", f"Brak pliku metryk pary:\n{pair_metrics_json}")
            return
            
        project_dir = os.path.dirname(pair_metrics_json)
        blast_gz_path = os.path.join(project_dir, "blast_identity.tsv.gz")
        
        if not os.path.exists(blast_gz_path) or os.path.getsize(blast_gz_path) == 0:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self, 
                "Krytyczny błąd I/O", 
                "Baza zmian .tsv.gz nie istnieje lub jest uszkodzona (0 bajtów).\nOtwarcie okna zablokowane ze względów bezpieczeństwa."
            )
            return

        # 🚀 SEKWENCJA DIAGNOSTYCZNA KROK 2: Pobranie krotki (Status, Komunikat błędu) z backendu
        success, error_details = self.detail_provider.prepare_ramdisk_source(pair_metrics_json)
        if success:
            self._open_fullscreen_analysis_window(pair_metrics_json)
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "Krytyczny błąd dekompresji ASN.1",
                f"Nie udało się rozpakować potoku do bufora /dev/shm/.\n\n"
                f"🧬 RAPORT BŁĘDU BACKENDU:\n{error_details}\n\n"
                f"Zweryfikuj ścieżki i i-węzły środowiska Kombajnu T430."
            )

    def _open_fullscreen_analysis_window(self, json_path: str):
        """[THE ATOMIC LINEAR ALLOCATOR]: Blokuje wątek za pomocą .exec() i sprząta PO zamknięciu okna."""
        from gui.dialogs.analysis_detail_window import AnalysisDetailWindow
        
        # Przekazanie wieczystego dostawcy jako parametr wejściowy konstruktora okna
        self.detail_window = AnalysisDetailWindow(json_path, self.detail_provider, parent=self)
        self.detail_window.setWindowModality(Qt.WindowModality.ApplicationModal)
        
        # 🔒 LOCK POSIX: .exec() zamraża wykonywanie tego bloku kodu w locie RAM
        self.detail_window.exec()
        
        # 🧼 SEKWENCJA I/O KROK 6: Oczyszczenie RAM-dysku następuje jawnym rozkazem PO zamknięciu okna
        self.detail_provider.clear_ramdisk_buffer()
