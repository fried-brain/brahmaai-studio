from typing import Literal

from pydantic import BaseModel


class AssistantStatusOutput(BaseModel):
    enabled: bool
    configured: bool
    reachable: bool
    model_available: bool
    code: Literal["disabled", "model_not_configured", "model_unavailable", "ready"]
