from pathlib import Path
from pydantic_settings import BaseSettings

_ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    slack_webhook_url: str = ""
    slack_signing_secret: str = ""
    db_path: str = str(Path(__file__).parent.parent / "fossick.db")
    case_data_path: str = str(Path(__file__).parent.parent / "case_data")
    docker_image: str = "fossick-mcp"
    mcp_timeout: int = 300

    model_config = {"env_file": str(_ENV_FILE)}

settings = Settings()
