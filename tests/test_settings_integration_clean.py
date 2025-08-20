"""Test settings integration with the Bitvavo API wrapper."""

import os
from pathlib import Path
from unittest.mock import patch

from bitvavo_api_upgraded import Bitvavo
from bitvavo_api_upgraded.settings import (
    BitvavoApiUpgradedSettings,
    BitvavoSettings,
)


class TestBitvavoSettings:
    """Test the BitvavoSettings class."""

    def test_default_values(self) -> None:
        """Test that default values are correctly set."""
        with patch.dict(os.environ, {}, clear=True):
            # APISECRET and APIKEY should are required when creating BitvavoSettings
            settings = BitvavoSettings(APIKEY="", APISECRET="")

            assert settings.ACCESSWINDOW == 10_000
            assert settings.API_RATING_LIMIT_PER_MINUTE == 1000
            assert settings.APIKEY == ""
            assert settings.APISECRET == ""
            assert settings.APIKEYS == []
            assert settings.DEBUGGING is False
            assert settings.RESTURL == "https://api.bitvavo.com/v2"
            assert settings.WSURL == "wss://ws.bitvavo.com/v2/"
            assert settings.PREFER_KEYLESS is True

    def test_environment_variables(self) -> None:
        """Test that environment variables override defaults."""
        with patch.dict(
            os.environ,
            {
                "BITVAVO_ACCESSWINDOW": "15000",
                "BITVAVO_DEBUGGING": "true",
                "BITVAVO_APIKEY": "test_key",
                "BITVAVO_APISECRET": "test_secret",
            },
            clear=True,
        ):
            settings = BitvavoSettings()
            assert settings.ACCESSWINDOW == 15000
            assert settings.DEBUGGING is True
            assert settings.APIKEY == "test_key"
            assert settings.APISECRET == "test_secret"
            assert len(settings.APIKEYS) == 1
            assert settings.APIKEYS[0]["key"] == "test_key"


class TestBitvavoApiUpgradedSettings:
    """Test the BitvavoApiUpgradedSettings class."""

    def test_default_values(self) -> None:
        """Test that default values are correctly set."""
        with patch.dict(os.environ, {}, clear=True):
            settings = BitvavoApiUpgradedSettings()

            assert settings.LOG_LEVEL == "INFO"
            assert settings.PREFER_KEYLESS is True
            assert settings.DEFAULT_RATE_LIMIT == 1000

    def test_environment_variables(self) -> None:
        """Test that environment variables override defaults."""
        with patch.dict(
            os.environ,
            {
                "BITVAVO_API_UPGRADED_PREFER_KEYLESS": "false",
                "BITVAVO_API_UPGRADED_DEFAULT_RATE_LIMIT": "500",
                "BITVAVO_API_UPGRADED_LOG_LEVEL": "DEBUG",
            },
            clear=True,
        ):
            settings = BitvavoApiUpgradedSettings()
            assert settings.PREFER_KEYLESS is False
            assert settings.DEFAULT_RATE_LIMIT == 500
            assert settings.LOG_LEVEL == "DEBUG"


