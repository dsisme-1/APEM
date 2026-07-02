import numpy as np
from src.core.config_loader import AppConfig


def slice_into_chunks(audio_data: np.ndarray, config: AppConfig) -> list[tuple[np.ndarray, float]]:
    """
    Memotong array data audio panjang menjadi potongan bingkai berdurasi tetap (3 detik).
    Mengembalikan daftar tuple berisi [array_chunk, offset_detik_kemunculan].
    """
    sr = config.audio.sample_rate
    chunk_len = config.audio.chunk_duration * sr  # Total sampel per 3 detik
    
    total_samples = len(audio_data)
    chunks = []
    
    # Geser pointer per 3 detik tanpa overlap untuk efisiensi monitoring standar
    for start_idx in range(0, total_samples, chunk_len):
        end_idx = start_idx + chunk_len
        
        # Jika potongan terakhir kurang dari 3 detik, beri padding senyap (zero-padding)
        if end_idx > total_samples:
            chunk = audio_data[start_idx:]
            padded_chunk = np.zeros(chunk_len, dtype=np.float32)
            padded_chunk[:len(chunk)] = chunk
            chunk = padded_chunk
        else:
            chunk = audio_data[start_idx:end_idx]
            
        # Hitung detik keberapa potongan ini dimulai dalam rekaman asli
        offset_second = float(start_idx / sr)
        chunks.append((chunk, offset_second))
        
    return chunks