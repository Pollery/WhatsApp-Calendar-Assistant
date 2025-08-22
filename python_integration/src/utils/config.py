import os
from pathlib import Path
from dotenv import load_dotenv

def load_config():
    """
    Load configuration variables.
    - If running locally: loads from .env file in project root.
    - If running in a container/CI/CD: 
      uses environment variables set by the platform.
    """

    # Try to load .env only if running locally
    env_path = Path(__file__).resolve().parents[0] / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)

    config = {
        "EVOLUTION_API_URL": os.getenv("EVOLUTION_API_URL", "http://localhost:8389"),
        "LLM_API_KEY": os.getenv("LLM_API_KEY"), 
        "MY_NUMBER": os.getenv("MY_NUMBER"),
        "BASE_URL": os.getenv("BASE_URL", "http://localhost:8389"),
        "AUTHENTICATION_API_KEY": os.getenv("AUTHENTICATION_API_KEY"),
        "INSTANCE_NAME": os.getenv("INSTANCE_NAME", "wpp-tablet"),
    }
    # Check required vars
    missing = [k for k, v in config.items() if v is None]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    return config
