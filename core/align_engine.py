# core/align_engine.py
import os
import re
import sys
import json
import shutil
import subprocess
from PyQt6.QtCore import QObject, pyqtSignal, QProcess, QProcessEnvironment, QEventLoop

class SinglePairAlignEngine(QObject):
    """
    [ATOMOWA JEDNOSTKA WYKONAWCZA JĄDRA V29.5 - MONOLITH SECURED]:
    Wykonuje wyrównania za pomocą bezpośrednich wywołań systemowych QProcess.
    Zapewnia natywne przekierowania strumieni I/O oraz sterylne indeksowanie kolumn.
    """
    started_signal = pyqtSignal(str)                                
    phase_changed_signal = pyqtSignal(str, int, str)               
    progress_signal = pyqtSignal(str, int)                         
    cli_log_signal = pyqtSignal(str) 
    finished_signal = pyqtSignal(bool, str, str, str)              

    def __init__(self, sample_fasta: str, reference_fasta: str, output_dir: str,
                 min_coverage: float, min_identity: float, threads: int,
                 run_mummer: bool, parent_key: str = "", run_blastn: bool = True,
                 mummer_scale: str = "BACTERIAL", blast_scale: str = "standard", parent=None):
        super().__init__(parent)
        self.sample_fasta = os.path.abspath(sample_fasta)
        self.reference_fasta = os.path.abspath(reference_fasta)
        self.output_dir = os.path.abspath(output_dir)
        self.min_coverage = min_coverage
        self.min_identity = min_identity
        self.threads = max(threads, 1)
        self.run_mummer = run_mummer
        self.run_blastn = run_blastn
        self.mummer_scale_mode = mummer_scale.upper()
        self.blast_scale_mode = blast_scale.lower()
        self.pair_key = parent_key if parent_key else "align_task"
        self._is_killed = False
        self.proc = None

    def kill_engine_process(self):
        self._is_killed = True

    def _run_command_direct_streaming(self, binary_name: str, args_list: list, init_msg: str, stdout_redirect: str = None) -> tuple:
        """
        [THE EVENT-DRIVEN KERNEL ENGINE - V48.1 - MULTI-THREAD]: Odpala procesy binarne OpenMP.
        Implementuje ścisły fallback binaru w locie RAM 0ms chroniący przed paraliżem [2.4].
        """
        if self._is_killed:
            return -1, "KILLED"
            
        self.cli_log_signal.emit(f"\n[JĄDRO CLI]: {init_msg}")
        python_bin_dir = os.path.dirname(sys.executable)
        
        # ✅ THE ABSOLUTE PATH ROUTING V48.1: Wstrzyknięcie wielonatywnego jądra MUMmer 4 OpenMP [2.4]
        if binary_name in ["nucmer", "show-coords"]:
            mummer4_bin = f"/home/ionadmin/miniforge3/envs/mummer4_env/bin/{binary_name}"
            # Bezpiecznik hybrydowy: jeśli bunkier istnieje, pożryj 80 wątków. Jeśli nie, spadaj na fallback! [2.4]
            full_binary_path = mummer4_bin if os.path.exists(mummer4_bin) else (shutil.which(binary_name) or binary_name)
        else:
            full_binary_path = os.path.join(python_bin_dir, binary_name)
            if not os.path.exists(full_binary_path):
                full_binary_path = shutil.which(binary_name) or binary_name
        env_profile = QProcessEnvironment.systemEnvironment()
        current_path_value = env_profile.value("PATH")
        env_profile.insert("PATH", f"{python_bin_dir}:{current_path_value}")
        
        self.cli_log_signal.emit(f" -> Bezpośredni program: {full_binary_path}")
        self.cli_log_signal.emit(f" -> Wektor argumentów: {str(args_list)}\n")
        
        # Inicjalizacja procesu bezpośrednio jako stały atrybut instancji klasy [2.4]
        self.proc = QProcess(self)
        self.proc.setProcessEnvironment(env_profile)
        
        # 🧼 SEPARATE CHANNELS INTERLOCK: Sterylna separacja kanałów I/O dla show-coords [2.4]
        if stdout_redirect:
            self.proc.setStandardOutputFile(stdout_redirect)
            self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        else:
            self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
            self.proc.readyReadStandardOutput.connect(self._handle_ready_read)
        # 🔒 PANCERNY INTERLOCK ZDARZENIOWY: Zero liczników czasu! [2.4]
        loop = QEventLoop()
        # Tylko fizyczna śmierć binaru zamyka pętlę zdarzeń sterowaną bezpośrednio sygnałem proc.finished! [2.4]
        self.proc.finished.connect(loop.quit)  
        
        self.proc.start(full_binary_path, args_list)
        
        # 🚀 ROZRUCH BEZLICZNIKOWY: loop.exec() zamraża metodę Pythona [2.4]
        # Interfejs graficzny monitora żyje i strumieniuje dane, bo pętla zdarzeń przetwarza sygnały w tle [2.4]
        loop.exec()
        # Bezpiecznik awaryjny dla twardego zabijania procesów z poziomu GUI
        if self._is_killed:
            if not stdout_redirect:
                # ✅ POPRAWKA: Wskazanie prawidłowego slotu zintegrowanego z Paczką nr 3
                try: self.proc.readyReadStandardOutput.disconnect(self._handle_ready_read)
                except Exception: pass
            self.proc.terminate()
            self.proc.waitForFinished(1000)
            self.proc.kill()
            return -1, "KILLED"

        return_code = self.proc.exitCode()
        error_msg = self.proc.errorString() if return_code != 0 else ""
        
        if not stdout_redirect:
            try: self.proc.readyReadStandardOutput.disconnect(self._handle_ready_read)
            except Exception: pass
            
        self.proc.deleteLater()
        self.proc = None
        return return_code, error_msg

    def _handle_ready_read(self):
        """[THE SECURE DISCONNECT SLOT]: Czyta bufor linii w locie rzeczywistym 0ms [2.4]."""
        if self.proc and self.proc.state() != QProcess.ProcessState.NotRunning:
            try:
                raw_data = self.proc.readAllStandardOutput().data()
                if raw_data:
                    text_line = str(raw_data, encoding='utf-8', errors='ignore').strip()
                    if text_line:
                        self.cli_log_signal.emit(f"   {text_line}")
            except RuntimeError:
                pass

    def execute_alignment_pipeline(self):
        """[PIPELINE ENGINE V54.0 - COORDS & SNPS TSV CORE]: Wymusza natywne sprawozdania MUMmer i BLASTn [2.4]."""
        try:
            self.started_signal.emit(self.pair_key)
            self.progress_signal.emit(self.pair_key, 5)
            mummer_data = {"mummer_status": "SKIPPED", "coverage": 0.0, "ani": 0.0, "total_aligned_length_bp": 0}
            blast_data = {"blastn_status": "SKIPPED", "pident": 0.0, "best_hit_e_value": 1.0, "mismatches": 0, "gaps": 0}
            
            if self.run_mummer:
                if self._is_killed: return
                self.phase_changed_signal.emit(self.pair_key, 1, "MUMMER_ALIGNING")
                self.progress_signal.emit(self.pair_key, 15)
                delta_out = os.path.join(self.output_dir, "mummer_run")
                
                if self.mummer_scale_mode == "VIRAL":
                    mummer_args = ["-t", str(self.threads), "-l", "12", "-c", "20", f"--prefix={delta_out}", self.sample_fasta, self.reference_fasta]
                else:
                    mummer_args = ["-t", str(self.threads), f"--prefix={delta_out}", self.sample_fasta, self.reference_fasta]
                    
                ret, err = self._run_command_direct_streaming("nucmer", mummer_args, "Wywołuję potok nucmer MULTI-THREAD OpenMP")
                if ret != 0: raise RuntimeError(f"Błąd nucmer: {err}")
                
                if self._is_killed: return
                self.phase_changed_signal.emit(self.pair_key, 2, "MUMMER_POST_PROCESSING")
                self.progress_signal.emit(self.pair_key, 35)
                
                delta_file = delta_out + ".delta"
                coords_file = delta_out + ".coords"
                snps_file = delta_out + ".snps.tsv"
                
                # A. GENEROWANIE RAPORTU WSPÓŁRZĘDNYCH (show-coords)
                coords_args = ["-r", "-c", "-l", "-T", delta_file]
                ret_c, err_c = self._run_command_direct_streaming("show-coords", coords_args, "Wyciągam metryki show-coords", stdout_redirect=coords_file)
                
                # B. GENEROWANIE RAPORTU MUTACJI PUNKTOWYCH (show-snps) - BRAK RADOSNEJ TWÓRCZOŚCI [2.4]
                snps_args = ["-T", "-r", "-H", delta_file]
                ret_s, err_s = self._run_command_direct_streaming("show-snps", snps_args, "Wyciągam natywny rejestr mutacji show-snps", stdout_redirect=snps_file)
                
                if ret_c == 0 and os.path.exists(coords_file):
                    mummer_data = self._parse_mummer_coords(coords_file)
                    mummer_data["mummer_status"] = "COMPLETED"
                else: 
                    mummer_data["mummer_status"] = f"ERROR: {err_c}"
                    
                # Zabezpieczenie przestrzeni dyskowej poprzez kompresję GZIP sprawozdań końcowych [2.4]
                if os.path.exists(delta_file): subprocess.run(["gzip", "-f", delta_file])
                if os.path.exists(coords_file): subprocess.run(["gzip", "-f", coords_file])
                if os.path.exists(snps_file): subprocess.run(["gzip", "-f", snps_file])

            if self.run_blastn:
                if self._is_killed: return
                self.phase_changed_signal.emit(self.pair_key, 3, "BLAST_DB_BUILDING")
                self.progress_signal.emit(self.pair_key, 50)
                blast_db_dir = os.path.join(self.output_dir, "blast_database")
                os.makedirs(blast_db_dir, exist_ok=True)
                blast_db_out = os.path.join(blast_db_dir, "ref_db")
                db_args = ["-in", self.reference_fasta, "-dbtype", "nucl", "-title", "ref_db", "-out", blast_db_out]
                ret_db, err_db = self._run_command_direct_streaming("makeblastdb", db_args, "Buduję bazę makeblastdb")
                if ret_db != 0: raise RuntimeError(f"Błąd makeblastdb: {err_db}")
                
                if self._is_killed: return
                self.phase_changed_signal.emit(self.pair_key, 4, "BLAST_ALIGNING")
                self.progress_signal.emit(self.pair_key, 65)
                
                blast_out_asn = os.path.join(self.output_dir, "blast_identity.asn")
                blast_out_tsv = os.path.join(self.output_dir, "blast_identity.tsv")
                
                if self.blast_scale_mode == "blastn-short":
                    blast_args = ["-task", "blastn-short", "-word_size", "7", "-query", self.sample_fasta, "-db", blast_db_out, "-out", blast_out_asn, "-outfmt", "11", "-evalue", "0.01", "-num_threads", str(self.threads)]
                elif self.blast_scale_mode == "megablast":
                    blast_args = ["-task", "megablast", "-word_size", "28", "-query", self.sample_fasta, "-db", blast_db_out, "-out", blast_out_asn, "-outfmt", "11", "-evalue", "0.01", "-num_threads", str(self.threads)]
                else:
                    blast_args = ["-task", "blastn", "-word_size", "11", "-query", self.sample_fasta, "-db", blast_db_out, "-out", blast_out_asn, "-outfmt", "11", "-evalue", "0.01", "-num_threads", str(self.threads)]
                    
                ret_b, err_b = self._run_command_direct_streaming("blastn", blast_args, "Uruchamiam silnik blastn (Zrzut bazy binarnej ASN.1)")
                
                if ret_b == 0 and os.path.exists(blast_out_asn):
                    # Pobieramy wyłącznie super-lekką, zwalidowaną tabelę statystyczną formatu 6 [2.4]
                    fmt_tsv_args = ["-archive", blast_out_asn, "-outfmt", "6 qseqid sseqid pident length mismatch gaps evalue", "-out", blast_out_tsv]
                    self._run_command_direct_streaming("blast_formatter", fmt_tsv_args, "Ekstrahuję czystą tabelę statystyczną TSV")
                    
                    if os.path.exists(blast_out_tsv):
                        blast_data = self._parse_blast_tsv(blast_out_tsv)
                        blast_data["blastn_status"] = "COMPLETED"
                        subprocess.run(["gzip", "-f", blast_out_tsv])
                    subprocess.run(["gzip", "-f", blast_out_asn])
                else:
                    blast_data["blastn_status"] = f"ERROR: {err_b}"
                    
                for ext in [".nhr", ".nin", ".nsq"]:
                    f_del = blast_db_out + ext
                    if os.path.exists(f_del):
                        try: os.remove(f_del)
                        except Exception: pass
                try: os.rmdir(blast_db_dir)
                except Exception: pass

            if self._is_killed: return
            self.phase_changed_signal.emit(self.pair_key, 5, "METRICS_AGREGATING")
            self.progress_signal.emit(self.pair_key, 90)
            
            cov_real = mummer_data["coverage"] if self.run_mummer else 0.0
            id_real = mummer_data["ani"] if self.run_mummer else blast_data["pident"]
            
            eval_status, is_match = "🟢 HIGH_HOMOLOGY", True
            notes = "Izolat wykazuje pełną syntenię i wysokie pokrewieństwo genetyczne z wzorcem RefSeq."
            
            if cov_real < self.min_coverage:
                eval_status, is_match = "🔴 SHORT_COVERAGE", False
                notes = f"Odrzucono: Pokrycie genomu ({cov_real:.2f}%) poniżej kryterium laboratorium."
            elif id_real < self.min_identity:
                eval_status, is_match = "🔴 LOW_IDENTITY", False
                notes = f"Odrzucono: Tożsamość ewolucyjna ANI ({id_real:.2f}%) poniżej progu rygoru."
                
            metrics_vector = {
                "pair_metadata": {"pair_key": self.pair_key, "timestamp_end": subprocess.getoutput("date '+%Y-%m-%d %H:%M:%S'"), "allocated_cores_execution": self.threads},
                "mummer_global_metrics": mummer_data, "blastn_local_metrics": blast_data,
                "biological_evaluation": {"thresholds_applied": {"required_min_coverage_pct": self.min_coverage, "required_min_identity_pct": self.min_identity}, "evaluation_status": eval_status, "is_epidemiological_match": is_match, "notes": notes}
            }
            
            json_path = os.path.join(self.output_dir, "pair_metrics.json")
            with open(json_path, "w", encoding="utf-8") as json_f:
                json.dump(metrics_vector, json_f, indent=4, ensure_ascii=False)
                
            self.progress_signal.emit(self.pair_key, 100)
            self.finished_signal.emit(True, self.pair_key, json_path, "")
            
        except Exception as e:
            self.finished_signal.emit(False, self.pair_key, "", str(e))

    def _parse_mummer_coords(self, coords_path: str) -> dict:
        """[THE ITERATIVE FORWARD COORDS PARSER]: Skanuje tabelę show-coords -T [2.4]."""
        try:
            if not os.path.exists(coords_path) or os.path.getsize(coords_path) == 0:
                return {"coverage": 0.0, "ani": 0.0, "total_aligned_length_bp": 0}
            total_aligned_len = 0
            weighted_identity_sum = 0.0
            ref_total_length = 0
            with open(coords_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    cleaned_line = line.strip()
                    if not cleaned_line: continue
                    tokens = cleaned_line.split("\t")
                    if len(tokens) >= 11:
                        try:
                            int(tokens[0].strip())
                            aligned_len = int(tokens[4].strip())
                            identity = float(tokens[6].strip())
                            ref_total_length = int(tokens[7].strip())
                            total_aligned_len += aligned_len
                            weighted_identity_sum += (identity * aligned_len)
                        except ValueError: continue
            global_coverage = (total_aligned_len / ref_total_length * 100.0) if ref_total_length > 0 else 0.0
            global_ani = (weighted_identity_sum / total_aligned_len) if total_aligned_len > 0 else 0.0
            if global_coverage > 100.0: global_coverage = 100.0
            return {"coverage": round(global_coverage, 2), "ani": round(global_ani, 2), "total_aligned_length_bp": total_aligned_len}
        except Exception:
            return {"coverage": 0.0, "ani": 0.0, "total_aligned_length_bp": 0}

    def _parse_blast_tsv(self, tsv_path: str) -> dict:
        """[THE TRADITIONAL BLAST TSV PARSER - RESTORED]: Przywrócone parsowanie 7-kolumnowej tabeli [2.4]."""
        try:
            if not os.path.exists(tsv_path) or os.path.getsize(tsv_path) == 0:
                return {"pident": 0.0, "best_hit_e_value": 1.0, "mismatches": 0, "gaps": 0}
            total_pident = 0.0
            total_mismatches = 0
            total_gaps = 0
            hits_count = 0
            best_evalue = 1.0
            with open(tsv_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    cleaned_line = line.strip()
                    if not cleaned_line: continue
                    tokens = cleaned_line.split("\t")
                    if len(tokens) >= 7:
                        hits_count += 1
                        total_pident += float(tokens[2])
                        total_mismatches += int(tokens[4])
                        total_gaps += int(tokens[5])
                        try:
                            ev = float(tokens[6])
                            if ev < best_evalue: best_evalue = ev
                        except ValueError: pass
            avg_pident = (total_pident / hits_count) if hits_count > 0 else 0.0
            return {"total_hits_processed": hits_count, "pident": avg_pident, "best_hit_e_value": best_evalue, "mismatches": total_mismatches, "gaps": total_gaps}
        except Exception:
            return {"pident": 0.0, "best_hit_e_value": 1.0, "mismatches": 0, "gaps": 0}
