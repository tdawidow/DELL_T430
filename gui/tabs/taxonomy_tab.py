# gui/tabs/taxonomy_tab.py
import os
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit,
                             QTableWidget, QTableWidgetItem, QPushButton, QHeaderView, QMessageBox, QDialog)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView
from pipeline.parsers import KrakenParser
import config

class TaxonomyTab(QWidget):
    """Karta 2: Wizualizacja metagenomiki - odfiltrowana tabela Kraken2 oraz interaktywne koła Krona."""
    
    def __init__(self):
        super().__init__()
        self.active_report_txt = None
        self.local_override_threshold = None
        
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # =====================================================================
        # LEWA STRONA: TABELA GATUNKÓW KRAKEN2
        # =====================================================================
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        filter_control_layout = QHBoxLayout()
        
        start_threshold = getattr(config, 'KRAKEN_NOISE_THRESHOLD', 0.1)
        self.table_title = QLabel(f"🦠 WYKRYTE TAKSONY (> {start_threshold}%):")
        self.table_title.setStyleSheet("font-weight: bold; color: #00FF66; font-size: 13px;")
        filter_control_layout.addWidget(self.table_title)
        
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
            QHeaderView::section { background-color: #2D2D2D; color: #00FF66; padding: 6px; font-weight: bold; border: 1px solid #2C2C2C; }
        """)
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        left_layout.addWidget(self.table_widget)
        main_layout.addWidget(left_container, stretch=4)
#paczka 2
        # =====================================================================
        # PRAWA STRONA: RAPORT KRONA HTML (ZAKODOWANE WYRÓWNANIE DO GÓRY)
        # =====================================================================
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        krona_title = QLabel("📊 INTERAKTYWNE KOŁA KRONA HTML:")
        krona_title.setStyleSheet("font-weight: bold; color: #00FF66; font-size: 14px;")
        right_layout.addWidget(krona_title)

        self.krona_view = QWebEngineView()
        self.krona_view.setStyleSheet("border: 1px solid #2C2C2C; border-radius: 4px;")
        
        settings = self.krona_view.settings()
        settings.setAttribute(settings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(settings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(settings.WebAttribute.LocalContentCanAccessFileUrls, True)
        
        self.krona_view.setFixedHeight(450)
        right_layout.addWidget(self.krona_view)

        self.btn_open_external = QPushButton("Otwórz Krona w przeglądarce systemowej 🌐")
        self.btn_open_external.setEnabled(False)
        self.btn_open_external.setStyleSheet("""
            QPushButton { background-color: #1E2D2F; color: #0099FF; border: 1px solid #0099FF; padding: 6px; }
            QPushButton:hover { background-color: #253F44; }
        """)
        self.btn_open_external.clicked.connect(self._open_krona_external)
        right_layout.addWidget(self.btn_open_external)

        right_layout.addStretch()
        main_layout.addWidget(right_container, stretch=6)

        # PANCERNY FUNKCJONALNY ZAPIS: Podpięcie zdarzenia kliknięcia TYLKO RAZ w __init__ [INDEX]
        self.table_widget.cellClicked.connect(self._handle_cell_clicked_preview)

    def reset_tab_for_new_run(self):
        """
        [PANCERNE CZYSZCZENIE STANÓW]: Całkowicie resetuje pamięć lokalną RAM 
        oraz widżety karty taksonomii przed nowym biegiem laboratoryjnym. 
        Gwarantuje 0% ryzyka pomyłkowego wyświetlenia starych wyników.
        """
        # 1. Zerowanie zmiennych cache w locie pamięci RAM
        self.active_report_txt = None
        self.local_override_threshold = None
        
        # 2. Przywrócenie domyślnego nagłówka z pliku konfiguracyjnego
        start_threshold = getattr(config, 'KRAKEN_NOISE_THRESHOLD', 0.1)
        self.table_title.setText(f"🦠 WYKRYTE TAKSONY (> {start_threshold}%):")
        self.txt_local_threshold.setText(str(start_threshold))
        
        # 3. Atomowe wyczyszczenie wierszy wbudowanej tabeli
        self.table_widget.setRowCount(0)
        
        # 4. Załadowanie czystej karty do silnika Chromium, aby wymazać stare koło Krona
        self.krona_view.setUrl(QUrl("about:blank"))
        
        # 5. Wygaszenie przycisku pełnoekranowego do stanu fabrycznego
        self.btn_open_external.setEnabled(False)

    def get_active_threshold(self) -> float:
        try:
            return float(self.txt_local_threshold.text().strip())
        except ValueError:
            return getattr(config, 'KRAKEN_NOISE_THRESHOLD', 0.1)

    def populate_kraken_table(self, filtered_rows: list):
        """Zasila tabelę odfiltrowanymi danymi i automatycznie synchronizuje tymczasowe filtry [INDEX]."""
        active_threshold = self.get_active_threshold()
        self.table_title.setText(f"🦠 WYKRYTE TAKSONY (> {active_threshold}%):")

        # Czysty, bezawaryjny start odczytu pliku raportu z dysku [INDEX]
        if self.active_report_txt and os.path.exists(self.active_report_txt):
            filtered_rows = KrakenParser.parse_kraken_report(self.active_report_txt, threshold=active_threshold)

        self.table_widget.setRowCount(0)
        self.table_widget.setRowCount(len(filtered_rows))
        
        for row_idx, data in enumerate(filtered_rows):
            item_percent = QTableWidgetItem(f"{data['percent']}%")
            item_reads = QTableWidgetItem(str(data['reads']))
            item_taxid = QTableWidgetItem(str(data['taxid']))
            item_name = QTableWidgetItem(data['name'])
            
            for item in [item_percent, item_reads, item_taxid, item_name]:
                item.setFlags(item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                
            item_percent.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_reads.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_taxid.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            
            self.table_widget.setItem(row_idx, 0, item_percent)
            self.table_widget.setItem(row_idx, 1, item_reads)
            self.table_widget.setItem(row_idx, 2, item_taxid)
            self.table_widget.setItem(row_idx, 3, item_name)

    def _handle_apply_local_filter(self):
        """Pobiera chwilowy próg i odświeża tabelę zarówno przed, jak i po analizie [INDEX]."""
        try:
            local_val = float(self.txt_local_threshold.text().strip())
        except ValueError:
            QMessageBox.critical(self, "Niepoprawny format", "Wpisany próg musi być liczbą zmiennoprzecinkową (np. 0.05)!")
            return
            
        self.local_override_threshold = local_val
        self.table_title.setText(f"🦠 WYKRYTE TAKSONY (> {local_val}%):")
        
        if not self.active_report_txt or not os.path.exists(self.active_report_txt):
            return
            
        refiltered_rows = KrakenParser.parse_kraken_report(self.active_report_txt, threshold=local_val)
        
        self.table_widget.setRowCount(0)
        self.table_widget.setRowCount(len(refiltered_rows))
        for row_idx, data in enumerate(refiltered_rows):
            item_percent = QTableWidgetItem(f"{data['percent']}%")
            item_reads = QTableWidgetItem(str(data['reads']))
            item_taxid = QTableWidgetItem(str(data['taxid']))
            item_name = QTableWidgetItem(data['name'])
            for item in [item_percent, item_reads, item_taxid, item_name]:
                item.setFlags(item.flags() ^ Qt.ItemFlag.ItemIsEditable)
            item_percent.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_reads.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_taxid.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            self.table_widget.setItem(row_idx, 0, item_percent)
            self.table_widget.setItem(row_idx, 1, item_reads)
            self.table_widget.setItem(row_idx, 2, item_taxid)
            self.table_widget.setItem(row_idx, 3, item_name)

    def load_krona_chart(self, html_file_path: str):
        """PANCERNE ŁADOWANIE: Sprawdza alternatywne nazwy plików HTML, aby zapobiec zniknięciu Krony [INDEX]."""
        if not html_file_path:
            return

        base_dir = os.path.dirname(html_file_path)
        actual_html = html_file_path
        
        if not os.path.exists(actual_html):
            alt_name = "krona_chart.html" if "krona_report.html" in html_file_path else "krona_report.html"
            actual_html = os.path.join(base_dir, alt_name)

        if os.path.exists(actual_html):
            self.krona_view.setUrl(QUrl.fromLocalFile(os.path.abspath(actual_html)))
            self.btn_open_external.setEnabled(True)
            
            potential_report = os.path.join(base_dir, "kraken_report.txt")
            if os.path.exists(potential_report):
                self.active_report_txt = potential_report

            self.populate_kraken_table([])

    def _open_krona_external(self):
        """
        [PANCERNY STANDARD WORKFLOW - WZÓR QUAST]: Otwiera interaktywne koło Krona 
        we wbudowanym, osobnym oknie modalnym programu. Pobiera dane bezpośrednio 
        z fizycznego pliku na dysku NVMe, gwarantując 100% stabilności wielozadaniowej.
        """
        # 1. Sprawdzenie, czy mamy zarejestrowaną ścieżkę do aktywnego raportu
        if not self.active_report_txt or not os.path.exists(self.active_report_txt):
            QMessageBox.warning(self, "Brak danych", "Nie odnaleziono pliku raportu na dysku NVMe!")
            return

        # 2. KONWERSJA ŚCIEŻKI W RAM: Wyliczamy bezwzględną lokalizację pliku HTML w podfolderze
        base_dir = os.path.dirname(self.active_report_txt)
        krona_html_path = os.path.join(base_dir, "krona_report.html")

        # Fallback bezpieczeństwa na alternatywną nazwę pliku wykresu
        if not os.path.exists(krona_html_path):
            krona_html_path = os.path.join(base_dir, "krona_chart.html")

        # 3. ROZRUCH OKNA MODALNEGO: Wykonuje się wyłącznie, gdy plik fizycznie istnieje na dysku
        if os.path.exists(krona_html_path):
            dialog = QDialog(self)
            dialog.setWindowTitle("Pełnoekranowy Raport Metagenomiczny Krona HTML")
            dialog.setMinimumSize(1100, 800)
            dialog.setStyleSheet("background-color: #1A1A1A; border: 1px solid #2C2C2C;")
            
            dialog_layout = QVBoxLayout(dialog)
            dialog_layout.setContentsMargins(0, 0, 0, 0)
            
            # TWARDE RODZICIELSTWO C++: Przeglądarka jest jednorazowym dzieckiem okna dialogowego
            web_browser = QWebEngineView(dialog)
            
            # Aktywacja natywnych zabezpieczeń Chromium dla prawidłowego renderu
            settings = web_browser.settings()
            settings.setAttribute(settings.WebAttribute.JavascriptEnabled, True)
            settings.setAttribute(settings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            settings.setAttribute(settings.WebAttribute.LocalContentCanAccessFileUrls, True)
            
            # Bezpieczne ładowanie adresu URL prosto z nośnika NVMe
            web_browser.setUrl(QUrl.fromLocalFile(os.path.abspath(krona_html_path)))
            
            dialog_layout.addWidget(web_browser)
            
            # Uruchomienie okna w odizolowanej pętli zdarzeń aplikacji
            dialog.exec()
        else:
            QMessageBox.critical(
                self, 
                "Błąd odczytu", 
                f"Nie odnaleziono interaktywnego wykresu HTML w katalogu analizy!\nOczekiwana ścieżka:\n{krona_html_path}"
            )

    def _handle_cell_clicked_preview(self, row, column):
        """Czyste, pasywne okno modalne: wyświetla pełną nazwę patogenu. 100% stabilności bez wątków w tle [INDEX]."""
        # Interesuje nas wyłącznie kolumna 3, która zawiera nazwy organizmów
        if column != 3:
            return
            
        item = self.table_widget.item(row, column)
        if not item or not item.text():
            return
            
        full_organism_name = item.text().strip()

        # Tworzenie dynamicznego, w pełni skalowalnego okna dialogowego Qt [INDEX]
        dialog = QDialog(self)
        dialog.setWindowTitle("Pełna nazwa taksonomiczna patogenu")
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
