import numpy as np
from datetime import datetime
from src.core.config_loader import AppConfig, load_config
from src.core.storage import Storage
from src.core.logger import setup_logger
from src.core.inference_engine import InferenceEngine  # <-- KUNCI 1: TAMBAHKAN IMPORT INI
from src.models.detection import Detection
from src.services.detector import Detector
from src.services.monitor import MonitorService
from src.services.dashboard import DashboardService

logger = setup_logger()


class AppController:
    """
    Konduktor Utama Sistem APEM.
    Menghubungkan lapisan REST API ke fungsionalitas Monitor, Detector, dan Storage.
    """

    def __init__(self):
        # 1. Muat Konfigurasi global dari model.yaml
        self.config = load_config()
        
        # 2. Inisialisasi Lapangan Data (SQLite)
        self.storage = Storage(self.config)
        
        # 3. KUNCI 2: Inisialisasi Otak Kecerdasan Buatan (Inference Engine) Dulu!
        self.engine = InferenceEngine(self.config)
        
        # 4. KUNCI 3: Masukkan self.config DAN self.engine ke dalam Detector
        self.detector = Detector(self.config, self.engine)
        
        # 5. Inisialisasi Layanan Agregator Dashboard
        self.dashboard_service = DashboardService(self.storage, self.config)
        
        # 6. Inisialisasi Background State Machine Monitoring
        self.monitor_service = MonitorService(self.config, self.storage, self.detector)
        
        logger.info("⚡ APEM Core AppController resmi mengudara dan mengambil kendali sistem.")

    def handle_manual_upload(self, audio_data: np.ndarray, filename: str) -> list[dict]:
        """
        Menangani alur unggah berkas audio WAV manual dari web.
        Mengirim ke Stateless Detector -> Simpan ke Database secara Atomik -> Kembalikan JSON.
        """
        logger.info(f"Memproses analisis audio unggahan manual: {filename}")
        
        results = self.detector.detect_chunk(audio_data)
        
        saved_results = []
        for res in results:
            detection_obj = Detection(
                id=None,
                session_id=None,
                timestamp=datetime.now(),
                offset_second=0.0,
                species=res["label"],
                confidence=res["confidence"],
                latency_ms=res["latency_ms"],
                audio_source="UPLOAD"
            )
            db_id = self.storage.save_detection_with_outbox(detection_obj)
            
            res_dict = dict(res)
            res_dict["id"] = db_id
            saved_results.append(res_dict)
            
        return saved_results

    def toggle_monitoring(self, enable: bool) -> dict:
        """Mengontrol sakelar on/off thread MonitorService dari REST API."""
        if enable:
            success = self.monitor_service.start_monitoring()
            status_msg = "Sistem pemantauan mikrofon berhasil diaktifkan." if success else "Sistem sudah aktif."
        else:
            success = self.monitor_service.stop_monitoring()
            status_msg = "Sistem pemantauan mikrofon berhasil dimatikan." if success else "Sistem sudah dalam kondisi mati."

        return {
            "success": success,
            "message": status_msg,
            "current_state": self.monitor_service.current_state
        }

    def get_system_status(self) -> dict:
        """Mengambil status kesehatan dan kondisi terkini perangkat untuk Dashboard."""
        return {
            "monitor_active": self.monitor_service.is_running,
            "monitor_state": self.monitor_service.current_state,
            "lora_enabled": self.config.lora.enabled,
            "lora_queue_count": self.storage.get_lora_queue_count()
        }

# Instansiasi AppController sebagai konduktor tunggal sistem
apem_core = AppController()