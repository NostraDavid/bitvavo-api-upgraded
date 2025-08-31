"""Modern, modular Bitvavo API client."""

from bitvavo_client.core.settings import BitvavoSettings
from bitvavo_client.facade import BitvavoClient

__version__ = "1.0.0"
__all__ = ["BitvavoClient", "BitvavoSettings"]
