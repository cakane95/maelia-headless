from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    GAMA_HOST: str = "gama-headless"
    GAMA_PORT: int = 6868
    MAELIA_MODEL_PATH: str
    MAELIA_EXPERIMENT_NAME: str = "simulationBase"


settings = Settings()