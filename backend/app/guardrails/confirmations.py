import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from typing import Any


@dataclass
class ProposedOperation:
    summary: str
    payload: dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def id(self) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"plm/{self.summary}"))

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.created_at + timedelta(minutes=10)


class ConfirmationStore:
    """In-Memory-Store fuer Proposed-Writes (Phase M7: persistente Variante).

    Flow: propose() -> 202 + confirmation_id an den Client ->
    User bestaetigt im Frontend -> confirm() fuehrt die Operation aus.
    """

    def __init__(self) -> None:
        self._store: dict[str, ProposedOperation] = {}

    def propose(self, summary: str, payload: dict[str, Any]) -> str:
        op = ProposedOperation(summary=summary, payload=payload)
        self._store[op.id] = op
        return op.id

    def confirm(self, confirmation_id: str) -> dict[str, Any]:
        op = self._store.get(confirmation_id)
        if op is None or op.is_expired:
            raise KeyError("Confirmation unbekannt oder abgelaufen")
        del self._store[confirmation_id]
        return op.payload


store = ConfirmationStore()
