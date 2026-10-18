# core/thread_manager.py
import os
import subprocess
from PyQt6.QtCore import QThread, pyqtSignal, QProcess

class PipelineExecutionThread(QThread):
    """[EVENT-DRIVEN MULTIPLEXING ENGINE V52.2]: Asynchroniczny potok bezdyskowy w RAM [2.4]."""
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, str)
    finished_signal = pyqtSignal(str)

    def __init__(self, command_list: list, env_vars: dict = None):
        super().__init__()
        self.command_list = command_list
        self.env_vars = env_vars if env_vars is not None else os.environ.copy()
        self.is_killed = False
        
        # 🚨 ASYNCHRONICZNE REJESTRY STANU I LICZNIKI ZDARZEŃ JĄDRA POSIX [2.4]
        self._active_qprocesses = []
        self._workers_counter = 0
        self._multiplex_success = True
        self._current_shm_sandbox = ""

    def execute_bam_to_fastq_conversion(self, s_in: str, s_out: str, max_t: int) -> bool:
        """[THE ADAPTIVE STREAM PIPE ROUTER - V52.5]: Bezdyskowa kaskada dekompresji BAM.GZ [2.4]."""
        self.log_signal.emit(f"[🧬] Inicjalizacja asynchronicznej konwersji formatu binarnego: {os.path.basename(s_in)}")
        t_safe = str(min(max_t, 16))
        samtools_bin = "/home/ionadmin/miniforge3/envs/ion_analysis/bin/samtools"
        
        # 🧭 SCENARIUSZ A: PLIK TO GZIPPOWANY .BAM.GZ (KASKADA RUR SYSTEMOWYCH W RAM)
        if s_in.lower().endswith(".bam.gz"):
            self.log_signal.emit("[🔗] Wykryto podwójną kompresję .bam.gz. Uruchamiam rurę POSIX Stream Pipe...")
            p1 = subprocess.Popen(["gzip", "-dc", s_in], stdout=subprocess.PIPE, env=self.env_vars)
            p2 = subprocess.Popen([samtools_bin, "fastq", "-@", t_safe, "-0", s_out, "-"], stdin=p1.stdout, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=self.env_vars)
            p1.stdout.close()
            stdout_data, _ = p2.communicate()
            if stdout_data: self.log_signal.emit(stdout_data.strip())
            return p2.returncode == 0
            
        # 🧭 SCENARIUSZ B: PLIK TO SUROWY NOMINALNY ALIGNMENT .BAM
        p_args = [samtools_bin, "fastq", "-@", t_safe, "-0", s_out, s_in]
        res = subprocess.run(p_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=self.env_vars)
        if res.stdout: self.log_signal.emit(res.stdout.strip())
        return res.returncode == 0

    def _handle_async_stdout(self):
        """[EVENT CALLBACK]: Przechwytuje linie tekstu z RAM bez blokowania GUI [2.4]."""
        process = self.sender()
        if isinstance(process, QProcess):
            data = process.readAllStandardOutput().data().decode("utf-8", errors="ignore")
            for line in data.splitlines():
                if line.strip():
                    self.log_signal.emit(line.strip())

    def _handle_single_worker_finished(self, exit_code, exit_status):
        """[EVENT CALLBACK]: Atomowy licznik jądra sterowany przerwaniami POSIX [2.4]."""
        if exit_code != 0 or exit_status != QProcess.ExitStatus.NormalExit:
            self._multiplex_success = False
            
        self._workers_counter -= 1
        if self._workers_counter <= 0:
            # Wyzwalacz zdarzeniowy (Trigger): koniec podprocesów wybudza pętlę główną
            self._multiplex_loop_active = False

    def execute_fast_analysis_stream(self, cmd_data: dict) -> bool:
        """[THE HYBRID STORAGE INTERLOCK - V52.11]: Bezpieczna chronologia alokacji i sprzątania RAM [2.4]."""
        import config
        import shutil
        args = cmd_data.get("args", [])
        try:
            active_input = args[args.index("-i") + 1]
            cleaned_fastq = args[args.index("-o") + 1]
        except (ValueError, IndexError): return False

        threads_limit = getattr(config, 'CURRENT_THREADS_LIMIT', 16)
        if active_input.lower().endswith((".bam", ".bam.gz")):
            bam_out = os.path.join(os.path.dirname(cleaned_fastq), "bam_extracted_reads.fastq.gz")
            if not self.execute_bam_to_fastq_conversion(active_input, bam_out, threads_limit):
                return False
            active_input = bam_out

        try:
            shm_stats = os.statvfs("/dev/shm")
            real_shm_gb = (shm_stats.f_bavail * shm_stats.f_frsize) / (1024 ** 3)
            sample_size_gb = os.path.getsize(active_input) / (1024 ** 3)
        except Exception: real_shm_gb, sample_size_gb = 0.0, 2.0

        is_compressed = active_input.lower().endswith((".gz", ".bam.gz"))
        ram_multiplier = 5.5 if is_compressed else 1.2
        ram_per_process = (6.0 if "--nano" in args else 2.0) + (sample_size_gb * ram_multiplier)

        x_cpu = max(int(threads_limit // 16), 1)
        x_ram = max(int(real_shm_gb // ram_per_process), 1)
        x_final = max(min(x_cpu, x_ram), 1)
        t_proc = min(max(int(threads_limit // x_final), 1), 16)

        if real_shm_gb < (x_final * sample_size_gb * 1.5) or x_ram < 1:
            self.log_signal.emit("[⚠️ ALERT ZASOBÓW]: Brak przestrzeni w /dev/shm. Fallback na NVMe...")
            return self._execute_fallback_nvme(active_input, cleaned_fastq, threads_limit, args)

        # 🎯 CHIRURGICZNE USYTUOWANIE ODKURZACZA: Sprzątamy shm TYLKO jeśli zapada decyzja o pracy w RAM
        self._current_shm_sandbox = os.path.join("/dev/shm", f"kombajn_sandbox_{os.getpid()}")
        
        # Sterylizujemy wyłącznie osierocone pozostałości o tym PID, wykluczając kolizje Batch
        if os.path.exists(self._current_shm_sandbox):
            try: shutil.rmtree(self._current_shm_sandbox)
            except Exception: pass
            
        os.makedirs(self._current_shm_sandbox, exist_ok=True)
        return self._execute_multiplex_shm(active_input, cleaned_fastq, x_final, t_proc, args)

    def _execute_multiplex_shm(self, s_in: str, s_out: str, x: int, t: int, orig_args: list) -> bool:
        """[SHM MULTIPLEX PROTOCOL V52.8]: Wdrożenie aktywnej telemetrii wizualnej w RAM [2.4]."""
        from PyQt6.QtCore import QEventLoop, QProcessEnvironment
        self._active_qprocesses.clear(); self._workers_counter = x; self._multiplex_success = True
        
        # 🛰️ TELEMETRIA T1: Natychmiastowe uderzenie informacyjne o podziale strumienia
        self.log_signal.emit(f"[🧱 SHM ENGINE]: Inicjalizacja bezdyskowego podziału strumienia próbki do pamięci RAM /dev/shm (Mnożnik: {x} części)...")
        
        mamba_bin = "/home/ionadmin/miniforge3/envs/ion_analysis/bin"
        split_cmd = [os.path.join(mamba_bin, "seqkit"), "split2", "-p", str(x), "-O", self._current_shm_sandbox, s_in]
        res_split = subprocess.run(split_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=self.env_vars)
        if res_split.returncode != 0:
            self.log_signal.emit("🚨 [BŁĄD SYSTEMOWY]: Splitter seqkit nie zdołał podzielić pliku w RAM!")
            return False

        preserved_flags = []
        try:
            for flag in ["-h", "-j"]:
                if flag in orig_args: preserved_flags.extend([flag, orig_args[orig_args.index(flag) + 1]])
        except (ValueError, IndexError): pass
        if "--nano" in orig_args: preserved_flags.append("--nano")

        fastp_bin = orig_args; base_raw = os.path.basename(s_in)
        for ext in [".fastq.gz", ".fastq", ".bam.gz", ".bam", ".BAM"]:
            if base_raw.endswith(ext):
                base_raw = base_raw[:-len(ext)]
                break
                
        q_env = QProcessEnvironment()
        for k, v in self.env_vars.items(): q_env.insert(k, v)

        # 🛰️ TELEMETRIA T2: Informacja o mapowaniu rdzeni i uruchomieniu sztafety
        self.log_signal.emit(f"[🚀 SHM ENGINE]: Rozruch sztafety równoległej. Uruchamiam {x} workerów fastp (Alokacja: {t} wątków per-proces) bezpośrednio w RAM tmpfs. Oczekiwanie na zdarzenia POSIX...")

        # 🚀 KROK 3: ASYNCHRONICZNY ROZRUCH WORKERÓW FASTP NA PŁASKICH ARGS
        fastp_bin = orig_args[0]
        part_suffix = ".fastq.gz" if s_in.lower().endswith(".gz") else ".fastq"
        
        for i in range(x):
            if self.is_killed: return False
            p_in = os.path.join(self._current_shm_sandbox, f"{base_raw}.part_{i+1:03d}{part_suffix}")
            p_out = os.path.join(self._current_shm_sandbox, f"chunk_{i}.fastq.gz")
            flat_args = ["-i", p_in, "-o", p_out, "-w", str(t)] + preserved_flags
            
            proc = QProcess(); proc.setProcessEnvironment(q_env)
            proc.readyReadStandardOutput.connect(self._handle_async_stdout)
            proc.finished.connect(self._handle_single_worker_finished)
            self._active_qprocesses.append(proc)
            proc.start(fastp_bin, flat_args)
            
        # 🚀 KROK 4: BEZKOLIZYJNA PĘTLA ZDARZEŃ QT WYCZEKUJĄCA NA PRZERWANIA JĄDRA
        self._multiplex_loop_active = True; loop = QEventLoop()
        while self._multiplex_loop_active and self._workers_counter > 0:
            if self.is_killed:
                for p in self._active_qprocesses: p.kill()
                return False
            loop.processEvents(QEventLoop.ProcessEventsFlag.AllEvents)
            
        if not self._multiplex_success: return False
        return self._consolidate_and_clean_shm(s_out)

    def _consolidate_and_clean_shm(self, final_out: str) -> bool:
        """[CONSOLIDATION & CLEAN-UP V52.6]: Atomowe scalenie i usuwanie plików-widm z ext4 [2.4]."""
        self.log_signal.emit("[🚀] Konsolidacja strumieni RAM na nośnik ext4...")
        cat_cmd = f"cat {self._current_shm_sandbox}/chunk_*.fastq.gz > {final_out}"
        res = subprocess.run(["sh", "-c", cat_cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=self.env_vars)
        subprocess.run(["rm", "-rf", self._current_shm_sandbox], env=self.env_vars)
        
        # 🔗 WSTRZYKNIĘCIE ANOMALII A: Czyszczenie tymczasowego wypakowanego pliku BAM z dysku Kingston
        bam_temp = os.path.join(os.path.dirname(final_out), "bam_extracted_reads.fastq.gz")
        if os.path.exists(bam_temp):
            try: os.remove(bam_temp)
            except Exception: pass
        return res.returncode == 0

    def _execute_fallback_nvme(self, s_in: str, s_out: str, max_t: int, orig_args: list) -> bool:
        """[DISK FALLBACK]: Tradycyjna praca jednowątkowa bezpośrednio na nośniku ext4 [2.4]."""
        self.log_signal.emit("[⚙️] Uruchamianie awaryjnego, liniowego potoku dyskowego NVMe...")
        t_safe = min(max_t, 4)  # Dynamiczne obniżenie wątkowości dla ochrony przed I/O Thrashing
        
        p_args = [orig_args[0], "-i", s_in, "-o", s_out, "-w", str(t_safe)]
        try:
            for flag in ["-h", "-j"]:
                if flag in orig_args:
                    p_args.extend([flag, orig_args[orig_args.index(flag) + 1]])
        except (ValueError, IndexError): pass
        if "--nano" in orig_args: p_args.append("--nano")
        
        res = subprocess.run(p_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=self.env_vars)
        if res.stdout: self.log_signal.emit(res.stdout.strip())
        return res.returncode == 0

    def run(self):
        try:
            for cmd_idx, cmd in enumerate(self.command_list):
                if self.is_killed:
                    self.log_signal.emit("[X] POTOK ZATRZYMANY PRZEZ UŻYTKOWNIKA.")
                    self.finished_signal.emit("KILLED")
                    return

                step_name = cmd.get("name", f"Krok {cmd_idx + 1}")

                if "fastp" in str(step_name).lower():
                    if not self.execute_fast_analysis_stream(cmd):
                        self.log_signal.emit("🚨 [BŁĄD]: Bezdyskowy potok fastp pękł w locie RAM!")
                        self.finished_signal.emit("FAILED")
                        return
                    self.log_signal.emit(f"[OK] ZAKOŃCZONO: {step_name}")
                    continue

                self.log_signal.emit(f"\n[>>>] URUCHAMIANIE: {step_name}")
                self.log_signal.emit(f"Command: {' '.join(cmd['args'])}\n")
                self.progress_signal.emit(int((cmd_idx / len(self.command_list)) * 100), step_name)

                # POPRAWKA: Przekazujemy tablicę env_vars (zapewnia widoczność fastp w Miniforge3)
                process = subprocess.Popen(
                    cmd["args"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    env=self.env_vars
                )

                while True:
                    if self.is_killed:
                        process.terminate()
                        self.finished_signal.emit("KILLED")
                        return
                        
                    line = process.stdout.readline()
                    if not line:
                        break
                    self.log_signal.emit(line.strip())

                process.wait()
                
                if process.returncode != 0:
                    self.log_signal.emit(f"\n[X] BŁĄD! Krok '{step_name}' zakończył się niepowodzeniem (Kod: {process.returncode}).")
                    self.finished_signal.emit("FAILED")
                    return
                
                self.log_signal.emit(f"[OK] ZAKOŃCZONO: {step_name}")

            self.progress_signal.emit(100, "Zakończono potok")
            self.finished_signal.emit("SUCCESS")

        except Exception as e:
            self.log_signal.emit(f"\n[Krytyczny Wyjątek Systemu]: {str(e)}")
            self.finished_signal.emit("FAILED")

    def kill_process(self):
        self.is_killed = True
