from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Detection:
    id: Optional[int]
    session_id: Optional[int]  # Bernilai None jika diunggah manual via Web/API di luar sesi aktif
    timestamp: datetime
    offset_second: float       # Detik keberapa burung bersuara di dalam rekaman audio
    species: str               # Nama spesies yang sudah terstandardisasi secara biologi
    confidence: float          # Skor probabilitas model AI (0.0 - 1.0)
    latency_ms: float          # Kecepatan inferensi perangkat keras (milidetik)
    audio_source: str          # Label sumber: UPLOAD, MICROPHONE, atau API