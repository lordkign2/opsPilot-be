"""
OpsPilot — RBAC Permission System (Phase 8).

Defines granular action-scoped permissions and maps each UserRole
to the set of permissions it holds. Permission checks are performed
at the API layer (no DB hit per request).
"""

from __future__ import annotations

import enum


class Permission(str, enum.Enum):
    """
    Granular action-scoped permissions for OpsPilot resources.

    Convention: "<resource>.<action>"
    """

    # ── Orders ───────────────────────────────────────────────
    ORDERS_READ = "orders.read"
    ORDERS_WRITE = "orders.write"
    ORDERS_DELETE = "orders.delete"

    # ── Payments ─────────────────────────────────────────────
    PAYMENTS_READ = "payments.read"
    PAYMENTS_INITIALIZE = "payments.initialize"
    PAYMENTS_VERIFY = "payments.verify"

    # ── Customers ────────────────────────────────────────────
    CUSTOMERS_READ = "customers.read"
    CUSTOMERS_WRITE = "customers.write"

    # ── Analytics ────────────────────────────────────────────
    ANALYTICS_READ = "analytics.read"

    # ── Notifications ────────────────────────────────────────
    NOTIFICATIONS_READ = "notifications.read"
    NOTIFICATIONS_SEND = "notifications.send"

    # ── Workflows ────────────────────────────────────────────
    WORKFLOWS_READ = "workflows.read"
    WORKFLOWS_WRITE = "workflows.write"
    WORKFLOWS_EXECUTE = "workflows.execute"

    # ── AI ───────────────────────────────────────────────────
    AI_QUERY = "ai.query"

    # ── Audit ────────────────────────────────────────────────
    AUDIT_READ = "audit.read"

    # ── API Keys ─────────────────────────────────────────────
    API_KEYS_MANAGE = "api_keys.manage"

    # ── Admin ────────────────────────────────────────────────
    ADMIN_MANAGE = "admin.manage"


# ── Role → Permissions Matrix ─────────────────────────────────

_ALL_PERMISSIONS: frozenset[Permission] = frozenset(Permission)

_OWNER_PERMISSIONS: frozenset[Permission] = _ALL_PERMISSIONS - {Permission.ADMIN_MANAGE}

_MANAGER_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.ORDERS_READ,
        Permission.ORDERS_WRITE,
        Permission.PAYMENTS_READ,
        Permission.PAYMENTS_INITIALIZE,
        Permission.CUSTOMERS_READ,
        Permission.CUSTOMERS_WRITE,
        Permission.ANALYTICS_READ,
        Permission.NOTIFICATIONS_READ,
        Permission.NOTIFICATIONS_SEND,
        Permission.WORKFLOWS_READ,
        Permission.WORKFLOWS_WRITE,
        Permission.WORKFLOWS_EXECUTE,
        Permission.AI_QUERY,
        Permission.API_KEYS_MANAGE,
    }
)

_CASHIER_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.ORDERS_READ,
        Permission.ORDERS_WRITE,
        Permission.PAYMENTS_INITIALIZE,
        Permission.PAYMENTS_VERIFY,
        Permission.PAYMENTS_READ,
        Permission.CUSTOMERS_READ,
    }
)

_SALES_REP_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.ORDERS_READ,
        Permission.ORDERS_WRITE,
        Permission.CUSTOMERS_READ,
        Permission.CUSTOMERS_WRITE,
    }
)


# Imported lazily to avoid circular imports at module load time.
# Used via `get_role_permissions()` below.
def get_role_permissions(role: str) -> frozenset[Permission]:
    """
    Return the set of permissions granted to a given role.

    Args:
        role: The ``UserRole.value`` string (e.g. ``"owner"``).

    Returns:
        Frozenset of :class:`Permission` values granted to the role.
    """
    mapping: dict[str, frozenset[Permission]] = {
        "super_admin": _ALL_PERMISSIONS,
        "owner": _OWNER_PERMISSIONS,
        "manager": _MANAGER_PERMISSIONS,
        "cashier": _CASHIER_PERMISSIONS,
        "sales_rep": _SALES_REP_PERMISSIONS,
    }
    return mapping.get(role, frozenset())
