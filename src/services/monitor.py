import threading
from datetime import datetime
from time import perf_counter

from src.core.config_loader import AppConfig
from src.core.storage import Storage
from src.core.logger import setup_logger
from src.models.session import MonitoringSession
from src.models.detection import Detection
from src.audio.microphone import record_hardware_chunk
from src.services.detector import Detector
from src.scheduler.daily_scheduler import is_within_schedule
from src.scheduler.duty_cycle import calculate_next_cycle, execution_sleep

logger = setup_logger()


class MonitorService(threading.Thread):
    """
    Background Service berbasis STATE MACHINE untuk mengatur siklus pemantauan real-time.
    State: IDLE -> RECORDING -> INFERENCE -> SLEEPING
    """

    def __init__(self, config: AppConfig, storage: Storage, detector: Detector):
        super().__init__()
        self.config = config
        self.storage = storage
        self.detector = detector
        
        # Kendali State Berbasis Bendera (Flags)
        self.current_state = "IDLE"
        self.is_monitoring = False  # Mengontrol apakah siklus rekam aktif atau standby
        self.active_session_id = None
        self._running = True        # Mengontrol siklus hidup thread utama
        
        # Otomatis nyalakan thread pembantu sejak awal aplikasi mengudara
        self.daemon = True
        self.start()
        logger.info("MonitorService Background Thread berhasil dinyalakan secara permanen.")

    def start_monitoring(self) -> bool:
        """Mengaktifkan bendera pemantauan dan membuka sesi baru."""
        if self.is_monitoring:
            logger.warning("Sistem pemantauan sudah berjalan aktif.")
            return False

        # Buat sesi baru di SQLite
        new_session = MonitoringSession(
            id=None,
            started_at=datetime.now(),
            ended_at=None,
            mode=self.config.monitor.mode,
            record_duration=self.config.monitor.record_duration,
            interval=self.config.monitor.interval,
            status="ACTIVE"
        )
        self.active_session_id = self.storage.start_session(new_session)
        
        # Naikkan bendera sakelar ke TRUE
        self.is_monitoring = True
        logger.info(f"Sistem Pemantauan DIMULAI. Sesi Aktif ID: #{self.active_session_id}")
        return True

    def stop_monitoring(self) -> bool:
        """Menurunkan bendera pemantauan ke kondisi standby tanpa membunuh thread."""
        if not self.is_monitoring:
            return False

        logger.info("Menerima permintaan penghentian pemantauan...")
        self.is_monitoring = False
        self.current_state = "IDLE"

        if self.active_session_id:
            self.storage.end_session(self.active_session_id)
            logger.info(f"Sesi ID: #{self.active_session_id} resmi ditutup.")
            self.active_session_id = None

        return True

    @property
    def is_running(self):
        """Properti pembantu agar kompatibel dengan AppController lama."""
        return self.is_monitoring

    def run(self) -> None:
        """Loop abadi pembantu yang bertugas mengawasi bendera is_monitoring."""
        while self._running:
            # JIKA STANDBY (Tombol belum diklik atau sudah di-stop)
            if not self.is_monitoring:
                self.current_state = "IDLE"
                execution_sleep(1)
                continue

            # CHECK SCHEDULER: Jika di luar jam operasional, paksa tidur
            if not is_within_schedule(self.config):
                if self.current_state != "SLEEPING":
                    logger.info("Di luar jendela jam operasional. Sistem memasuki state SLEEPING (Standby)...")
                    self.current_state = "SLEEPING"
                execution_sleep(10)
                continue

            # =================================================================
            # STATE 1: RECORDING
            # =================================================================
            self.current_state = "RECORDING"
            duration = self.config.monitor.record_duration
            sr = self.config.audio.sample_rate
            
            logger.info(f"[{self.current_state}] Merekam suara alam via mikrofon ({duration} detik)...")
            start_time = perf_counter()
            
            # Panggil fungsi rekam hardware
            audio_data = record_hardware_chunk(duration, sr)
            
            # Cek kembali bendera, siapa tahu tombol stop diklik saat proses rekam berlangsung
            if not self.is_monitoring:
                continue

            # =================================================================
            # STATE 2: INFERENCE
            # =================================================================
            self.current_state = "INFERENCE"
            logger.info(f"[{self.current_state}] Menganalisis gelombang audio...")
            
            results = self.detector.detect_chunk(audio_data)
            
            for res in results:
                detection_obj = Detection(
                    id=None,
                    session_id=self.active_session_id,
                    timestamp=datetime.now(),
                    offset_second=0.0,
                    species=res["label"],
                    confidence=res["confidence"],
                    latency_ms=res["latency_ms"],
                    audio_source="MICROPHONE"
                )
                self.storage.save_detection_with_outbox(detection_obj)
                logger.info(f"🔥 TERDETEKSI VIA MIC: {res['label']} ({round(res['confidence']*100, 2)}%)")

            elapsed_time = perf_counter() - start_time

            # =================================================================
            # STATE 3: SLEEPING
            # =================================================================
            if self.config.monitor.mode == "duty_cycle" and self.is_monitoring:
                self.current_state = "SLEEPING"
                sleep_duration = calculate_next_cycle(elapsed_time, self.config)
                logger.info(f"[{self.current_state}] Menghemat daya. CPU tidur selama {sleep_duration} detik...")
                
                for _ in range(sleep_duration):
                    if not self.is_monitoring:
                        break
                    execution_sleep(1)
            else:
                execution_sleep(0.1)