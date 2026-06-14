import anthropic
from backend.config import settings


class AgentBase:
    """Base class that creates Anthropic client lazily so API key is read at call time."""

    def _get_client(self) -> anthropic.AsyncAnthropic:
        key = getattr(self, "_anthropic_key", None) or settings.anthropic_api_key
        if not key:
            # Last resort: read directly from .env
            from pathlib import Path
            env_file = Path(__file__).parent.parent.parent / ".env"
            if env_file.exists():
                for line in env_file.read_text().splitlines():
                    if line.startswith("ANTHROPIC_API_KEY="):
                        key = line.split("=", 1)[1].strip()
                        break
        return anthropic.AsyncAnthropic(api_key=key)
