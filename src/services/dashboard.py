from src.core.storage import Storage
from src.core.config_loader import AppConfig


class DashboardService:
    """Mengagregasikan data mentah dari SQLite menjadi struktur JSON siap saji."""

    def __init__(self, storage: Storage, config: AppConfig):
        self.storage = storage
        self.config = config

    def generate_summary(self) -> dict:
        """Menyusun statistik ringkas untuk konsumsi UI SPA."""
        return {
            "total_detections_today": self.storage.get_total_today(),
            "unique_species_count": self.storage.get_unique_species_count(),
            "average_latency_ms": self.storage.get_average_latency(),
            "lora_queue_count": self.storage.get_lora_queue_count(),
            "latest_detections": self.storage.get_latest_detections(limit=15),
            "chart_data": self.storage.get_daily_stats()
        }