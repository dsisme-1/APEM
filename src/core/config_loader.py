from dataclasses import dataclass
from pathlib import Path
import yaml

CONFIG_PATH = Path("config/model.yaml")

@dataclass
class ModelConfig:
    path: str
    labels: str

@dataclass
class AudioConfig:
    sample_rate: int
    chunk_duration: int
    mono: bool

@dataclass
class InferenceConfig:
    threshold: float
    top_k: int

@dataclass
class SchedulerConfig:
    enabled: bool
    start: str
    stop: str

@dataclass
class MonitorConfig:
    enabled: bool
    mode: str
    record_duration: int
    interval: int
    scheduler: SchedulerConfig

@dataclass
class LoRaConfig:
    enabled: bool
    port: str
    baudrate: int
    frequency: int
    tx_mode: str
    buffer_size: int
    flush_interval: int
    retry: int
    timeout: int

@dataclass
class DatabaseConfig:
    path: str

@dataclass
class LoggingConfig:
    level: str

@dataclass
class AppConfig:
    model: ModelConfig
    audio: AudioConfig
    inference: InferenceConfig
    monitor: MonitorConfig
    lora: LoRaConfig
    database: DatabaseConfig
    logging: LoggingConfig


def load_config() -> AppConfig:
    """Membaca konfigurasi dari model.yaml ke dalam format AppConfig dataclass."""
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        cfg = yaml.safe_load(file)

    return AppConfig(
        model=ModelConfig(**cfg["model"]),
        audio=AudioConfig(**cfg["audio"]),
        inference=InferenceConfig(**cfg["inference"]),
        monitor=MonitorConfig(
            enabled=cfg["monitor"]["enabled"],
            mode=cfg["monitor"]["mode"],
            record_duration=cfg["monitor"]["record_duration"],
            interval=cfg["monitor"]["interval"],
            scheduler=SchedulerConfig(**cfg["monitor"]["scheduler"])
        ),
        lora=LoRaConfig(**cfg["lora"]),
        database=DatabaseConfig(**cfg["database"]),
        logging=LoggingConfig(**cfg["logging"]),
    )