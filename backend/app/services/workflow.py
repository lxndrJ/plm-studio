from sqlalchemy import select

from app.core.deps import role_allows
from app.core.errors import ValidationError
from app.models.workflow import WorkflowTransition


def get_transition(db, entity_type: str, from_status: str, to_status: str) -> WorkflowTransition | None:
    return db.execute(
        select(WorkflowTransition).where(
            WorkflowTransition.entity_type == entity_type,
            WorkflowTransition.from_status == from_status,
            WorkflowTransition.to_status == to_status,
        )
    ).scalar_one_or_none()


def assert_transition_allowed(db, *, entity_type: str, from_status: str, to_status: str, user_role: str) -> WorkflowTransition:
    """A status jump is only allowed when a row in workflow_transitions permits
    it AND the caller's role is sufficient. Anything else is a 422."""
    if from_status == to_status:
        raise ValidationError(
            f"status is already '{from_status}'",
            code="invalid_transition",
        )
    transition = get_transition(db, entity_type, from_status, to_status)
    if transition is None:
        raise ValidationError(
            f"transition {entity_type}: '{from_status}' -> '{to_status}' is not in the workflow matrix",
            code="invalid_transition",
            details={"entity_type": entity_type, "from_status": from_status, "to_status": to_status},
        )
    if not role_allows(user_role, transition.required_role):
        raise ValidationError(
            f"transition '{from_status}' -> '{to_status}' requires role '{transition.required_role}', caller has '{user_role}'",
            code="insufficient_role_for_transition",
            status_code=403,
            details={"required_role": transition.required_role, "caller_role": user_role},
        )
    return transition
