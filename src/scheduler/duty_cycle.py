import time
from src.core.config_loader import AppConfig


def execution_sleep(seconds: int) -> None:
    """Melakukan jeda suspensi CPU yang aman."""
    if seconds > 0:
        time.sleep(seconds)


def calculate_next_cycle(elapsed_record_time: float, config: AppConfig) -> int:
    """
    Menghitung sisa waktu tidur yang harus dilakukan sistem agar siklus 
    Interval Duty Cycle tetap presisi dan konsisten di lapangan.
    """
    target_interval = config.monitor.interval
    # Kurangi target waktu jeda dengan durasi riil yang habis saat proses inferensi/rekam
    remaining_sleep = target_interval - int(elapsed_record_time)
    
    return max(0, remaining_sleep)