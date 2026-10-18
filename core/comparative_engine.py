# core/comparative_engine.py
import os
import json
from datetime import datetime

class ComparativeEngine:
    """[ANALYTICAL BACKEND ENGINE V46.7]: Sterylny procesor danych matrycy."""
    def __init__(self, project_dir: str):
        self.project_dir = os.path.abspath(project_dir)
        self.manifest_path = os.path.join(self.project_dir, ".matrix_master_manifest.json")
        self.manifest_data = {}
        self._load_manifest()

    def _load_manifest(self):
        """Siłowo wczytuje centralny paszport super-projektu z dysku."""
        if os.path.exists(self.manifest_path):
            try:
                with open(self.manifest_path, 'r', encoding='utf-8') as f:
                    self.manifest_data = json.load(f)
            except Exception:
                self.manifest_data = {}

    def get_samples_axis_n(self) -> list:
        """Wyciąga sterylną listę realnie przebadanych próbek (Oś N) [2.4]."""
        samples = []
        passports = self.manifest_data.get("matrix_sample_passport", {})
        for s_id, context in passports.items():
            samples.append({
                "sample_id": s_id,
                "display_label": context.get("operator_display_label", s_id),
                "species": context.get("extracted_species", "Nieznany")
            })
        return sorted(samples, key=lambda x: x["sample_id"])

    def get_reference_axis_m_for_sample(self, sample_id: str) -> list:
        """Filtruje macierz krzyżową i przypisuje kody kolorów z jądra [2.4]."""
        results = []
        grid = self.manifest_data.get("matrix_grid", [])
        
        for task in grid:
            s_ctx = task.get("sample_context", {})
            if s_ctx.get("patient_sample_id") != sample_id:
                continue
                
            ref_ctx = task.get("reference_context", {})
            metrics = task.get("quick_metrics", {})
            rating = metrics.get("evaluation_rating", "🔴 BŁĄD PROCESU")
            
            # [THE GRADIENT MATRIX FILTER]: Mapowanie tożsamości barwnej jądra [2.4]
            if "HIGH_HOMOLOGY" in rating:
                bg_color, fg_color = "#003311", "#00FF66"  # Czysta zieleń sukcesu [2.4]
            elif "LOW_IDENTITY" in rating or "SHORT_COVERAGE" in rating:
                bg_color, fg_color = "#332200", "#ECC94B"  # Laboratoryjne złoto ostrzegawcze [2.4]
            else:
                bg_color, fg_color = "#4d0000", "#FF3333"  # Krwista czerwień awarii [2.4]
                
            results.append({
                "accession_id": ref_ctx.get("accession_id", "N/A"),
                "organism_name": ref_ctx.get("organism_full_name", "Unknown"),
                "coverage": f"{metrics.get('genome_coverage_pct', 0.0):.2f}",
                "identity": f"{metrics.get('sequence_identity_pct', 0.0):.2f}",
                "rating": rating,
                "bg_color": bg_color,
                "fg_color": fg_color,
                "results_link": task.get("pair_results_link", "")
            })
        return results
