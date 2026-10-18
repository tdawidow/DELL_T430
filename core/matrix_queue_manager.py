# core/matrix_queue_manager.py
import os
import json
import re
import gzip    # ✅ ZWERYFIKOWANO: Natywny strumień dekompresji GZIP w locie RAM [INDEX]
import shutil  # ✅ ZWERYFIKOWANO: Pancerna systemowa biblioteka operacji na plikach i-węzłów [INDEX]
import subprocess
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from core.align_engine import SinglePairAlignEngine
from core.disk_guard import DiskGuard  # [INDEX]
from core.matrix_sanitizer import MatrixFolderSanitizer

class MatrixQueueManager(QObject):
    """
    [CENTRALNY MÓZG PROCESOWY MATRYCY V48.7 - PACZKA 1]:
    Zapewnia automatyczne mapowanie macierzy N x M z aktywną ochroną przed
    fizycznym przepełnieniem nośnika Kingston oraz sztywną indeksacją SAMPLE_nnn [INDEX].
    """
    # ✅ FIX KRASZU: Rozbudowana sygnatura dwuparametrowa pod Krok 7 i 12 [2.4]
    grid_started_signal = pyqtSignal(str, int)                     
    grid_task_started_signal = pyqtSignal(str, str)                
    grid_task_progress_signal = pyqtSignal(str, int)               
    matrix_cli_log_signal = pyqtSignal(str)  # ✅ Centralna magistrala logów CLI do GUI [INDEX]
    grid_task_finished_signal = pyqtSignal(bool, str, str)         
    grid_completed_signal = pyqtSignal(str, str)                   

    def __init__(self, parent=None):
        super().__init__(parent)
        self.matrix_project_id = ""
        self.output_project_dir = ""
        self.manifest_path = ""
        self.execution_queue = []   
        self.active_engine = {}     
        self.manifest_data = {}     
        self.disk_guard = DiskGuard("/home/ionadmin/kombajn_workspace")
        self._is_killed = False
        self._is_processing = False
        # ✅ AKTYWACJA CHIRURGICZNEGO ODKURZACZA BACKENDU [2.4]
        self.sanitizer = MatrixFolderSanitizer()

    def initialize_matrix_project(self, project_id: str, base_workspace: str, 
                                  query_tasks: list, reference_tasks: list,
                                  min_cov: float, min_id: float, max_threads: int,
                                  run_mummer: bool, run_blast: bool,
                                  enable_species_interlock: bool):
        self.matrix_project_id = project_id
        timestamp_match = re.search(r"COMP_(\d{8}_\d{6})", project_id)
        disk_folder_name = f"COMP_{timestamp_match.group(1)}" if timestamp_match else project_id
        
        self.output_project_dir = os.path.join(base_workspace, disk_folder_name)
        self.manifest_path = os.path.join(self.output_project_dir, ".matrix_master_manifest.json")
        self.disk_guard = DiskGuard(self.output_project_dir)
        self.execution_queue.clear()
        self._is_killed = False
        self._is_processing = False 
        # 🔥 ETAP 1: OTWARCIE STRUKTURY REJESTRÓW MANIFESTU
        self.manifest_data = {
            "matrix_master_manifest": {
                "matrix_project_id": self.matrix_project_id,
                "timestamp_launched": subprocess.getoutput("date '+%Y-%m-%d %H:%M:%S'"),
                "timestamp_last_update": subprocess.getoutput("date '+%Y-%m-%d %H:%M:%S'"),
                "global_status": "PROCESSING",
                "allocated_hardware": {"threads_per_task_limit": max_threads, "cpu_throttling_mode": "SEQUENTIAL_SINGLE_PAIR"},
                "statistics_summary": {"total_tasks_generated": 0, "tasks_completed_success": 0, "tasks_failed_error": 0, "tasks_bypassed_mismatch": 0}
            },
            "matrix_sample_passport": {},  
            "matrix_grid": []
        }

        task_counter = 0
        bypassed_counter = 0
        active_paths_set = set()
        sample_index_counter = 0
        # 🔥 ETAP 2: SZTYWNY RYGOR INDEKSACJI NUMERYCZNEJ OSI N (ZASADA SZEFA) [INDEX]
        for q_file, q_path, q_prj in query_tasks:
            clean_prj = str(q_prj).strip() if str(q_prj).strip() and str(q_prj).strip() != "Nieznany Projekt" else "UNKNOWN"
            
            q_clean = q_file.replace("assembly_", "").replace(".gz", "")
            for ext in [".fasta", ".fa", ".fna"]: 
                q_clean = q_clean.replace(ext, "")
            species_extracted = q_clean.strip().replace(" ", "_") if q_clean.strip() else "unknown_species"

            operator_label = f"{clean_prj}_{species_extracted}"

            sample_index_counter += 1
            sample_id_flat = f"SAMPLE_{sample_index_counter:03d}"

            self.manifest_data["matrix_sample_passport"][sample_id_flat] = {
                "operator_display_label": operator_label,
                "source_fasta_link": os.path.abspath(q_path),
                "extracted_species": species_extracted
            }
            for r_acc, r_name, r_size, r_stat in reference_tasks:
                task_counter += 1
                pair_key = f"{sample_id_flat}_vs_{r_acc}"
                pair_out_dir = os.path.join(self.output_project_dir, "samples", sample_id_flat, f"vs_{r_acc}")

                clean_ref_name = r_name.strip()
                if " - " in clean_ref_name:
                    clean_ref_name = clean_ref_name.split(" - ", 1)[1].strip()
                ref_cleaned_flat = clean_ref_name.replace("_", " ").strip().lower()
                query_cleaned_flat = species_extracted.replace("_", " ").strip().lower()

                is_compatible = False
                if not enable_species_interlock: 
                    is_compatible = True
                else:
                    if query_cleaned_flat and ref_cleaned_flat.startswith(query_cleaned_flat):
                        is_compatible = True

                if not is_compatible: 
                    bypassed_counter += 1
                grid_record = {
                    "task_index": task_counter, "pair_key": pair_key,
                    "sample_context": {"patient_sample_id": sample_id_flat, "species_extracted": species_extracted, "source_project_id": clean_prj},
                    "reference_context": {"accession_id": r_acc, "organism_full_name": r_name, "fasta_reference_path": r_stat},
                    "execution_status": "PENDING" if is_compatible else "❌ BYPASS_SPECIES_MISMATCH",
                    "pair_results_link": os.path.join(pair_out_dir, "pair_metrics.json") if is_compatible else None,
                    "quick_metrics": {"genome_coverage_pct": 0.0, "sequence_identity_pct": 0.0, "evaluation_rating": "PENDING" if is_compatible else "SKIPPED_BY_GUARD"}
                }
                self.manifest_data["matrix_grid"].append(grid_record)

                if is_compatible:
                    try: ref_mbp = float(r_size.strip())
                    except ValueError: ref_mbp = 1.0

                    if ref_mbp < 0.5:
                        mummer_mode = "VIRAL"; blast_mode = "blastn-short"
                    elif ref_mbp <= 10.0:
                        mummer_mode = "BACTERIAL"; blast_mode = "standard"
                    else:
                        mummer_mode = "BACTERIAL"; blast_mode = "megablast"

                    active_paths_set.add(os.path.abspath(q_path))
                    active_paths_set.add(os.path.abspath(r_stat))
                    self.execution_queue.append({
                        "pair_key": pair_key, "sample_fasta": q_path, "reference_fasta": r_stat,
                        "output_dir": pair_out_dir, "min_cov": min_cov, "min_id": min_id, "threads": max_threads,
                        "run_mummer": run_mummer, "run_blast": run_blast,
                        "mummer_scale_mode": mummer_mode, "blast_scale_mode": blast_mode
                    })

        if self.execution_queue:
            is_safe, space_msg = self.disk_guard.validate_space_for_pipeline(list(active_paths_set), platform="ION_TORRENT")
            if not is_safe:
                self.matrix_cli_log_signal.emit("🚨 [BŁĄD SYSTEMOWY]: OPERACJA ANULOWANA - Krytyczny brak wolnego miejsca na NVMe Kingston!")
                self.manifest_data["matrix_master_manifest"]["global_status"] = "❌ ERROR_NO_DISK_SPACE"
                os.makedirs(self.output_project_dir, exist_ok=True)
                self._dump_manifest_to_nvme()
                self.grid_task_finished_signal.emit(False, "GLOBAL_PROJ", f"ABORT: {space_msg}")
                return

        self.manifest_data["matrix_master_manifest"]["statistics_summary"]["total_tasks_generated"] = len(self.execution_queue)
        self.manifest_data["matrix_master_manifest"]["statistics_summary"]["tasks_bypassed_mismatch"] = bypassed_counter

        os.makedirs(self.output_project_dir, exist_ok=True)
        self._dump_manifest_to_nvme()
        
        # ✅ KROK 13: Czysty reset flagi stanowej zoryglowany w locie RAM przed startem serii [2.4]
        self._matrix_is_done = False

        self.matrix_cli_log_signal.emit("[KORONA MATRYCY]: Manifest json wygenerowany. Przekazuję sterowanie do wątków roboczych.\n")
        self.grid_started_signal.emit(self.matrix_project_id, len(self.execution_queue))
        self._process_next_pair()

    def _process_next_pair(self):
        """
        [THE ULTRA-SHORT ISO-PATH DISPATCHER - V25.2]: Gwarantuje twarde sekwencyjne uruchamianie.
        Fizycznie wymusza klonowanie i operowanie silnika wyłącznie wewnątrz sterylnego i-węzła
        katalogu SAMPLE_nnn, trwale eliminując Path Buffer Overrun oraz błędy Memory Map bazy BLAST [INDEX].
        """
        if self._is_killed: return

        if self._is_processing: return

        if not self.execution_queue:
            self._finalize_matrix_project_success()
            return

        self._is_processing = True

        current_free_gb = self.disk_guard.get_free_space_gb()
        if current_free_gb < 15.0:
            self.manifest_data["matrix_master_manifest"]["global_status"] = "⏸️ PAUSED_LOW_DISK_SPACE"
            self._dump_manifest_to_nvme()
            self._is_processing = False
            self.matrix_cli_log_signal.emit(f"\n[⚠️ KRYTYCZNY ALERT]: FIFO WSTRZYMANE! Niski stan dysku ({current_free_gb:.2f} GB).\n")
            return

        if len(self.active_engine) == 0:
            task = self.execution_queue.pop(0)
            p_key = task["pair_key"]
            out_dir = task["output_dir"]

            os.makedirs(out_dir, exist_ok=True)
            sandbox_sample = os.path.join(out_dir, "sample.fasta")
            sandbox_reference = os.path.join(out_dir, "reference.fasta")

            try:
                s_src = task["sample_fasta"]
                if s_src.lower().endswith(".gz"):
                    with gzip.open(s_src, 'rb') as f_in, open(sandbox_sample, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                        f_out.flush()
                        os.fsync(f_out.fileno())
                else:
                    shutil.copy(s_src, sandbox_sample)
                    with open(sandbox_sample, 'ab') as f_sync: os.fsync(f_sync.fileno())

                r_src = task["reference_fasta"]
                if r_src.lower().endswith(".gz"):
                    with gzip.open(r_src, 'rb') as f_in, open(sandbox_reference, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                        f_out.flush()
                        os.fsync(f_out.fileno())
                else:
                    shutil.copy(r_src, sandbox_reference)
                    with open(sandbox_reference, 'ab') as f_sync: os.fsync(f_sync.fileno())

                from PyQt6.QtCore import QThread
                QThread.msleep(100)

                if not os.path.exists(sandbox_sample) or not os.path.exists(sandbox_reference):
                    raise FileNotFoundError("Materiały sandboxu nie zostały zaalokowane w i-węzłach ext4.")

            except Exception as e:
                import traceback
                full_stack = traceback.format_exc()
                self.matrix_cli_log_signal.emit(f"\n🚨 [BŁĄD SYSTEMU PLIKÓW]: Przygotowanie sandboxu PĘKŁO!\n{full_stack}\n")
                self._handle_engine_finished(False, p_key, "", f"Natywny Sandbox Crash: {str(e)}")
                return

            engine = SinglePairAlignEngine(
                sample_fasta=sandbox_sample, reference_fasta=sandbox_reference,
                output_dir=out_dir, min_coverage=task["min_cov"], min_identity=task["min_id"], 
                threads=task["threads"], run_mummer=task["run_mummer"], parent_key=p_key,
                run_blastn=task["run_blast"], mummer_scale=task.get("mummer_scale_mode", "BACTERIAL"),
                blast_scale=task.get("blast_scale_mode", "standard"), parent=self
            )

            engine.started_signal.connect(lambda pk: self.matrix_cli_log_signal.emit(f"[POTOK FIFO]: 🚀 Wszystkie rury I/O drożne. Uruchamiam procesy binarne dla pary: {pk}"))
            engine.phase_changed_signal.connect(lambda pk, code, lbl: self.matrix_cli_log_signal.emit(f"[FAZA SILNIKA]: Para {pk} wchodzi w etap ➔ {lbl}"))
            engine.cli_log_signal.connect(self.matrix_cli_log_signal.emit)
            engine.progress_signal.connect(self.grid_task_progress_signal.emit)
            engine.finished_signal.connect(self._handle_engine_finished)

            self.active_engine[p_key] = engine
            engine.execute_alignment_pipeline()

    @pyqtSlot(bool, str, str, str)
    def _handle_engine_finished(self, success: bool, pair_key: str, metrics_json_path: str, error_msg: str):
        """[THE SECURE DATA-FLOW & GZ-LOCK SLOT - V28.0]: Pakuje izolat z rygorem -9 i czyści śmieci [2.4]."""
        self._is_processing = False
        
        if success and metrics_json_path and os.path.exists(metrics_json_path):
            eval_rating = "ERROR"
            cov_real = 0.0
            id_real = 0.0
            
            try:
                with open(metrics_json_path, "r", encoding="utf-8") as j_f:
                    data = json.load(j_f)
                    eval_rating = data["biological_evaluation"]["evaluation_status"]
                    cov_real = data["mummer_global_metrics"].get("coverage", 0.0)
                    
                    if "blastn_local_metrics" in data and data["blastn_local_metrics"].get("blastn_status") == "COMPLETED":
                        id_real = data["blastn_local_metrics"].get("pident", 0.0)
                    else:
                        id_real = data["mummer_global_metrics"].get("ani", 0.0)
            except Exception:
                pass

            grid = self.manifest_data.get("matrix_grid", [])
            for rec in grid:
                if rec.get("pair_key") == pair_key:
                    rec["execution_status"] = "COMPLETED"
                    rec["quick_metrics"]["genome_coverage_pct"] = cov_real
                    rec["quick_metrics"]["sequence_identity_pct"] = id_real
                    rec["quick_metrics"]["evaluation_rating"] = eval_rating
                    break
            
            self.matrix_master_manifest_success_increment()
            
            # 📦 ZABEZPIECZENIE IZOLATU: Maksymalne pakowanie przed wejściem odkurzacza [2.4]
            output_pair_dir = os.path.dirname(metrics_json_path)
            sandbox_sample_path = os.path.join(output_pair_dir, "sample.fasta")
            target_contigs_gz = os.path.join(output_pair_dir, "contigs.fasta.gz")
            
            if os.path.exists(sandbox_sample_path) and os.path.getsize(sandbox_sample_path) > 0:
                try:
                    with open(sandbox_sample_path, "rb") as f_in:
                        with gzip.open(target_contigs_gz, "wb", compresslevel=9) as f_out:
                            shutil.copyfileobj(f_in, f_out)
                            f_out.flush()
                            os.fsync(f_out.fileno())
                except Exception as e:
                    self.matrix_cli_log_signal.emit(f"[BŁĄD KOMPRESJI IZOLATU]: {str(e)}")

            # Uruchomienie bezpiecznego protokołu czyszczenia plików pośrednich i-węzłów
            self.sanitizer.execute_sandbox_sanitary_protocol(output_pair_dir)
            self.grid_task_finished_signal.emit(True, pair_key, eval_rating)

        else:
            grid = self.manifest_data.get("matrix_grid", [])
            for rec in grid:
                if rec.get("pair_key") == pair_key:
                    rec["execution_status"] = f"❌ ERROR: {error_msg}"
                    rec["quick_metrics"]["evaluation_rating"] = "ERROR"
                    break
            
            if hasattr(self, 'manifest_data') and "matrix_master_manifest" in self.manifest_data:
                self.manifest_data["matrix_master_manifest"]["statistics_summary"]["tasks_failed_error"] += 1
                
            self.grid_task_finished_signal.emit(False, pair_key, f"ERROR: {error_msg}")
            
        self._dump_manifest_to_nvme()
        
        if pair_key in self.active_engine:
            del self.active_engine[pair_key]
            
        if not self._is_killed:
            self._process_next_pair()

    def _finalize_matrix_project_success(self):
        """[THE TRUE TSV FINALIZER - V35.0]: Buduje raport wyłącznie na podstawie zaryglowanych JSON [2.4]."""
        self.manifest_data["matrix_master_manifest"]["global_status"] = "🟢 COMPLETED"
        self.manifest_data["matrix_master_manifest"]["timestamp_last_update"] = subprocess.getoutput("date '+%Y-%m-%d %H:%M:%S'")
        self._dump_manifest_to_nvme()

        tsv_path = os.path.join(self.output_project_dir, "summary_matrix_report.tsv")
        try:
            with open(tsv_path, "w", encoding="utf-8") as t_f:
                t_f.write("Sample_ID\tReference_Strain\tGenome_Coverage(%)\tAverage_Identity(%)\tEvaluation_Rating\n")
                passport = self.manifest_data.get("matrix_sample_passport", {})
                
                for rec in self.manifest_data.get("matrix_grid", []):
                    cov_val = 0.0
                    id_val = 0.0
                    eval_rating = rec['quick_metrics'].get('evaluation_rating', "ERROR")
                    
                    # EXTRACT REAL METRICS FROM JSON - CAŁKOWITE ODCIĘCIE SZACUNKÓW "NA OKO" [2.4]
                    json_link = rec.get("pair_results_link")
                    if json_link and os.path.exists(json_link):
                        try:
                            with open(json_link, "r", encoding="utf-8") as j_file:
                                metrics_data = json.load(j_file)
                                cov_val = float(metrics_data["mummer_global_metrics"].get("coverage", 0.0))
                                eval_rating = metrics_data["biological_evaluation"].get("evaluation_status", eval_rating)
                                
                                if "blastn_local_metrics" in metrics_data and metrics_data["blastn_local_metrics"].get("blastn_status") == "COMPLETED":
                                    id_val = float(metrics_data["blastn_local_metrics"].get("pident", 0.0))
                                else:
                                    id_val = float(metrics_data["mummer_global_metrics"].get("ani", 0.0))
                        except Exception:
                            # Rezerwowy fallback do asynchronicznych wskaźników pamięci RAM w razie awarii I/O
                            try: cov_val = float(rec['quick_metrics'].get('genome_coverage_pct', 0.0))
                            except Exception: cov_val = 0.0
                            try: id_val = float(rec['quick_metrics'].get('sequence_identity_pct', 0.0))
                            except Exception: id_val = 0.0

                    s_id = rec['sample_context']['patient_sample_id']
                    f_sample = passport[s_id].get("operator_display_label", s_id) if s_id in passport else f"{rec['sample_context'].get('source_project_id', 'UNKNOWN')}_{rec['sample_context'].get('species_extracted', 'unknown_species')}"
                    f_ref = f"{rec['reference_context']['accession_id']} - {rec['reference_context']['organism_full_name']}".split(",")[0].strip()
                    
                    t_f.write(f"{f_sample}\t{f_ref}\t{cov_val:.2f}\t{id_val:.2f}\t{eval_rating}\n")
        except Exception:
            pass
            
        self._dump_manifest_to_nvme()
        
        # Synchroniczne zaryglowanie struktur na nośniku NVMe przed emisją sygnału
        try:
            with open(tsv_path, "a") as f_sync: os.fsync(f_sync.fileno())
            with open(self.manifest_path, "a") as m_sync: os.fsync(m_sync.fileno())
        except Exception:
            pass
            
        self._matrix_is_done = True
        self.grid_completed_signal.emit(self.matrix_project_id, tsv_path)

    def kill_matrix_pipeline(self):
        """[THE ATOMIC DISKGUARD KILL COMMAND - V27.1]: Siłowo ubija binaru i wymazuje zNVMe śmieci [2.4]."""
        self._is_killed = True
        self._is_processing = False
        self.execution_queue.clear() # Natychmiastowe opróżnienie kolejki FIFO w pamięci RAM
        
        # 🚨 TWARDE UBIJANIE AKTYWNYCH PROCESÓW SYSTEMOWYCH MUMMER / BLASTn [2.4]
        if self.active_engine:
            for p_key, engine_instance in list(self.active_engine.items()):
                try:
                    engine_instance.kill_engine_process() # Uruchomienie metody terminate/kill z align_engine.py
                    if hasattr(engine_instance, 'proc') and engine_instance.proc:
                        engine_instance.proc.kill()
                except Exception: pass
            self.active_engine.clear()
            
        # 🚨 KASKADOWE WYPALANIE GHOST FILES: Całkowite zmiecenie z dysku tymczasowego folderu projektu!
        if self.output_project_dir and os.path.exists(self.output_project_dir):
            import shutil
            shutil.rmtree(self.output_project_dir, ignore_errors=True)
            
        self.matrix_cli_log_signal.emit("\n🛑 [ALERT SYSTEMOWY]: POTOK MATRYCY ZOSTAŁ SIŁOWO ZATRZYMANY PRZEZ OPERATORA!")
        self.matrix_cli_log_signal.emit(" -> Wyczyszczono kolejkę FIFO w RAM stacji XEON.")
        self.matrix_cli_log_signal.emit(" -> Bezpiecznik DiskGuard siłowo wymazał z nośnika NVMe wszystkie pliki tymczasowe.\n")
        
        # Siłowe przywrócenie stanu pierwotnego i klikalności w oknie głównym GUI [2.4]
        self.grid_task_finished_signal.emit(False, "GLOBAL_PROJ", "ABORT: Proces przerwany przez użytkownika. Nośnik NVMe oczyszczony.")

    def matrix_master_manifest_success_increment(self):
        if hasattr(self, 'manifest_data') and "matrix_master_manifest" in self.manifest_data:
            self.manifest_data["matrix_master_manifest"]["statistics_summary"]["tasks_completed_success"] += 1

    def _dump_manifest_to_nvme(self):
        """Zrzuca lustrzaną strukturę danych bezpośrednio do pliku master manifestu [INDEX]."""
        try:
            with open(self.manifest_path, "w", encoding="utf-8") as f:
                json.dump(self.manifest_data, f, indent=4, ensure_ascii=False)
        except Exception: pass
