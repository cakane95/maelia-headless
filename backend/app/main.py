from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.services.gama_service import (
    get_realtime_series,
    get_simulation_state,
    load_maelia,
    pause_maelia,
    play_maelia,
    step_maelia,
    stop_maelia,
)


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


@app.post("/simulation/load")
async def simulation_load():
    try:
        return load_maelia()
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