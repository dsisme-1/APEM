import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from src.core.config_loader import AppConfig
from src.core.logger import setup_logger

logger = setup_logger()


def load_wav(file_path: str, config: AppConfig) -> np.ndarray:
    """
    Memuat berkas audio WAV, melakukan konversi ke mono jika diperlukan,
    dan melakukan resampling ke target sample rate standar model AI.
    """
    data, samplerate = sf.read(file_path)
    target_sr = config.audio.sample_rate

    # Konversi ke Mono jika audio bertipe Stereo (multi-channel)
    if len(data.shape) > 1:
        data = np.mean(data, axis=1)

    # Lakukan Resampling jika sample rate file asli tidak sesuai target (misal 44.1kHz ke 48kHz)
    if samplerate != target_sr:
        logger.info(f"Resampling audio dari {samplerate}Hz ke {target_sr}Hz.")
        # Menggunakan resample_poly untuk efisiensi komputasi di perangkat edge
        gcd = np.gcd(samplerate, target_sr)
        data = resample_poly(data, target_sr // gcd, samplerate // gcd)

    return data.astype(np.float32)