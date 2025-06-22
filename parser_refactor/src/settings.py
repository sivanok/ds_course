from pydantic.v1 import BaseSettings
from dotenv import load_dotenv


class Settings(BaseSettings):
    GOOGLE_APPLICATION_CREDENTIALS: str
    GCP_PROJECT_ID: str
    GCP_LOCATION: str
    INPUT_BUCKET_NAME: str
    IMAGES_BUCKET_NAME: str
    GOOGLE_CLOUD_LOCATION: str

    class Config:
        env_file = ".env"
        case_sensitive = True


def load_settings(env_dev: bool = False) -> Settings:
    load_dotenv(".env")
    if env_dev:
        load_dotenv(".env_dev", override=True)
    return Settings()
