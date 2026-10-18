# core/library_manager.py
import os
import json
from datetime import datetime
import config

class LibraryManager:
    def __init__(self):
        self.library_dir = config.LIBRARY_DIR
        self.index_file = config.LIBRARY_INDEX_FILE
        self._initialize_library()

    def _initialize_library(self):
        """Tworzy strukturę biblioteki i plik indeksu, jeśli nie istnieją."""
        os.makedirs(self.library_dir, exist_ok=True)
        if not os.path.exists(self.index_file):
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump({}, f, indent=4, ensure_ascii=False)

    def _load_index(self) -> dict:
        """Wczytuje aktualny indeks biblioteki z pliku JSON."""
        try:
            with open(self.index_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _save_index(self, index: dict):
        """Zapisuje zaktualizowany indeks biblioteki do pliku JSON."""
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(index, f, indent=4, ensure_ascii=False)

    def check_genome_status(self, accession_number: str) -> dict:
        """
        Sprawdza, czy genom o danym numerze Accession istnieje w lokalnej bibliotece.
        Zwraca słownik z informacjami o pliku lub informację o braku pozycji.
        """
        accession_number = accession_number.strip()
        index = self._load_index()
        
        if accession_number in index:
            file_path = os.path.join(self.library_dir, index[accession_number]['filename'])
            # Dodatkowa weryfikacja czy plik fizyczne istnieje na dysku Kingston
            if os.path.exists(file_path):
                return {
                    "status": "LOCAL",
                    "path": file_path,
                    "metadata": index[accession_number]
                }
        
        return {"status": "ONLINE", "path": None, "metadata": None}

    def add_genome_to_library(self, accession_number: str, organism_name: str, sequence_length_bp: int, fasta_content: str) -> str:
        """
        Zapisuje nowo pobraną sekwencję FASTA do biblioteki na Kingston KC3000
        oraz aktualizuje indeks JSON o metadane.
        """
        accession_number = accession_number.strip()
        filename = f"{accession_number}.fasta"
        full_path = os.path.join(self.library_dir, filename)

        # Zapis fizycznego pliku sekwencji
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(fasta_content)

        # Aktualizacja bazy danych indeksu
        index = self._load_index()
        index[accession_number] = {
            "organism": organism_name.strip(),
            "length_bp": int(sequence_length_bp),
            "filename": filename,
            "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self._save_index(index)
        
        return full_path

    def get_all_local_references(self) -> list:
        """Zwraca kompletną listę wszystkich pozycji zapisanych w bibliotece."""
        index = self._load_index()
        local_list = []
        for acc, meta in index.items():
            local_list.append({
                "accession": acc,
                "organism": meta["organism"],
                "length_bp": meta["length_bp"],
                "added_at": meta["added_at"]
            })
        return local_list
