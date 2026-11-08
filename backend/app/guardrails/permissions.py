"""Role enforcement for write operations. Read endpoints only need a valid
login (any role); every mutating action requires at least 'editor', releases
and admin functions are checked via require_roles / workflow required_role."""

from app.core.deps import require_roles

require_editor = require_roles("editor", "approver", "admin")
require_approver = require_roles("approver", "admin")
require_admin = require_roles("admin")
