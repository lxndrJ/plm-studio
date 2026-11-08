from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import NumberRange


def next_number(session: Session, prefix: str) -> str:
    """Vergibt die naechste Nummer aus dem Nummernkreis.

    Verwendet SELECT ... FOR UPDATE, damit parallele Requests keine
    Nummer doppelt ziehen koennen. Der Aufrufer committet.
    """
    row = session.execute(
        select(NumberRange).where(NumberRange.prefix == prefix).with_for_update()
    ).scalar_one()
    number = f"{prefix}{row.next_value:0{row.padding}d}"
    row.next_value += 1
    return number
