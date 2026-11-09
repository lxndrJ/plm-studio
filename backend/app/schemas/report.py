import uuid
from datetime import datetime

from pydantic import BaseModel


class ReportCreate(BaseModel):
    reason: str | None = None


class ReportResponse(BaseModel):
    report_id: str
    template: str
    created_by: uuid.UUID
    created_at: datetime


class ReportDetail(ReportResponse):
    content_snapshot: dict
    pdf_available: bool
