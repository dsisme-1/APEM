import os
from datetime import datetime
import numpy as np
import sounddevice as sd
import soundfile as sf
from src.core.logger import setup_logger

logger = setup_logger()

# Buat folder khusus penyimpanan rekaman di root proyek jika belum ada
RECORDINGS_DIR = "stored_recordings"
if not os.path.exists(RECORDINGS_DIR):
    os.makedirs(RECORDINGS_DIR)


def record_hardware_chunk(duration: int, sample_rate: int) -> np.ndarray:
    """
    Merekam audio langsung dari mikrofon laptop, menyimpannya sebagai file .wav 
    untuk kebutuhan dataset training, dan mengembalikan array untuk AI Engine.
    """
    try:
        # 1. Proses Perekaman Fisik via Hardware Mic
        audio_recorded = sd.rec(
            int(duration * sample_rate), 
            samplerate=sample_rate, 
            channels=1, 
            dtype='float32'
        )
        sd.wait()  # Tunggu perekaman 3 detik selesai
        
        flattened_audio = audio_recorded.flatten()

        # 2. KUNCI DATA COLLECTOR: Simpan hasil rekaman menjadi file .wav nyata
        # Penamaan file otomatis menggunakan timestamp agar unik dan rapi
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"rec_{timestamp_str}.wav"
        file_path = os.path.join(RECORDINGS_DIR, file_name)
        
        # Tulis array ke dalam format file WAV 48kHz Mono
        sf.write(file_path, flattened_audio, sample_rate)
        logger.info(f"💾 [Data Collector] Berhasil menyimpan file training: {file_path}")

        return flattened_audio
        
    except Exception as e:
        logger.error(f"Gagal mengakses hardware mikrofon laptop: {e}.")
        return np.zeros(int(duration * sample_rate), dtype=np.float32)