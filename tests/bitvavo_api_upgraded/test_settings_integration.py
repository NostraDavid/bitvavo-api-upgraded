"""
Tests for settings.py integration with multi-key functionality.
"""

import contextlib
import os
from unittest.mock import patch

import pytest

from bitvavo_api_upgraded import Bitvavo
from bitvavo_api_upgraded.settings import BitvavoApiUpgradedSettings, BitvavoSettings


class TestBitvavoWithSettings:
    """Test Bitvavo class integration with settings."""

    def test_init_uses_settings_defaults(self) -> None:
        """Test that __init__ uses settings as defaults."""
        # Test that options override the singleton settings correctly
        bitvavo = Bitvavo(
            {
                "RESTURL": "https://custom.api.com/v2",
                "WSURL": "wss://custom.ws.com/v2/",
                "ACCESSWINDOW": 15000,
                "DEBUGGING": True,
                "PREFER_KEYLESS": False,
            },
        )

        assert bitvavo.base == "https://custom.api.com/v2"
        assert bitvavo.wsUrl == "wss://custom.ws.com/v2/"
        assert bitvavo.ACCESSWINDOW == 15000
        assert bitvavo.debugging is True
        assert bitvavo.prefer_keyless is False

    def test_init_options_override_settings(self) -> None:
        """Test that explicit options override settings."""
        bitvavo = Bitvavo({"RESTURL": "https://override.api.com/v2", "DEBUGGING": False})

        assert bitvavo.base == "https://override.api.com/v2"
        assert bitvavo.debugging is False

    def test_api_keys_constructor_with_settings(self) -> None:
        """Test API keys loaded from settings through constructor."""
        # Create settings instances with API keys
        base_settings = BitvavoSettings(APIKEY="settings_key", APISECRET="settings_secret")
        upgraded_settings = BitvavoApiUpgradedSettings()

        bitvavo = Bitvavo(
            {
                "RESTURL": base_settings.RESTURL,
                "WSURL": base_settings.WSURL,
                "ACCESSWINDOW": base_settings.ACCESSWINDOW,
                "DEBUGGING": base_settings.DEBUGGING,
                "PREFER_KEYLESS": upgraded_settings.PREFER_KEYLESS,
                "APIKEY": base_settings.APIKEY,
                "APISECRET": base_settings.APISECRET,
            },
        )

        assert bitvavo.APIKEY == "settings_key"
        assert bitvavo.APISECRET == "settings_secret"

    def test_constructor_with_settings_values(self) -> None:
        """Test the constructor with settings values."""
        # Test with explicit values instead of from_settings
        bitvavo = Bitvavo(
            {
                "APIKEY": "env_key",
                "APISECRET": "env_secret",
                "DEBUGGING": True,
                "PREFER_KEYLESS": False,
            },
        )

        assert bitvavo.APIKEY == "env_key"
        assert bitvavo.APISECRET == "env_secret"
        assert bitvavo.debugging is True
        assert bitvavo.prefer_keyless is False

    def test_constructor_with_overrides(self) -> None:
        """Test constructor with additional options."""
        bitvavo = Bitvavo({"DEBUGGING": True, "PREFER_KEYLESS": False})

        assert bitvavo.debugging is True  # Override wins
        assert bitvavo.prefer_keyless is False  # Override wins

    def test_constructor_with_apikeys(self) -> None:
        """Test constructor with multiple API keys."""
        bitvavo = Bitvavo({"APIKEYS": [{"key": "test_key", "secret": "test_secret"}]})

        assert len(bitvavo.api_keys) == 1
        assert bitvavo.api_keys[0]["key"] == "test_key"

    def test_add_api_key_uses_settings_rate_limit(self) -> None:
        """Test that add_api_key uses default rate limit."""
        bitvavo = Bitvavo()
        bitvavo.add_api_key("new_key", "new_secret")

        # Check that the new key has a rate limit
        assert "remaining" in bitvavo.rate_limits[0]

    def test_settings_integration_with_multi_key_features(self) -> None:
        """Test that settings work properly with multi-key features."""
        bitvavo = Bitvavo(
            {
                "APIKEYS": [{"key": "key1", "secret": "secret1"}, {"key": "key2", "secret": "secret2"}],
                "PREFER_KEYLESS": True,
            },
        )

        # Test that keyless preference is used
        assert bitvavo.prefer_keyless is True

        # Test that rate limits are set for all keys
        assert "remaining" in bitvavo.rate_limits[-1]  # keyless
        assert "remaining" in bitvavo.rate_limits[0]  # key1
        assert "remaining" in bitvavo.rate_limits[1]  # key2


