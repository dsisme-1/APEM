import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from src.core.config_loader import AppConfig
from src.core.logger import setup_logger
from src.models.session import MonitoringSession
from src.models.detection import Detection
from src.models.lora_packet import LoRaPacket

logger = setup_logger()


class Storage:
    """
    Atomic Data Access Layer untuk basis data SQLite APEM.
    Menangani penyimpanan terelasi antara Sesi, Deteksi, dan Antrean LoRa Outbox.
    """

    def __init__(self, config: AppConfig):
        self.db_path = Path(config.database.path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_tables()

    def _connect(self) -> sqlite3.Connection:
        """Membuka koneksi ke SQLite."""
        return sqlite3.connect(self.db_path)

    def _create_tables(self) -> None:
        """Membuat skema 3 tabel utama jika belum eksis di database."""
        with self._connect() as conn:
            cursor = conn.cursor()
            
            # 1. Tabel Sesi Monitoring
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS monitoring_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    mode TEXT NOT NULL,
                    record_duration INTEGER NOT NULL,
                    interval INTEGER NOT NULL,
                    status TEXT NOT NULL
                )
            """)

            # 2. Tabel Hasil Deteksi Burung
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS detections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    timestamp TEXT NOT NULL,
                    offset_second REAL NOT NULL,
                    species TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    latency_ms REAL NOT NULL,
                    audio_source TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES monitoring_sessions(id) ON DELETE SET NULL
                )
            """)

            # 3. Tabel Antrean Outbox LoRa
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS lora_outbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    detection_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    last_retry TEXT,
                    created_at TEXT NOT NULL,
                    sent_at TEXT,
                    FOREIGN KEY (detection_id) REFERENCES detections(id) ON DELETE CASCADE
                )
            """)
            
            conn.commit()
        logger.info("SQLite database initialized dengan skema 3 tabel (Sesi, Deteksi, Outbox).")

    # =========================================================================
    # OPERASI SAKELAR & TRANSAKSI ATOMIK (DETECTION + OUTBOX QUEUE)
    # =========================================================================

    def save_detection_with_outbox(self, detection: Detection) -> int:
        """
        Menyimpan data Deteksi sekalian memasukkannya ke antrean LoRa Outbox.
        Menggunakan SATU transaksi atomik penuh (jika satu gagal, semua rollback).
        """
        timestamp_str = detection.timestamp.isoformat()
        now_str = datetime.now().isoformat()

        with self._connect() as conn:
            cursor = conn.cursor()
            
            # Step A: Masukkan data ke tabel detections
            cursor.execute("""
                INSERT INTO detections 
                (session_id, timestamp, offset_second, species, confidence, latency_ms, audio_source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                detection.session_id,
                timestamp_str,
                detection.offset_second,
                detection.species,
                detection.confidence,
                detection.latency_ms,
                detection.audio_source
            ))
            
            # Ambil ID terakhir dari deteksi yang baru saja dimasukkan
            detection_id = cursor.lastrowid
            
            # Step B: Masukkan referensi ID ke tabel lora_outbox (Status default: PENDING)
            cursor.execute("""
                INSERT INTO lora_outbox
                (detection_id, status, retry_count, last_retry, created_at, sent_at)
                VALUES (?, 'PENDING', 0, NULL, ?, NULL)
            """, (detection_id, now_str))
            
            # Transaksi otomatis di-commit oleh context manager 'with' jika sukses tanpa error
            return detection_id

    # =========================================================================
    # OPERASI CRUD MONITORING SESSIONS
    # =========================================================================

    def start_session(self, session: MonitoringSession) -> int:
        """Membuat sesi monitoring baru di database."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO monitoring_sessions (started_at, ended_at, mode, record_duration, interval, status)
                VALUES (?, NULL, ?, ?, ?, 'ACTIVE')
            """, (session.started_at.isoformat(), session.mode, session.record_duration, session.interval))
            return cursor.lastrowid

    def end_session(self, session_id: int) -> None:
        """Menutup sesi monitoring aktif dan memperbarui timestamp selesainya."""
        now_str = datetime.now().isoformat()
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE monitoring_sessions 
                SET ended_at = ?, status = 'COMPLETED'
                WHERE id = ?
            """, (now_str, session_id))

    def get_active_session(self) -> Optional[dict]:
        """Mendapatkan detail sesi yang saat ini sedang aktif (jika ada)."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM monitoring_sessions WHERE status = 'ACTIVE' ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            return dict(row) if row else None

    # =========================================================================
    # OPERASI QUERY UNTUK DASHBOARD SERVICE & API
    # =========================================================================

    def get_latest_detections(self, limit: int = 20) -> List[dict]:
        """Mengambil data riwayat deteksi terbaru beserta data ID sesinya."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM detections ORDER BY id DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_total_today(self) -> int:
        """Menghitung total kicauan burung yang berhasil dideteksi hari ini."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM detections WHERE DATE(timestamp) = DATE('now')")
            return cursor.fetchone()[0]

    def get_unique_species_count(self) -> int:
        """Menghitung variasi jumlah spesies unik yang pernah terdeteksi."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(DISTINCT species) FROM detections")
            return cursor.fetchone()[0]

    def get_average_latency(self) -> float:
        """Menghitung rata-rata kecepatan inferensi perangkat keras AI (ms)."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT AVG(latency_ms) FROM detections")
            val = cursor.fetchone()[0]
            return round(val or 0.0, 2)

    def get_daily_stats(self) -> List[dict]:
        """Mengambil ringkasan jumlah deteksi per hari untuk kebutuhan grafik Chart.js."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DATE(timestamp) as date, COUNT(*) as total 
                FROM detections 
                GROUP BY DATE(timestamp) 
                ORDER BY date ASC
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    # =========================================================================
    # OPERASI KENDALI ANTREAN LORA OUTBOX
    # =========================================================================

    def get_pending_lora_packets(self, limit: int = 5) -> List[dict]:
        """Mengambil antrean paket data LoRa yang berstatus PENDING."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT lo.id as outbox_id, lo.detection_id, d.timestamp, d.species, d.confidence 
                FROM lora_outbox lo
                JOIN detections d ON lo.detection_id = d.id
                WHERE lo.status = 'PENDING'
                ORDER BY lo.id ASC LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def update_lora_status(self, outbox_id: int, status: str, retry_increment: int = 0) -> None:
        """Memperbarui status pengiriman paket LoRa (SUCCESS, FAILED, SENDING)."""
        now_str = datetime.now().isoformat()
        with self._connect() as conn:
            cursor = conn.cursor()
            if status == 'SUCCESS':
                cursor.execute("""
                    UPDATE lora_outbox 
                    SET status = 'SUCCESS', sent_at = ? 
                    WHERE id = ?
                """, (now_str, outbox_id))
            else:
                cursor.execute("""
                    UPDATE lora_outbox 
                    SET status = ?, retry_count = retry_count + ?, last_retry = ? 
                    WHERE id = ?
                """, (status, retry_increment, now_str, outbox_id))

    def get_lora_queue_count(self) -> int:
        """Mendapatkan jumlah antrean paket LoRa yang belum sukses terkirim."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM lora_outbox WHERE status = 'PENDING' or status = 'FAILED'")
            return cursor.fetchone()[0]