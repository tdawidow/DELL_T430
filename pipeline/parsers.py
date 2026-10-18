# pipeline/parsers.py
import os
import re

class KrakenParser:
    """Moduł odpowiedzialny za analizę raportów Kraken2 oraz bezpieczną ekstrakcję odczytów."""

    @staticmethod
    def parse_kraken_report(report_path: str, threshold: float = 0.1) -> list:
        """Skanuje plik kraken_report.txt i odrzuca szum poniżej progu 0.1%."""
        filtered_results = []
        if not os.path.exists(report_path):
            return filtered_results

        with open(report_path, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) < 6:
                    continue
                
                try:
                    percent = float(parts[0].strip())
                    reads = int(parts[1].strip())
                    rank = parts[3].strip()
                    taxid = parts[4].strip()
                    name = parts[5].strip()
                except ValueError:
                    continue

                if percent < threshold:
                    continue

                if rank in ['D', 'G', 'S']:
                    filtered_results.append({
                        "percent": percent,
                        "reads": reads,
                        "rank": rank,
                        "taxid": taxid,
                        "name": name
                    })
        return filtered_results

    @staticmethod
    def sanitize_linux_name(name: str) -> str:
        """Oczyszcza nazwy taksonów z nawiasów, spacji i znaków specjalnych dla Linuksa."""
        name_clean = re.sub(r'\[.*?\]|\(.*?\)', '', name)
        name_clean = re.sub(r'[^a-zA-Z0-9_\-]', '_', name_clean.strip())
        name_clean = re.sub(r'_{2,}', '_', name_clean)
        return name_clean.strip('_')

    @classmethod
    def build_extraction_command(cls, kraken_output_path: str, fastq_input_path: str, 
                                 taxid: str, output_fastq_path: str, is_clade: bool = True) -> list:
        """
        Buduje pancerne polecenie dla Krakentools.
        Wymusza flagę --fastq-output (4-liniowy format jakości Phred).
        """
        cmd = [
            "extract_kraken_reads.py",
            "-k", kraken_output_path,
            "-s", fastq_input_path,
            "-t", str(taxid).strip(),
            "-o", output_fastq_path,
            "--fastq-output"  # Gwarantuje poprawny format Phred (174MB)
        ]
        if is_clade:
            cmd.append("--include-children")
        return cmd

    @staticmethod
    def compress_extracted_fastq_cmd(output_fastq_path: str) -> list:
        """
        NOWOŚĆ: Generuje systemowe polecenie kompresji poekstrakcyjnej.
        Błyskawicznie kurczy plik tekstowy 180MB do binarnych 47MB (.fastq.gz).
        """
        # gzip -f wymusza nadpisanie i automatycznie usuwa ciężki plik .fastq po spakowaniu
        return ["gzip", "-f", output_fastq_path]
