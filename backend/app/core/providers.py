"""Which model answers: Google's Gemini, or the company's own model (Private mode, local-model.md).

One type for the backend and the agent, so a request can never carry a provider the other side reads differently.
"""

from enum import StrEnum


class Provider(StrEnum):
    GEMINI = "gemini"
    LOCAL = "local"
