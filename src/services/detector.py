import numpy as np
from src.core.config_loader import AppConfig
from src.core.inference_engine import InferenceEngine
from src.core.logger import setup_logger

logger = setup_logger()

# ==============================================================================
# DAFTAR SPESIES TARGET (WHITE-LIST FILTERS)
# ==============================================================================
SPESIES_TARGET = [
    
]


class Detector:
    """
    Modul Stateless Detector yang menjembatani antara data audio mentah 
    dengan Inference Engine AI TFLite, otomatis membaca konfigurasi dari YAML.
    """

    def __init__(self, config: AppConfig, engine: InferenceEngine):
        self.config = config
        self.engine = engine
        
        # KUNCI PERBAIKAN: Langsung ambil nilai threshold dari model.yaml secara otomatis!
        # Mengasumsikan di dalam objek config Anda strukturnya adalah config.model.confidence_threshold
        try:
            self.threshold = float(self.config.model.confidence_threshold)
        except AttributeError:
            # Fallback aman jika struktur objek config di sistem Anda sedikit berbeda
            self.threshold = 0.30
        
        logger.info(f"🔍 Detector diinisialisasi dengan Confidence Threshold (dari YAML): {int(self.threshold * 100)}%")
        if SPESIES_TARGET:
            logger.info(f"🎯 Mode Penyaringan Aktif: Memantau {len(SPESIES_TARGET)} spesies target.")
        else:
            logger.info("🌍 Mode Global Aktif: Meloloskan seluruh daftar spesies tanpa filter taksonomi.")

    def detect_chunk(self, audio_chunk: np.ndarray) -> list:
        """
        Menerima array audio 3 detik, mengeksekusi prediksi AI, 
        dan menyaring hasil berdasarkan threshold serta spesies target.
        """
        expected_samples = self.config.monitor.record_duration * self.config.audio.sample_rate
        if len(audio_chunk) != expected_samples:
            logger.warning(f"Dimensi audio tidak standar! Got {len(audio_chunk)} but expected {expected_samples}. Proses dilewati.")
            return []

        try:
            raw_logits, latency_ms = self.engine.predict_raw(audio_chunk)
            top_indices = np.argsort(raw_logits)[::-1][:5]
            
            filtered_results = []
            for idx in top_indices:
                # Mengambil nilai logits mentah
                logits_val = float(raw_logits[idx])
                
                # Solusi: Batasi nilai maksimal di 1.0 (100%) agar tidak over-scale di dashboard
                confidence = min(logits_val, 1.0) if logits_val > 0 else 0.0
                
                # Gunakan self.threshold dinamis yang dibaca dari YAML
                if confidence >= self.threshold:
                    species_label = self.engine.labels[idx] if idx < len(self.engine.labels) else f"Unknown_Index_{idx}"
                    
                    if SPESIES_TARGET and (species_label not in SPESIES_TARGET):
                        continue
                        
                    filtered_results.append({
                        "label": species_label,
                        "confidence": confidence,
                        "latency_ms": round(latency_ms, 2)
                    })
            
            return filtered_results

        except Exception as e:
            logger.error(f"Gagal mengeksekusi kalkulasi inferensi pada Detector: {e}")
            return []