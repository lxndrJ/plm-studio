from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, JSONResponse

from app.core.deps import CurrentUser, DbSession
from app.core.errors import NotFoundError
from app.guardrails import confirmations as conf_guard
from app.guardrails.permissions import require_editor
from app.models.report import ReportExport
from app.models.user import User
from app.schemas.confirmation import ConfirmationProposed
from app.schemas.report import ReportCreate, ReportDetail, ReportResponse
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["reports"])


def _response(row: ReportExport) -> ReportResponse:
    return ReportResponse(
        report_id=row.report_id,
        template=row.template,
        created_by=row.created_by,
        created_at=row.created_at,
    )


def _detail(row: ReportExport) -> ReportDetail:
    return ReportDetail(
        **_response(row).model_dump(),
        content_snapshot=row.content_snapshot,
        pdf_available=report_service.pdf_path(row.report_id).exists(),
    )


@router.post("/parts/{part_number}", status_code=201, response_model=ReportDetail)
def create_part_report(
    part_number: str,
    body: ReportCreate,
    db: DbSession,
    user: Annotated[User, Depends(require_editor)],
    direct: Annotated[bool, Query()] = False,
):
    if not direct:
        return _propose_report(
            db,
            user,
            action_payload={
                "template": report_service.TEMPLATE_PART_SHEET,
                "part_number": part_number,
                "reason": body.reason,
            },
            summary=f"create PDF report (part_sheet_v1) for part '{part_number}' (released content only)",
        )
    return _detail(
        report_service.create_report(db, user=user, part_number=part_number, reason=body.reason)
    )


def _propose_report(db, user, *, action_payload: dict, summary: str):
    conf = conf_guard.propose(
        db, user=user, action="create_report", payload=action_payload, summary=summary
    )
    return JSONResponse(
        status_code=202,
        content=ConfirmationProposed(confirmation_id=conf.id, summary=conf.summary).model_dump(
            mode="json"
        ),
    )


@router.post("/parts/{part_number}/bom", status_code=201, response_model=ReportDetail)
def create_bom_report(
    part_number: str,
    body: ReportCreate,
    db: DbSession,
    user: Annotated[User, Depends(require_editor)],
    direct: Annotated[bool, Query()] = False,
):
    if not direct:
        return _propose_report(
            db,
            user,
            action_payload={
                "template": report_service.TEMPLATE_BOM_EXPLOSION,
                "part_number": part_number,
                "reason": body.reason,
            },
            summary=f"create BOM explosion report for '{part_number}' (released content only)",
        )
    return _detail(
        report_service.create_bom_report(db, user=user, part_number=part_number, reason=body.reason)
    )


@router.post("/parts/{part_number}/bom-diff", status_code=201, response_model=ReportDetail)
def create_bom_diff_report(
    part_number: str,
    rev_a: Annotated[str, Query()],
    rev_b: Annotated[str, Query()],
    body: ReportCreate,
    db: DbSession,
    user: Annotated[User, Depends(require_editor)],
    direct: Annotated[bool, Query()] = False,
):
    """M14: BOM comparison report (bom_diff_v1) between two revisions.
    Both revisions must be released — reports contain released content only."""
    if not direct:
        return _propose_report(
            db,
            user,
            action_payload={
                "template": report_service.TEMPLATE_BOM_DIFF,
                "part_number": part_number,
                "rev_a": rev_a,
                "rev_b": rev_b,
                "reason": body.reason,
            },
            summary=(
                f"create BOM diff report (bom_diff_v1) for '{part_number}' "
                f"rev {rev_a} vs {rev_b} (released content only)"
            ),
        )
    return _detail(
        report_service.create_bom_diff_report(
            db, user=user, part_number=part_number, rev_a=rev_a, rev_b=rev_b, reason=body.reason
        )
    )


@router.post("/ecrs/{ecr_number}", status_code=201, response_model=ReportDetail)
def create_ecr_report(
    ecr_number: str,
    body: ReportCreate,
    db: DbSession,
    user: Annotated[User, Depends(require_editor)],
    direct: Annotated[bool, Query()] = False,
):
    if not direct:
        return _propose_report(
            db,
            user,
            action_payload={
                "template": report_service.TEMPLATE_ECR,
                "ecr_number": ecr_number,
                "reason": body.reason,
            },
            summary=f"create ECR/ECO report for '{ecr_number}'",
        )
    return _detail(
        report_service.create_ecr_report(db, user=user, ecr_number=ecr_number, reason=body.reason)
    )


@router.get("", response_model=list[ReportResponse])
def list_reports(db: DbSession, user: CurrentUser):
    return [_response(r) for r in report_service.list_reports(db)]


@router.get("/{report_id}", response_model=ReportDetail)
def get_report(report_id: str, db: DbSession, user: CurrentUser):
    return _detail(report_service.get_report(db, report_id))


@router.get("/{report_id}/download")
def download_report(report_id: str, db: DbSession, user: CurrentUser):
    report_service.get_report(db, report_id)
    path = report_service.pdf_path(report_id)
    if not path.exists():
        raise NotFoundError(
            f"PDF file for report '{report_id}' not found on the server",
            code="report_file_missing",
        )
    return FileResponse(path, media_type="application/pdf", filename=f"{report_id}.pdf")
