import shutil
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.controller.app_controller import AppController
from src.audio.loader import load_wav
from src.core.logger import setup_logger
from src.controller.app_controller import apem_core as controller
logger = setup_logger()

# Inisialisasi FastAPI
app = FastAPI(
    title="APEM - AI-Powered Ecoacoustic Monitor",
    description="REST API murni untuk sistem monitoring bioakustik edge",
    version="1.0.0"
)

# Konfigurasi Direktori Statis dan Templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")



# Buat folder uploads jika belum ada
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


# =========================================================================
# ROUTE 1: HALAMAN UTAMA (ENTRY POINT UI)
# =========================================================================


@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    """Melayani halaman dashboard statis utama."""
    return templates.TemplateResponse(request=request, name="index.html")

# =========================================================================
# ROUTE 2: ENDPOINT API DATA DASHBOARD (GET JSON)
# =========================================================================

@app.get("/api/dashboard", response_class=JSONResponse)
def get_dashboard_data():
    """
    Endpoint utama yang di-fetch secara berkala oleh dashboard.js.
    Mengembalikan data statistik ringkas harian dan riwayat deteksi terbaru.
    """
    try:
        summary = controller.dashboard_service.generate_summary()
        system_status = controller.get_system_status()
        
        # Gabungkan data ringkasan dengan status perangkat terkini
        return JSONResponse(content={**summary, **system_status})
    except Exception as e:
        logger.error(f"Gagal mengambil data dashboard: {e}")
        raise HTTPException(status_code=500, detail="Gagal memproses data internal server.")


# =========================================================================
# ROUTE 3: ENDPOINT API UNGGAN AUDIO MANUAL (POST JSON)
# =========================================================================
# PERBAIKAN PADA SRC/API/API_SERVER.PY
@app.post("/api/upload", response_class=JSONResponse)
async def upload_audio_manual(file: UploadFile = File(...)):
    """
    Menerima file WAV dari form upload, memotongnya menjadi fragmen 3 detik,
    mengeksekusi deteksi via stateless engine, dan mengembalikan JSON terintegrasi.
    """
    if not file.filename.lower().endswith(".wav"):
        raise HTTPException(status_code=400, detail="Format file tidak didukung. Harus .wav")

    temp_file_path = UPLOAD_DIR / file.filename
    try:
        # 1. Simpan file sementara ke disk
        with temp_file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 2. Muat audio utuh (Mono & 48kHz)
        audio_data = load_wav(str(temp_file_path), controller.config)

        # 3. KUNCI PERBAIKAN: Potong audio panjang menjadi deretan frame 3 detik!
        from src.audio.chunker import slice_into_chunks
        audio_frames = slice_into_chunks(audio_data, controller.config)

        all_detections = []
        logger.info(f"Memproses analisis audio {file.filename} (Terbagi menjadi {len(audio_frames)} frame 3-detik).")

        # 4. Iterasi setiap frame dan kirim ke controller secara bertahap
        for frame_data, offset_sec in audio_frames:
            # handle_manual_upload dimodifikasi sedikit atau panggil langsung stateless detector-nya:
            results = controller.detector.detect_chunk(frame_data)
            
            for res in results:
                # Simpan ke SQLite secara atomik per kicauan yang lolos threshold
                from src.models.detection import Detection
                from datetime import datetime
                
                detection_obj = Detection(
                    id=None,
                    session_id=None,
                    timestamp=datetime.now(),
                    offset_second=offset_sec, # Catat detik keberapa burung bersuara!
                    species=res["label"],
                    confidence=res["confidence"],
                    latency_ms=res["latency_ms"],
                    audio_source="UPLOAD"
                )
                db_id = controller.storage.save_detection_with_outbox(detection_obj)
                
                all_detections.append({
                    "id": db_id,
                    "label": res["label"],
                    "confidence": res["confidence"],
                    "latency_ms": res["latency_ms"],
                    "offset_second": offset_sec
                })

        return JSONResponse(content={
            "status": "success",
            "filename": file.filename,
            "detections_count": len(all_detections),
            "detections": all_detections
        })

    except Exception as e:
        logger.error(f"Gagal memproses file unggahan {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Gagal menganalisis file audio: {str(e)}")
        
    finally:
        if temp_file_path.exists():
            temp_file_path.unlink()


# =========================================================================
# ROUTE 4: ENDPOINT API SAKELAR KENDALI MONITORING (POST JSON)
# =========================================================================

@app.post("/api/control", response_class=JSONResponse)
async def control_monitoring_system(request: Request):
    """
    Menerima instruksi JSON untuk menyalakan atau mematikan background thread
    perekaman mikrofon real-time lapangan (State Machine).
    """
    try:
        body = await request.json()
        enable = body.get("enable", False)
        
        # Eksekusi toggle via controller
        result = controller.toggle_monitoring(enable)
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.error(f"Gagal mengeksekusi instruksi kontrol: {e}")
        raise HTTPException(status_code=500, detail="Gagal memproses perintah kendali.")