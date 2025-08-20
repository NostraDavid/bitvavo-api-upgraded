"""
Test settings integration using tests/vars.env file.

This demonstrates how to override env_file in test code without modifying settings.py.
"""

import os
from pathlib import Path
from unittest.mock import patch

from pydantic_settings import SettingsConfigDict

from bitvavo_api_upgraded import Bitvavo
from bitvavo_api_upgraded.settings import BitvavoApiUpgradedSettings, BitvavoSettings


def test_settings_with_vars_env() -> None:
    """Test settings using tests/vars.env file by overriding env_file."""

    # Get path to tests/vars.env
    test_dir = Path(__file__).parent
    vars_env_path = test_dir / "vars.env"

    print(f"Using env file: {vars_env_path}")
    assert vars_env_path.exists(), f"vars.env file should exist at {vars_env_path}"

    # Create settings classes with overridden env_file
    class TestBitvavoSettings(BitvavoSettings):
        model_config = SettingsConfigDict(
            env_file=str(vars_env_path),
            env_file_encoding="utf-8",
            env_prefix="BITVAVO_",
            extra="ignore",
        )

    class TestBitvavoApiUpgradedSettings(BitvavoApiUpgradedSettings):
        model_config = SettingsConfigDict(
            env_file=str(vars_env_path),
            env_file_encoding="utf-8",
            env_prefix="BITVAVO_API_UPGRADED_",
            extra="ignore",
        )

    # Clear any environment variables that might interfere
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

        # Test the settings
        base_settings = TestBitvavoSettings()
        upgraded_settings = TestBitvavoApiUpgradedSettings()

        print("\n📋 Base Settings from tests/vars.env:")
        print(f"   APIKEY: {base_settings.APIKEY}")
        print(f"   APISECRET: {base_settings.APISECRET}")
        print(f"   DEBUGGING: {base_settings.DEBUGGING}")
        print(f"   RESTURL: {base_settings.RESTURL}")
        print(f"   ACCESSWINDOW: {base_settings.ACCESSWINDOW}")

        print("\n⚡ Upgraded Settings from tests/vars.env:")
        print(f"   PREFER_KEYLESS: {upgraded_settings.PREFER_KEYLESS}")
        print(f"   DEFAULT_RATE_LIMIT: {upgraded_settings.DEFAULT_RATE_LIMIT}")
        print(f"   LOG_LEVEL: {upgraded_settings.LOG_LEVEL}")
        print(f"   RATE_LIMITING_BUFFER: {upgraded_settings.RATE_LIMITING_BUFFER}")

        # Verify the values match what's in tests/vars.env
        print("\n✅ Verification:")
        assert base_settings.APIKEY == "test_key_from_vars_env"
        assert base_settings.APISECRET == "test_secret_from_vars_env"
        assert base_settings.DEBUGGING is True
        assert base_settings.RESTURL == "https://test-api.bitvavo.com/v2"
        assert upgraded_settings.PREFER_KEYLESS is False
        assert upgraded_settings.DEFAULT_RATE_LIMIT == 750
        assert upgraded_settings.LOG_LEVEL == "DEBUG"

        print("   ✓ All values correctly loaded from tests/vars.env!")

        # Test with Bitvavo class by patching the settings modules
        with (
            patch("src.bitvavo_api_upgraded.bitvavo.bitvavo_settings", base_settings),
            patch("src.bitvavo_api_upgraded.bitvavo.bitvavo_upgraded_settings", upgraded_settings),
        ):
            print("\n🚀 Testing Bitvavo with patched settings:")
            bitvavo = Bitvavo(
                {
                    "RESTURL": base_settings.RESTURL,
                    "WSURL": base_settings.WSURL,
                    "ACCESSWINDOW": base_settings.ACCESSWINDOW,
                    "DEBUGGING": base_settings.DEBUGGING,
                    "PREFER_KEYLESS": upgraded_settings.PREFER_KEYLESS,
                    "APIKEY": base_settings.APIKEY,
                    "APISECRET": base_settings.APISECRET,
                }
            )

            print(f"   APIKEY: {bitvavo.APIKEY}")
            print(f"   debugging: {bitvavo.debugging}")
            print(f"   base URL: {bitvavo.base}")
            print(f"   prefer_keyless: {bitvavo.prefer_keyless}")

            # Verify Bitvavo uses the test settings
            assert bitvavo.APIKEY == "test_key_from_vars_env"
            assert bitvavo.debugging is True
            assert bitvavo.base == "https://test-api.bitvavo.com/v2"
            assert bitvavo.prefer_keyless is False

            print("   ✓ Bitvavo correctly uses settings from tests/vars.env!")


def test_settings_inheritance_approach() -> None:
    """Alternative approach: Create test settings by inheriting and overriding."""

    test_dir = Path(__file__).parent
    vars_env_path = test_dir / "vars.env"

    # Clear any environment variables that might interfere
    env_vars_to_clear = [
        "BITVAVO_APIKEY",
        "BITVAVO_APISECRET",
        "BITVAVO_DEBUGGING",
        "BITVAVO_RESTURL",
        "BITVAVO_API_UPGRADED_PREFER_KEYLESS",
        "BITVAVO_API_UPGRADED_DEFAULT_RATE_LIMIT",
        "BITVAVO_API_UPGRADED_LOG_LEVEL",
    ]

    for var in env_vars_to_clear:
        _ = os.environ.pop(var, None)

    # Even cleaner approach - define the settings as class attributes
    class VarsEnvBitvavoSettings(BitvavoSettings):
        model_config = SettingsConfigDict(
            env_file=vars_env_path,
            env_file_encoding="utf-8",
            env_prefix="BITVAVO_",
            extra="ignore",
        )

    class VarsEnvBitvavoApiUpgradedSettings(BitvavoApiUpgradedSettings):
        model_config = SettingsConfigDict(
            env_file=vars_env_path,
            env_file_encoding="utf-8",
            env_prefix="BITVAVO_API_UPGRADED_",
            extra="ignore",
        )

    # Test that these work correctly
    settings = VarsEnvBitvavoSettings()
    upgraded = VarsEnvBitvavoApiUpgradedSettings()

    print("\n🧪 Testing inheritance approach:")
    print(f"   Settings APIKEY: {settings.APIKEY}")
    print(f"   Upgraded PREFER_KEYLESS: {upgraded.PREFER_KEYLESS}")

    assert settings.APIKEY == "test_key_from_vars_env"
    assert upgraded.PREFER_KEYLESS is False
    print("   ✓ Inheritance approach works!")
