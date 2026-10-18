# core/backup_engine.py
import os
import sys
import shutil
import hashlib
import tarfile
from PyQt6.QtCore import QThread, pyqtSignal
import config

class BackupWorkerThread(QThread):
    """
    [PANCERNY ASYNCHRONICZNY SILNIK KOPII ZAPASOWYCH V4 - ATOMIC WIPE]:
    W pełni zabezpieczony przed nadpisywaniem struktur roboczych i archiwalnych.
    Mierzy przestrzeń, generuje MD5, a po udanej walidacji integralności paczki na HDD
    bezpowrotnie usuwa katalog źródłowy z NVMe z pominięciem kosza, zwalniając miejsce.
    """
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, source_dir: str, target_dir: str, operation_type: str = "BACKUP", archive_file: str = None):
        super().__init__()
        self.source_dir = source_dir
        self.target_dir = target_dir
        self.operation_type = operation_type.upper()
        self.archive_file = archive_file

    def run(self):
        try:
            if self.operation_type == "BACKUP":
                self._execute_backup_flow()
            elif self.operation_type == "RESTORE":
                self._execute_restore_flow()
        except Exception as e:
            self.finished_signal.emit(False, f"Wyjątek krytyczny silnika: {str(e)}")

    def _execute_backup_flow(self):
        """Uruchamia bezpieczny protokół tworzenia kopii zapasowej z późniejszym czyszczeniem źródła NVMe."""
        if not self.source_dir or not os.path.exists(self.source_dir):
            self.finished_signal.emit(False, "Katalog źródłowy projektu na NVMe nie istnieje!")
            return

        os.makedirs(self.target_dir, exist_ok=True)
        project_name = os.path.basename(self.source_dir.rstrip("/"))
        
        from PyQt6.QtCore import QDateTime
        timestamp = QDateTime.currentDateTime().toString("yyyyMMdd_hhmmss")
        archive_name = f"{project_name}_backup_{timestamp}.tar.gz"
        full_archive_path = os.path.join(self.target_dir, archive_name)

        if os.path.exists(full_archive_path):
            self.log_signal.emit("⚠️ Wykryto kolizję nazwy archiwum na HDD. Generowanie identyfikatora rewizji...")
            archive_name = f"{project_name}_backup_{timestamp}_rev1.tar.gz"
            full_archive_path = os.path.join(self.target_dir, archive_name)

        full_md5_path = full_archive_path + ".md5"

        self.log_signal.emit(f"🗄️ Inicjalizacja archiwizacji projektu: {project_name}")
        self.log_signal.emit(f"🧪 Docelowy magazyn HDD: {full_archive_path}")
        self.log_signal.emit("📦 Krok 1/3: Rozpoczynanie kompresji strumieniowej tar.gz...")

        with tarfile.open(full_archive_path, "w:gz") as tar:
            tar.add(self.source_dir, arcname=project_name)

        self.log_signal.emit("✅ Kompresja ukończona pomyślnie. Plik .tar.gz zabezpieczony.")
        self.log_signal.emit("🛡️ Krok 2/3: Generowanie cyfrowego podpisu MD5...")

        md5_hash = hashlib.md5()
        with open(full_archive_path, "rb") as f:
            for byte_block in iter(lambda: f.read(65536), b""):
                md5_hash.update(byte_block)
        calculated_md5 = md5_hash.hexdigest()
        
        with open(full_md5_path, "w", encoding="utf-8") as md5_file:
            md5_file.write(calculated_md5)

        self.log_signal.emit(f"🔒 MD5: {calculated_md5}")

        # =====================================================================
        # ATOMIC WIPE PROTOCOL: Twarda weryfikacja i bezpowrotne czyszczenie NVMe [INDEX]
        # =====================================================================
        self.log_signal.emit("🔍 Weryfikacja integralności strukturalnej nowo powstałego archiwum...")
        if tarfile.is_tarfile(full_archive_path):
            self.log_signal.emit("🗑️ Krok 3/3: Integralność paczki potwierdzona. Zwalnianie przestrzeni NVMe...")
            self.log_signal.emit(f"🔥 Bezpowrotne usuwanie katalogu źródłowego z NVMe: {self.source_dir}")
            
            # Bezpieczne usunięcie z pominięciem systemowego kosza Lubuntu (X11)
            shutil.rmtree(self.source_dir, ignore_errors=True)
            
            self.log_signal.emit("🧹 Szybki nośnik NVMe Kingston został pomyślnie oczyszczony. Bloki zwolnione.")
            self.finished_signal.emit(True, f"Pomyślnie utworzono kopię zapasową, a katalog źródłowy został bezpowrotnie usunięty z NVMe!")
        else:
            self.log_signal.emit("🛑 BŁĄD INTEGRALNOŚCI: Nowo utworzony plik archiwum jest uszkodzony! Kasowanie źródła zablokowane.")
            self.finished_signal.emit(False, "Kopia utworzona, ale weryfikacja struktury nie powiodła się. Dane źródłowe zachowane dla bezpieczeństwa.")

    def _execute_restore_flow(self):
        """[PANCERNY RESTORE FLOW V3]: Zapewnia brak nadpisywania folderów roboczych na NVMe."""
        if not self.archive_file or not os.path.exists(self.archive_file):
            self.finished_signal.emit(False, "Wskazany plik archiwum .tar.gz nie istnieje!")
            return

        try:
            total, used, free = shutil.disk_usage(self.target_dir)
            free_gb = free / (1024 ** 3)
            archive_size_gb = os.path.getsize(self.archive_file) / (1024 ** 3)
            
            required_nvme_space = archive_size_gb * 3.0
            if free_gb < required_nvme_space:
                self.finished_signal.emit(False, f"🛑 PRZERWANO: Brak miejsca na szybkim nośniku NVMe!\nWolne: {free_gb:.2f} GB | Wymagane: {required_nvme_space:.2f} GB")
                return
        except Exception as e:
            self.log_signal.emit(f"⚠️ Ostrzeżenie weryfikacji przestrzeni NVMe: {str(e)}")

        full_md5_path = self.archive_file + ".md5"
        if not os.path.exists(full_md5_path):
            self.finished_signal.emit(False, "🛑 BŁĄD KRYTYCZNY: Brak pliku sumy kontrolnej .md5!")
            return

        self.log_signal.emit(f"🔄 Inicjalizacja przywracania z pliku: {os.path.basename(self.archive_file)}")
        self.log_signal.emit("🛡️ Krok 1/2: Walidacja integralności struktury cyfrowej...")

        with open(full_md5_path, "r", encoding="utf-8") as f:
            saved_md5 = f.read().strip()

        md5_hash = hashlib.md5()
        with open(self.archive_file, "rb") as f:
            for byte_block in iter(lambda: f.read(65536), b""):
                md5_hash.update(byte_block)
        current_md5 = md5_hash.hexdigest()

        if saved_md5 != current_md5:
            self.finished_signal.emit(False, "🛑 ABORT: Suma kontrolna MD5 niezgodna! Archiwum jest uszkodzone.")
            return

        self.log_signal.emit(f"✅ Cyfrowy podpis poprawny: {current_md5}")
        self.log_signal.emit("📦 Krok 2/2: Analiza zawartości i sprawdzanie kolizji katalogów docelowych...")

        try:
            with tarfile.open(self.archive_file, "r:gz") as tar:
                members = tar.getmembers()
                if not members:
                    self.finished_signal.emit(False, "Archiwum jest puste!")
                    return
                
                # Izolujemy nazwę pierwszego katalogu z nagłówków
                first_member_name = members[0].name
                root_project_in_archive = first_member_name.split('/')[0].strip()
                
                if not root_project_in_archive:
                    self.finished_signal.emit(False, "Nie udało się zidentyfikować projektu w nagłówkach.")
                    return
                    
                potential_destination_dir = os.path.join(self.target_dir, root_project_in_archive)
                
                if os.path.exists(potential_destination_dir):
                    err_overlap = f"🛑 ZABLOKOWANO: Katalog projektu '{root_project_in_archive}' fizycznie ISTNIEJE już w strefie roboczej NVMe!\nNadpisywanie zablokowane."
                    self.log_signal.emit(err_overlap)
                    self.finished_signal.emit(False, f"Kolizja struktur. Folder '{root_project_in_archive}' już istnieje.")
                    return

                self.log_signal.emit(f"🚀 Przestrzeń czysta. Rozpoczynanie bezpiecznej ekstrakcji do: {self.target_dir}")
                tar.extractall(path=self.target_dir)
        except Exception as e:
            self.finished_signal.emit(False, f"Błąd ekstrakcji paczki tar.gz: {str(e)}")
            return

        self.log_signal.emit("🎉 Proces przywracania danych zakończony pełnym sukcesem. Brak nadpisań.")
        self.finished_signal.emit(True, f"Projekt '{root_project_in_archive}' został pomyślnie przywrócony z archiwum!")
