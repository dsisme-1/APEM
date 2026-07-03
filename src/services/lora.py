import threading
import time
import json
import serial
from datetime import datetime
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
        
        # Ambil parameter serial dinamis dari file konfigurasi AppConfig Mas
        self.port = getattr(config.lora, 'port', '/dev/ttyUSB0')
        self.baudrate = getattr(config.lora, 'baudrate', 9600)
        
        # Sesuai request Mas: Langsung set identitas statis "APEM_1" tanpa nyari blok node/interval lagi
        self.node_id = "APEM_1"
        
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
                        # JIKA DISABLED:
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
                        # JIKA ENABLED: Kirim data fisik beneran lewat modul Serial UART E22 ke udara!
                        logger.info(f"[LoRa Aktif] Memproses {len(pending_packets)} paket dari total {queue_count} antrean...")
                        
                        # Buka koneksi serial port hardware
                        try:
                            with serial.Serial(self.port, self.baudrate, timeout=1.0) as ser:
                                for packet in pending_packets:
                                    # Pastikan thread bisa interupsi stop di tengah perulangan paket
                                    if not self.is_running:
                                        break
                                        
                                    outbox_id = packet["outbox_id"]
                                    
                                    # Ubah status antrean sementara menjadi 'SENDING'
                                    self.storage.update_lora_status(outbox_id, "SENDING")
                                    
                                    # Konversi ISO string timestamp bawaan database Mas ke bentuk angka float epoch
                                    try:
                                        dt = datetime.fromisoformat(packet['timestamp'])
                                        epoch_timestamp = dt.timestamp()
                                    except Exception:
                                        epoch_timestamp = time.time()
                                        
                                    # Bungkus data ke format JSON ringkas yang sinkron dengan APEM-Basecamp
                                    payload = {
                                        "node": self.node_id,
                                        "timestamp": epoch_timestamp,
                                        "species": packet['species'],
                                        "conf": round(packet['confidence'], 3)
                                    }
                                    
                                    # Berikan token baris baru (\n) sebagai pembatas paket di basecamp nanti
                                    json_str = json.dumps(payload) + "\n"
                                    
                                    # Tembakkan ke antena!
                                    ser.write(json_str.encode('utf-8'))
                                    logger.info(f"[LoRa Transmit Success] Antena berhasil memancarkan data paket #{outbox_id}: {packet['species']}")
                                    
                                    # Perbarui status di database jika sukses total
                                    self.storage.update_lora_status(outbox_id, "SUCCESS")
                                    
                                    # Jeda sangat singkat (0.2 detik) antar paket dalam satu batch agar hardware serial stabil
                                    time.sleep(0.2)
                                    
                        except serial.SerialException as se:
                            logger.error(f"[LoRa Hardware Error] Gagal mengakses port {self.port}: {se}")
                            # Jika hardware bermasalah (tercabut), kembalikan ke status FAILED dan naikkan retry
                            for packet in pending_packets:
                                self.storage.update_lora_status(packet["outbox_id"], "FAILED", retry_increment=1)
                            time.sleep(5)  # Jeda untuk proteksi hardware sebelum mencoba loop berikutnya
                            
                # Beri jeda waktu polling antrean database agar CPU Radxa rileks (Setiap 5 detik)
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Terjadi galat pada LoraService Loop: {e}")
                time.sleep(10)