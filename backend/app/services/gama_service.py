from gama_client.message_types import MessageTypes
from gama_client.sync_client import GamaSyncClient

from app.core.config import settings


def launch_maelia():
    client = GamaSyncClient(
        settings.GAMA_HOST,
        settings.GAMA_PORT,
        default_timeout=120.0,
    )

    client.connect()

    try:
        response = client.load(
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

        exp_id = response["content"]

        step_response = client.step(exp_id, nb_step=1, timeout=120.0)

        return {
            "status": "success",
            "experiment_id": exp_id,
            "load_response": response,
            "step_response": step_response,
        }

    finally:
        client.close_connection()