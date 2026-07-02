import threading
import time
from src.core.config_loader import AppConfig
from src.core.storage import Storage
from src.core.logger import setup_logger

logger = setup_logger()


class LoraService(threading.Thread):
    """
    Background Service untuk menangani Outbox Pattern transmisi LoRa.
    Berjalan secara PASIF jika konfigurasi lora.enabled = false.
    """

    def __init__(self, config: AppConfig, storage: Storage):
        super().__init__()
        self.config = config
        self.storage = storage
        self.is_running = True
        logger.info("LoraService (Outbox Poller) berhasil diinisialisasi.")

    def stop(self) -> None:
        """Menghentikan loop background thread LoRa."""
        self.is_running = False

    def run(self) -> None:
        """Loop utama pemeriksaan antrean lora_outbox di SQLite."""
        while self.is_running:
            try:
                # 1. Periksa apakah ada paket dengan status 'PENDING' di database
                pending_packets = self.storage.get_pending_lora_packets(limit=5)
                
                if pending_packets:
                    queue_count = self.storage.get_lora_queue_count()
                    
                    # 2. Cek Sakelar Konfigurasi Utama
                    if not self.config.lora.enabled:
                        # JIKA DISABLED (Sesuai Masukan Final): 
                        # Tetap jalankan roda antrean secara pasif, cetak log, dan update status agar aman
                        for packet in pending_packets:
                            outbox_id = packet["outbox_id"]
                            logger.info(
                                f"[LoRa Pasif] Mendeteksi antrean paket #{outbox_id} ({packet['species']}). "
                                f"Transmisi dilewati (Status LoRa: DISABLED)."
                            )
                            # Tandai sebagai SUCCESS di database agar antrean tidak menumpuk berulang
                            self.storage.update_lora_status(outbox_id, "SUCCESS")
                    else:
                        # JIKA ENABLED (Untuk Fase 9/10 di masa depan jika hardware dipasang):
                        # Jalankan logika pemancaran data lewat modul Serial UART E22
                        logger.info(f"[LoRa Aktif] Memproses {len(pending_packets)} paket dari total {queue_count} antrean...")
                        for packet in pending_packets:
                            outbox_id = packet["outbox_id"]
                            self.storage.update_lora_status(outbox_id, "SUCCESS")
                            
                # Beri jeda waktu polling antrean (misal setiap 5 detik sekali) agar CPU Radxa rileks
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Terjadi galat pada LoraService Loop: {e}")
                time.sleep(10)