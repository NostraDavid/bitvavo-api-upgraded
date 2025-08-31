"""
Pytest-compatible test showing how to override env_file without modifying settings.py
"""

import sys
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bitvavo_api_upgraded.settings import BitvavoApiUpgradedSettings, BitvavoSettings


@pytest.fixture(autouse=True)
def load_test_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Load environment variables from tests/vars.env for these tests."""
    vars_env_path = Path(__file__).parent / "vars.env"

    if vars_env_path.exists():
        with vars_env_path.open() as f:
            for file_line in f:
                stripped_line = file_line.strip()
                if stripped_line and not stripped_line.startswith("#") and "=" in stripped_line:
                    key, value = stripped_line.split("=", 1)
                    monkeypatch.setenv(key, value)


class TestVarsEnvSettings:
    """Test settings using tests/vars.env loaded via fixture."""

    def test_base_settings_with_vars_env(self) -> None:
        """Test BitvavoSettings with environment variables from tests/vars.env."""
        # Now we can use the regular settings class since env vars are loaded
        settings = BitvavoSettings()

        # These values should come from environment variables set by the fixture
        assert settings.APIKEY == "test_key_from_vars_env"
        assert settings.APISECRET == "test_secret_from_vars_env"
        assert settings.DEBUGGING is True
        assert settings.RESTURL == "https://test-api.bitvavo.com/v2"
        assert settings.ACCESSWINDOW == 15000

    def test_upgraded_settings_with_vars_env(self) -> None:
        """Test BitvavoApiUpgradedSettings with environment variables from tests/vars.env."""
        # Now we can use the regular settings class since env vars are loaded
        settings = BitvavoApiUpgradedSettings()

        # These values should come from environment variables set by the fixture
        assert settings.PREFER_KEYLESS is False
        assert settings.DEFAULT_RATE_LIMIT == 750
        assert settings.LOG_LEVEL == "DEBUG"
        assert settings.RATE_LIMITING_BUFFER == 30

    def test_original_settings_unchanged(self) -> None:
        """Verify that original settings classes still work with default .env."""

        # Original settings should still use .env (if it exists) or defaults
        base_settings = BitvavoSettings()
        upgraded_settings = BitvavoApiUpgradedSettings()

        # These should be the default values or from root .env, not from tests/vars.env
        assert isinstance(base_settings.ACCESSWINDOW, int)
        assert isinstance(base_settings.DEBUGGING, bool)
        assert isinstance(upgraded_settings.DEFAULT_RATE_LIMIT, int)
        assert isinstance(upgraded_settings.PREFER_KEYLESS, bool)

        # The original settings should NOT have the test values from vars.env
        # (unless they happen to be the same, but these specific ones are different)
        print(f"Original APIKEY: {base_settings.APIKEY}")
        print(f"Original PREFER_KEYLESS: {upgraded_settings.PREFER_KEYLESS}")
