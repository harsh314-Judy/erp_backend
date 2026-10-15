from fastapi import HTTPException, status

MANAGE_ADMINS = "manage_admins"
MANAGE_STAFF_USERS = "manage_staff_users"
VIEW_FINANCIALS = "view_financials"
APPROVE_JOBS = "approve_jobs"
EDIT_INVENTORY = "edit_inventory"
VIEW_INVENTORY = "view_inventory"
VIEW_ASSIGNED_WORK = "view_assigned_work"
MANAGE_SALES = "manage_sales"
MANAGE_PURCHASING = "manage_purchasing"
VIEW_SUPPLIERS = "view_suppliers"
MANAGE_COMPANY = "manage_company"
VIEW_REPORTS = "view_reports"

_ALL = frozenset(
    {
        MANAGE_ADMINS,
        MANAGE_STAFF_USERS,
        VIEW_FINANCIALS,
        APPROVE_JOBS,
        EDIT_INVENTORY,
        VIEW_INVENTORY,
        VIEW_ASSIGNED_WORK,
        MANAGE_SALES,
        MANAGE_PURCHASING,
        VIEW_SUPPLIERS,
        MANAGE_COMPANY,
        VIEW_REPORTS,
    }
)

ROLE_CAPABILITIES: dict[str, frozenset[str]] = {
    "super_admin": _ALL,
    "admin": _ALL - {MANAGE_ADMINS},
    "accountant": frozenset(
        {
            APPROVE_JOBS,
            EDIT_INVENTORY,
            VIEW_INVENTORY,
            VIEW_ASSIGNED_WORK,
            MANAGE_SALES,
            MANAGE_PURCHASING,
            VIEW_SUPPLIERS,
            VIEW_REPORTS,
        }
    ),
    "staff": frozenset({VIEW_ASSIGNED_WORK, VIEW_INVENTORY}),
}

_PRIVILEGED_ROLES = frozenset({"super_admin", "admin"})


def role_has(role_name: str | None, capability: str) -> bool:
    if role_name is None:
        return False
    return capability in ROLE_CAPABILITIES.get(role_name, frozenset())


def can_see_prices(role_name: str | None) -> bool:
    return role_has(role_name, EDIT_INVENTORY) or role_has(role_name, VIEW_FINANCIALS)


def can_manage_role(actor_role: str | None, target_role: str) -> bool:
    if actor_role == "super_admin":
        return True
    if actor_role == "admin":
        return target_role not in _PRIVILEGED_ROLES
    return False


def forbid(detail: str = "You do not have access to this action") -> None:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
