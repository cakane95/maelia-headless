from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.services.gama_service import launch_maelia


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
def health():
    return {"status": "ok"}


@app.post("/launch")
async def launch():
    return launch_maelia()