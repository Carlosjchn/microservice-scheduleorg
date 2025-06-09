from pydantic_settings import BaseSettings
from functools import lru_cache
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    APP_NAME: str = "Schedule Generator AI Service"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Microservice for generating work schedules using Google's Generative AI"
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    MODEL_NAME: str = "gemini-2.5-pro-preview-06-05"
    DEBUG: bool = False

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings() 