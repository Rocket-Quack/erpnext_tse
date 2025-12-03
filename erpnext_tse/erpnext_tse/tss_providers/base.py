# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see LICENSE

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTSEProvider(ABC):
    """Abstract base class for TSE providers (Fiskaly, local TSE, ...)."""

    def __init__(self, settings_doc):
        # settings_doc is the "TSE Settings" singleton document
        self.settings = settings_doc

    # --- High-level operations used by the UI / other code ------------------

    @abstractmethod
    def test_auth(self) -> dict[str, Any]:
        """Run a connectivity/auth test and return a small result dict."""
        raise NotImplementedError

    @abstractmethod
    def ensure_valid_access_token(self) -> str:
        """Return a valid access token, refreshing it if necessary."""
        raise NotImplementedError

    @abstractmethod
    def request(self, method: str, path: str, **kwargs) -> Any:
        """Perform an authenticated HTTP request to the provider."""
        raise NotImplementedError
