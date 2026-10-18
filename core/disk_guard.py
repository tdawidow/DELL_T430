# core/disk_guard.py
import os
import shutil

class DiskGuard:
    """Narzędzie bezpieczeństwa monitorujące przestrzeń dysku Kingston KC3000."""
    
    def __init__(self, target_directory: str):
        """Inicjalizuje moduł dla wskazanego katalogu roboczego."""
        self.target_dir = os.path.abspath(target_directory)

    def get_free_space_gb(self) -> float:
        """Zwraca rzeczywistą ilość wolnego miejsca na partycji w gigabajtach (GB)."""
        try:
            # shutil.disk_usage działa natywnie i bezbłędnie w systemie Linux
            total, used, free = shutil.disk_usage(self.target_dir)
            return round(free / (1024 ** 3), 2)
        except FileNotFoundError:
            # Jeśli katalog jeszcze nie powstał, sprawdzamy katalog nadrzędny
            parent_dir = os.path.dirname(self.target_dir)
            total, used, free = shutil.disk_usage(parent_dir)
            return round(free / (1024 ** 3), 2)

    def validate_space_for_pipeline(self, input_files_paths: list, platform: str) -> tuple:
        """
        Ocenia, czy wolne miejsce na dysku Kingston KC3000 jest wystarczające.
        Wykorzystuje mnożniki bezpieczeństwa dla technologii Ion Torrent i Nanopore.
        
        Zwraca: (True/False, "Komunikat statusu dla GUI")
        """
        # 1. Oblicz całkowitą wagę surowych plików wejściowych
        total_input_size_bytes = 0
        for path in input_files_paths:
            if os.path.exists(path):
                total_input_size_bytes += os.path.getsize(path)
                
        input_size_gb = total_input_size_bytes / (1024 ** 3)
        
        # 2. Dobierz mnożnik bioinformatyczny na pliki tymczasowe i pośrednie
        # POD5 dla Nanopore generuje ogromną ilość danych podczas basecallingu i składania.
        # Pliki BAM dla Ion Torrent po rozpakowaniu do potoków generują mniejszy narzut.
        multiplier = 2.5 if platform.upper() == "NANOPORE" else 1.5
        
        # Dodajemy stały margines bezpieczeństwa na logi i raporty (np. 15 GB)
        required_space_gb = (input_size_gb * multiplier) + 15.0
        free_space_gb = self.get_free_space_gb()
        
        # 3. Weryfikacja logiczna
        if free_space_gb >= required_space_gb:
            status_msg = f"Przestrzeń OK (Dostępne: {free_space_gb} GB, Wymagane szacunkowo: {round(required_space_gb, 2)} GB)"
            return True, status_msg
        else:
            status_msg = f"BRAK MIEJSCA! Dostępne: {free_space_gb} GB, Wymagane: {round(required_space_gb, 2)} GB. Oczyść dysk!"
            return False, status_msg
