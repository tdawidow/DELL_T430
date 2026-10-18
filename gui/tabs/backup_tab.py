# gui/tabs/backup_tab.py
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QGroupBox, QTextEdit, QMessageBox)
from PyQt6.QtCore import Qt
import config
from core.backup_engine import BackupWorkerThread
from core.explorer import CoreExplorer, ExplorerMode, FilterProfile
from core.workspace_manager import WorkspaceManager

class BackupTab(QWidget):
    """Karta 6 [PANCERNA V3]: Autonomiczne centrum zarządzania kopiami zapasowymi i magazynem HDD 2 TB."""
    
    def __init__(self):
        super().__init__()
        self.main_window = None
        self.worker = None
        self.ws = WorkspaceManager(init_system=False)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # =====================================================================
        # SEKCJA 1: WIZUALNE PODPIĘCIE ŚCIEŻEK (STREFY I/O)
        # =====================================================================
        io_box = QGroupBox("🗄️ PARAMETRY ŚCIEŻEK SESJI ARCHIWIZACJI")
        io_layout = QVBoxLayout(io_box)
        io_layout.setSpacing(8)

        io_layout.addWidget(QLabel("🧬 Aktywny projekt roboczy do zapisu (Folder wejściowy z szybkiego NVMe):"))
        h_layout1 = QHBoxLayout()
        self.txt_source_project = QLineEdit()
        self.txt_source_project.setPlaceholderText("Wskaż folder aktywnego projektu laboratoryjnego...")
        btn_browse_src = QPushButton("Przeglądaj NVMe...")
        btn_browse_src.clicked.connect(self._browse_source_project)
        h_layout1.addWidget(self.txt_source_project)
        h_layout1.addWidget(btn_browse_src)
        io_layout.addLayout(h_layout1)

        io_layout.addWidget(QLabel("💾 Repozytorium kopii zapasowych (Folder docelowy na mechanicznym HDD 2 TB):"))
        h_layout2 = QHBoxLayout()
        self.txt_backup_repo = QLineEdit()
        
        # Prawidłowa stylizacja i blokada edycji
        self.txt_backup_repo.setReadOnly(True)
        self.txt_backup_repo.setStyleSheet("background-color: #1A1A1A; color: #00FF66; font-weight: bold; padding: 4px;")
        
        # WYMUSZONY WYSOKI PRIORYTET ZAŁADUNKU TEKSTU [INDEX]
        self.update_backup_repo_field()
        
        # Prawidłowe zakotwiczenie widżetu w strukturze h_layout2
        h_layout2.addWidget(self.txt_backup_repo)
        io_layout.addLayout(h_layout2)

        layout.addWidget(io_box)

        # =====================================================================
        # SEKCJA 2: PRZYCISKI OPERACYJNE (KONTROLA DWUKIERUNKOWA)
        # =====================================================================
        actions_layout = QHBoxLayout()
        
        self.btn_run_backup = QPushButton("UTWÓRZ KOPIĘ BEZPIECZEŃSTWA (BACKUP) 💾")
        self.btn_run_backup.setStyleSheet("""
            QPushButton { background-color: #004d99; color: #FFFFFF; font-weight: bold; padding: 10px; border: 1px solid #0099FF; }
            QPushButton:hover { background-color: #0066cc; }
            QPushButton:disabled { background-color: #1A1A1A; color: #555555; border: 1px solid #222222; }
        """)
        self.btn_run_backup.clicked.connect(self._start_backup_operation)
        
        self.btn_run_restore = QPushButton("PRZYWRÓĆ PROJEKT Z ARCHIWUM (RESTORE) 🔄")
        self.btn_run_restore.setStyleSheet("""
            QPushButton { background-color: #22863a; color: #FFFFFF; font-weight: bold; padding: 10px; border: 1px solid #28a745; }
            QPushButton:hover { background-color: #28a745; }
            QPushButton:disabled { background-color: #1A1A1A; color: #555555; border: 1px solid #222222; }
        """)
        self.btn_run_restore.clicked.connect(self._start_restore_operation)

        actions_layout.addWidget(self.btn_run_backup)
        actions_layout.addWidget(self.btn_run_restore)
        layout.addLayout(actions_layout)

        # =====================================================================
        # SEKCJA 3: KONSOLA LOGOWANIA POSTĘPU (SANDBOXED LOGS)
        # =====================================================================
        log_box = QGroupBox("📊 KONSOLA WERYFIKACJI INTEGRALNOŚCI I POSTĘPU PROCESU")
        log_layout = QVBoxLayout(log_box)
        
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setStyleSheet("background-color: #0A0A0A; color: #00FF66; font-family: 'DejaVu Sans Mono', monospace; font-size: 12px;")
        log_layout.addWidget(self.log_viewer)
        
        layout.addWidget(log_box)
