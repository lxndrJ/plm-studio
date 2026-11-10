"""Report engine (M6): versioned, external-safe PDF reports via Typst.

A report is a frozen snapshot (report_exports.content_snapshot) rendered to
PDF. The filter only allows released content (api-contract rule 12): the
snapshot is built from the latest released revision and internal attributes
(costs, suppliers) are stripped.
"""

import subprocess
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ApiError, ConflictError, NotFoundError
from app.models.part import PartRevision
from app.models.report import ReportExport
from app.models.user import User
from app.services import audit as audit_service
from app.services.bom_service import get_bom, get_part_by_number
from app.services.numbering import allocate_number

TEMPLATE_PART_SHEET = "part_sheet_v1"
TEMPLATE_BOM_EXPLOSION = "bom_explosion_v1"
TEMPLATE_ECR = "ecr_v1"

INTERNAL_ATTRIBUTE_KEYS = {
    "preis",
    "price",
    "cost",
    "kosten",
    "einkaufspreis",
    "supplier",
    "lieferant",
}


def reports_dir() -> Path:
    path = Path(get_settings().STORAGE_DIR) / "reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def pdf_path(report_id: str) -> Path:
    return reports_dir() / f"{report_id}.pdf"


def _released_revision(db: Session, part) -> PartRevision:
    rev = db.execute(
        select(PartRevision)
        .where(PartRevision.part_id == part.id, PartRevision.status == "released")
        .order_by(PartRevision.revision.desc())
        .limit(1)
    ).scalar_one_or_none()
    if rev is None:
        raise ConflictError(
            f"part '{part.part_number}' has no released revision; reports only contain released content",
            code="no_released_revision",
        )
    return rev


def build_part_snapshot(db: Session, *, report_id: str, part_number: str) -> dict:
    part = get_part_by_number(db, part_number)
    rev = _released_revision(db, part)
    bom = []
    for item in get_bom(db, rev.id):
        comp = db.get(PartRevision, item.component_rev_id)
        bom.append(
            {
                "position": item.position,
                "component_part_number": comp.part.part_number,
                "component_name": comp.part.name,
                "quantity": float(item.quantity),
                "unit": item.unit,
            }
        )
    attributes = {
        k: v for k, v in (rev.attributes or {}).items() if k not in INTERNAL_ATTRIBUTE_KEYS
    }
    return {
        "report_id": report_id,
        "template": TEMPLATE_PART_SHEET,
        "part": {
            "part_number": part.part_number,
            "name": part.name,
            "description": part.description,
            "part_type": part.part_type,
        },
        "revision": {
            "revision": rev.revision,
            "status": rev.status,
            "change_reason": rev.change_reason,
            "attributes": attributes,
        },
        "bom": bom,
    }


def build_bom_snapshot(db: Session, *, report_id: str, part_number: str) -> dict:
    """Recursive BOM explosion of the latest released revision (multi-level,
    cycle-safe)."""
    part = get_part_by_number(db, part_number)
    rev = _released_revision(db, part)
    lines: list[dict] = []
    seen: set = set()

    def walk(parent_rev_id, level: int, prefix: str) -> None:
        for item in get_bom(db, parent_rev_id):
            key = (parent_rev_id, item.component_rev_id, item.position)
            if key in seen:
                continue
            seen.add(key)
            comp = db.get(PartRevision, item.component_rev_id)
            pos = f"{prefix}{item.position}" if prefix else str(item.position)
            lines.append(
                {
                    "level": level,
                    "position": pos,
                    "component_part_number": comp.part.part_number,
                    "component_name": comp.part.name,
                    "quantity": float(item.quantity),
                    "unit": item.unit,
                }
            )
            walk(item.component_rev_id, level + 1, f"{pos}.")

    walk(rev.id, 1, "")
    return {
        "report_id": report_id,
        "template": TEMPLATE_BOM_EXPLOSION,
        "part": {"part_number": part.part_number, "name": part.name, "part_type": part.part_type},
        "revision": {"revision": rev.revision, "status": rev.status},
        "lines": lines,
    }


