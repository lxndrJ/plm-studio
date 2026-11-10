"""M11: CSV/JSON export of parts and BOMs (authenticated, internal use)."""

import csv
import io
import json
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import func, select

from app.core.deps import CurrentUser, DbSession
from app.models.bom import BomItem
from app.models.numbering import PartClass
from app.models.part import Part, PartRevision
from app.services.bom_service import get_part_by_number, latest_revision

router = APIRouter(prefix="/export", tags=["export"])


def _part_export_rows(db: DbSession) -> list[dict]:
    latest = (
        select(PartRevision.part_id.label("pid"), func.max(PartRevision.revision).label("rev"))
        .group_by(PartRevision.part_id)
        .subquery()
    )
    pr = (
        select(
            PartRevision.part_id,
            PartRevision.revision,
            PartRevision.status,
            PartRevision.attributes,
        )
        .join(
            latest, (PartRevision.part_id == latest.c.pid) & (PartRevision.revision == latest.c.rev)
        )
        .subquery()
    )
    classes = dict(db.execute(select(PartClass.id, PartClass.code)).all())
    rows = []
    for part, rev_label, status, attrs in db.execute(
        select(Part, pr.c.revision, pr.c.status, pr.c.attributes)
        .join(pr, pr.c.part_id == Part.id)
        .order_by(Part.part_number)
    ):
        rows.append(
            {
                "part_number": part.part_number,
                "name": part.name,
                "part_type": part.part_type,
                "class_code": classes.get(part.class_id, ""),
                "description": part.description or "",
                "revision": rev_label,
                "status": status,
                "attributes": attrs or {},
                "created_at": part.created_at.isoformat(),
            }
        )
    return rows


@router.get("/parts")
def export_parts(
    db: DbSession,
    user: CurrentUser,
    format: Annotated[str, Query(pattern="^(csv|json)$")] = "csv",
):
    rows = _part_export_rows(db)
    if format == "json":
        return JSONResponse(rows)
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=[
            "part_number",
            "name",
            "part_type",
            "class_code",
            "description",
            "revision",
            "status",
            "attributes",
            "created_at",
        ],
    )
    writer.writeheader()
    for row in rows:
        row = dict(row)
        row["attributes"] = json.dumps(row["attributes"], ensure_ascii=False)
        writer.writerow(row)
    return PlainTextResponse(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="parts.csv"'},
    )


@router.get("/bom/{part_number}")
def export_bom(
    db: DbSession,
    user: CurrentUser,
    part_number: str,
    rev: Annotated[str | None, Query()] = None,
    format: Annotated[str, Query(pattern="^(csv|json)$")] = "csv",
):
    from app.api.bom import db_get_rev

    part = get_part_by_number(db, part_number)
    target = db_get_rev(db, part.id, rev) if rev is not None else latest_revision(db, part.id)
    if target is None:
        rows = []
    else:
        rows = [
            {
                "position": item.position,
                "component_part_number": item.component_rev.part.part_number,
                "component_name": item.component_rev.part.name,
                "component_revision": item.component_rev.revision,
                "quantity": float(item.quantity),
                "unit": item.unit,
            }
            for item in db.execute(
                select(BomItem).where(BomItem.parent_rev_id == target.id).order_by(BomItem.position)
            ).scalars()
        ]
    if format == "json":
        return JSONResponse(
            {
                "part_number": part_number,
                "revision": target.revision if target else None,
                "items": rows,
            }
        )
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=[
            "position",
            "component_part_number",
            "component_name",
            "component_revision",
            "quantity",
            "unit",
        ],
    )
    writer.writeheader()
    for row in rows:
        row = dict(row)
        row["quantity"] = f"{row['quantity']:g}"
        writer.writerow(row)
    return PlainTextResponse(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="bom_{part_number}.csv"'},
    )
