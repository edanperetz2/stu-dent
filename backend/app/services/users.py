from sqlalchemy import ColumnElement

from app.models.user import RoleEnum, User


def active_user_filters(*roles: RoleEnum) -> list[ColumnElement[bool]]:
    """WHERE-clause fragments for active, non-deleted users of the given
    role(s) -- the "role == X, is_active, deleted_at IS NULL" triplet
    repeated identically across several picker-list/lookup queries.
    """
    role_filter = User.role.in_(roles) if len(roles) > 1 else User.role == roles[0]
    return [role_filter, User.is_active.is_(True), User.deleted_at.is_(None)]