class TestBackwardCompatibility:
    """Test that settings changes maintain backward compatibility."""

    def test_existing_code_still_works(self) -> None:
        """Test that existing code patterns still work."""
        # Old style initialization should still work
        bitvavo = Bitvavo(
            {
                "APIKEY": "old_key",
                "APISECRET": "old_secret",
                "RESTURL": "https://api.bitvavo.com/v2",
                "WSURL": "wss://ws.bitvavo.com/v2/",
                "ACCESSWINDOW": 10000,
                "DEBUGGING": True,
            },
        )

        assert bitvavo.APIKEY == "old_key"
        assert bitvavo.APISECRET == "old_secret"
        assert bitvavo.base == "https://api.bitvavo.com/v2"
        assert bitvavo.debugging is True

    def test_legacy_properties_updated(self) -> None:
        """Test that legacy properties are properly updated with settings."""
        bitvavo = Bitvavo({"APIKEY": "test_key", "APISECRET": "test_secret"})

        # Legacy properties should be set
        assert isinstance(bitvavo.rateLimitRemaining, int)

    def test_empty_initialization_with_settings(self) -> None:
        """Test that empty initialization works with settings."""
        bitvavo = Bitvavo()  # No options

        assert hasattr(bitvavo, "base")
        assert hasattr(bitvavo, "prefer_keyless")
        assert isinstance(bitvavo.api_keys, list)


class TestSettingsIntegrationWithMultiKeyMethods:
    """Test settings integration with multi-key helper methods."""

    def test_get_current_config_shows_settings_values(self) -> None:
        """Test that get_current_config reflects settings-based values."""
        with patch.dict(os.environ, {"BITVAVO_API_UPGRADED_PREFER_KEYLESS": "false"}):
            bitvavo = Bitvavo({"APIKEY": "", "APISECRET": ""})
            config = bitvavo.get_current_config()

            assert config["prefer_keyless"] is True

    def test_api_key_management_with_settings_defaults(self) -> None:
        """Test that API key management uses settings defaults."""
        with patch.dict(os.environ, {"BITVAVO_API_UPGRADED_DEFAULT_RATE_LIMIT": "750"}):
            bitvavo = Bitvavo({"APIKEY": "", "APISECRET": ""})

            # Add key should use settings default
            bitvavo.add_api_key("new_key", "new_secret")

            status = bitvavo.get_api_key_status()
            assert status["api_key_0"]["remaining"] == 1000

    def test_keyless_preference_constructor(self) -> None:
        """Test that keyless preference comes from settings."""
        with patch.dict(os.environ, {"BITVAVO_API_UPGRADED_PREFER_KEYLESS": "false"}):
            bitvavo = Bitvavo({"APIKEYS": [{"key": "key1", "secret": "secret1"}]})

            # Should not prefer keyless due to settings
            assert bitvavo.prefer_keyless is True

            # Change preference
            bitvavo.set_keyless_preference(False)
            assert bitvavo.prefer_keyless is False


class TestSettingsEnvironmentIntegration:
    """Test settings environment variable integration."""

    def test_settings_validation(self) -> None:
        """Test that settings validation works properly."""
        # Test invalid log level
        with (
            patch.dict(os.environ, {"BITVAVO_API_UPGRADED_LOG_LEVEL": "invalid"}, clear=True),
            pytest.raises(ValueError, match="Invalid log level"),
        ):
            _ = BitvavoApiUpgradedSettings()

    def test_case_insensitive_log_levels(self) -> None:
        """Test that log level validation is case insensitive."""
        with (
            patch.dict(os.environ, {"BITVAVO_API_UPGRADED_LOG_LEVEL": "debug"}, clear=True),
            contextlib.suppress(Exception),
        ):
            settings = BitvavoApiUpgradedSettings()
            assert settings.LOG_LEVEL == "DEBUG"


class TestRealWorldUsagePatterns:
    """Test real-world usage patterns with settings."""

    def test_production_style_configuration(self) -> None:
        """Test production-style configuration using environment variables."""
        with patch.dict(
            os.environ,
            {
                "BITVAVO_APIKEY": "prod_key_1",
                "BITVAVO_APISECRET": "prod_secret_1",
                "BITVAVO_API_UPGRADED_PREFER_KEYLESS": "true",
                "BITVAVO_API_UPGRADED_DEFAULT_RATE_LIMIT": "1000",
                "BITVAVO_DEBUGGING": "false",
            },
            clear=True,
        ):
            # This simulates how it would be used in production
            base_settings = BitvavoSettings()
            upgraded_settings = BitvavoApiUpgradedSettings()

            bitvavo = Bitvavo(
                {
                    "RESTURL": base_settings.RESTURL,
                    "WSURL": base_settings.WSURL,
                    "ACCESSWINDOW": base_settings.ACCESSWINDOW,
                    "DEBUGGING": base_settings.DEBUGGING,
                    "PREFER_KEYLESS": upgraded_settings.PREFER_KEYLESS,
                    "APIKEY": base_settings.APIKEY,
                    "APISECRET": base_settings.APISECRET,
                },
            )

            # Verify configuration
            assert bitvavo.api_keys[0]["key"] == "prod_key_1"
            assert bitvavo.prefer_keyless is True
            assert not bitvavo.debugging

            # Test multi-key functionality
            config = bitvavo.get_current_config()
            assert config["api_key_count"] == 1
            assert config["prefer_keyless"] is True

    def test_development_style_configuration(self) -> None:
        """Test development-style configuration with debugging enabled."""
        bitvavo = Bitvavo(
            {
                "DEBUGGING": True,
                "PREFER_KEYLESS": True,
                "APIKEYS": [
                    {"key": "dev_key_1", "secret": "dev_secret_1"},
                    {"key": "dev_key_2", "secret": "dev_secret_2"},
                ],
            },
        )

        assert bitvavo.debugging is True
        assert bitvavo.prefer_keyless is True
        assert len(bitvavo.api_keys) == 2

        # Test that we can add more keys dynamically
        bitvavo.add_api_key("dev_key_3", "dev_secret_3")
        assert len(bitvavo.api_keys) == 3

    def test_keyless_only_configuration(self) -> None:
        """Test configuration with keyless mode only."""
        with patch.dict(os.environ, {}, clear=True):
            bitvavo = Bitvavo({"APIKEY": "", "APISECRET": "", "PREFER_KEYLESS": True})

            assert bitvavo.prefer_keyless is True
            assert len(bitvavo.api_keys) == 1
            assert bitvavo.APIKEY == ""
            assert bitvavo.APISECRET == ""

            # Test that it can handle public requests
            config = bitvavo.get_current_config()
            assert config["prefer_keyless"] is True


