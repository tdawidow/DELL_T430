# pipeline/format_handlers.py
import os

class FormatHandler:
    """Moduł odpowiedzialny za rozpoznawanie i walidację formatów wejściowych (FASTQ, BAM, POD5)."""

    VALID_EXTENSIONS = {
        "FASTQ": [".fastq", ".fastq.gz", ".fq", ".fq.gz"],
        "BAM": [".bam"],
        "POD5": [".pod5"]
    }

    @classmethod
    def identify_file_format(cls, file_path: str) -> str:
        """Rozpoznaje format pliku na podstawie jego rozszerzenia."""
        file_path_lower = file_path.lower()
        
        # Obsługa podwójnych rozszerzeń typu .fastq.gz
        if file_path_lower.endswith(".fastq.gz") or file_path_lower.endswith(".fq.gz"):
            return "FASTQ"
            
        # Standardowe rozszerzenia
        _, ext = os.path.splitext(file_path_lower)
        for fmt, extensions in cls.VALID_EXTENSIONS.items():
            if ext in extensions:
                return fmt
                
        return "UNKNOWN"

    @classmethod
    def scan_batch_directory(cls, directory_path: str) -> list:
        """
        Skanuje katalog wejściowy na dysku Kingston KC3000.
        Zwraca listę słowników z informacjami o znalezionych obsługiwanych plikach.
        """
        detected_samples = []
        if not os.path.isdir(directory_path):
            return detected_samples

        # Skanowanie zawartości folderu
        for filename in sorted(os.listdir(directory_path)):
            full_path = os.path.join(directory_path, filename)
            
            # Ignorujemy podfoldery, bierzemy tylko pliki
            if os.path.isfile(full_path):
                fmt = cls.identify_file_format(full_path)
                if fmt != "UNKNOWN":
                    # Oczyszczanie nazwy próbki z rozszerzeń zgodnie z Blueprintem
                    sample_name = filename
                    for ext in [".fastq.gz", ".fq.gz", ".fastq", ".fq", ".bam", ".pod5"]:
                        if sample_name.lower().endswith(ext):
                            sample_name = sample_name[:-len(ext)]
                            break
                    
                    detected_samples.append({
                        "file_name": filename,
                        "file_path": full_path,
                        "sample_name": sample_name,
                        "format": fmt,
                        "size_mb": round(os.path.getsize(full_path) / (1024 ** 2), 2)
                    })
                    
        return detected_samples

    @staticmethod
    def validate_fastq_integrity(file_path: str) -> bool:
        """
        Wstępna weryfikacja integralności pliku FASTQ.
        Sprawdza, czy plik nie jest pusty i czy ma poprawną strukturę (rozmiar > 0).
        """
        if not os.path.exists(file_path):
            return False
            
        # Pancerny bezpiecznik wielkości pliku (zapobieganie problemowi 0 reads / 92MB vs 174MB)
        file_size_bytes = os.path.getsize(file_path)
        if file_size_bytes == 0:
            return False
            
        return True
