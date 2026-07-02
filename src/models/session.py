from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class MonitoringSession:
    id: Optional[int]
    started_at: datetime
    ended_at: Optional[datetime]
    mode: str                  # IDLE, CONTINUOUS, DUTY_CYCLE
    record_duration: int       # Durasi aktif merekam per chunk (detik)
    interval: int              # Jeda tidur/sleep dalam mode duty cycle (detik)
    status: str                # ACTIVE, COMPLETED