# pipeline/step2_compare.py
import os
import config

class ComparativePipelineStep2:
    """Silnik wykonawczy dla Etapu 2: lokalne mapowania BLASTn oraz wykresy MUMmer Dot Plot."""

    def __init__(self, current_project_path: str):
        self.project_path = current_project_path
        self.dir_compare = os.path.join(self.project_path, "04_Comparative")

    def build_comparison_commands(self, query_fasta: str, reference_fasta: str, 
                                  min_match_length: int, reverse_complement: bool = False) -> list:
        """
        Generuje sekwencję komend CLI dla narzędzi makeblastdb, blastn, nucmer i mummerplot.
        Wykorzystuje globalny limit wątków z konfiguratora, chroniąc system przed zawieszeniem.
        """
        commands = []
        threads_str = str(config.CURRENT_THREADS_LIMIT)

        # Definicje ścieżek wyjściowych wewnątrz folderu projektu
        blast_db_prefix = os.path.join(self.dir_compare, "temp_blast_db")
        blast_output_tab = os.path.join(self.dir_compare, "blastn_mutations.tab")
        mummer_prefix = os.path.join(self.dir_compare, "mummer_align")
        mummer_delta = f"{mummer_prefix}.delta"

        # 1. KROK: Tworzenie tymczasowej lokalnej bazy BLAST z pliku referencyjnego
        commands.append({
            "name": "Przygotowanie bazy referencyjnej BLAST (makeblastdb)",
            "args": ["makeblastdb", "-in", reference_fasta, "-dbtype", "nucl", "-out", blast_db_prefix]
        })

        # 2. KROK: Uruchomienie lokalnego BLASTn (Format tabelaryczny 6 z kluczowymi kolumnami)
        # qstart qend sstart send pident mismatch gaps qseqid sseqid
        commands.append({
            "name": "Analiza polimorfizmów całogenomowych (BLASTn)",
            "args": [
                "blastn",
                "-query", query_fasta,
                "-db", blast_db_prefix,
                "-out", blast_output_tab,
                "-outfmt", "6 qstart qend sstart send pident mismatch gaps qseqid sseqid",
                "-num_threads", threads_str
            ]
        })

        # 3. KROK: Dopasowanie makroskopowe genomów (MUMmer nucmer)
        commands.append({
            "name": "Wyrównanie strukturalne genomów (MUMmer nucmer)",
            "args": ["nucmer", "--prefix=", mummer_prefix, reference_fasta, query_fasta, "--threads", threads_str]
        })

        # 4. KROK: Generowanie skryptów wykresu Gnuplot (mummerplot)
        mummerplot_args = [
            "mummerplot",
            "-R", reference_fasta,
            "-Q", query_fasta,
            "--png",
            "-p", os.path.join(self.dir_compare, "dotplot"),
            mummer_delta
        ]
        
        # Opcjonalne odwrócenie nici (Reverse Complement) na wykresie
        if reverse_complement:
            mummerplot_args.append("-r")

        commands.append({
            "name": "Generowanie wykresu makroskopowego Dot Plot (mummerplot)",
            "args": mummerplot_args
        })

        return commands

    @staticmethod
    def parse_blast_tabular_results(blast_tab_path: str) -> list:
        """
        Parsuje plik wynikowy formatu wyjściowego 6 z BLASTn.
        Wyodrębnia pozycje i typy zmian, filtrując idealne dopasowania.
        """
        mutations_list = []
        if not os.path.exists(blast_tab_path):
            return mutations_list

        with open(blast_tab_path, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) < 7:
                    continue
                
                try:
                    q_start = parts[0]
                    q_end = parts[1]
                    p_ident = float(parts[4])
                    mismatches = int(parts[5])
                    gaps = int(parts[6])
                except ValueError:
                    continue

                # Jeśli dopasowanie nie jest w 100% identyczne, wyodrębniamy anomalie/mutacje
                if p_ident < 100.0 or mismatches > 0 or gaps > 0:
                    mutation_type = "Substytucja / Mismatch" if mismatches > 0 else "Indel (Przerwa)"
                    if gaps > 0 and mismatches > 0:
                        mutation_type = "Złożona zmiana (SNP+Indel)"

                    mutations_list.append({
                        "position": f"{q_start}-{q_end}",
                        "type": mutation_type,
                        "identity": f"{p_ident}%",
                        "mismatches": str(mismatches + gaps)
                    })

        return mutations_list
