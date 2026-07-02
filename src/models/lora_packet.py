from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class LoRaPacket:
    id: Optional[int]
    detection_id: int
    status: str                # PENDING, SENDING, SUCCESS, FAILED
    retry_count: int           # Jumlah percobaan pengiriman yang sudah dilakukan
    last_retry: Optional[datetime]
    created_at: datetime
    sent_at: Optional[datetime]