# pipeline/step1_auto.py
import os
import config

class AutoPipelineStep1:
    """Generator potoku analitycznego dla Etapu 1 z jawnym wstrzykiwaniem ścieżek Miniforge3 i obsługą serii Batch."""

    def __init__(self, project_container_path: str, sample_file_path: str = None):
        """
        Konstruktor potoku. Jeśli sample_file_path jest podany (Tryb Batch), izoluje
        wyniki w podkatalogu o nazwie pliku, chroniąc dane przed nadpisaniem [INDEX].
        """
        self.project_path = project_container_path
        
        # LOGIKA IZOLACJI ARCHITEKTONICZNEJ DLA TRYBU BATCH [INDEX]
        if sample_file_path:
            # os.path.basename wyciąga np. "IonCode_0110.bam" z pełnej ścieżki
            raw_filename = os.path.basename(sample_file_path)
            # Usuwamy kropki i rozszerzenia, aby uzyskać czystą nazwę podfolderu [INDEX]
            sample_folder_name = raw_filename.replace(".fastq.gz", "").replace(".fastq", "").replace(".bam", "").replace(".BAM", "")
            
            # Punkt startowy dla tej próbki staje się dedykowanym podfolderem [INDEX]
            self.sample_root = os.path.join(self.project_path, sample_folder_name)
        else:
            # Pełna ciągłość wsteczna: dla pojedynczej próbki działamy bezpośrednio w głównym katalogu [INDEX]
            self.sample_root = self.project_path

        # Dynamiczne budowanie standardowej struktury podkatalogów laboratoryjnych [INDEX]
        self.dir_qc = os.path.join(self.sample_root, "01_QC")
        self.dir_tax = os.path.join(self.sample_root, "02_Taxonomy")
        self.dir_asm = os.path.join(self.sample_root, "03_Assembly")
        
        # Pancerne wymuszenie fizycznego utworzenia struktury na dysku NVMe [INDEX]
        os.makedirs(self.dir_qc, exist_ok=True)
        os.makedirs(self.dir_tax, exist_ok=True)
        os.makedirs(self.dir_asm, exist_ok=True)
        
        self.bin_prefix = "/home/ionadmin/miniforge3/envs/ion_analysis/bin/"
        self.mamba_python = os.path.join(self.bin_prefix, "python3")

    def build_pipeline_commands(self, input_fastq: str, platform: str, kraken_db: str, 
                                allocated_ram_gb: int, skip_qc: bool = False, force_only_assembly: bool = False) -> list:
        """[STERILE PIPELINE GENERATOR V52.5]: Pozbawiony nadmiarowości wejściowy spis bazy danych [2.4]."""
        commands = []
        cleaned_fastq = os.path.join(self.dir_qc, "cleaned_reads.fastq.gz")
        current_fastq = cleaned_fastq if not skip_qc else input_fastq
        active_input = input_fastq

        # =====================================================================
        # 1. KROK: KONTROLA JAKOŚCI (fastp) - TRADYCYJNY REKORD ODNIESIENIA [2.4]
        # =====================================================================
        if not skip_qc:
            report_html = os.path.join(self.dir_qc, "fastp_report.html")
            report_json = os.path.join(self.dir_qc, "fastp_report.json")
            
            fastp_args = [
                os.path.join(self.bin_prefix, "fastp"),
                "-i", active_input,
                "-o", cleaned_fastq,
                "-w", str(min(config.CURRENT_THREADS_LIMIT, 16)),
                "-h", report_html,
                "-j", report_json
            ]
            if platform.upper() == "NANOPORE":
                fastp_args.append("--nano")
                
            commands.append({
                "name": "Kontrola Jakości i Kompresja (fastp)",
                "args": fastp_args
            })

        else:
            commands.append({
                "name": "Pominięcie QC (Praca bezpośrednia na wskazanym wyciągu FASTQ.GZ)",
                "args": ["echo", f"Analiza pliku wyodrębnionego: {os.path.basename(active_input)}"]
            })

        if not force_only_assembly:
            kraken_output = os.path.join(self.dir_tax, "kraken_output.txt")
            kraken_report = os.path.join(self.dir_tax, "kraken_report.txt")
            kraken_args = [os.path.join(self.bin_prefix, "kraken2"), "--db", kraken_db, "--threads", str(min(config.CURRENT_THREADS_LIMIT, 16)), "--report", kraken_report]
            if current_fastq.lower().endswith(".gz"): kraken_args.append("--gzip-compressed")
            kraken_args.extend(["--output", kraken_output, current_fastq])
            commands.append({"name": "Klasyfikacja Taksonomiczna (Kraken2)", "args": kraken_args})

            krona_text = os.path.join(self.dir_tax, "krona_input.txt")
            krona_html = os.path.join(self.dir_tax, "krona_report.html")
            commands.append({"name": "Konwersja raportu Kraken do Krona", "args": [self.mamba_python, os.path.join(self.bin_prefix, "kreport2krona.py"), "-r", kraken_report, "-o", krona_text]})
            commands.append({"name": "Generowanie koła Krona HTML", "args": [os.path.join(self.bin_prefix, "ktImportText"), krona_text, "-o", krona_html]})

        if platform.upper() == "ION_TORRENT":
            asm_output_dir = os.path.join(self.dir_asm, "spades_output")
            asm_args = [os.path.join(self.bin_prefix, "spades.py"), "--iontorrent", "-s", current_fastq, "-o", asm_output_dir, "-m", str(allocated_ram_gb), "-t", str(min(config.CURRENT_THREADS_LIMIT, 16))]
            commands.append({"name": "Składanie Genomu De Novo (SPAdes IonTorrent ze wskazanego wyciągu)", "args": asm_args})
            final_contigs = os.path.join(asm_output_dir, "scaffolds.fasta")
        else:
            asm_output_dir = os.path.join(self.dir_asm, "flye_output")
            asm_args = [os.path.join(self.bin_prefix, "flye"), "--nano-hq", current_fastq, "--out-dir", asm_output_dir, "--threads", str(min(config.CURRENT_THREADS_LIMIT, 16))]
            commands.append({"name": "Składanie Genomu De Novo (Flye Nanopore HQ ze wskazanego wyciągu)", "args": asm_args})
            final_contigs = os.path.join(asm_output_dir, "assembly.fasta")

        quast_output_dir = os.path.join(self.dir_asm, "quast_report")
        commands.append({"name": "Analiza Jakości Składania Genomu (QUAST)", "args": [self.mamba_python, os.path.join(self.bin_prefix, "quast.py"), final_contigs, "-o", quast_output_dir, "--threads", str(min(config.CURRENT_THREADS_LIMIT, 16))]})
        return commands

    @staticmethod
    def commit_nvme_buffer(file_path: str):
        """Wymusza twarde opróżnienie i zamknięcie cache NVMe Kingston KC3000."""
        if os.path.exists(file_path):
            try:
                fd = os.open(file_path, os.O_RDWR)
                os.fsync(fd)
                os.close(fd)
            except Exception:
                pass
