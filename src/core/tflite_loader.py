"""
TensorFlow Lite interpreter loader untuk APEM.
Otomatis mendeteksi lingkungan runtime untuk efisiensi eksekusi tensor.
"""

try:
    # Prioritas utama: Menggunakan tflite-runtime yang super ringan di Radxa/Raspberry Pi
    from tflite_runtime.interpreter import Interpreter
except ImportError:
    # Fallback: Menggunakan TensorFlow utuh saat fase development di Laptop/PC
    from tensorflow.lite.python.interpreter import Interpreter


def create_interpreter(model_path: str) -> Interpreter:
    """Membuat dan mengembalikan objek interpreter TFLite sesuai runtime yang tersedia."""
    return Interpreter(model_path=model_path)