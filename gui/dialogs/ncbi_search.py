# gui/dialogs/ncbi_search.py
# esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
# esummary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

import os
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QLabel
from PyQt6.QtCore import Qt
from core.workspace_manager import WorkspaceManager  # ✅ NOWOŚĆ: Import zarządcy konfiguracji [INDEX]
from config import NCBI_ESEARCH_URL, NCBI_ESUMMARY_URL


class NcbiSearchDialog(QDialog):
    """Wyskakujące okienko modalne (Dialog) do wyszukiwania genomów referencyjnych w bazie NCBI Entrez."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Wyszukiwarka Genomów Referencyjnych NCBI")
        self.setMinimumSize(750, 450)
        self.setModal(True)
        
        # Dziedziczenie ciemnego motywu
        self.setStyleSheet("""
            QDialog { background-color: #121212; border: 1px solid #2C2C2C; }
            QLabel { color: #E0E0E0; font-weight: bold; }
            QLineEdit { background-color: #1E1E1E; border: 1px solid #3A3A3A; border-radius: 4px; padding: 5px; color: #FFFFFF; }
            QPushButton { background-color: #2D2D2D; border: 1px solid #3A3A3A; border-radius: 4px; padding: 6px 15px; font-weight: bold; color: #FFFFFF; }
            QPushButton:hover { background-color: #3D3D3D; border: 1px solid #00FF66; }
            QTableWidget { background-color: #1E1E1E; gridline-color: #2C2C2C; color: #FFFFFF; border: 1px solid #2C2C2C; }
            QHeaderView::section { background-color: #2D2D2D; color: #00FF66; padding: 5px; font-weight: bold; border: 1px solid #2C2C2C; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # 1. PAREK WYSZUKIWANIA
        search_layout = QHBoxLayout()
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Wpisz nazwę organizmu, szczepu lub numer Accession (np. Salmonella enterica)...")
        self.search_field.returnPressed.connect(self._execute_search)
        
        btn_search = QPushButton("Szukaj 🔍")
        btn_search.clicked.connect(self._execute_search)
        
        search_layout.addWidget(self.search_field)
        search_layout.addWidget(btn_search)
        layout.addLayout(search_layout)

        # 2. TABELA WYNIKÓW
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(["Status", "Accession ID", "Nazwa organizmu / Szczep", "Rozmiar (bp)"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.results_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        layout.addWidget(self.results_table)

        # 3. PRZYCISKI STOPKI
        footer_layout = QHBoxLayout()
        footer_layout.addStretch()
        
        btn_cancel = QPushButton("Anuluj")
        btn_cancel.clicked.connect(self.reject)
        
        self.btn_select = QPushButton("Wybierz i użyj 🧬")
        self.btn_select.setEnabled(False)
        self.btn_select.setStyleSheet("background-color: #004d1a; border: 1px solid #00ff66;")
        self.btn_select.clicked.connect(self._accept_selection)
        
        footer_layout.addWidget(btn_cancel)
        footer_layout.addWidget(self.btn_select)
        layout.addLayout(footer_layout)
        
        # Zmienna przechowująca dane o wybranym rekordzie
        self.selected_genome_data = None
        self.results_table.itemSelectionChanged.connect(self._handle_selection_changed)

    def _execute_search(self):
        """
        [ZINTEGROWANY SILNIK INTERNETOWY URLLIB - NAPRAWA FILTRÓW REFSEQ]: 
        Automatycznie wykrywa typ zapytania. W Ścieżce B stosuje rygorystyczny, 
        potrójny iloczyn logiczny AND, odcinając makulaturę shotgun i wymuszając 
        ładowanie czystych, całogenomowych sekwencji NC_ [INDEX].
        """
        import urllib.request
        import urllib.parse
        import re
        import xml.etree.ElementTree as ET

        query = self.search_field.text().strip()
        if not query:
            return
            
        self.results_table.setRowCount(0)

        # 🛡️ DYNAMICZNY ODCZYT ŚCIEŻKI Z PLIKU CONFIG-JSON
        target_library_dir = "/home/ionadmin/kombajn_workspace/references_library"
        try:
            ws = WorkspaceManager(init_system=False)
            current_cfg = ws._read_config_from_disk()
            target_library_dir = current_cfg.get("references_library_dir", target_library_dir).strip()
        except Exception:
            pass

        # WZORZEC REGEX DLA NUMERÓW ACCESSION ID (np. NC_003356, NZ_CP012345)
        accession_pattern = r'^[A-Z]{2,4}_?[0-9]+(\.[0-9]+)?$'
        id_list = []
        is_direct_accession = bool(re.match(accession_pattern, query, re.IGNORECASE))

        try:
            # KROK 1: PRAWIDŁOWY, PEŁNY ADRES INSTYTUCJONALNY ESEARCH
            esearch_base_url = NCBI_ESEARCH_URL
            
            if is_direct_accession:
                # -------------------------------------------------------------
                # ŚCIEŻKA A: Wyszukiwanie bezpośrednie po Accession ID
                # -------------------------------------------------------------
                search_params = {
                    "db": "nuccore",
                    "term": query,
                    "retmode": "xml",
                    "retmax": "1",
                    "tool": "kombajn_t430",
                    "email": "wompmodlin.pdk@ron.mil.pl"
                }
            else:
                # -------------------------------------------------------------
                # ŚCIEŻKA B: ZKORYGOWANY, PANCERNY RYGOR WALIDACJI BIOLOGICZNEJ [INDEX]
                # Zmiana operatora OR na potrójny iloczyn AND ze znacznikami polowymi [PROP] i [TITL].
                # Gwarantuje ładowanie wyłącznie pełnych chromosomów referencyjnych!
                # -------------------------------------------------------------
                search_params = {
                    "db": "nuccore",
                    "term": f"{query}[ORGN] AND \"complete genome\"[TITL] AND srcdb_refseq[PROP]",
                    "retmode": "xml",
                    "retmax": "300", # Zwiększony retmax dla panoramicznego widoku serii
                    "tool": "kombajn_t430",
                    "email": "wompmodlin.pdk@ron.mil.pl"
                }

            # Bezpieczne kodowanie parametrów GET dla urllib
            encoded_params = urllib.parse.urlencode(search_params)
            esearch_url = f"{esearch_base_url}?{encoded_params}"
            
            with urllib.request.urlopen(esearch_url, timeout=10) as response:
                search_xml = response.read()
                
            search_root = ET.fromstring(search_xml)
            id_elements = search_root.findall(".//IdList/Id")
            id_list = [id_el.text for id_el in id_elements if id_el.text]

            if not id_list:
                self.results_table.setRowCount(1)
                item_err = QTableWidgetItem("Nie znaleziono pasujących genomów referencyjnych w NCBI.")
                item_err.setForeground(Qt.GlobalColor.red)
                self.results_table.setItem(0, 2, item_err)
                return

            # -----------------------------------------------------------------
            # KROK INTERNETOWY 2: Pobranie szczegółowych metadanych (ESummary)
            # -----------------------------------------------------------------
            ids_string = ",".join(id_list)
            esummary_base_url = NCBI_ESUMMARY_URL

            summary_params = {
                "db": "nuccore",
                "id": ids_string,
                "retmode": "xml",
                "tool": "kombajn_t430",
                "email": "wompmodlin.pdk@ron.mil.pl"
            }
            
            encoded_summary_params = urllib.parse.urlencode(summary_params)
            esummary_url = f"{esummary_base_url}?{encoded_summary_params}"
            
            with urllib.request.urlopen(esummary_url, timeout=10) as response:
                summary_xml = response.read()
                
            summary_root = ET.fromstring(summary_xml)
            doc_sums = summary_root.findall(".//DocSum")
            
            self.results_table.setRowCount(len(doc_sums))
            
            for idx, doc_sum in enumerate(doc_sums):
                accession_el = doc_sum.find(".//Item[@Name='Caption']")
                accession = accession_el.text.strip() if accession_el is not None else "N/A"
                
                title_el = doc_sum.find(".//Item[@Name='Title']")
                name = title_el.text.strip() if title_el is not None else "Unknown Organism"
                
                # Pobranie surowej wielkości z bazy w parach zasad (bp)
                length_el = doc_sum.find(".//Item[@Name='Length']")
                size_bp = float(length_el.text.strip()) if length_el is not None and length_el.text else 0.0
                
                # DOPASOWANIE ZMIENNYCH: Konwersja par zasad na Mega-bazy (bp -> Mbp)
                size_mbp = size_bp / 1000000.0
                size_str = f"{size_mbp:.2f}"

                # =====================================================================
                # 🛡️ REFORMA MULTI-MASKI V16: PANCERNY INTERLOCK WERYFIKACJI DISKGUARD [INDEX]
                # Całkowicie omijamy kropkę wersji i sprawdzamy kompletną tablicę rozszerzeń ext4!
                # =====================================================================
                clean_acc = accession.split(".")[0].strip() if "." in accession else accession.strip()
                possible_extensions = [".fasta.gz", ".fasta", ".fa.gz", ".fa", ".fna.gz", ".fna"]
                
                is_cached = False
                # Skanujemy i-węzły folderu w locie RAM pod kątem obecności dowolnego formatu [INDEX]
                for ext in possible_extensions:
                    check_path = os.path.join(target_library_dir, f"{clean_acc}{ext}")
                    if os.path.exists(check_path) and os.path.getsize(check_path) > 0:
                        is_cached = True
                        break

                if is_cached:
                    status_text = "W BIBLIOTECE"
                else:
                    status_text = "ONLINE - Do pobrania"

                item_status = QTableWidgetItem(status_text)
                if is_cached:
                    # Wykryto lokalny cache - zapalamy jaskrawą zieleń sukcesu bazy [INDEX]
                    item_status.setForeground(Qt.GlobalColor.green)
                else:
                    item_status.setForeground(Qt.GlobalColor.cyan)
                    
                item_acc = QTableWidgetItem(accession)
                item_name = QTableWidgetItem(name)
                item_size = QTableWidgetItem(size_str)
                
                for item in [item_status, item_acc, item_name, item_size]:
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    
                self.results_table.setItem(idx, 0, item_status)
                self.results_table.setItem(idx, 1, item_acc)
                self.results_table.setItem(idx, 2, item_name)
                
                # Bezpieczne wstrzyknięcie elementu rozmiaru bez ryzyka UnboundLocalError [INDEX]
                self.results_table.setItem(idx, 3, item_size)
                
        except Exception as e:
            self.results_table.setRowCount(1)
            item_err = QTableWidgetItem(f"Błąd jądra sieciowego e-utils: {str(e)}")
            item_err.setForeground(Qt.GlobalColor.red)
            self.results_table.setItem(0, 2, item_err)

    def _handle_selection_changed(self):
        """Aktywuje przycisk akceptacji, gdy użytkownik zaznaczy wiersz."""
        selected_ranges = self.results_table.selectedRanges()
        if selected_ranges:
            self.btn_select.setEnabled(True)
        else:
            self.btn_select.setEnabled(False)

    def _accept_selection(self):
        """
        [ZWERYFIKOWANY INTEGRATOR BATCH V1]: Skanuje tabelę i zbiera metadane 
        DLA WSZYSTKICH zaznaczonych przez operatora wierszy jednocześnie.
        Pakuje je do listy słowników dla masowego rozruchu na Osi M [INDEX].
        """
        self.selected_genomes_list = [] # Zamieniamy pojedynczy słownik na elastyczną listę obiektów
        
        # Pobieramy numery wszystkich unikalnych wierszy, które operator podświetlił myszką
        selected_rows = set()
        for selection_range in self.results_table.selectedRanges():
            for r in range(selection_range.topRow(), selection_range.bottomRow() + 1):
                selected_rows.add(r)
                
        # Przechodzimy pętlą przez zebrane indeksy wierszy i pakujemy je do koszyka RAM
        for row in sorted(selected_rows):
            if row < 0:
                continue
                
            size_mbp_item = self.results_table.item(row, 3)
            raw_bp_reconverted = "0"
            
            if size_mbp_item and size_mbp_item.text():
                try:
                    mbp_value = float(size_mbp_item.text().strip())
                    raw_bp_reconverted = str(int(mbp_value * 1000000))
                except ValueError:
                    raw_bp_reconverted = "0"

            # Wstrzykujemy dane pojedynczego izolatu do paczki zbiorczej
            genome_data = {
                "status": self.results_table.item(row, 0).text() if self.results_table.item(row, 0) else "ONLINE",
                "accession": self.results_table.item(row, 1).text().strip() if self.results_table.item(row, 1) else "N/A",
                "name": self.results_table.item(row, 2).text().strip() if self.results_table.item(row, 2) else "Unknown Organism",
                "size_bp": raw_bp_reconverted
            }
            self.selected_genomes_list.append(genome_data)
            
        if self.selected_genomes_list:
            self.accept() # Zamykamy okno sukcesem tylko gdy koszyk nie jest pusty
