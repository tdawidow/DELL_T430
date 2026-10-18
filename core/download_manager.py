# core/download_manager.py
import os
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from core.universal_downloader import UniversalDownloadWorker

class BatchDownloadManager(QObject):
    """
    [CENTRALNY MANAGER KOLEJKOWANIA SIECIOWEGO V1 - THROTTLED POOL]:
    Zapewnia automatyczne i sekwencyjne pobieranie masowych serii genomów z NCBI.
    Rygorystycznie ogranicza aktywność do maksymalnie 3 pobierań jednocześnie,
    zapobiegając blokadom anty-DDoS (HTTP 429) i odciążając magistralę I/O [INDEX].
    """
    # Sygnały przekaźnikowe (Signal Relay) synchronizujące postęp bezpośrednio z tabelą GUI
    task_started_signal = pyqtSignal(str)              # Emituje path: wątek przeszedł z oczekiwania do pobierania
    task_progress_signal = pyqtSignal(int, str)         # Emituje (procent, path): postęp konkretnego wątku
    task_finished_signal = pyqtSignal(bool, str, str)   # Emituje (sukces, komunikat, path): finał operacji dyskowej

    def __init__(self, parent=None):
        """Inicjalizuje centralny menedżer dławienia strumieni sieciowych."""
        super().__init__(parent)
        self.master_queue = []    # Koszyk zadań oczekujących w kolejce FIFO (lista słowników)
        self.active_slots = {}    # Słownik żywych, aktywnych wątków {target_path: UniversalDownloadWorker}
        self.max_concurrent = 3   # Twardy, zwalidowany inżynieryjnie limit slotów przesyłowych [INDEX]

    def add_batch_to_queue(self, download_tasks: list):
        """
        Przyjmuje paczkę zadań seryjnych z GUI i wstrzykuje je do kolejki FIFO.
        :param download_tasks: Lista słowników o strukturze {"url": str, "target": str, "monitor_log": object}
        """
        for task in download_tasks:
            target = task.get("target")
            url = task.get("url")
            monitor_log = task.get("monitor_log")
            
            if not target or not url:
                continue
                
            # Budujemy wewnętrzny rekord zadania dla locie RAM
            task_record = {
                "url": url,
                "target": target,
                "monitor_log": monitor_log
            }
            self.master_queue.append(task_record)

        # Wywołujemy kaskadowy start procesów w wolnych slotach
        self._process_next_queue_slots()

    def _process_next_queue_slots(self):
        """[CASCADE INJECTOR]: Sprawdza dostępność wolnych slotów i budzi kolejne wątki [INDEX]."""
        # Dopóki mamy wolne miejsca i zadania czekające w koszyku FIFO
        while len(self.active_slots) < self.max_concurrent and self.master_queue:
            # Pobieramy dokładnie jedno zadanie z samej góry listy oczekujących (FIFO pop)
            task = self.master_queue.pop(0)
            target_path = task["target"]
            source_url = task["url"]
            monitor_log = task["monitor_log"]

            # Sprawdzamy czy dany plik nie jest już przypadkiem procesowany (Zabezpieczenie RAM)
            if target_path in self.active_slots:
                continue

            # Inicjalizacja asynchronicznego workera z automatyczną kompresją GZIP
            worker = UniversalDownloadWorker(source_url, target_path)
            
            # Podpinanie logowania bezpośrednio do głównego Monitora Procesu
            if monitor_log:
                worker.log_signal.connect(monitor_log)

            # Przechwytywanie i tunelowanie sygnałów postępu oraz ukończenia operacji przez lambdy [INDEX]
            worker.progress_signal.connect(
                lambda pct, fp=target_path: self._handle_worker_progress(pct, fp)
            )
            worker.finished_signal.connect(
                lambda success, msg, fp=target_path: self._handle_worker_finished(success, msg, fp)
            )

            # Ryglujemy wątek w słowniku aktywnych zasobów, chroniąc przed Garbage Collectorem
            self.active_slots[target_path] = worker
            
            # Emitujemy sygnał przejścia zadania ze statusu OCZEKIWANIA w tryb AKTYWNY
            self.task_started_signal.emit(target_path)
            
            # Uruchomienie odizolowanego procesu sieciowego
            worker.start()

    def _handle_worker_progress(self, percent: int, target_path: str):
        """Tuneluje surowy procent postępu z konkretnego wątku wprost do słuchacza GUI [INDEX]."""
        self.task_progress_signal.emit(percent, target_path)

    def _handle_worker_finished(self, success: bool, final_msg_or_path: str, target_path: str):
        """
        [SIGNAL RELAY]: Przechwytuje koniec pracy wątku, zwalnia slot transmisyjny
        i automatycznie wybudza z kolejki FIFO kolejne oczekujące zadanie [INDEX].
        """
        # Usunięcie instancji z rejestru aktywnych slotów roboczych
        if target_path in self.active_slots:
            worker = self.active_slots.pop(target_path)
            # Wymuszenie bezpiecznego odraczania pamięci w standardzie Qt POSIX
            worker.deleteLater()

        # Emitujemy sygnał zbiorczy do tabeli Osi M w celu zmiany barwy na 🟢 lub 🔴
        # Przekazujemy final_msg_or_path (który przy sukcesie jest nową ścieżką .gz!) [INDEX]
        self.task_finished_signal.emit(success, final_msg_or_path, target_path)

        # KASKADA: Samoczynne wybudzenie kolejnego oczekującego w pętli zadania! [INDEX]
        self._process_next_queue_slots()

    def kill_all_manager_downloads(self):
        """Twarde ryglowanie i czyszczenie całego podsystemu przesyłowego (Stop/Kill)."""
        self.master_queue.clear()
        for target_path, worker in list(self.active_slots.items()):
            if worker:
                worker.kill_download()
                worker.quit()
                worker.wait()
                worker.deleteLater()
        self.active_slots.clear()
