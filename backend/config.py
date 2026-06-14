from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str = ""
    slack_webhook_url: str = ""
    slack_signing_secret: str = ""
    db_path: str = "fossick.db"
    case_data_path: str = "./case_data"
    docker_image: str = "fossick-mcp"
    mcp_timeout: int = 300

    model_config = {"env_file": ".env"}

settings = Settings()
