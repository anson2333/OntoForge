"""
Tests for Domain Pack Loader
"""

import pytest
from pathlib import Path
import tempfile

from backend.config.loader import DomainPackLoader, DomainPackLoaderError


VALID_YAML_CONFIG = """
schema_version: "1.0"

domain:
  id: domain.test
  name: Test Domain
  taxonomy_tree:
    - category_1
    - category_2

core_metrics:
  - name: metric_1
    expected_unit: ms
    aliases:
      - alias_1
    value_type: float

validation:
  required_context_keys:
    - key_1
  unit_normalization:
    ms:
      - ms
      - millisecond
"""

INVALID_VERSION_CONFIG = """
schema_version: "99.9"

domain:
  id: domain.test
  name: Test Domain
  taxonomy_tree: []

core_metrics: []

validation:
  required_context_keys: []
  unit_normalization: {}
"""


class TestDomainPackLoader:
    """Tests for DomainPackLoader."""

    def test_load_valid_yaml(self):
        """Test loading a valid YAML config."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(VALID_YAML_CONFIG)
            config_path = f.name

        try:
            loader = DomainPackLoader()
            config = loader.load(config_path, format="yaml")

            assert config.schema_version == "1.0"
            assert config.domain.id == "domain.test"
            assert config.domain.name == "Test Domain"
            assert len(config.core_metrics) == 1
            assert config.core_metrics[0].name == "metric_1"
        finally:
            Path(config_path).unlink()

    def test_load_nonexistent_file(self):
        """Test loading fails for nonexistent file."""
        loader = DomainPackLoader()
        with pytest.raises(DomainPackLoaderError, match="Config file not found"):
            loader.load("/nonexistent/path/config.yaml")

    def test_load_unsupported_version(self):
        """Test loading fails for unsupported schema version."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(INVALID_VERSION_CONFIG)
            config_path = f.name

        try:
            loader = DomainPackLoader()
            with pytest.raises(DomainPackLoaderError, match="Unsupported schema version"):
                loader.load(config_path, format="yaml")
        finally:
            Path(config_path).unlink()

    def test_get_domain_pack_id(self):
        """Test retrieving domain pack ID."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(VALID_YAML_CONFIG)
            config_path = f.name

        try:
            loader = DomainPackLoader()
            loader.load(config_path, format="yaml")
            assert loader.get_domain_pack_id() == "domain.test"
        finally:
            Path(config_path).unlink()

    def test_get_domain_pack_version(self):
        """Test retrieving domain pack version."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(VALID_YAML_CONFIG)
            config_path = f.name

        try:
            loader = DomainPackLoader()
            loader.load(config_path, format="yaml")
            assert loader.get_domain_pack_version() == "1.0"
        finally:
            Path(config_path).unlink()

    def test_reload_detects_changes(self):
        """Test reload detects config file changes."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(VALID_YAML_CONFIG)
            config_path = f.name

        try:
            loader = DomainPackLoader()
            loader.load(config_path, format="yaml")
            initial_hash = loader.config_hash

            # Modify file
            with open(config_path, "a") as f:
                f.write("\n# Comment added\n")

            changed = loader.reload()
            assert changed is True
            assert loader.config_hash != initial_hash
        finally:
            Path(config_path).unlink()

    def test_compute_hash_consistency(self):
        """Test hash computation is consistent."""
        loader = DomainPackLoader()
        content = "test content"
        hash1 = loader._compute_hash(content)
        hash2 = loader._compute_hash(content)
        assert hash1 == hash2
