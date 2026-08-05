"""
Module: Enterprise Features — Role-Based Access Control.

Three roles as specified: Admin, Accountant, Auditor. Permissions are
modeled as (resource, action) pairs rather than a giant flat list, so
adding a new resource later just means adding one row per role instead of
touching a monolithic enum.
"""
from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    ACCOUNTANT = "accountant"
    AUDITOR = "auditor"


class Action(str, Enum):
    VIEW = "view"
    CREATE = "create"
    EDIT = "edit"
    DELETE = "delete"
    APPROVE = "approve"
    MANAGE_USERS = "manage_users"
    MANAGE_SETTINGS = "manage_settings"


# resource -> role -> set of allowed actions
PERMISSION_MATRIX: dict[str, dict[Role, set[Action]]] = {
    "journal_entry": {
        Role.ADMIN: {Action.VIEW, Action.CREATE, Action.EDIT, Action.DELETE, Action.APPROVE},
        Role.ACCOUNTANT: {Action.VIEW, Action.CREATE, Action.EDIT},
        Role.AUDITOR: {Action.VIEW},
    },
    "reports": {
        Role.ADMIN: {Action.VIEW, Action.CREATE},
        Role.ACCOUNTANT: {Action.VIEW, Action.CREATE},
        Role.AUDITOR: {Action.VIEW},
    },
    "invoice_ocr": {
        Role.ADMIN: {Action.VIEW, Action.CREATE, Action.EDIT, Action.DELETE},
        Role.ACCOUNTANT: {Action.VIEW, Action.CREATE, Action.EDIT},
        Role.AUDITOR: {Action.VIEW},
    },
    "audit_log": {
        Role.ADMIN: {Action.VIEW},
        Role.ACCOUNTANT: set(),  # accountants cannot view or tamper with the audit trail
        Role.AUDITOR: {Action.VIEW},
    },
    "users": {
        Role.ADMIN: {Action.VIEW, Action.CREATE, Action.EDIT, Action.DELETE, Action.MANAGE_USERS},
        Role.ACCOUNTANT: set(),
        Role.AUDITOR: {Action.VIEW},
    },
    "org_settings": {
        Role.ADMIN: {Action.VIEW, Action.EDIT, Action.MANAGE_SETTINGS},
        Role.ACCOUNTANT: {Action.VIEW},
        Role.AUDITOR: {Action.VIEW},
    },
    "api_keys": {
        Role.ADMIN: {Action.VIEW, Action.CREATE, Action.DELETE},
        Role.ACCOUNTANT: set(),
        Role.AUDITOR: set(),
    },
}


def has_permission(role: str | Role, resource: str, action: str | Action) -> bool:
    """Check whether a role may perform an action on a resource.
    Unknown resource/role combinations default to NO access (fail closed),
    not fail open — a typo in a resource name should never silently grant
    access.
    """
    try:
        role_enum = Role(role) if not isinstance(role, Role) else role
        action_enum = Action(action) if not isinstance(action, Action) else action
    except ValueError:
        return False
    resource_perms = PERMISSION_MATRIX.get(resource)
    if not resource_perms:
        return False
    return action_enum in resource_perms.get(role_enum, set())


def list_permissions(role: str | Role) -> dict[str, list[str]]:
    """All permissions a role has, grouped by resource — used to render
    a settings page showing 'what can this role do'."""
    try:
        role_enum = Role(role) if not isinstance(role, Role) else role
    except ValueError:
        return {}
    return {
        resource: sorted(a.value for a in perms.get(role_enum, set()))
        for resource, perms in PERMISSION_MATRIX.items()
    }
