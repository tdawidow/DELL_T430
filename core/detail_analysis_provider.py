# core/detail_analysis_provider.py
import os

class DetailAnalysisProvider:
    """[THE PRE-FLIGHT VALIDATION GATE V55.0]: Sterylna brama weryfikacji sprawozdań pary [2.4]."""
    def __init__(self):
        # Zachowujemy pasywny wskaźnik ścieżki dla zachowania kompatybilności wstecznej interfejsów GUI
        self.ramdisk_path = "/dev/shm/kombajn_temp_align.txt"

    def clear_ramdisk_buffer(self):
        """Metoda pasywna - zachowana dla zachowania spójności wywołań sygnałów PyQt6 [2.4]."""
        pass

    def prepare_ramdisk_source(self, metrics_json_path: str) -> tuple:
        """[THE REVENUE INTERLOCK GUARD]: Sprawdza obecność kompletu trzech spakowanych raportów GZ [2.4]."""
        project_dir = os.path.dirname(os.path.abspath(metrics_json_path))
        
        # Definicje trzech zaryglowanych na dysku NVMe Kingston sprawozdań końcowych [2.4]
        required_files = [
            ("Maksymalnie spakowany izolat pacjenta", os.path.join(project_dir, "contigs.fasta.gz")),
            ("Natywny rejestr mutacji show-snps", os.path.join(project_dir, "mummer_run.snps.tsv.gz")),
            ("Raport współrzędnych show-coords", os.path.join(project_dir, "mummer_run.coords.gz"))
        ]
        
        # Chirurgiczny sprawdzian fizycznej obecności i-węzłów na partycji ext4 [2.4]
        for label, file_path in required_files:
            if not os.path.exists(file_path):
                return False, f"🚨 ALARM I/O: {label} NIE ISTNIEJE pod ścieżką:\n{file_path}"
            if os.path.getsize(file_path) == 0:
                return False, f"🚨 USZKODZENIE DANYCH: {label} ma rozmiar 0 bajtów."
                
        # Komplet zweryfikowany pomyślnie - otwieramy śluzę i wpuszczamy strumień danych do GUI [2.4]
        return True, ""