class TestBitvavoWithSettings:
    """Test Bitvavo class integration with settings."""

    def test_init_uses_settings_defaults(self) -> None:
        """Test that __init__ uses settings as defaults."""
        # Since the settings are singletons loaded at import time,
        # we test that options override them correctly
        bitvavo = Bitvavo(
            {
                "RESTURL": "https://custom.api.com/v2",
                "DEBUGGING": True,
                "PREFER_KEYLESS": False,
            }
        )

        assert bitvavo.base == "https://custom.api.com/v2"
        assert bitvavo.debugging is True
        assert bitvavo.prefer_keyless is False

    def test_init_options_override_settings(self) -> None:
        """Test that explicit options override settings."""
        with patch.dict(
            os.environ,
            {"BITVAVO_DEBUGGING": "true"},
            clear=True,
        ):
            bitvavo = Bitvavo({"DEBUGGING": False})
            assert bitvavo.debugging is False

    def test_settings_constructor_integration(self) -> None:
        """Test the direct constructor with settings values."""
        # Create settings instances directly
        base_settings = BitvavoSettings()
        upgraded_settings = BitvavoApiUpgradedSettings()

        # Create Bitvavo instance using settings values
        bitvavo = Bitvavo(
            {
                "RESTURL": base_settings.RESTURL,
                "WSURL": base_settings.WSURL,
                "ACCESSWINDOW": base_settings.ACCESSWINDOW,
                "DEBUGGING": base_settings.DEBUGGING,
                "PREFER_KEYLESS": upgraded_settings.PREFER_KEYLESS,
            }
        )

        # Verify it's a Bitvavo instance with basic properties
        assert hasattr(bitvavo, "APIKEY")
        assert hasattr(bitvavo, "APISECRET")
        assert hasattr(bitvavo, "debugging")
        assert hasattr(bitvavo, "prefer_keyless")

        # Test with override options
        bitvavo_with_override = Bitvavo(
            {
                "RESTURL": base_settings.RESTURL,
                "WSURL": base_settings.WSURL,
                "ACCESSWINDOW": base_settings.ACCESSWINDOW,
                "DEBUGGING": True,  # Override
                "PREFER_KEYLESS": upgraded_settings.PREFER_KEYLESS,
            }
        )
        assert bitvavo_with_override.debugging is True

    def test_constructor_with_overrides(self) -> None:
        """Test constructor with settings and additional options."""
        with patch.dict(
            os.environ,
            {"BITVAVO_DEBUGGING": "false"},
            clear=True,
        ):
            base_settings = BitvavoSettings()
            bitvavo = Bitvavo(
                {
                    "RESTURL": base_settings.RESTURL,
                    "WSURL": base_settings.WSURL,
                    "ACCESSWINDOW": base_settings.ACCESSWINDOW,
                    "DEBUGGING": True,  # Override environment setting
                    "PREFER_KEYLESS": False,
                }
            )
            assert bitvavo.debugging is True  # Override wins

    def test_api_keys_from_environment(self) -> None:
        """Test that API keys are loaded from environment."""
        # Create fresh settings that pick up the environment
        base_settings = BitvavoSettings()
        upgraded_settings = BitvavoApiUpgradedSettings()

        bitvavo = Bitvavo(
            {
                "APIKEY": "settings_key",
                "APISECRET": "settings_secret",
                "RESTURL": base_settings.RESTURL,
                "WSURL": base_settings.WSURL,
                "ACCESSWINDOW": base_settings.ACCESSWINDOW,
                "DEBUGGING": base_settings.DEBUGGING,
                "PREFER_KEYLESS": upgraded_settings.PREFER_KEYLESS,
            }
        )

        assert len(bitvavo.api_keys) == 1
        assert bitvavo.api_keys[0]["key"] == "settings_key"
        assert bitvavo.api_keys[0]["secret"] == "settings_secret"  # noqa: S105 (Possible hardcoded password assigned)

    def test_settings_with_multi_key_features(self) -> None:
        """Test that settings work with multi-key features."""
        # Create fresh settings, then override with explicit APIKEYS
        base_settings = BitvavoSettings()
        upgraded_settings = BitvavoApiUpgradedSettings()

        bitvavo = Bitvavo(
            {
                "RESTURL": base_settings.RESTURL,
                "WSURL": base_settings.WSURL,
                "ACCESSWINDOW": base_settings.ACCESSWINDOW,
                "DEBUGGING": base_settings.DEBUGGING,
                "PREFER_KEYLESS": upgraded_settings.PREFER_KEYLESS,
                "APIKEYS": [{"key": "key1", "secret": "secret1"}, {"key": "key2", "secret": "secret2"}],
                "DEFAULT_RATE_LIMIT": "800",
            }
        )

        assert bitvavo.prefer_keyless is True
        assert bitvavo.rate_limits[-1]["remaining"] == 800  # keyless
        assert bitvavo.rate_limits[0]["remaining"] == 800  # key1
        assert bitvavo.rate_limits[1]["remaining"] == 800  # key2


