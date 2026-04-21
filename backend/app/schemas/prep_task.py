from datetime import datetime

from pydantic import BaseModel


class PrepTaskResponse(BaseModel):
    id: int
    user_id: int
    type: str           # defrost | move | check_expiry
    description: str
    container_id: int | None
    scheduled_at: datetime
    status: str         # pending | done | skipped

    model_config = {"from_attributes": True}


class PrepTaskDone(BaseModel):
    task_id: int
