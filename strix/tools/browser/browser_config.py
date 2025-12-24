import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BrowserConfig:
    """Browser configuration management"""

    SESSION_ENV_VAR = "STRIX_SESSION_FILE"
    storage_state_path: str | None = None

    @classmethod
    def from_path(cls, storage_state_path: str | None = None) -> "BrowserConfig":
        """Load configuration from provided path"""
        if storage_state_path is None:
            storage_state_path = os.getenv(cls.SESSION_ENV_VAR)

        if storage_state_path:
            storage_state_path = os.path.abspath(os.path.expanduser(storage_state_path))

        return cls(storage_state_path=storage_state_path)

    def validate(self) -> None:
        """Validate configuration"""
        if self.storage_state_path:
            path = Path(self.storage_state_path)
            if not path.exists():
                raise FileNotFoundError(
                    f"Storage state file not found: {self.storage_state_path}"
                )
            if not path.is_file():
                raise ValueError(
                    f"Storage state path is not a file: {self.storage_state_path}"
                )