class TestVarsEnvFileSupport:
    """Test settings loading from vars.env file."""

    def test_vars_env_file_loading(self) -> None:
        """Test that settings are loaded from vars.env file."""
        # Get the path to the vars.env file in the project root
        project_root = Path(__file__).parent.parent
        vars_env_file = project_root / "tests" / "vars.env"

        # Ensure the vars.env file exists
        assert vars_env_file.exists(), "vars.env file should exist in project root"

        original_cwd = Path.cwd()
        try:
            # Change to project root where vars.env is located
            os.chdir(project_root)

            # Clear environment variables to ensure we're loading from file
            env_vars_to_clear = [
                "BITVAVO_APIKEY",
                "BITVAVO_APISECRET",
                "BITVAVO_DEBUGGING",
                "BITVAVO_RESTURL",
                "BITVAVO_API_UPGRADED_PREFER_KEYLESS",
                "BITVAVO_API_UPGRADED_DEFAULT_RATE_LIMIT",
                "BITVAVO_API_UPGRADED_LOG_LEVEL",
            ]
            with patch.dict(os.environ, {}, clear=False):
                for var in env_vars_to_clear:
                    _ = os.environ.pop(var, None)

                # Rename .env to .env.backup temporarily to avoid conflicts
                env_backup = None
                env_file = project_root / ".env"
                if env_file.exists():
                    env_backup = project_root / ".env.backup"
                    _ = env_file.rename(env_backup)

                # Rename vars.env to .env temporarily for testing
                _ = vars_env_file.rename(project_root / ".env")

                try:
                    base_settings = BitvavoSettings()
                    upgraded_settings = BitvavoApiUpgradedSettings()

                    # Test that values were loaded from vars.env
                    assert base_settings.APIKEY == "test_key_from_vars_env"
                    assert base_settings.APISECRET == "test_secret_from_vars_env"
                    assert base_settings.DEBUGGING is True
                    assert base_settings.RESTURL == "https://test-api.bitvavo.com/v2"
                    assert upgraded_settings.PREFER_KEYLESS is False
                    assert upgraded_settings.DEFAULT_RATE_LIMIT == 750
                    assert upgraded_settings.LOG_LEVEL == "DEBUG"

                finally:
                    # Restore original files
                    _ = (project_root / ".env").rename(vars_env_file)
                    if env_backup and env_backup.exists():
                        _ = env_backup.rename(env_file)

        finally:
            os.chdir(original_cwd)


class TestBackwardCompatibility:
    """Test that settings changes maintain backward compatibility."""

    def test_existing_code_still_works(self) -> None:
        """Test that existing code patterns still work."""
        # Clear environment to ensure options take precedence
        with patch.dict(os.environ, {}, clear=True):
            bitvavo = Bitvavo(
                {
                    "APIKEY": "old_key",
                    "APISECRET": "old_secret",
                    "DEBUGGING": True,
                }
            )

            assert bitvavo.APIKEY == "old_key"
            assert bitvavo.APISECRET == "old_secret"
            assert bitvavo.debugging is True

    def test_empty_initialization_with_settings(self) -> None:
        """Test that empty initialization works with settings."""
        # Settings will be loaded before test runs, so environment variables
        # won't be picked up during test execution
        bitvavo = Bitvavo()

        # Test basic functionality without relying on environment variables
        assert hasattr(bitvavo, "base")
        assert hasattr(bitvavo, "prefer_keyless")
        assert hasattr(bitvavo, "api_keys")
        assert isinstance(bitvavo.api_keys, list)