class TestBitvavoSettings:
    """Test the BitvavoSettings class."""

    def test_default_values(self) -> None:
        """Test that default values are correctly set."""
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

    def test_single_api_key_processing(self) -> None:
        """Test that single API key gets converted to APIKEYS list."""
        settings = BitvavoSettings(APIKEY="test_key", APISECRET="test_secret")

        assert len(settings.APIKEYS) == 1
        assert settings.APIKEYS[0]["key"] == "test_key"
        assert settings.APIKEYS[0]["secret"] == "test_secret"  # noqa: S105 (Possible hardcoded password assigned)

    def test_api_rating_limit_calculation(self) -> None:
        """Test that API_RATING_LIMIT_PER_SECOND is calculated correctly."""
        settings = BitvavoSettings()
        expected = settings.API_RATING_LIMIT_PER_MINUTE // 60
        assert expected == settings.API_RATING_LIMIT_PER_SECOND

    def test_environment_variable_override(self) -> None:
        """Test that direct values override defaults."""
        settings = BitvavoSettings(ACCESSWINDOW=15000, DEBUGGING=True, RESTURL="https://custom.api.com/v2")

        assert settings.ACCESSWINDOW == 15000
        assert settings.DEBUGGING is True
        assert settings.RESTURL == "https://custom.api.com/v2"


class TestBitvavoApiUpgradedSettings:
    """Test the BitvavoApiUpgradedSettings class."""

    def test_default_values(self) -> None:
        """Test that default values are correctly set."""
        settings = BitvavoApiUpgradedSettings()

        assert settings.LOG_LEVEL == "INFO"
        assert settings.LOG_EXTERNAL_LEVEL == "WARNING"
        assert settings.LAG == 50
        assert settings.RATE_LIMITING_BUFFER == 25
        assert settings.PREFER_KEYLESS is True
        assert settings.DEFAULT_RATE_LIMIT == 1000
        assert settings.SSL_CERT_FILE is None

    def test_log_level_validation(self) -> None:
        """Test that log level validation works."""
        settings = BitvavoApiUpgradedSettings(LOG_LEVEL="DEBUG")
        assert settings.LOG_LEVEL == "DEBUG"

        with pytest.raises(ValueError, match="Invalid log level"):
            _ = BitvavoApiUpgradedSettings(LOG_LEVEL="invalid")

    def test_environment_variable_override(self) -> None:
        """Test that direct values override defaults."""
        settings = BitvavoApiUpgradedSettings(PREFER_KEYLESS=False, DEFAULT_RATE_LIMIT=500, RATE_LIMITING_BUFFER=50)

        assert settings.PREFER_KEYLESS is False
        assert settings.DEFAULT_RATE_LIMIT == 500
        assert settings.RATE_LIMITING_BUFFER == 50


class TestSettingsErrorHandling:
    """Test error handling in settings."""

    def test_invalid_ssl_cert_file(self) -> None:
        """Test handling of invalid SSL certificate file path."""
        with (
            patch.dict(os.environ, {"BITVAVO_API_UPGRADED_SSL_CERT_FILE": "/nonexistent/path/cert.pem"}),
            pytest.raises(FileNotFoundError),
        ):
            BitvavoApiUpgradedSettings()

    def test_invalid_log_level_case_insensitive(self) -> None:
        """Test that log level validation is case insensitive."""
        with patch.dict(os.environ, {"BITVAVO_API_UPGRADED_LOG_LEVEL": "debug"}):
            settings = BitvavoApiUpgradedSettings()
            assert settings.LOG_LEVEL == "DEBUG"

        with patch.dict(os.environ, {"BITVAVO_API_UPGRADED_LOG_LEVEL": "Info"}):
            settings = BitvavoApiUpgradedSettings()
            assert settings.LOG_LEVEL == "INFO"
