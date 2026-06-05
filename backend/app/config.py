import json
import os
from pathlib import Path
from pydantic_settings import BaseSettings


# Manually load .env and set in os.environ to override any shell environment variables
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    with open(_env_path) as _f:
        for line in _f:
            if line.strip() and not line.strip().startswith("#"):
                try:
                    key, val = line.strip().split("=", 1)
                    val = val.strip("'\" ")
                    os.environ[key] = val
                except Exception:
                    pass

class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:password@localhost:5432/plum_claims"
    groq_api_key: str = ""

    model_config = {"env_file": ".env"}


settings = Settings()

_policy_path = Path(__file__).parent.parent / "policy_terms.json"
with open(_policy_path) as _f:
    POLICY: dict = json.load(_f)