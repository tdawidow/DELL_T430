# core/session_logger.py
import os
import json
from datetime import datetime

class SessionLogger:
    """Zapisuje dokładny stan i parametry kliknięte w GUI dla danego projektu."""
    
    @staticmethod
    def save_session_manifest(project_path: str, gui_parameters: dict):
        """
        Zapisuje parametry wejściowe wewnątrz kontenera projektu.
        gui_parameters zawiera np. platformę, stan checkboxa pominięcia QC, wybrany RAM.
        """
        manifest_path = os.path.join(project_path, "session_manifest.json")
        
        manifest_data = {
            "execution_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "project_directory": project_path,
            "configured_parameters": gui_parameters,
            "pipeline_status": "INITIALIZED"
        }
        
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest_data, f, indent=4, ensure_ascii=False)
            
    @staticmethod
    def update_project_status(project_path: str, status: str):
        """Aktualizuje status na sam koniec analizy (np. SUCCESS lub FAILED)."""
        manifest_path = os.path.join(project_path, "session_manifest.json")
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            data["pipeline_status"] = status
            data["finished_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
