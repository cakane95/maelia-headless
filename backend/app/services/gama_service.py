import asyncio
from typing import Any
from pathlib import Path
import shutil
import tempfile
import zipfile

from fastapi import UploadFile

from gama_client.message_types import MessageTypes
from gama_client.sync_client import GamaSyncClient

from app.core.config import settings


client: GamaSyncClient | None = None
experiment_id: str | None = None

eau_sol_series: list[dict[str, Any]] = []
azote_perdu_series: list[dict[str, Any]] = []
stress_hydrique_series: list[dict[str, Any]] = []
soc_series: list[dict[str, Any]] = []
qn_demande_series: list[dict[str, Any]] = []
emissions_ges_series: list[dict[str, Any]] = []

sampling_task: asyncio.Task | None = None
sampling_enabled: bool = False

simulation_ended: bool = False
simulation_finishing: bool = False
simulation_status_message: str | None = None
simulation_output_dir: str | None = None

def _resolve_simulation_output_dir(relative_path: str) -> str:
    model_dir = Path(settings.MAELIA_MODEL_PATH).parent

    output_dir = (model_dir / relative_path).resolve()

    return str(output_dir)

def upload_includes_zip(territory: str, zip_file: UploadFile) -> dict[str, Any]:
    territory = territory.strip()

    if not territory:
        raise RuntimeError("Territory name is required.")

    if territory.startswith("includes_"):
        includes_name = territory
    else:
        includes_name = f"includes_{territory}"

    if not zip_file.filename or not zip_file.filename.endswith(".zip"):
        raise RuntimeError("The uploaded file must be a .zip file.")

    includes_root = (
        Path(settings.MAELIA_MODEL_PATH)
        .parents[2]
        / "includes"
    )

    target_dir = includes_root / includes_name

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        zip_path = tmp_dir / zip_file.filename

        with zip_path.open("wb") as buffer:
            shutil.copyfileobj(zip_file.file, buffer)

        if not zipfile.is_zipfile(zip_path):
            raise RuntimeError("The uploaded file is not a valid zip archive.")

        extract_dir = tmp_dir / "extracted"
        extract_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as archive:
            archive.extractall(extract_dir)

        extracted_items = list(extract_dir.iterdir())

        if len(extracted_items) == 1 and extracted_items[0].is_dir():
            source_dir = extracted_items[0]
        else:
            source_dir = extract_dir

        if not source_dir.name.startswith("includes_"):
            # Si le zip contient directement les fichiers sans dossier racine,
            # on accepte quand même et on les place dans includes_<territoire>.
            source_name_is_valid = source_dir == extract_dir
        else:
            source_name_is_valid = True

        if not source_name_is_valid:
            raise RuntimeError("The includes folder name must start with 'includes_'.")

        if target_dir.exists():
            shutil.rmtree(target_dir)

        shutil.copytree(source_dir, target_dir)

    return {
        "status": "success",
        "message": "Includes folder uploaded successfully.",
        "territory": territory,
        "includes_name": includes_name,
        "target_dir": str(target_dir),
    }


