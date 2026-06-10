from fastapi import FastAPI, HTTPException, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.services.gama_service import (
    upload_includes_zip,
    get_realtime_series,
    get_simulation_state,
    load_maelia,
    pause_maelia,
    play_maelia,
    step_maelia,
    stop_maelia,
    create_outputs_zip,
)

from typing import Any
from pydantic import BaseModel


app = FastAPI(title="MAELIA Headless Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/simulation/state")
async def simulation_state():
    return get_simulation_state()

class LoadPayload(BaseModel):
    parameters: list[dict[str, Any]] | None = None

@app.post("/simulation/includes/upload")
async def upload_includes(
    territory: str = Form(...),
    file: UploadFile = File(...),
):
    try:
        return upload_includes_zip(territory=territory, zip_file=file)
    except RuntimeError as error:
        raise HTTPException(status_code=400, detail=str(error))


@app.post("/simulation/load")
async def simulation_load(payload: LoadPayload | None = None):
    try:
        print("Parameters received:", payload.parameters if payload else None)
        return load_maelia(payload)
    except RuntimeError as error:
        raise HTTPException(status_code=400, detail=str(error))


@app.post("/simulation/play")
async def simulation_play():
    try:
        return play_maelia()
    except RuntimeError as error:
        raise HTTPException(status_code=400, detail=str(error))


@app.post("/simulation/pause")
async def simulation_pause():
    try:
        return pause_maelia()
    except RuntimeError as error:
        raise HTTPException(status_code=400, detail=str(error))


@app.post("/simulation/step")
async def simulation_step(nb_step: int = 1):
    try:
        return step_maelia(nb_step=nb_step)
    except RuntimeError as error:
        raise HTTPException(status_code=400, detail=str(error))


@app.post("/simulation/stop")
async def simulation_stop():
    try:
        return stop_maelia()
    except RuntimeError as error:
        raise HTTPException(status_code=400, detail=str(error))
    
@app.get("/simulation/realtime")
async def simulation_realtime():
    return get_realtime_series()

@app.get("/simulation/outputs/download")
async def download_outputs():
    try:
        zip_path = create_outputs_zip()

        return FileResponse(
            path=zip_path,
            filename="maelia_outputs.zip",
            media_type="application/zip",
        )

    except RuntimeError as error:
        raise HTTPException(status_code=400, detail=str(error))