import os
import tempfile
from unittest.mock import patch

import pytest

from bitvavo_api_upgraded.settings import BitvavoApiUpgradedSettings, BitvavoSettings


@pytest.mark.parametrize(
    ("log_level", "expected"),
    [
        ("INFO", "INFO"),
        ("DEBUG", "DEBUG"),
        ("INVALID", pytest.raises(ValueError)),  # noqa: PT011
    ],
)
def test_validate_log_level(log_level: str, expected: str) -> None:
    if isinstance(expected, str):
        assert BitvavoApiUpgradedSettings.validate_log_level(log_level) == expected
    else:
        with expected:
            BitvavoApiUpgradedSettings.validate_log_level(log_level)


def test_api_rating_limit_per_second() -> None:
    """
    Input divided by 60
    """
    settings = BitvavoSettings(API_RATING_LIMIT_PER_SECOND=120)
    assert settings.API_RATING_LIMIT_PER_SECOND == 2


def test_api_rating_limit_per_minute() -> None:
    """
    Input not changed
    """
    val = 120
    settings = BitvavoSettings(API_RATING_LIMIT_PER_MINUTE=val)
    assert settings.API_RATING_LIMIT_PER_MINUTE == val  # noqa: SIM300


class TestSSLCertificateConfiguration:
    """Tests for the SSL certificate auto-detection and configuration."""

    def test_ssl_cert_file_set_explicitly(self) -> None:
        """Test when SSL_CERT_FILE is explicitly set to a valid path."""
        with tempfile.NamedTemporaryFile() as temp_cert:
            original_env = os.environ.get("SSL_CERT_FILE")
            try:
                settings = BitvavoApiUpgradedSettings(SSL_CERT_FILE=temp_cert.name)
                assert temp_cert.name == settings.SSL_CERT_FILE
                assert temp_cert.name == os.environ.get("SSL_CERT_FILE")
            finally:
                # Restore original environment
                if original_env is not None:
                    os.environ["SSL_CERT_FILE"] = original_env
                elif "SSL_CERT_FILE" in os.environ:
                    del os.environ["SSL_CERT_FILE"]

    def test_ssl_cert_file_explicit_but_missing(self) -> None:
        """Test when SSL_CERT_FILE is set but the file doesn't exist."""
        with pytest.raises(FileNotFoundError, match="SSL certificate file not found"):
            BitvavoApiUpgradedSettings(SSL_CERT_FILE="/nonexistent/cert.pem")

    def test_ssl_cert_file_auto_detection_success(self) -> None:
        """Test successful auto-detection of SSL certificate file."""
        original_env = os.environ.get("SSL_CERT_FILE")
        try:
            # Ensure SSL_CERT_FILE is not set in environment to allow auto-detection
            if "SSL_CERT_FILE" in os.environ:
                del os.environ["SSL_CERT_FILE"]

            # Mock the Path constructor and exists method
            with patch("bitvavo_api_upgraded.settings.Path") as mock_path_class:
                # Set up the mock to return a specific Path object that has exists() return True
                # for the first certificate path
                mock_path_instance = mock_path_class.return_value
                mock_path_instance.exists.side_effect = (
                    lambda: str(mock_path_class.call_args[0][0]) == "/etc/ssl/certs/ca-certificates.crt"
                )

                settings = BitvavoApiUpgradedSettings()
                assert settings.SSL_CERT_FILE == "/etc/ssl/certs/ca-certificates.crt"
                assert os.environ.get("SSL_CERT_FILE") == "/etc/ssl/certs/ca-certificates.crt"
        finally:
            # Cleanup
            if original_env is not None:
                os.environ["SSL_CERT_FILE"] = original_env
            elif "SSL_CERT_FILE" in os.environ:
                del os.environ["SSL_CERT_FILE"]

    def test_ssl_cert_file_auto_detection_no_certs_found(self) -> None:
        """Test when no SSL certificates are found during auto-detection."""
        original_env = os.environ.get("SSL_CERT_FILE")
        try:
            # Mock Path.exists to return False for all paths
            with patch("bitvavo_api_upgraded.settings.Path.exists", return_value=False):
                settings = BitvavoApiUpgradedSettings()
                assert settings.SSL_CERT_FILE is None
                # Environment should not be modified
                assert original_env == os.environ.get("SSL_CERT_FILE")
        finally:
            # Restore original environment
            if original_env is not None:
                os.environ["SSL_CERT_FILE"] = original_env
            elif "SSL_CERT_FILE" in os.environ:
                del os.environ["SSL_CERT_FILE"]

    def test_ssl_cert_file_precedence_order(self) -> None:
        """Test that SSL certificate detection follows the correct precedence order."""
        original_env = os.environ.get("SSL_CERT_FILE")
        try:
            # Ensure SSL_CERT_FILE is not set in environment to allow auto-detection
            if "SSL_CERT_FILE" in os.environ:
                del os.environ["SSL_CERT_FILE"]

            # Mock the Path constructor to control exists() behavior
            with patch("bitvavo_api_upgraded.settings.Path") as mock_path_class:
                # Set up the mock to return a specific Path object that has exists() return True
                # for both Debian and CentOS certificate paths
                mock_path_instance = mock_path_class.return_value
                mock_path_instance.exists.side_effect = lambda: str(mock_path_class.call_args[0][0]) in [
                    "/etc/ssl/certs/ca-certificates.crt",
                    "/etc/ssl/certs/ca-bundle.crt",
                ]

                settings = BitvavoApiUpgradedSettings()
                # Should pick the first one in the list (Debian/Ubuntu/NixOS)
                assert settings.SSL_CERT_FILE == "/etc/ssl/certs/ca-certificates.crt"
                assert os.environ.get("SSL_CERT_FILE") == "/etc/ssl/certs/ca-certificates.crt"
        finally:
            if original_env is not None:
                os.environ["SSL_CERT_FILE"] = original_env
            elif "SSL_CERT_FILE" in os.environ:
                del os.environ["SSL_CERT_FILE"]

    def test_ssl_cert_file_environment_persistence(self) -> None:
        """Test that the SSL_CERT_FILE environment variable persists after settings creation."""
        original_env = os.environ.get("SSL_CERT_FILE")
        try:
            with tempfile.NamedTemporaryFile() as temp_cert:
                # Create settings with explicit SSL cert file
                _ = BitvavoApiUpgradedSettings(SSL_CERT_FILE=temp_cert.name)

                # Verify environment variable is set
                assert os.environ.get("SSL_CERT_FILE") == temp_cert.name

                # Create another settings instance without SSL_CERT_FILE
                # It should not auto-detect since env var is already set
                _ = BitvavoApiUpgradedSettings()
                assert os.environ.get("SSL_CERT_FILE") == temp_cert.name
        finally:
            if original_env is not None:
                os.environ["SSL_CERT_FILE"] = original_env
            elif "SSL_CERT_FILE" in os.environ:
                del os.environ["SSL_CERT_FILE"]
