from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    WHAPI_BASE_URL: str
    WHAPI_TOKEN: str
    WHAPI_CHANNEL: str = "CATWMN-PVGDR"  # Default channel
    WHAPI_PHONE: str = "+6287731624016"  # Default phone (without spaces)

    model_config = ConfigDict(
        env_file=".env",
        extra="ignore"
    )

settings = Settings()
