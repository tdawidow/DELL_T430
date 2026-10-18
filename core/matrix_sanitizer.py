# core/matrix_sanitizer.py
import os
import shutil

class MatrixFolderSanitizer(QObject if 'QObject' in globals() else object):
    """
    [CHIRURGICZNY ROBOTNIK SANITARNY TŁA - V34]:
    Niszczy wyłącznie surowe klony sekwencji wejściowych (*.fasta) oraz 
    całe drzewo katalogu blast_database, pozostawiając wyniki JSON, TSV oraz GZ [▲2].
    """
    def __init__(self, parent=None):
        if hasattr(self, 'parent'):
            super().__init__(parent)

    def execute_sandbox_sanitary_protocol(self, target_pair_dir: str):
        """
        [PANCERNY WYMIATACZ I-WĘZŁÓW]: Wywoływany po zwolnieniu deskryptorów.
        Siłowo czyści bazy BLAST oraz surowy wsad, chroniąc raporty końcowe [▲2].
        """
        if not target_pair_dir or not os.path.exists(target_pair_dir):
            return

        # Krok 1: Chirurgiczne, bezwzględne czyszczenie surowych klonów genomów wejściowych [▲2]
        target_files_to_wipe = ["sample.fasta", "reference.fasta"]
        for file_name in target_files_to_wipe:
            full_wipe_path = os.path.join(target_pair_dir, file_name)
            if os.path.exists(full_wipe_path) and os.path.isfile(full_wipe_path):
                try: os.remove(full_wipe_path)
                except Exception: pass

        # Krok 2: Bezwzględne, siłowe niszczenie całego osieroconego katalogu bazy BLAST [▲2]
        blast_db_dir = os.path.join(target_pair_dir, "blast_database")
        if os.path.exists(blast_db_dir):
            shutil.rmtree(blast_db_dir, ignore_errors=True)