##########################################################################
    def showEvent(self, event):
        """[DYNAMIC REFRESH]: Dynamicznie synchronizuje stany przy każdym fizycznym wejściu operatora na kartę."""
        self.update_backup_repo_field()
        super().showEvent(event)

    def update_backup_repo_field(self):
        """[PANCERNY ODCZYT Z DYSKU V2]: Wyciąga dane z JSON, a w przypadku pustki wymusza twardy fallback laboratoryjny."""
        actual_backup_dir = ""
        try:
            current_cfg = self.ws._read_config_from_disk()
            actual_backup_dir = current_cfg.get("backup_repository_dir", "").strip()
        except Exception:
            pass
            
        # TWARDY BEZPIECZNIK FALLBACKU: Jeśli JSON jest czysty, trvale przypisujemy Twój magazyn HDD [INDEX]
        if not actual_backup_dir or actual_backup_dir == "":
            actual_backup_dir = "/mnt/backup_hdd1/Backup_T430"
            
        self.txt_backup_repo.setText(actual_backup_dir)
        config.BACKUP_DIR = actual_backup_dir

    def _browse_source_project(self):
        """Wzywa wbudowany CoreExplorer do bezpiecznego wskazania folderu projektu na NVMe."""
        current_cfg = self.ws._read_config_from_disk()
        start_dir = current_cfg.get("output_workspace_dir", None)
        explorer = CoreExplorer(self, mode=ExplorerMode.DIRECTORY_SELECT, start_dir=start_dir)
        if explorer.exec():
            path = explorer.get_selected_path()
            if path:
                self.txt_source_project.setText(path)

    def _start_backup_operation(self):
        """Uruchamia safe-guard weryfikacji wolnego miejsca na HDD i odpala asynchroniczny backup."""
        source = self.txt_source_project.text().strip()
        
        # Bezpieczne czytanie ścieżki bezpośrednio z pola ekranowego przed rozruchem wątku
        target = self.txt_backup_repo.text().strip()
        if not target or target == "":
            target = "/mnt/backup_hdd1/Backup_T430"

        if not source or not os.path.exists(source):
            QMessageBox.warning(self, "Błąd wejścia", "Wskazany katalog źródłowy projektu nie istnieje na dysku NVMe!")
            return

        if self.main_window and getattr(self.main_window, 'current_pipeline_thread', None):
            QMessageBox.critical(self, "Zablokowano", "Nie można wykonywać kopii w trakcie trwania aktywnego potoku!")
            return

        # KALKULATOR WAGOWY
        import shutil
        try:
            total, used, free = shutil.disk_usage(target)
            free_gb = free / (1024 ** 3)
            
            total_size_bytes = 0
            for dirpath, dirnames, filenames in os.walk(source):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if os.path.exists(fp): total_size_bytes += os.path.getsize(fp)
            source_gb = total_size_bytes / (1024 ** 3)
            
            if free_gb < (source_gb * 1.5):
                QMessageBox.critical(self, "Brak przestrzeni na HDD", f"🛑 PRZERWANO: Niewystarczająca ilość miejsca na dysku HDD!\nWymagane: {(source_gb*1.5):.2f} GB | Wolne: {free_gb:.2f} GB")
                return
        except Exception:
            pass

        self._lock_ui(True)
        self.log_viewer.clear()
        
        self.worker = BackupWorkerThread(source_dir=source, target_dir=target, operation_type="BACKUP")
        self.worker.log_signal.connect(self._append_log)
        self.worker.finished_signal.connect(self._operation_completed)
        self.worker.start()

    def _start_restore_operation(self):
        """[FINAL HARD FIX]: Odpytuje pole i zmusza CoreExplorer do bezwarunkowego startu w Twoim magazynie HDD."""
        target_nvme = getattr(config, 'WORKSPACE_DIR', "/home/ionadmin/kombajn_workspace/projects")
        
        # Twarde wyciągnięcie ścieżki magazynu bezpośrednio z załadowanego pola tekstowego
        start_hdd = self.txt_backup_repo.text().strip()
        if not start_hdd or start_hdd == "":
            start_hdd = "/mnt/backup_hdd1/Backup_T430"

        # Wywołanie bezpiecznego okna w 100% zwalidowanej lokalizacji HDD
        explorer = CoreExplorer(self, mode=ExplorerMode.FILE_SELECT, filter_profile=FilterProfile.ARCHIVE_DATA, start_dir=start_hdd)
        if explorer.exec():
            archive_path = explorer.get_selected_path()
            if not archive_path:
                return

            if self.main_window and getattr(self.main_window, 'current_pipeline_thread', None):
                QMessageBox.critical(self, "Zablokowano", "Nie można przywracać projektów w trakcie trwania aktywnego potoku!")
                return

            self._lock_ui(True)
            self.log_viewer.clear()

            self.worker = BackupWorkerThread(source_dir=None, target_dir=target_nvme, operation_type="RESTORE", archive_file=archive_path)
            self.worker.log_signal.connect(self._append_log)
            self.worker.finished_signal.connect(self._operation_completed)
            self.worker.start()

    def _append_log(self, text: str):
        self.log_viewer.append(text)

    def _lock_ui(self, is_locked: bool):
        """
        [PANCERNE API INTERLOCKU S-1.4 - REWIZJA EXCEPTION]: Wygasza lokalne przyciski
        na karcie oraz bezwzględnie paraliżuje cały pasek boczny main_window (w tym przycisk startu).
        Wymusza twardy wyjątek dla indeksu 6, uniemożliwiając systemowi ucieczkę z widoku logów.
        """
        # 1. Kontrola dostępności lokalnych kontrolek karty 7
        self.btn_run_backup.setEnabled(not is_locked)
        self.btn_run_restore.setEnabled(not is_locked)
        
        # 2. 🚨 WSTREKIWANIE WYJĄTKU RYGLA: Blokujemy panel boczny, ale omijamy indeks 7 (tę kartę!)
        if self.main_window and hasattr(self.main_window, '_set_peripheral_tabs_enabled'):
            # Jeśli blokujemy (is_locked=True), przekazujemy False do włączenia peryferyjów, narzucając exclude_idx=6
            self.main_window._set_peripheral_tabs_enabled(not is_locked, exclude_idx=6)

    def _operation_completed(self, success: bool, message: str):
        """Obsługuje bezpieczny finisz asynchronicznego wątku kopii i bezwarunkowo zdejmuje rygiel sprzętowy."""
        # ✅ JAWNE I ABSOLUTNE ZWOLNIENIE RYGLA: Przywracamy kolory i pełną sterowność main_window
        self._lock_ui(False)
        
        if success:
            QMessageBox.information(self, "Sukces operacji", message)
            if self.main_window and hasattr(self.main_window, 'tab_history'):
                try:
                    if self.main_window.tab_history.txt_history_path.text().strip():
                        self.main_window.tab_history._load_historical_analysis()
                except Exception: 
                    pass
        else:
            QMessageBox.critical(self, "Błąd potoku magazynu", message)
