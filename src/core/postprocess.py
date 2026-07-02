import numpy as np
from src.core.config_loader import AppConfig


def sigmoid(x: np.ndarray) -> np.ndarray:
    """Mengubah skor logit mentah model menjadi skala probabilitas nilai 0 hingga 1."""
    return 1.0 / (1.0 + np.exp(-x))


def process_and_filter(
    raw_logits: np.ndarray, 
    labels: list[str], 
    config: AppConfig
) -> list[dict]:
    """
    Mengubah logit mentah menjadi probabilitas, mengurutkan skor tertinggi,
    dan menyaring hasil berdasarkan kriteria batas minimum (threshold) dan jumlah maksimal (top_k).
    """
    probabilities = sigmoid(raw_logits)
    threshold = config.inference.threshold
    top_k = config.inference.top_k

    # Urutkan index dari probabilitas terbesar ke terkecil
    sorted_indices = np.argsort(probabilities)[::-1]
    filtered_results = []

    for idx in sorted_indices:
        confidence = float(probabilities[idx])

        # Lewati jika skor berada di bawah ambang batas deteksi minimum
        if confidence < threshold:
            continue

        raw_label = labels[idx].strip()
        parts = raw_label.split()

        # Terapkan perbaikan format standar penamaan spesies biologi (Masukan PDD)
        # Sesuai konvensi: Kata pertama Kapital (Genus), kata kedua lowercase (Spesies)
        if len(parts) >= 2:
            standardized_label = f"{parts[0].capitalize()} {parts[1].lower()}"
            if len(parts) > 2:
                standardized_label += " " + " ".join(parts[2:])
        else:
            standardized_label = raw_label.capitalize()

        filtered_results.append({
            "label": standardized_label,
            "confidence": confidence
        })

        # Batasi jumlah output sesuai dengan batas konfigurasi top_k
        if len(filtered_results) >= top_k:
            break

    return filtered_results