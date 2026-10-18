# core/universal_downloader.py
import os
import sys
import urllib.request
import gzip  # ✅ NOWOŚĆ: Natywny moduł kompresji jądra Pythona [INDEX]
from PyQt6.QtCore import QThread, pyqtSignal

class UniversalDownloadWorker(QThread):
    """
    [PANCERNY ASYNCHRONICZNY SILNIK SIECIOWY JĄDRA V3 - AUTO-GZIP]:
    Odpowiada za bezpieczne, blokowe pobieranie plików z internetu bezpośrednio na NVMe.
    Po pomyślnej walidacji pakuje plik tekstowy do formatu .gz i kasuje oryginał [INDEX].
    Działa w odizolowanym procesie systemowym, eliminując lag interfejsu.
    """
    # Definicja uniwersalnych sygnałów komunikacyjnych z warstwą GUI
    log_signal = pyqtSignal(str)          # Surowe komunikaty tekstowe do Monitora
    progress_signal = pyqtSignal(int)     # Procentowy postęp (0-100%) dla paska stanu
    finished_signal = pyqtSignal(bool, str) # Końcowy status (Sukces True/False, Ścieżka/Komunikat)

    def __init__(self, source_url: str, target_path: str):
        """
        Inicjalizuje instancję workera sieciowego.
        :param source_url: Pełny adres HTTP/HTTPS do pliku źródłowego (API NCBI Eutils)
        :param target_path: Bezwzględna ścieżka zapisu na dysku NVMe
        """
        super().__init__()
        self.source_url = source_url
        self.target_path = target_path
        self._is_killed = False

    def run(self):
        """
        [PANCERNY STRUMIENIOWY SILNIK SIECIOWY V3 - KOMPRESJA W LOCIE]:
        Zapewnia ciągłe pobieranie gigantycznych genomów bioinformatycznych z NCBI.
        Ignoruje brak nagłówka Content-Length, obsługuje api_key, a po walidacji
        automatycznie konwertuje pliki do .gz w celu drastycznej oszczędności i-węzłów [INDEX].
        """
        try:
            self.log_signal.emit(f"[SIEC]: Uruchamiam bezpieczne połączenie z serwerem zdalnym...")
            
            # Maskowanie klucza API w logu konsoli dla zachowania prywatności
            if "api_key=" in self.source_url:
                base_url = self.source_url.split("&api_key=")[0]
                self.log_signal.emit(f" -> Adres URL: {base_url}&api_key=********")
            else:
                self.log_signal.emit(f" -> Adres URL: {self.source_url}")
            
            # Tworzymy katalog nadrzędny biblioteki referencji
            os.makedirs(os.path.dirname(self.target_path), exist_ok=True)

            # Budujemy pancerny konfigurator nagłówków, uodporniający na Error 403 / 429
            req = urllib.request.Request(
                self.source_url, 
                headers={'User-Agent': 'Mozilla/5.0 (X11; Lubuntu; Linux x86_64) KombajnT430/Bioinformatics_Engine'}
            )

            # Otwieramy strumień sieciowy z twardym limitem oczekiwania na 30 sekund
            with urllib.request.urlopen(req, timeout=30) as response:
                # Dynamiczna detekcja wielkości pliku (Failsafe dla Chunked Encoding z NCBI)
                content_length = response.getheader('Content-Length')
                total_size = int(content_length) if content_length else 0
                
                if total_size > 0:
                    self.log_signal.emit(f" -> Rozmiar zadeklarowany: {total_size / 1024.0 / 1024.0:.2f} MB. Pobieranie blokowe.")
                else:
                    self.log_signal.emit(" -> Rozmiar nieokreślony (Transfer-Encoding: Chunked). Aktywuję ciągłe przechwytywanie strumienia.")

                bytes_downloaded = 0
                block_size = 65536 # Zwiększamy bufor do 64 KB dla przyspieszenia dużych FASTA przez magistralę PCIe
                
                # Atomowe otwarcie pliku do zapisu binarnego
                with open(self.target_path, 'wb') as target_file:
                    while True:
                        if self._is_killed:
                            self.log_signal.emit("[!!!] POBIERANIE ANULOWANE PRZEZ SYSTEM [!!!]")
                            raise InterruptedError("Operacja przerwana przez operatora.")

                        # Pobieramy surowy pakiet danych bez względu na stan Content-Length
                        buffer = response.read(block_size)
                        if not buffer:
                            break # Strumień gniazda TCP został wyczerpany, pobieranie ukończone

                        target_file.write(buffer)
                        bytes_downloaded += len(buffer)

                        # Dynamiczne wyliczanie postępu procentowego (tylko jeśli znamy rozmiar)
                        if total_size > 0:
                            percent = int((bytes_downloaded / total_size) * 100)
                            self.progress_signal.emit(percent)
                        else:
                            # Dla trybu Chunked: informujemy operatora w Monitorze o przyroście danych w locie RAM
                            if bytes_downloaded % (block_size * 10) == 0:
                                self.log_signal.emit(f" -> Pobrano przyrostowo: {bytes_downloaded / 1024.0 / 1024.0:.2f} MB...")

                    # Wymuszenie twardego zaryglowania sektorów na nośniku NVMe
                    target_file.flush()
                    os.fsync(target_file.fileno())

            # 🛡️ PANCERNY STRAŻNIK PUSTYCH ODPOWIEDZI (Filtr 1-bajtowych plików-widm Master Records) [INDEX]
            if os.path.exists(self.target_path) and os.path.getsize(self.target_path) > 15:
                # Sprawdzamy czy pobrany plik nie jest przypadkiem komunikatem o błędzie XML/HTML zamiast FASTA
                is_valid_fasta = False
                try:
                    with open(self.target_path, "r", encoding="utf-8", errors="ignore") as check_f:
                        first_char = check_f.read(1)
                        if first_char == ">":
                            is_valid_fasta = True
                except Exception:
                    pass

                if is_valid_fasta:
                    # =========================================================
                    # 🗜️ PROTOKÓŁ AUTOMATYCZNEJ KOMPRESJI GZIP [INDEX]
                    # =========================================================
                    if not self.target_path.lower().endswith(".gz"):
                        self.log_signal.emit("[STORAGE]: Pobieranie ukończone. Uruchamiam automatyczną kompresję GZIP...")
                        gz_target_path = self.target_path + ".gz"
                        
                        # Blokowe przepisanie pliku do strumienia skompresowanego (poziom kompresji 6 - optymalny zrównoważony)
                        with open(self.target_path, 'rb') as f_in:
                            with gzip.open(gz_target_path, 'wb', compresslevel=6) as f_out:
                                while True:
                                    chunk = f_in.read(65536)
                                    if not chunk:
                                        break
                                    f_out.write(chunk)
                        
                        # Bezwzględne usunięcie pierwotnego, nieskompresowanego pliku tekstowego z dysku [INDEX]
                        os.remove(self.target_path)
                        
                        # Nadpisujemy ścieżkę docelową wersją skompresowaną dla celów komunikacji z GUI [INDEX]
                        self.target_path = gz_target_path

                    final_size_mb = os.path.getsize(self.target_path) / (1024.0 * 1024.0)
                    self.progress_signal.emit(100)
                    self.finished_signal.emit(True, self.target_path) # Dynamicznie zwracamy pełną ścieżkę do .fasta.gz [INDEX]
                else:
                    raise ValueError("Pobrany plik nie zaczyna się od znaku '>' (Błędny format sekwencji NCBI Nuccore).")
            else:
                raise FileNotFoundError("Odrzucono rekord: Serwer zwrócił pusty plik (Master Accession / brak sekwencji FASTA).")

        except Exception as e:
            # Bezpieczne i bezwarunkowe usunięcie śmieci i-węzłów z dysku NVMe w razie awarii [INDEX]
            if os.path.exists(self.target_path):
                try:
                    os.remove(self.target_path)
                except Exception:
                    pass
            self.finished_signal.emit(False, f"Awaria potoku sieciowego: {str(e)}")

    def kill_download(self):
        """Wymusza twarde i natychmiastowe przerwanie pobierania."""
        self._is_killed = True
