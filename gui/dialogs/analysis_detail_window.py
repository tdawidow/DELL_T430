# gui/dialogs/analysis_detail_window.py
import os
import json
import gzip
from PyQt6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QTableView, QScrollArea)
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QCoreApplication
from PyQt6.QtGui import QFont, QColor, QBrush
from PyQt6.QtCharts import QChart, QChartView, QPieSeries, QLineSeries, QValueAxis

class VerticalAlignmentModel(QAbstractTableModel):
    """[THE VIRTUAL NUCLEOTIDE MATRIX MODEL - V3.1]: Wirtualna matryca z dynamicznym podświetleniem mutacji."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._matrix_data = []
        self.headers = ["Poz. Query", "Sample (Próbka)", "Homologia", "Reference", "Poz. Sbjct"]
        self.highlighted_row = -1

    def rowCount(self, parent=QModelIndex()):
        return len(self._matrix_data)

    def columnCount(self, parent=QModelIndex()):
        return 5

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.headers[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._matrix_data)):
            return None
            
        row = index.row()
        col = index.column()
        row_data = self._matrix_data[row]
        is_active_mutation = (row == self.highlighted_row)

        if role == Qt.ItemDataRole.DisplayRole:
            return row_data[col]

        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter

        if role == Qt.ItemDataRole.FontRole:
            font = QFont("Monospace", 10)
            if is_active_mutation:
                font.setBold(True)
            return font

        if role == Qt.ItemDataRole.BackgroundRole:
            if is_active_mutation and col in (0, 2, 4):
                return QBrush(QColor("#FFF3CD"))
                
            if col in (1, 3):
                base = str(row_data[col]).upper()
                if base == 'A': return QBrush(QColor("#C6F6D5"))
                elif base == 'T': return QBrush(QColor("#FED7D7"))
                elif base == 'C': return QBrush(QColor("#BEE3F8"))
                elif base == 'G': return QBrush(QColor("#FEFCBF"))
                elif base == 'N': return QBrush(QColor("#E2E8F0"))
            return QBrush(QColor("#FFFFFF"))

        if role == Qt.ItemDataRole.ForegroundRole:
            if is_active_mutation and col in (0, 2, 4):
                return QBrush(QColor("#856404"))
                
            if col in (1, 3):
                base = str(row_data[col]).upper()
                if base == 'A': return QBrush(QColor("#22543D"))
                elif base == 'T': return QBrush(QColor("#742A2A"))
                elif base == 'C': return QBrush(QColor("#2B6CB0"))
                elif base == 'G': return QBrush(QColor("#744210"))
                elif base == 'N': return QBrush(QColor("#4A5568"))
            elif col == 2:
                symbol = row_data[col]
                if symbol == "<===>": return QBrush(QColor("#00802B"))
                elif symbol == "<xxx>": return QBrush(QColor("#E53E3E"))
            return QBrush(QColor("#1A202C"))

        return None

    def set_highlighted_row(self, row_idx: int):
        old_row = self.highlighted_row
        self.highlighted_row = row_idx
        if old_row != -1:
            self.dataChanged.emit(self.index(old_row, 0), self.index(old_row, 4))
        if row_idx != -1:
            self.dataChanged.emit(self.index(row_idx, 0), self.index(row_idx, 4))

    def update_data(self, new_matrix):
        self.beginResetModel()
        self._matrix_data = new_matrix
        self.endResetModel()

class AnalysisDetailWindow(QDialog):
    """[THE 4-PANEL TELEMETRY SLUICE V55.0]: Całkowicie zreorganizowany interfejs master-detail [2.4]."""
    def __init__(self, pair_metrics_json: str, provider_instance, parent=None):
        super().__init__(parent)
        from PyQt6.QtGui import QPainter
        
        self.metrics_json_path = os.path.abspath(pair_metrics_json)
        self.metrics_data = {}
        self.provider = provider_instance
        self.current_contig_id = None

        self.setWindowTitle("Pancerna Śluza Szczegółowej Analizy Epidemiologicznej")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowMaximizeButtonHint | Qt.WindowType.WindowCloseButtonHint)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)
        
        self.lbl_header_info = QLabel("Dekodowanie struktur i-węzłów paszportu z manifestu... [2.4]")
        self.lbl_header_info.setStyleSheet("font-size: 12px; font-weight: bold; color: #00FF66; background-color: #11141A; padding: 6px; border: 1px solid #2C323F; border-radius: 4px;")
        self.lbl_header_info.setWordWrap(True)
        main_layout.addWidget(self.lbl_header_info)
        
        vertical_splitter_layout = QVBoxLayout()
        vertical_splitter_layout.setSpacing(12)
        
        # =====================================================================
        # ──────── S E K C J A   G Ó R N A   ( 1 / 3   W Y S O K O Ś C I ) ─────
        # =====================================================================
        top_section_layout = QHBoxLayout()
        top_section_layout.setSpacing(12)
        
        p1_container = QWidget()
        p1_layout = QVBoxLayout(p1_container)
        p1_layout.setContentsMargins(0, 0, 0, 0)
        p1_layout.setSpacing(4)
        p1_layout.addWidget(QLabel("📋 PANEL 1: LISTA KONTIGÓW IZOLATU (Z pliku coords.gz):"))
        
        self.contigs_table = QTableWidget()
        self.contigs_table.setColumnCount(3)
        self.contigs_table.setHorizontalHeaderLabels(["ID Contigu", "Długość (bp)", "Mummer Cov %"])
        self.contigs_table.setStyleSheet("background-color: #1A1A1A; gridline-color: #2C2C2C; color: #FFFFFF; border: 1px solid #2C2C2C;")
        
        self.contigs_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.contigs_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.contigs_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        
        self.contigs_table.itemClicked.connect(self._handle_contig_row_selected)
        p1_layout.addWidget(self.contigs_table)
        top_section_layout.addWidget(p1_container, stretch=4)
        
        p2_container = QWidget()
        p2_layout = QVBoxLayout(p2_container)
        p2_layout.setContentsMargins(0, 0, 0, 0)
        p2_layout.setSpacing(4)
        p2_layout.addWidget(QLabel("📊 PANEL 2: LABORATORYJNE WSKAŹNIKI ZGODNOŚCI:"))
        
        charts_row = QHBoxLayout()
        charts_row.setSpacing(8)
        
        cov_box = QVBoxLayout()
        self.chart_view_cov = QChartView()
        self.chart_view_cov.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.chart_view_cov.setStyleSheet("border: 1px solid #2C2C2C; background-color: #1A1A1A;")
        self.lbl_chart_cov_title = QLabel("BREADTH OF COVERAGE")
        self.lbl_chart_cov_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_chart_cov_title.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 11px;")
        cov_box.addWidget(self.chart_view_cov, stretch=9)
        cov_box.addWidget(self.lbl_chart_cov_title, stretch=1)
        
        id_box = QVBoxLayout()
        self.chart_view_id = QChartView()
        self.chart_view_id.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.chart_view_id.setStyleSheet("border: 1px solid #2C2C2C; background-color: #1A1A1A;")
        self.lbl_chart_id_title = QLabel("GLOBAL IDENTITY (ANI)")
        self.lbl_chart_id_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_chart_id_title.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 11px;")
        id_box.addWidget(self.chart_view_id, stretch=9)
        id_box.addWidget(self.lbl_chart_id_title, stretch=1)
        
        charts_row.addLayout(cov_box)
        charts_row.addLayout(id_box)
        p2_layout.addLayout(charts_row)
        top_section_layout.addWidget(p2_container, stretch=6)
        
        vertical_splitter_layout.addLayout(top_section_layout, stretch=1)
        
        # =====================================================================
        # ──────── S E K C J A   D O L N A   ( 2 / 3   W Y S O K O Ś C I ) ─────
        # =====================================================================
        bottom_section_layout = QHBoxLayout()
        bottom_section_layout.setSpacing(12)
        
        p4_container = QWidget()
        p4_layout = QVBoxLayout(p4_container)
        p4_layout.setContentsMargins(0, 0, 0, 0)
        p4_layout.setSpacing(4)
        p4_layout.addWidget(QLabel("📈 PANEL 4: PROFIL MAPOWANIA LINIOWEHO (Oś X-Przewijana dla bakterii/grzybów):"))
        
        self.scroll_area_chart = QScrollArea()
        self.scroll_area_chart.setWidgetResizable(True)
        self.scroll_area_chart.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.scroll_area_chart.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area_chart.setStyleSheet("background-color: #1A1A1A; border: 1px solid #2C2C2C;")
        
        self.chart_view_profile = QChartView()
        self.chart_view_profile.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.scroll_area_chart.setWidget(self.chart_view_profile)
        
        p4_layout.addWidget(self.scroll_area_chart)
        bottom_section_layout.addWidget(p4_container, stretch=4)
        
        p3_container = QWidget()
        p3_layout = QVBoxLayout(p3_container)
        p3_layout.setContentsMargins(0, 0, 0, 0)
        p3_layout.setSpacing(4)
        p3_layout.addWidget(QLabel("🧬 PANEL 3: PIONOWY PODGLĄD STRUKTURY NUKLEOTYDÓW (Zero szukania - Direct Hashing):"))
        
        self.alignment_view = QTableView()
        self.alignment_model = VerticalAlignmentModel()
        self.alignment_view.setModel(self.alignment_model)
        self.alignment_view.setFont(QFont("Monospace", 10))
        self.alignment_view.setStyleSheet("gridline-color: #E2E8F0; border: 1px solid #CBD5E0; background-color: #FFFFFF;")
        self.alignment_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.alignment_view.verticalHeader().setVisible(False)
        self.alignment_view.verticalHeader().setDefaultSectionSize(16)
        
        p3_layout.addWidget(self.alignment_view)
        bottom_section_layout.addWidget(p3_container, stretch=6)
        
        vertical_splitter_layout.addLayout(bottom_section_layout, stretch=2)
        main_layout.addLayout(vertical_splitter_layout)
        
        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch()
        btn_close = QPushButton("Zamknij Śluzę Analizy Szczegółowej ❌")
        btn_close.setStyleSheet("background-color: #2D3748; color: #FFFFFF; font-weight: bold; padding: 6px 20px; border: 1px solid #4A5568; border-radius: 4px;")
        btn_close.clicked.connect(self.close)
        bottom_bar.addWidget(btn_close)
        main_layout.addLayout(bottom_bar)

        self.showMaximized()
        self._load_metrics_and_populate_window()

    def _load_metrics_and_populate_window(self):
        """[THE CORE PASSPORT EXTRACTOR]: Odkodowuje manifest i siłowo wstrzykuje nazwy laboratoryjne [2.4]."""
        if not os.path.exists(self.metrics_json_path):
            self.lbl_header_info.setText("❌ BŁĄD SYSTEMOWY: Plik metryk pary nie istnieje!")
            return
            
        try:
            with open(self.metrics_json_path, 'r', encoding='utf-8') as f:
                self.metrics_data = json.load(f)
        except Exception as e:
            self.lbl_header_info.setText(f"❌ BŁĄD KORUPCJI STRUCT JSON: {str(e)}")
            return

        project_dir = os.path.dirname(self.metrics_json_path)
        resolved_sample_name = "Nieznany Izolat Pacjenta"
        resolved_reference_name = "Severe acute respiratory syndrome coronavirus 2 complete genome"
        
        # DEKODOWANIE PASZPORTU: Przejście 3 poziomy w górę do nadrzędnego manifestu super-matrycy [2.4]
        parent_project_dir = os.path.abspath(os.path.join(project_dir, "../../../"))
        master_manifest_path = os.path.join(parent_project_dir, ".matrix_master_manifest.json")
        
        meta = self.metrics_data.get("pair_metadata", {})
        pair_key = meta.get("pair_key", "SAMPLE_001_vs_NC_045512")
        sample_id, acc_id = pair_key.split("_vs_") if "_vs_" in pair_key else ("SAMPLE_001", "NC_045512")

        if os.path.exists(master_manifest_path):
            try:
                with open(master_manifest_path, "r", encoding="utf-8") as mm_f:
                    m_data = json.load(mm_f)
                    passport = m_data.get("matrix_sample_passport", {})
                    if sample_id in passport:
                        resolved_sample_name = passport[sample_id].get("operator_display_label", resolved_sample_name)
                        
                    grid = m_data.get("matrix_grid", [])
                    for task in grid:
                        if task.get("pair_key") == pair_key:
                            resolved_reference_name = task.get("reference_context", {}).get("organism_full_name", resolved_reference_name)
                            break
            except Exception:
                pass

        eval_m = self.metrics_data.get("biological_evaluation", {})
        status_txt = eval_m.get("evaluation_status", "🔴 UNKNOWN")
        
        self.lbl_header_info.setText(
            f"🧬 IZOLAT PACJENTA: {resolved_sample_name}\n"
            f"🔬 REFERENCJA NCBI: {resolved_reference_name} [ID: {acc_id}]  │  OCENA: {status_txt}"
        )
        
        self._render_pie_charts_homology()
        self._populate_contigs_table_from_coords()

    def _render_pie_charts_homology(self):
        """[THE MAXIMIZED PIE ENGINE]: Rozciąga tarcze kół do wartości 0.95 z napisami pod spodem [2.4]."""
        mummer_m = self.metrics_data.get("mummer_global_metrics", {})
        blast_m = self.metrics_data.get("blastn_local_metrics", {})
        
        cov_val = float(mummer_m.get("coverage", 0.0))
        id_val = float(blast_m.get("pident", 0.0)) if blast_m.get("blastn_status") == "COMPLETED" else float(mummer_m.get("ani", 0.0))
        
        # WYKRES A: MAKSYMALIZACJA KOŁA POKRYCIA
        series_cov = QPieSeries()
        slice_cov_active = series_cov.append("Pokryte", cov_val)
        slice_cov_remain = series_cov.append("Brak", max(0.0, 100.0 - cov_val))
        slice_cov_active.setBrush(QColor("#48BB78"))
        slice_cov_remain.setBrush(QColor("#2D3748"))
        
        # Wymuszenie siłowego rozciągnięcia struktury wektorowej koła do krawędzi kontenera [2.4]
        series_cov.setPieSize(0.95)
        
        chart_cov = QChart()
        chart_cov.addSeries(series_cov)
        chart_cov.setBackgroundBrush(QBrush(QColor("#1A1A1A")))
        chart_cov.legend().setVisible(False)
        self.chart_view_cov.setChart(chart_cov)
        self.lbl_chart_cov_title.setText(f"BREADTH OF COVERAGE: {cov_val:.2f}%")
        
        # WYKRES B: MAKSYMALIZACJA KOŁA TOŻSAMOŚCI ANI
        series_id = QPieSeries()
        slice_id_active = series_id.append("Zgodne", id_val)
        slice_id_remain = series_id.append("Polimorfizmy", max(0.0, 100.0 - id_val))
        slice_id_active.setBrush(QColor("#0099FF"))
        slice_id_remain.setBrush(QColor("#E53E3E"))
        
        series_id.setPieSize(0.95)
        
        chart_id = QChart()
        chart_id.addSeries(series_id)
        chart_id.setBackgroundBrush(QBrush(QColor("#1A1A1A")))
        chart_id.legend().setVisible(False)
        self.chart_view_id.setChart(chart_id)
        self.lbl_chart_id_title.setText(f"GLOBAL IDENTITY (ANI): {id_val:.2f}%")

    def _populate_contigs_table_from_coords(self):
        """[FAST COORDS PARSER]: Ładuje listę contigów bezpośrednio ze spakowanego raportu [2.4]."""
        self.contigs_table.setRowCount(0)
        project_dir = os.path.dirname(self.metrics_json_path)
        coords_gz_path = os.path.join(project_dir, "mummer_run.coords.gz")
        
        if not os.path.exists(coords_gz_path):
            self.contigs_table.setRowCount(1)
            self.contigs_table.setItem(0, 0, QTableWidgetItem("❌ Brak mummer_run.coords.gz"))
            return
            
        try:
            detected_contigs = {}
            with gzip.open(coords_gz_path, 'rt', encoding='utf-8') as f:
                for line in f:
                    cleaned = line.strip()
                    if not cleaned: continue
                    parts = cleaned.split('\t')
                    if len(parts) >= 12:
                        try:
                            int(parts[0].strip())
                            c_id = parts[11].strip()
                            aligned_len = int(parts[4].strip())
                            c_cov_pct = float(parts[10].strip())
                            
                            if c_id not in detected_contigs:
                                detected_contigs[c_id] = {"length": aligned_len, "cov": c_cov_pct}
                            else:
                                detected_contigs[c_id]["length"] += aligned_len
                        except ValueError:
                            continue
                            
            self.contigs_table.setRowCount(len(detected_contigs))
            for row_idx, (c_id, info) in enumerate(sorted(detected_contigs.items())):
                item_id = QTableWidgetItem(c_id)
                item_id.setData(Qt.ItemDataRole.UserRole, c_id)
                self.contigs_table.setItem(row_idx, 0, item_id)
                self.contigs_table.setItem(row_idx, 1, QTableWidgetItem(str(info["length"])))
                self.contigs_table.setItem(row_idx, 2, QTableWidgetItem(f"{info['cov']:.2f}%"))
                
            if self.contigs_table.rowCount() > 0:
                self.contigs_table.selectRow(0)
                self._handle_contig_row_selected(self.contigs_table.item(0, 0))
        except Exception as e:
            self.contigs_table.setRowCount(1)
            self.contigs_table.setItem(0, 0, QTableWidgetItem(f"❌ Błąd I/O: {str(e)}"))

    def _handle_contig_row_selected(self, item):
        """[THE ASYNCHRONOUS VIEWPORT DISPATCHER]: Zarządza synchronizacją profilu 2D i taśmy RAM [2.4]."""
        row = item.row()
        id_cell = self.contigs_table.item(row, 0)
        if not id_cell: return
        
        contig_id = id_cell.data(Qt.ItemDataRole.UserRole)
        self.current_contig_id = contig_id
        
        # 1. Aktualizacja Panelu 4: Rysowanie wykresu pokrycia liniowego 2D dla contigu
        self._render_linear_coverage_chart_2d(contig_id)
        
        # 2. Aktualizacja Panelu 3: Wirtualny wtrysk liter do pionowej taśmy
        self._render_virtual_alignment_ribbon(contig_id)

    def _render_linear_coverage_chart_2d(self, contig_id: str):
        """[THE LINE CHART ENGINE - X-SORT FIX]: Sortuje punkty rosnąco po osi X, eliminując pętle wykresu [2.4]."""
        project_dir = os.path.dirname(self.metrics_json_path)
        coords_gz_path = os.path.join(project_dir, "mummer_run.coords.gz")
        
        series = QLineSeries()
        raw_points = []
        max_x = 0
        
        if os.path.exists(coords_gz_path):
            try:
                with gzip.open(coords_gz_path, 'rt', encoding='utf-8') as f:
                    for line in f:
                        cleaned = line.strip()
                        if not cleaned: continue
                        parts = cleaned.split('\t')
                        if len(parts) >= 12 and parts[11].strip() == contig_id:
                            try:
                                q_start = int(parts[0].strip())
                                q_end = int(parts[1].strip())
                                c_cov = float(parts[6].strip())
                                
                                # Gromadzimy punkty jako krotki w tymczasowej liście RAM do posortowania [2.4]
                                raw_points.append((q_start, c_cov))
                                raw_points.append((q_end, c_cov))
                                
                                if q_end > max_x: max_x = q_end
                            except ValueError: continue
            except Exception: pass

        # 🧼 KROK CHIRURGICZNY: Bezwarunkowe sortowanie punktów rosnąco po współrzędnej X (Indeks 0) [2.4]
        raw_points.sort(key=lambda pt: pt[0])
        
        # Wstrzyknięcie uporządkowanych chronologicznie punktów do serii, co trwale likwiduje cofanie się wykresu [2.4]
        for x, y in raw_points:
            series.append(x, y)

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle(f"PROFIL POKRYCIA LINIOWEGO CONTIGU: {contig_id}")
        chart.setBackgroundBrush(QBrush(QColor("#11141A")))
        chart.setTitleBrush(QBrush(QColor("#FFFFFF")))
        chart.legend().setVisible(False)
        
        if max_x > 1000000:
            self.chart_view_profile.setFixedWidth(4000)
            axis_x_label = "Pozycja w genomie (Mbp)"
        elif max_x > 50000:
            self.chart_view_profile.setFixedWidth(2000)
            axis_x_label = "Pozycja w genomie (Kbp)"
        else:
            self.chart_view_profile.setFixedWidth(self.scroll_area_chart.width() - 20)
            axis_x_label = "Pozycja w genomie (bp)"

        axis_x = QValueAxis()
        axis_x.setRange(0, max_x)
        axis_x.setTitleText(axis_x_label)
        axis_x.setLabelsColor(QColor("#FFFFFF"))
        axis_x.setTitleBrush(QBrush(QColor("#FFFFFF")))
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)
        
        axis_y = QValueAxis()
        axis_y.setTickCount(5)
        axis_y.setRange(0, 100.0)
        axis_y.setTitleText("Pokrycie / Głębokość Mapowania %")
        axis_y.setLabelsColor(QColor("#FFFFFF"))
        axis_y.setTitleBrush(QBrush(QColor("#FFFFFF")))
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)
        
        self.chart_view_profile.setChart(chart)


    def _render_virtual_alignment_ribbon(self, contig_id: str):
        """[THE DIRECT-INDEX RIBBON ENGINE]: Wtrysk par kwasów z odcięciem przeszukiwania [2.4]."""
        project_dir = os.path.dirname(self.metrics_json_path)
        contigs_gz_path = os.path.join(project_dir, "contigs.fasta.gz")
        snps_gz_path = os.path.join(project_dir, "mummer_run.snps.tsv.gz")
        
        mutations_lookup = {}
        if os.path.exists(snps_gz_path):
            try:
                with gzip.open(snps_gz_path, 'rt', encoding='utf-8') as f:
                    for line in f:
                        cleaned = line.strip()
                        if not cleaned: continue
                        parts = cleaned.split('\t')
                        if len(parts) >= 11 and parts[10].strip() == contig_id:
                            try:
                                q_pos = int(parts[3].strip())
                                r_pos = int(parts[0].strip())
                                b_ref = parts[1].strip()
                                b_qry = parts[2].strip()
                                
                                if b_ref == ".": symbol = "[ INSERCJA ]"
                                elif b_qry == ".": symbol = "[ DELECJA ]"
                                else: symbol = f"[ SNV ]: {b_qry} ➔ {b_ref}"
                                
                                mutations_lookup[q_pos] = (symbol, b_qry, b_ref, r_pos)
                            except ValueError: continue
            except Exception: pass

        alignment_matrix = []
        first_mutation_row_idx = -1
        
        if os.path.exists(contigs_gz_path):
            try:
                with gzip.open(contigs_gz_path, 'rt', encoding='utf-8') as f:
                    current_pos_counter = 0
                    in_target_contig = False
                    
                    for line in f:
                        cleaned = line.strip()
                        if cleaned.startswith(">"):
                            header_id = cleaned[1:].split()[0].strip()
                            in_target_contig = (header_id == contig_id)
                            continue
                            
                        if in_target_contig:
                            for base in cleaned:
                                current_pos_counter += 1
                                pos_str = str(current_pos_counter)
                                
                                if current_pos_counter in mutations_lookup:
                                    symbol, b_qry, b_ref, r_pos = mutations_lookup[current_pos_counter]
                                    row = [pos_str, b_qry, symbol, b_ref, str(r_pos)]
                                    if first_mutation_row_idx == -1:
                                        first_mutation_row_idx = len(alignment_matrix)
                                else:
                                    row = [pos_str, base, "<===>", base, pos_str]
                                    
                                alignment_matrix.append(row)
            except Exception: pass

        self.alignment_model.update_data(alignment_matrix)
        
        if first_mutation_row_idx != -1:
            self.alignment_model.set_highlighted_row(first_mutation_row_idx)
            start_viewport = max(0, first_mutation_row_idx - 10)
            self.alignment_view.verticalScrollBar().setValue(start_viewport)
            QCoreApplication.processEvents()
            self.alignment_view.selectRow(first_mutation_row_idx)
        else:
            self.alignment_model.set_highlighted_row(-1)
