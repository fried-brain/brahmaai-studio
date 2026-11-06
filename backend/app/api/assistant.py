from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import current_user
from app.models import User
from app.schemas.assistant_status import AssistantStatusOutput

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.get("/status", response_model=AssistantStatusOutput)
def assistant_status(request: Request, _user: Annotated[User, Depends(current_user)]):
    result = request.app.state.local_llm_client.status()
    return AssistantStatusOutput(
        enabled=result.enabled,
        configured=result.configured,
        reachable=result.reachable,
        model_available=result.model_available,
        code=result.code,
    )
