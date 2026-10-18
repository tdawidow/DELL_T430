# gui/tabs/monitor_tab.py
import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QProgressBar, QPushButton, QDialog
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView

class MonitorTab(QWidget):
    """Karta 1: Asynchroniczny monitor potoku laboratoryjnego z podglądem wyników QUAST i FASTA."""
    
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # 1. Górny pasek statusu zadania
        self.lbl_task_status = QLabel("Stan systemu: Oczekiwanie na uruchomienie analizy...")
        self.lbl_task_status.setStyleSheet("font-weight: bold; color: #FFA500; font-size: 13px;")
        layout.addWidget(self.lbl_task_status)

        # 2. Globalny pasek postępu (Progress Bar)
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar { border: 1px solid #3A3A3A; border-radius: 4px; text-align: center; background: #1E1E1E; color: white; font-weight: bold; }
            QProgressBar::chunk { background-color: #00FF66; width: 10px; }
        """)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # 3. Główna konsola logów CLI
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setStyleSheet("""
            QTextEdit { 
                background-color: #0A0A0A; 
                color: #A0AEC0; 
                font-family: 'DejaVu Sans Mono', 'Courier New', monospace; 
                font-size: 12px; 
                border: 1px solid #2C2C2C; 
                border-radius: 4px; 
            }
        """)
        layout.addWidget(self.log_viewer)

        # =====================================================================
        # PANEL SZYBKIEGO PODGLĄDU WYNIKÓW (NOWOŚĆ - AKTYWOWANY PO SKŁADANIU)
        # =====================================================================
        self.result_buttons_layout = QHBoxLayout()
        
        self.btn_view_quast = QPushButton("📊 Otwórz Raport Jakości QUAST (HTML)")
        self.btn_view_quast.setEnabled(False)
        self.btn_view_quast.setStyleSheet("background-color: #2b6cb0; font-weight: bold; color: white; padding: 8px;")
        self.btn_view_quast.clicked.connect(self._open_quast_report)
        
        self.btn_preview_fasta = QPushButton("🧬 Szybki Podgląd Zmontowanego Genomu (FASTA)")
        self.btn_preview_fasta.setEnabled(False)
        self.btn_preview_fasta.setStyleSheet("background-color: #4a5568; font-weight: bold; color: white; padding: 8px;")
        self.btn_preview_fasta.clicked.connect(self._preview_fasta_sequence)

        self.result_buttons_layout.addWidget(self.btn_view_quast)
        self.result_buttons_layout.addWidget(self.btn_preview_fasta)
        layout.addLayout(self.result_buttons_layout)

        # Ścieżki cache do plików bieżącego projektu
        self.active_quast_html = None
        self.active_fasta_path = None

    def append_log(self, text: str):
        """Dopisuje nadchodzący strumień danych z wątku CLI do konsoli."""
        self.log_viewer.append(text)
        # Automatyczne przewijanie konsoli w dół wraz z przyrostem logów
        self.log_viewer.moveCursor(self.log_viewer.textCursor().MoveOperation.End)

    def update_sample_progress(self, percent: int, current_step_name: str):
        """[THE SECURE STEP REPAINT ENGINE]: Siłowo przesuwa pasek w czasie rzeczywistym [2.4]."""
        from PyQt6.QtWidgets import QApplication
        self.progress_bar.setValue(percent)
        self.lbl_task_status.setText(f"Stan systemu: Przetwarzanie... [{current_step_name} - {percent}%]")
        self.lbl_task_status.setStyleSheet("font-weight: bold; color: #00FF66; font-size: 13px;")
        
        # ✅ THE EVENT LOOP OVERRIDE: Wymuszenie przemalowania kontrolek na żywo w RAM stacji XEON [2.4]
        self.progress_bar.repaint()
        self.lbl_task_status.repaint()
        QApplication.processEvents()  # Opróżnia bufor, pasek rośnie schodkowo podczas obliczeń [2.4]

    def set_batch_mode_active(self, is_active: bool, total_samples: int = 0):
        """[THE MONITOR TELEMETRY INTERLOCK]: Przygotowuje mianownik serii dla paska % [2.4]."""
        from PyQt6.QtWidgets import QApplication
        if is_active:
            self.progress_bar.setValue(0)
            self.lbl_task_status.setText(f"Stan systemu: Rozruch matrycy... [Załadowano par: {total_samples}]")
            self.lbl_task_status.setStyleSheet("font-weight: bold; color: #00FF66; font-size: 13px;")
            # ✅ WYMUSZENIE W LOCIE: Siłowe odrysowanie tekstu przed zablokowaniem wątku przez BLASTn [2.4]
            self.lbl_task_status.repaint()
            QApplication.processEvents()
        else:
            self.lbl_task_status.setText("Stan systemu: Oczekiwanie na uruchomienie analizy...")
            self.lbl_task_status.setStyleSheet("font-weight: bold; color: #FFA500; font-size: 13px;")
            self.lbl_task_status.repaint()
            QApplication.processEvents()

    def activate_results_preview(self, project_path: str):
        """Automatycznie namierza wygenerowane pliki i odblokowuje przyciski podglądu."""
        # Lokalizacja raportu QUAST
        potential_quast = os.path.join(project_path, "03_Assembly", "quast_report", "report.html")
        if os.path.exists(potential_quast):
            self.active_quast_html = potential_quast
            self.btn_view_quast.setEnabled(True)
            self.btn_view_quast.setStyleSheet("background-color: #22863a; font-weight: bold; color: white; padding: 8px;")

        # Lokalizacja genomu FASTA (SPAdes lub Flye)
        self.active_fasta_path = None
        for filename in [
            os.path.join("03_Assembly", "spades_output", "scaffolds.fasta"),
            os.path.join("03_Assembly", "flye_output", "assembly.fasta")
        ]:
            full_path = os.path.join(project_path, filename)
            if os.path.exists(full_path):
                self.active_fasta_path = full_path
                self.btn_preview_fasta.setEnabled(True)
                self.btn_preview_fasta.setStyleSheet("background-color: #004d99; font-weight: bold; color: white; padding: 8px;")
                break

    def reset_controls_for_new_run(self):
        """Resetuje przyciski i stan przed nowym biegiem."""
        self.btn_view_quast.setEnabled(False)
        self.btn_view_quast.setStyleSheet("background-color: #4a5568; font-weight: bold; color: white; padding: 8px;")
        self.btn_preview_fasta.setEnabled(False)
        self.btn_preview_fasta.setStyleSheet("background-color: #4a5568; font-weight: bold; color: white; padding: 8px;")
        self.log_viewer.clear()
        self.progress_bar.setValue(0)

    def _open_quast_report(self):
        """Otwiera interaktywny raport QUAST w osobnym wyskakującym oknie z silnikiem Chromium."""
        if self.active_quast_html and os.path.exists(self.active_quast_html):
            dialog = QDialog(self)
            dialog.setWindowTitle("Raport Jakości Składania Genomu - QUAST")
            dialog.setMinimumSize(900, 650)
            
            dialog_layout = QVBoxLayout(dialog)
            dialog_layout.setContentsMargins(0, 0, 0, 0)
            
            web_browser = QWebEngineView()
            web_browser.settings().setAttribute(web_browser.settings().WebAttribute.JavascriptEnabled, True)
            web_browser.setUrl(QUrl.fromLocalFile(os.path.abspath(self.active_quast_html)))
            
            dialog_layout.addWidget(web_browser)
            dialog.exec()

    def _preview_fasta_sequence(self):
        """Otwiera okno szybkiego podglądu pierwszych 100 linii zmontowanego pliku FASTA."""
        if self.active_fasta_path and os.path.exists(self.active_fasta_path):
            try:
                preview_lines = []
                with open(self.active_fasta_path, "r", encoding="utf-8") as f:
                    for _ in range(100):
                        line = f.readline()
                        if not line:
                            break
                        preview_lines.append(line)

                dialog = QDialog(self)
                dialog.setWindowTitle(f"Podgląd FASTA: {os.path.basename(self.active_fasta_path)}")
                dialog.setMinimumSize(700, 500)
                dialog.setStyleSheet("background-color: #121212; color: #E0E0E0;")

                dialog_layout = QVBoxLayout(dialog)
                
                info_lbl = QLabel(f"Lokalizacja pliku: {self.active_fasta_path}\n(Wyświetlono nagłówki i pierwsze 100 linii sekwencji Fasta)")
                info_lbl.setStyleSheet("font-weight: bold; color: #00FF66;")
                dialog_layout.addWidget(info_lbl)

                text_area = QTextEdit()
                text_area.setReadOnly(True)
                text_area.setPlainText("".join(preview_lines))
                text_area.setStyleSheet("""
                    QTextEdit { 
                        background-color: #1A1A1A; 
                        color: #48BB78; 
                        font-family: 'DejaVu Sans Mono', monospace; 
                        font-size: 11px; 
                        border: 1px solid #3A3A3A; 
                    }
                """)
                dialog_layout.addWidget(text_area)
                dialog.exec()
            except Exception as e:
                QMessageBox.critical(self, "Błąd", f"Nie można otworzyć pliku FASTA: {str(e)}")
