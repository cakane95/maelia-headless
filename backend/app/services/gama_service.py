import asyncio
from typing import Any

from gama_client.message_types import MessageTypes
from gama_client.sync_client import GamaSyncClient

from app.core.config import settings


client: GamaSyncClient | None = None
experiment_id: str | None = None

eau_sol_series: list[dict[str, Any]] = []
azote_perdu_series: list[dict[str, Any]] = []

sampling_task: asyncio.Task | None = None
sampling_enabled: bool = False

simulation_ended: bool = False
simulation_finishing: bool = False
simulation_status_message: str | None = None


async def _gama_message_handler(message: dict) -> None:
    global simulation_finishing

    content = message.get("content", {})

    if isinstance(content, dict):
        msg = content.get("message", "")

        if "FIN DE SIMULATION" in msg and not simulation_finishing:
            simulation_finishing = True
            asyncio.create_task(_finalize_simulation())


async def _finalize_simulation() -> None:
    global simulation_ended, simulation_status_message

    await asyncio.sleep(0.5)

    try:
        sample_realtime_metrics()
    except Exception as error:
        print(f"Final sampling error: {error}")

    stop_sampling()

    simulation_ended = True
    simulation_status_message = "Simulation terminée"


def _get_client() -> GamaSyncClient:
    global client

    if client is None:
        client = GamaSyncClient(
            settings.GAMA_HOST,
            settings.GAMA_PORT,
            other_message_handler=_gama_message_handler,
            default_timeout=120.0,
        )
        client.connect()

    return client


def _ensure_experiment_loaded() -> str:
    if experiment_id is None:
        raise RuntimeError("No MAELIA experiment is currently loaded.")

    return experiment_id


def _deduplicate(series: list[dict[str, Any]]) -> list[dict[str, Any]]:
    points_by_cycle: dict[Any, dict[str, Any]] = {}

    for point in series:
        points_by_cycle[point["cycle"]] = point

    return list(points_by_cycle.values())


def sample_realtime_metrics() -> dict[str, Any]:
    exp_id = _ensure_experiment_loaded()
    gama = _get_client()

    cycle_response = gama.expression(
        exp_id,
        "cycle",
        timeout=120.0,
    )

    hm_response = gama.expression(
        exp_id,
        "parcelleAqYieldNC(first(listeParcelles)).Hm",
        timeout=120.0,
    )

    nlosses_response = gama.expression(
        exp_id,
        "parcelleAqYieldNC(first(listeParcelles)).Nlosses",
        timeout=120.0,
    )

    cycle = cycle_response["content"]

    eau_sol_series.append(
        {
            "cycle": cycle,
            "hm": hm_response["content"],
        }
    )

    azote_perdu_series.append(
        {
            "cycle": cycle,
            "nlosses": nlosses_response["content"],
        }
    )

    return {"cycle": cycle}


async def _controlled_play_loop() -> None:
    global sampling_enabled

    while sampling_enabled:
        try:
            exp_id = _ensure_experiment_loaded()
            gama = _get_client()

            gama.step(
                exp_id,
                nb_step=1,
                sync=True,
                timeout=120.0,
            )

            sample_realtime_metrics()

        except Exception as error:
            print(f"Controlled play error: {error}")
            sampling_enabled = False

        await asyncio.sleep(0.05)


def start_controlled_play() -> None:
    global sampling_task, sampling_enabled

    if sampling_task is not None and not sampling_task.done():
        return

    sampling_enabled = True
    sampling_task = asyncio.create_task(_controlled_play_loop())


def stop_sampling() -> None:
    global sampling_enabled

    sampling_enabled = False


def load_maelia() -> dict[str, Any]:
    global experiment_id
    global simulation_ended, simulation_finishing, simulation_status_message
    global eau_sol_series, azote_perdu_series
    global sampling_task, sampling_enabled

    stop_sampling()

    experiment_id = None
    sampling_task = None
    sampling_enabled = False

    simulation_ended = False
    simulation_finishing = False
    simulation_status_message = None

    eau_sol_series = []
    azote_perdu_series = []

    gama = _get_client()

    response = gama.load(
        settings.MAELIA_MODEL_PATH,
        settings.MAELIA_EXPERIMENT_NAME,
        timeout=120.0,
    )

    if response["type"] != MessageTypes.CommandExecutedSuccessfully.value:
        return {
            "status": "error",
            "step": "load",
            "response": response,
        }

    experiment_id = response["content"]

    sample_realtime_metrics()

    return {
        "status": "success",
        "message": "MAELIA experiment loaded",
        "experiment_id": experiment_id,
        "response": response,
    }


def play_maelia() -> dict[str, Any]:
    exp_id = _ensure_experiment_loaded()

    if simulation_ended:
        return {
            "status": "error",
            "message": "Simulation already ended",
            "experiment_id": exp_id,
        }

    start_controlled_play()

    return {
        "status": "success",
        "message": "MAELIA controlled play started",
        "experiment_id": exp_id,
    }


def pause_maelia() -> dict[str, Any]:
    stop_sampling()

    return {
        "status": "success",
        "message": "MAELIA controlled play paused",
        "experiment_id": experiment_id,
    }


def step_maelia(nb_step: int = 1) -> dict[str, Any]:
    exp_id = _ensure_experiment_loaded()
    gama = _get_client()

    response = gama.step(
        exp_id,
        nb_step=nb_step,
        sync=True,
        timeout=120.0,
    )

    sample_realtime_metrics()

    return {
        "status": "success",
        "message": f"MAELIA simulation advanced by {nb_step} step(s)",
        "experiment_id": exp_id,
        "response": response,
    }


def stop_maelia() -> dict[str, Any]:
    global client, experiment_id, sampling_task

    stop_sampling()

    exp_id = _ensure_experiment_loaded()
    gama = _get_client()

    response = gama.stop(
        exp_id,
        timeout=120.0,
    )

    gama.close_connection()

    client = None
    experiment_id = None
    sampling_task = None

    return {
        "status": "success",
        "message": "MAELIA simulation stopped and connection closed",
        "experiment_id": exp_id,
        "response": response,
    }


def get_simulation_state() -> dict[str, Any]:
    return {
        "client_connected": client is not None,
        "experiment_loaded": experiment_id is not None,
        "experiment_id": experiment_id,
        "simulation_ended": simulation_ended,
        "simulation_status_message": simulation_status_message,
    }


def get_realtime_series() -> dict[str, Any]:
    eau_sol_data = _deduplicate(eau_sol_series)
    azote_perdu_data = _deduplicate(azote_perdu_series)

    return {
        "simulation_ended": simulation_ended,
        "simulation_status_message": simulation_status_message,
        "eauSol": {
            "title": "Eau dans le sol",
            "description": "Évolution de Hm pour la première parcelle.",
            "xKey": "cycle",
            "series": [
                {
                    "key": "hm",
                    "label": "Hm",
                    "unit": "mm",
                    "color": "#2563eb",
                }
            ],
            "count": len(eau_sol_data),
            "data": eau_sol_data,
        },
        "azotePerdu": {
            "title": "Azote perdu",
            "description": "Évolution des pertes en azote pour la première parcelle.",
            "xKey": "cycle",
            "series": [
                {
                    "key": "nlosses",
                    "label": "Nlosses",
                    "unit": "kg N/ha",
                    "color": "#ef4444",
                }
            ],
            "count": len(azote_perdu_data),
            "data": azote_perdu_data,
        },
    }