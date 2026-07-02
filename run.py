# Ganti isi file run.py menjadi seperti ini agar sinkron:
import uvicorn
from src.controller.app_controller import apem_core
from src.services.lora import LoraService

def main():
    print("=========================================================================")
    print("          APEM (AI-Powered Ecoacoustic Monitor) INITIALIZATION           ")
    print("=========================================================================")

    # Gunakan konfigurasi dan storage dari objek tunggal apem_core
    config = apem_core.config
    storage = apem_core.storage

    # Jalankan LoraService Pasif
    lora_worker = LoraService(config, storage)
    lora_worker.daemon = True
    lora_worker.start()

    # Jalankan Uvicorn
    uvicorn.run(
        "src.api.api_server:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )

if __name__ == "__main__":
    main()