def build_ecr_snapshot(db: Session, *, report_id: str, ecr_number: str) -> dict:
    from app.models.change import Ecr

    ecr = db.execute(select(Ecr).where(Ecr.number == ecr_number)).scalar_one_or_none()
    if ecr is None:
        raise NotFoundError(f"ECR '{ecr_number}' not found", code="ecr_not_found")
    ecos = [
        {
            "number": eco.number,
            "status": eco.status,
            "created_at": eco.created_at.isoformat(),
            "affected": [
                {
                    "part_number": r.part.part_number,
                    "revision": r.revision,
                    "status": r.status,
                }
                for r in eco.affected_revisions
            ],
        }
        for eco in ecr.ecos
    ]
    return {
        "report_id": report_id,
        "template": TEMPLATE_ECR,
        "ecr": {
            "number": ecr.number,
            "description": ecr.description,
            "status": ecr.status,
            "created_at": ecr.created_at.isoformat(),
        },
        "ecos": ecos,
    }


def _esc(value) -> str:
    return (
        str(value).replace("\\", "\\\\").replace('"', '\\"').replace("[", "\\[").replace("]", "\\]")
    )


def _typst_bom(snapshot: dict) -> str:
    part = snapshot["part"]
    rows = (
        "\n".join(
            "[{}{}], [{}], [{}], [{} {}],".format(
                "\u00a0" * line["level"],
                _esc(line["position"]),
                _esc(line["component_part_number"]),
                _esc(line["component_name"]),
                line["quantity"],
                line["unit"],
            )
            for line in snapshot["lines"]
        )
        or "[\u2014], [\u2014], [\u2014], [\u2014],"
    )
    return f"""#set page(paper: "a4", margin: 2cm)
#set text(font: "DejaVu Sans", size: 11pt)

#text(size: 18pt, weight: "bold")[St\u00fcckliste {_esc(part['part_number'])} \u2014 {_esc(part['name'])}]

Report {_esc(snapshot['report_id'])} (template {_esc(snapshot['template'])}), revision {snapshot['revision']['revision']} ({snapshot['revision']['status']}), mehrstufig

#table(
  columns: 4,
  table.header([Pos], [Sachnummer], [Bezeichnung], [Menge]),
{rows}
)
"""


def _typst_ecr(snapshot: dict) -> str:
    ecr = snapshot["ecr"]
    eco_lines = []
    for eco in snapshot["ecos"]:
        affected = (
            ", ".join(
                f"{a['part_number']} rev {a['revision']} ({a['status']})" for a in eco["affected"]
            )
            or "\u2014"
        )
        eco_lines.append(
            f"== ECO {_esc(eco['number'])} ({eco['status']})\nBetroffen: {_esc(affected)}"
        )
    ecos_block = "\n\n".join(eco_lines) or "keine ECOs"
    return f"""#set page(paper: "a4", margin: 2cm)
#set text(font: "DejaVu Sans", size: 11pt)

#text(size: 18pt, weight: "bold")[\u00c4nderungsantrag {_esc(ecr['number'])}]

Report {_esc(snapshot['report_id'])} (template {_esc(snapshot['template'])}), Status: {ecr['status']}

#text(size: 12pt)[{_esc(ecr['description'])}]

{ecos_block}
"""


def _typst_document(snapshot: dict) -> str:
    if snapshot["template"] == TEMPLATE_BOM_EXPLOSION:
        return _typst_bom(snapshot)
    if snapshot["template"] == TEMPLATE_ECR:
        return _typst_ecr(snapshot)
    return _typst_part_sheet(snapshot)


def _typst_part_sheet(snapshot: dict) -> str:
    part = snapshot["part"]
    rev = snapshot["revision"]
    attr_lines = ", ".join(f"{k}: {_esc(v)}" for k, v in rev["attributes"].items()) or "—"
    bom_rows = (
        "\n".join(
            f"[{_esc(b['position'])}], [{_esc(b['component_part_number'])}], "
            f"[{_esc(b['component_name'])}], [{b['quantity']} {b['unit']}],"
            for b in snapshot["bom"]
        )
        or "[—], [—], [—], [—],"
    )
    return f"""#set page(paper: "a4", margin: 2cm)
#set text(font: "DejaVu Sans", size: 11pt)

#text(size: 18pt, weight: "bold")[{_esc(part['part_number'])} — {_esc(part['name'])}]

Report {_esc(snapshot['report_id'])} (template {_esc(snapshot['template'])}), revision {rev['revision']} ({rev['status']})

#text(size: 12pt)[{_esc(part['description'] or "")}]

== Technische Daten
{attr_lines}

== Stückliste
#table(
  columns: 4,
  table.header([Pos], [Sachnummer], [Bezeichnung], [Menge]),
{bom_rows}
)
"""


