from datetime import datetime
from src.core.config_loader import AppConfig
from src.core.logger import setup_logger

logger = setup_logger()


def is_within_schedule(config: AppConfig) -> bool:
    """
    Memeriksa apakah waktu sistem saat ini berada di dalam batas jam
    operasional yang dikonfigurasi pada model.yaml.
    """
    if not config.monitor.scheduler.enabled:
        return True  # Jika scheduler di-disable, anggap selalu masuk jadwal (24 jam)

    try:
        now = datetime.now().time()
        start_time = datetime.strptime(config.monitor.scheduler.start, "%H:%M").time()
        stop_time = datetime.strptime(config.monitor.scheduler.stop, "%H:%M").time()

        if start_time <= stop_time:
            return start_time <= now <= stop_time
        else:
            # Mengakomodasi jika jadwal melewati tengah malam (cross-midnight)
            return now >= start_time or now <= stop_time
    except ValueError as e:
        logger.error(f"Format jam scheduler di model.yaml salah: {e}. Mengabaikan batasan jadwal.")
        return True