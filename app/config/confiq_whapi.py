from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    # WHAPI config (legacy, bisa dihapus nanti)
    WHAPI_BASE_URL: str = ""
    WHAPI_TOKEN: str = ""
    WHAPI_CHANNEL: str = "CATWMN-PVGDR"
    WHAPI_PHONE: str = "+6287731624016"

    # Baileys service config
    BAILEYS_SERVICE_URL: str = "http://localhost:3000"
    BAILEYS_API_KEY: str = "baileys-internal-2026"

    # Which provider to use: "baileys" or "whapi"
    WA_PROVIDER: str = "baileys"

    model_config = ConfigDict(
        env_file=".env",
        extra="ignore"
    )

settings = Settings()
