"""
Domain Pack Loader
Loads and parses domain-pack.yaml/json configuration files with version compatibility checking.
"""

import hashlib
import json
from pathlib import Path
from typing import Union

import yaml
from pydantic import ValidationError

from backend.schemas.domain_pack import DomainPackConfig


class DomainPackLoaderError(Exception):
    """Raised when domain pack loading fails."""
    pass


class DomainPackLoader:
    """
    Loads domain pack configuration from YAML or JSON files.
    Validates schema version compatibility and builds in-memory registries.
    """

    SUPPORTED_SCHEMA_VERSIONS = ["1.0"]

    def __init__(self):
        self.current_config: Union[DomainPackConfig, None] = None
        self.config_hash: Union[str, None] = None
        self.config_path: Union[Path, None] = None

    def load(self, config_path: Union[str, Path], format: str = "yaml") -> DomainPackConfig:
        """
        Load domain pack from file.

        Args:
            config_path: Path to domain-pack.yaml or domain-pack.json
            format: File format ("yaml" or "json")

        Returns:
            Validated DomainPackConfig instance

        Raises:
            DomainPackLoaderError: If loading or validation fails
        """
        self.config_path = Path(config_path)

        if not self.config_path.exists():
            raise DomainPackLoaderError(f"Config file not found: {config_path}")

        try:
            # Read file content
            raw_content = self.config_path.read_text(encoding="utf-8")
            self.config_hash = self._compute_hash(raw_content)

            # Parse based on format
            if format == "yaml":
                data = yaml.safe_load(raw_content)
            elif format == "json":
                data = json.loads(raw_content)
            else:
                raise DomainPackLoaderError(f"Unsupported format: {format}")

            # Validate schema version
            schema_version = data.get("schema_version")
            if not schema_version:
                raise DomainPackLoaderError("Missing 'schema_version' field in config")

            if schema_version not in self.SUPPORTED_SCHEMA_VERSIONS:
                raise DomainPackLoaderError(
                    f"Unsupported schema version: {schema_version}. "
                    f"Supported versions: {', '.join(self.SUPPORTED_SCHEMA_VERSIONS)}"
                )

            # Validate with Pydantic
            self.current_config = DomainPackConfig(**data)
            return self.current_config

        except yaml.YAMLError as e:
            raise DomainPackLoaderError(f"YAML parsing error: {e}")
        except json.JSONDecodeError as e:
            raise DomainPackLoaderError(f"JSON parsing error: {e}")
        except ValidationError as e:
            raise DomainPackLoaderError(f"Schema validation error: {e}")

    def reload(self) -> bool:
        """
        Reload configuration from the same path.

        Returns:
            True if config changed, False if unchanged

        Raises:
            DomainPackLoaderError: If no config was previously loaded
        """
        if not self.config_path:
            raise DomainPackLoaderError("No config path set. Load a config first.")

        old_hash = self.config_hash
        format_ext = self.config_path.suffix.lstrip(".")
        format = "yaml" if format_ext in ["yaml", "yml"] else "json"

        self.load(self.config_path, format=format)

        return self.config_hash != old_hash

    def get_domain_pack_id(self) -> str:
        """Get unique identifier for the loaded domain pack."""
        if not self.current_config:
            raise DomainPackLoaderError("No config loaded")
        return self.current_config.domain.id

    def get_domain_pack_version(self) -> str:
        """Get schema version of the loaded domain pack."""
        if not self.current_config:
            raise DomainPackLoaderError("No config loaded")
        return self.current_config.schema_version

    @staticmethod
    def _compute_hash(content: str) -> str:
        """Compute SHA-256 hash of config content for reproducibility."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
