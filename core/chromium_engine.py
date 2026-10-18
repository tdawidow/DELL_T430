# core/chromium_engine.py
# =====================================================================
# 🚨 NIENARUSZALNA BAZA PRAWDY V47.4: MONOLITYCZNY SYSTEM BLOKAD I/O
# =====================================================================
import os
import gzip
import shutil
import json
import re
from datetime import datetime
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QLabel
from PyQt6.QtCore import QThread, QUrl, pyqtSignal
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineDownloadRequest, QWebEnginePage
from PyQt6.QtWebEngineWidgets import QWebEngineView

class ChromiumBrowserWindow(QMainWindow):
    """[INCUBATOR CHROMIUM CORE V47.4 - FULL INTERLOCK]: Profil OTR z blokadami I/O [2.4]."""
    def __init__(self, target_url: str, download_dir: str, parent=None):
        super().__init__(parent)
        self.download_dir = download_dir
        self.profile = QWebEngineProfile("", self)
        self.profile.downloadRequested.connect(self._handle_download_request)
        
        self.web_view = QWebEngineView(self)
        self.web_view.setPage(QWebEnginePage(self.profile, self.web_view))
        
        nav_widget = QWidget()
        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setContentsMargins(5, 2, 5, 2)
        nav_layout.setSpacing(6)
        
        self.btn_back = QPushButton("◀ Wstecz")
        self.btn_forward = QPushButton("Dalej ▶")
        self.btn_refresh = QPushButton("🔄 Odśwież")
        self.btn_home = QPushButton("🏠 Home")
        
        self.btn_back.clicked.connect(self.web_view.back)
        self.btn_forward.clicked.connect(self.web_view.forward)
        self.btn_refresh.clicked.connect(self.web_view.reload)
        self.btn_home.clicked.connect(lambda: self.web_view.load(QUrl(target_url)))
        
        self.web_view.urlChanged.connect(self._update_navigation_states)
        self.btn_back.setEnabled(False)
        self.btn_forward.setEnabled(False)

        for btn in [self.btn_back, self.btn_forward, self.btn_refresh, self.btn_home]:
            btn.setStyleSheet("background-color: #2D2D2D; color: #FFFFFF; font-weight: bold; padding: 4px 10px; border-radius: 3px;")
            nav_layout.addWidget(btn)
            
        # ✅ WYCIĄGNIĘCIE POZA PĘTLĘ FOR (Wcięcie 8 spacji): Sterylna belka progresu [2.4]
        self.lbl_progress = QLabel("")
        self.lbl_progress.setStyleSheet("color: #00FF66; font-weight: bold; font-family: 'Monospace'; padding-left: 15px;")
        nav_layout.addWidget(self.lbl_progress)

        nav_layout.addStretch()
        
        central_container = QWidget()
        main_layout = QVBoxLayout(central_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        main_layout.addWidget(nav_widget, 0)      
        main_layout.addWidget(self.web_view, 1)   
        
        self.setCentralWidget(central_container)
        self.web_view.load(QUrl(target_url))
        self.showMaximized()

    def _handle_download_request(self, download_item: QWebEngineDownloadRequest):
        """Przechwytuje strumień sieciowy i siłowo zamraża interfejs na czas transferu [2.4]."""
        # 🚨 ABSOLUTNY RYGOR INTERFEJSU: Natychmiastowe zaryglowanie klawiszy i widoku strony! [2.4]
        self.btn_back.setEnabled(False)
        self.btn_forward.setEnabled(False)
        self.btn_refresh.setEnabled(False)
        self.btn_home.setEnabled(False)
        self.web_view.setDisabled(True)
        
        self.lbl_progress.setStyleSheet("color: #ECC94B; font-weight: bold;")
        self.lbl_progress.setText("📥 INICJALIZACJA STRUMIENIA BINARNEGO...")

        download_item.setDownloadDirectory(self.download_dir)
        full_path = os.path.join(self.download_dir, download_item.suggestedFileName())
        
        # Przepięcie szyny pod poprawne, zwalidowane sygnały zmian bajtów RAM [2.4]
        download_item.receivedBytesChanged.connect(lambda: self._update_download_progress(download_item))
        download_item.stateChanged.connect(lambda state, p=full_path: self._check_download_state(state, p))
        download_item.accept()

    def _update_download_progress(self, download_item: QWebEngineDownloadRequest):
        """Kalkuluje bajty directly z i-węzła żądania i wstrzykuje % na żywo do UI [2.4]."""
        received = download_item.receivedBytes()
        total = download_item.totalBytes()
        
        if total > 0:
            pct = int((received / total) * 100)
            self.lbl_progress.setText(f"📥 POBIERANIE: {pct}% ({received // 1024 // 1024} MB / {total // 1024 // 1024} MB)")
            if received == total:
                self.lbl_progress.setStyleSheet("color: #00FF66; font-weight: bold;")
                self.lbl_progress.setText("⚡ POBRANO PLIK. ROZPOCZYNANIE ASYNCHRONICZNEGO PAKOWANIA GZIP...")
        else:
            self.lbl_progress.setText("📥 POBIERANIE: Trwa buforowanie pakietów ...")

    def _check_download_state(self, state, file_path):
        """Reaguje na status pobrania pliku z sieci i przekazuje sterowanie do robotnika [2.4]."""
        if state == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            self.compressor = AsynchronousPackerThread(file_path, self.download_dir)
            # Podłączenie jutrzejszego interlocku sygnałowego powrotu do RAM [2.4]
            self.compressor.packer_finished_signal.connect(self._handle_packer_completed)
            self.compressor.start()

    def _handle_packer_completed(self, base_name, status):
        """[THE FINAL READY NOTICE]: Wywoływany po zaryglowaniu operacji I/O. Odblokowuje cały system [2.4]."""
        # Odblokowanie i przywrócenie sterowności kontrolek nawigacyjnych jądra Chromium [2.4]
        self.btn_refresh.setEnabled(True)
        self.btn_home.setEnabled(True)
        self.web_view.setDisabled(False)
        self._update_navigation_states() # Przywrócenie poprawnego stanu Wstecz/Dalej ze stosu
        
        if status == "ERROR":
            self.lbl_progress.setStyleSheet("color: #FF3333; font-weight: bold;")
            self.lbl_progress.setText(f"❌ AWARIA ZAPISU DYSKU: {base_name}")
        else:
            self.lbl_progress.setStyleSheet("color: #00FF66; font-weight: bold;")
            # ✅ REKLAMOWANY KOMUNIKAT KOŃCOWY OPERATORA: Pełne zwolnienie blokady dysku [2.4]
            self.lbl_progress.setText(f"✅ Zakończono pakowanie GZIP dla {base_name} - można pobrać kolejny plik!")

    def _update_navigation_states(self):
        """Odpytuje stos stron i zarządza dostępnością klawiszy Wstecz/Dalej [2.4]."""
        history = self.web_view.history()
        if history:
            self.btn_back.setEnabled(history.canGoBack())
            self.btn_forward.setEnabled(history.canGoForward())
        else:
            self.btn_back.setEnabled(False)
            self.btn_forward.setEnabled(False)

class AsynchronousPackerThread(QThread):
    """[THE BACKEND RENAME & PACKER INTERLOCK V47.6]: Monolityczny potok kaskadowy [2.4]."""
    packer_finished_signal = pyqtSignal(str, str)

    def __init__(self, source_file_path: str, download_dir: str):
        super().__init__()
        self.source_path = source_file_path
        self.download_dir = download_dir

    def run(self):
        """METODA A: Centralna kaskada I/O. Unifikacja do formatu .gz w ciemno [2.4]."""
        if not os.path.exists(self.source_path):
            self.packer_finished_signal.emit("Brak pliku", "ERROR")
            return
            
        filename = os.path.basename(self.source_path)
        ext_lower = filename.lower()
        current_active_path = self.source_path
        
        # KROK 2 & 3: Standaryzacja binarna do formatu .gz bez weryfikacji zawartości [2.4]
        if ext_lower.endswith('.gz') or ext_lower.endswith('.tar.gz'):
            # Stan 1: Plik już jest spakowany poprawnie. Przechodzimy bezpośrednio dalej.
            pass

        elif ext_lower.endswith('.zip') or ext_lower.endswith('.7z') or ext_lower.endswith('.rar'):
            # Stan 2: Archiwum obcych pakerów -> dynamiczne przepakowanie do formatu .gz [2.4]
            import subprocess
            try:
                if ext_lower.endswith('.zip'):
                    import zipfile
                    with zipfile.ZipFile(self.source_path, 'r') as z_ref:
                        for zip_info in z_ref.infolist():
                            if zip_info.is_dir(): continue
                            inner_name = os.path.basename(zip_info.filename)
                            target_gz_path = os.path.join(self.download_dir, f"{inner_name}.gz")
                            with z_ref.open(zip_info) as f_in, gzip.open(target_gz_path, 'wb', compresslevel=6) as f_out:
                                shutil.copyfileobj(f_in, f_out)
                            current_active_path = target_gz_path
                else:
                    # ✅ MOSTEK NATIVE LINUX: Obsługa .7z i .rar przez siłowy proces systemowy Lubuntu [2.4]
                    tmp_extract_dir = os.path.join(self.download_dir, f"tmp_7z_{datetime.now().strftime('%H%M%S')}")
                    os.makedirs(tmp_extract_dir, exist_ok=True)
                    subprocess.run(["7z", "e", self.source_path, f"-o{tmp_extract_dir}", "-y"], check=True, stdout=subprocess.DEVNULL)
                    for extracted_file in os.listdir(tmp_extract_dir):
                        src_extracted = os.path.join(tmp_extract_dir, extracted_file)
                        if os.path.isdir(src_extracted): continue
                        target_gz_path = os.path.join(self.download_dir, f"{extracted_file}.gz")
                        with open(src_extracted, 'rb') as f_in, gzip.open(target_gz_path, 'wb', compresslevel=6) as f_out:
                            shutil.copyfileobj(f_in, f_out)
                        current_active_path = target_gz_path
                    shutil.rmtree(tmp_extract_dir) # Czyszczenie śmieci I/O z NVMe
                os.remove(self.source_path)
            except Exception as e:
                self.packer_finished_signal.emit(f"Błąd Stanu 2 (7z/ZIP): {str(e)}", "ERROR")
                return

        else:
            # Stan 3: Każdy inny przypadek (Niespakowany) -> siłowa kompresja bez wykluczeń! [2.4]
            target_gz_path = os.path.join(self.download_dir, f"{filename}.gz")
            try:
                with open(self.source_path, 'rb') as f_in, gzip.open(target_gz_path, 'wb', compresslevel=6) as f_out:
                    shutil.copyfileobj(f_in, f_out)
                os.remove(self.source_path)
                current_active_path = target_gz_path
            except Exception as e:
                self.packer_finished_signal.emit(str(e), "ERROR")
                return

        # KROK 4: Sprawdzenie rygorystycznych wymogów specyfikacji ION S5 [2.4]
        final_filename = os.path.basename(current_active_path)
        final_ext_lower = final_filename.lower()
        
        is_ion_s5 = "GSS5" in final_filename and (final_ext_lower.endswith(".fastq.gz") or final_ext_lower.endswith(".bam.gz"))

        if is_ion_s5:
            # Wywołanie odizolowanej metody B - zmiana nazwy oraz paszport JSON [2.4]
            final_filename = self._rename_and_create_passport_json(current_active_path, final_filename)
            if final_filename.startswith("ERROR:"):
                self.packer_finished_signal.emit(final_filename, "ERROR")
                return

        # KROK 5: Zgłoszenie bezwarunkowego zakończenia pobrania i gotowości I/O [2.4]
        self.packer_finished_signal.emit(final_filename, "SUCCESS")

    def _rename_and_create_passport_json(self, current_path: str, filename: str) -> str:
        """METODA B: Wyznacza licznik dzienny, zmienia nazwę na dysku i tworzy paszport .json [2.4]."""
        try:
            date_match = re.search(r"R_(\d{4})_(\d{2})_(\d{2})_(\d{2})_(\d{2})_(\d{2})", filename)
            date_str = f"{date_match.group(1)}{date_match.group(2)}{date_match.group(3)}" if date_match else datetime.now().strftime("%Y%m%d")
            time_str = f"{date_match.group(4)}{date_match.group(5)}" if date_match else datetime.now().strftime("%H%M")
            
            machine_id = filename.split("user_") if "user_" in filename else filename
            raw_sample = machine_id.replace(".fastq.gz", "").replace(".bam.gz", "")
            
            daily_prefix = f"{date_str}-{time_str}_"
            daily_counter = 1

            for f in os.listdir(self.download_dir):
                if f.startswith(daily_prefix):
                    counter_match = re.search(r"_(\d{2})\.", f)
                    if counter_match:
                        val = int(counter_match.group(1))
                        if val >= daily_counter: daily_counter = val + 1
                        
            base_target_name = f"{daily_prefix}{daily_counter:02d}"
            target_ext = ".fastq.gz" if "fastq" in filename.lower() else ".bam.gz"
            
            new_target_path = os.path.join(self.download_dir, f"{base_target_name}{target_ext}")
            os.rename(current_path, new_target_path)
            
            # Zrzut satelickiego paszportu medycznego JSON
            passport_path = os.path.join(self.download_dir, f"{base_target_name}.json")
            metadata = {
                "base_name_docelowa": base_target_name,
                "original_filename_input": filename,
                "sekwencer_id": "ION_S5_GSS5_MATRIX",
                "data_analizy": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}",
                "godzina_analizy": f"{time_str[:2]}:{time_str[2:]}",
                "nazwa_probki_raw": raw_sample,
                "numer_kolejny_z_dnia": daily_counter,
                "timestamp_pobrania": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            with open(passport_path, 'w', encoding='utf-8') as j_out:
                json.dump(metadata, j_out, indent=4, ensure_ascii=False)
                
            return f"{base_target_name}{target_ext}"
        except Exception as e:
            return f"ERROR: {str(e)}"
