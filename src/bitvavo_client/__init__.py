"""Modern, modular Bitvavo API client."""

from bitvavo_client.core.settings import BitvavoSettings
from bitvavo_client.facade import Bitvavo

__version__ = "1.0.0"
__all__ = ["Bitvavo", "BitvavoSettings"]
