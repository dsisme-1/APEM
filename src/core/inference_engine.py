from pathlib import Path
from time import perf_counter
import numpy as np

from src.core.tflite_loader import create_interpreter
from src.core.config_loader import AppConfig
from src.core.logger import setup_logger
logger = setup_logger()


class InferenceEngine:
    """
    TensorFlow Lite Engine yang murni stateless untuk APEM.
    Hanya bertanggung jawab memuat model dan mengeksekusi invoke tensor matematika.
    """

    def __init__(self, config: AppConfig):
        self.config = config
        self.model_path = Path(config.model.path)
        self.label_path = Path(config.model.labels)

        if not self.model_path.exists():
            raise FileNotFoundError(f"Berkas model tidak ditemukan di: {self.model_path}")
        if not self.label_path.exists():
            raise FileNotFoundError(f"Berkas label tidak ditemukan di: {self.label_path}")

        # Membuat interpreter berbasis tflite_runtime atau tensorflow biasa
        self.interpreter = create_interpreter(str(self.model_path))
        self.interpreter.allocate_tensors()

        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        
        self.labels = self._load_labels()
        logger.info("Mesin inferensi TFLite berhasil dimuat ke dalam memori.")

    def _load_labels(self) -> list[str]:
        """Membaca daftar nama kelas burung ke dalam memori."""
        with open(self.label_path, "r", encoding="utf-8") as f:
            labels = [line.strip() for line in f if line.strip()]
        logger.info(f"Berhasil memuat {len(labels)} daftar spesies global.")
        return labels

    def predict_raw(self, audio_chunk: np.ndarray) -> tuple[np.ndarray, float]:
        """
        Mengeksekusi prediksi tensor matematika murni.
        Menerima array numpy audio 3 detik, mengembalikan nilai logit mentah dan latensi (ms).
        """
        # Sesuaikan dimensi data (tambahkan dimensi batch size = 1)
        input_data = np.expand_dims(audio_chunk, axis=0).astype(np.float32)
        self.interpreter.set_tensor(self.input_details[0]["index"], input_data)

        start_time = perf_counter()
        self.interpreter.invoke()
        latency_ms = (perf_counter() - start_time) * 1000

        # Ambil output logit mentah sebelum dilewatkan ke fungsi aktivasi
        raw_logits = self.interpreter.get_tensor(self.output_details[0]["index"])[0]
        return raw_logits, latency_ms