def render_pdf(report_id: str, snapshot: dict) -> Path:
    out = pdf_path(report_id)
    typ = reports_dir() / f"{report_id}.typ"
    typ.write_text(_typst_document(snapshot), encoding="utf-8")
    binary = get_settings().TYPST_BINARY
    try:
        proc = subprocess.run(
            [binary, "compile", str(typ), str(out)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except FileNotFoundError:
        raise ApiError(
            f"typst binary '{binary}' not found on the server",
            status_code=503,
            code="renderer_unavailable",
        )
    except subprocess.TimeoutExpired:
        raise ApiError("typst compile timed out", status_code=502, code="render_failed")
    if proc.returncode != 0:
        raise ApiError(
            f"typst compile failed: {proc.stderr[-300:]}",
            status_code=502,
            code="render_failed",
        )
    return out


def _create(
    db: Session,
    *,
    user: User,
    template: str,
    snapshot: dict,
    reason: str | None,
    subject: dict,
) -> ReportExport:
    report_id = snapshot["report_id"]
    render_pdf(report_id, snapshot)
    row = ReportExport(
        report_id=report_id,
        template=template,
        content_snapshot=snapshot,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    audit_service.log_change(
        db,
        entity_type="report",
        entity_id=row.id,
        action="create",
        user_id=user.id,
        new_values={"report_id": report_id, "template": template, **subject},
        reason=reason,
    )
    db.commit()
    db.refresh(row)
    return row


def create_report(
    db: Session, *, user: User, part_number: str, reason: str | None = None
) -> ReportExport:
    report_id = allocate_number(db, "RPT")
    snapshot = build_part_snapshot(db, report_id=report_id, part_number=part_number)
    return _create(
        db,
        user=user,
        template=TEMPLATE_PART_SHEET,
        snapshot=snapshot,
        reason=reason,
        subject={"part_number": part_number},
    )


def create_bom_report(
    db: Session, *, user: User, part_number: str, reason: str | None = None
) -> ReportExport:
    report_id = allocate_number(db, "RPT")
    snapshot = build_bom_snapshot(db, report_id=report_id, part_number=part_number)
    return _create(
        db,
        user=user,
        template=TEMPLATE_BOM_EXPLOSION,
        snapshot=snapshot,
        reason=reason,
        subject={"part_number": part_number},
    )


def create_ecr_report(
    db: Session, *, user: User, ecr_number: str, reason: str | None = None
) -> ReportExport:
    report_id = allocate_number(db, "RPT")
    snapshot = build_ecr_snapshot(db, report_id=report_id, ecr_number=ecr_number)
    return _create(
        db,
        user=user,
        template=TEMPLATE_ECR,
        snapshot=snapshot,
        reason=reason,
        subject={"ecr_number": ecr_number},
    )


def create_report_for(db: Session, *, user: User, template: str, payload) -> ReportExport:
    """Dispatch for the confirmation-token replay (action create_report)."""
    from app.core.errors import ValidationError

    if template == TEMPLATE_PART_SHEET:
        if not payload.part_number:
            raise ValidationError("part_number required for part_sheet_v1", code="invalid_payload")
        return create_report(db, user=user, part_number=payload.part_number, reason=payload.reason)
    if template == TEMPLATE_BOM_EXPLOSION:
        if not payload.part_number:
            raise ValidationError(
                "part_number required for bom_explosion_v1", code="invalid_payload"
            )
        return create_bom_report(
            db, user=user, part_number=payload.part_number, reason=payload.reason
        )
    if template == TEMPLATE_ECR:
        if not payload.ecr_number:
            raise ValidationError("ecr_number required for ecr_v1", code="invalid_payload")
        return create_ecr_report(
            db, user=user, ecr_number=payload.ecr_number, reason=payload.reason
        )
    raise ValidationError(f"unknown report template '{template}'", code="unknown_template")


def list_reports(db: Session) -> list[ReportExport]:
    return list(db.execute(select(ReportExport).order_by(ReportExport.report_id)).scalars())


def get_report(db: Session, report_id: str) -> ReportExport:
    row = db.execute(
        select(ReportExport).where(ReportExport.report_id == report_id)
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError(f"report '{report_id}' not found", code="report_not_found")
    return row