async def _gama_message_handler(message: dict) -> None:
    global simulation_finishing, simulation_output_dir

    print("message received from server: ", message)

    content = message.get("content", {})

    if isinstance(content, dict):
        msg = content.get("message", "")

        if "cheminRelatifDuDossierDeSortieDeSimulation:" in msg:
            relative_path = msg.split(
                "cheminRelatifDuDossierDeSortieDeSimulation:",
                1,
            )[1].strip()

            simulation_output_dir = _resolve_simulation_output_dir(relative_path)

            print("Simulation output dir:", simulation_output_dir)

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

    stress_hydrique_response = gama.expression(
        exp_id,
        "mean(list(cultureAqYieldNC) collect each.indiceSatifactionHydrique)",
        timeout=120.0,
    )

    soc_response = gama.expression(
        exp_id,
        "parcelleAqYieldNC(first(listeParcelles)).SOC_perc",
        timeout=120.0,
    )

    qn_demande_response = gama.expression(
        exp_id,
        "first(list(cultureAqYieldNC) collect each.sommeTranspirationR)",
        timeout=120.0,
    )

    emissions_ges_response = gama.expression(
        exp_id,
        "parcelleAqYieldNC(first(listeParcelles)).sorties_bilan_net_GES",
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

    stress_hydrique_series.append(
        {
            "cycle": cycle,
            "stressHydrique": stress_hydrique_response["content"],
        }
    )

    soc_series.append(
        {
            "cycle": cycle,
            "socPerc": soc_response["content"],
        }
    )

    qn_demande_series.append(
        {
            "cycle": cycle,
            "qn": qn_demande_response["content"],
        }
    )

    emissions_ges_series.append(
        {
            "cycle": cycle,
            "bilanGes": emissions_ges_response["content"],
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


def load_maelia(payload: Any | None = None) -> dict[str, Any]:  
    parameters = payload.parameters if payload and payload.parameters else []
    print("GAMA load parameters:", parameters)

    global experiment_id
    global simulation_ended, simulation_finishing, simulation_status_message
    global eau_sol_series, azote_perdu_series
    global stress_hydrique_series, soc_series
    global qn_demande_series, emissions_ges_series
    global sampling_task, sampling_enabled
    global simulation_output_dir

    stop_sampling()

    experiment_id = None
    sampling_task = None
    sampling_enabled = False

    simulation_ended = False
    simulation_finishing = False
    simulation_status_message = None
    simulation_output_dir = None

    eau_sol_series = []
    azote_perdu_series = []
    stress_hydrique_series = []
    soc_series = []
    qn_demande_series = []
    emissions_ges_series = []

    gama = _get_client()

    response = gama.load(
        settings.MAELIA_MODEL_PATH,
        settings.MAELIA_EXPERIMENT_NAME,
        parameters=parameters,
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
    stress_hydrique_data = _deduplicate(stress_hydrique_series)
    soc_data = _deduplicate(soc_series)
    qn_demande_data = _deduplicate(qn_demande_series)
    emissions_ges_data = _deduplicate(emissions_ges_series)

    return {
        "simulation_ended": simulation_ended,
        "simulation_status_message": simulation_status_message,
        "simulation_output_available": simulation_output_dir is not None,
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
        "stressHydrique": {
            "title": "Stress hydrique",
            "description": "Évolution du stress hydrique moyen des cultures.",
            "xKey": "cycle",
            "series": [
                {
                    "key": "stressHydrique",
                    "label": "Stress hydrique",
                    "unit": "déficit de transpi.",
                    "color": "#2563eb",
                }
            ],
            "count": len(stress_hydrique_data),
            "data": stress_hydrique_data,
        },
        "soc": {
            "title": "SOC %",
            "description": "Évolution du carbone organique du sol pour la première parcelle.",
            "xKey": "cycle",
            "series": [
                {
                    "key": "socPerc",
                    "label": "SOC",
                    "unit": "%",
                    "color": "#A52A2A",
                }
            ],
            "count": len(soc_data),
            "data": soc_data,
        },
        "qnDemande": {
            "title": "QNdemande",
            "description": "Évolution de QN pour la première culture.",
            "xKey": "cycle",
            "series": [
                {
                    "key": "qn",
                    "label": "QN",
                    "unit": "",
                    "color": "#2563eb",
                }
            ],
            "count": len(qn_demande_data),
            "data": qn_demande_data,
        },
        "emissionsGes": {
            "title": "Émissions GES",
            "description": "Évolution du bilan net de GES pour la première parcelle.",
            "xKey": "cycle",
            "series": [
                {
                    "key": "bilanGes",
                    "label": "Bilan net de GES",
                    "unit": "kgeqCO2/ha",
                    "color": "#92400e",
                }
            ],
            "count": len(emissions_ges_data),
            "data": emissions_ges_data,
        },
    }

def create_outputs_zip() -> Path:
    if simulation_output_dir is None:
        raise RuntimeError("No simulation output directory is available.")

    output_dir = Path(simulation_output_dir)

    if not output_dir.exists():
        raise RuntimeError(f"Simulation output directory does not exist: {simulation_output_dir}")

    if not output_dir.is_dir():
        raise RuntimeError(f"Simulation output path is not a directory: {simulation_output_dir}")

    tmp_dir = Path(tempfile.gettempdir())
    zip_base = tmp_dir / "maelia_outputs"

    zip_path = shutil.make_archive(
        base_name=str(zip_base),
        format="zip",
        root_dir=str(output_dir),
    )

    return Path(zip_path)