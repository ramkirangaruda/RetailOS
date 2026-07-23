"""
Minimal role-based API authentication for RetailOS.

DEMO-SCOPE IMPLEMENTATION: API keys and roles are read from an environment
variable (or a small hardcoded default set for local development) rather
than a real user/secrets store, and requests are authenticated via a
static X-API-Key header rather than OAuth/JWT/sessions. This is
deliberately scoped to demonstrate role-based access control actually
being enforced at the application layer (the only layer this project
gates access at - see src/storage/access_control.py's module docstring
for why raw DuckDB file access isn't covered). It is not meant to be
production-grade credential management: keys are plaintext, there's no
rotation/expiry, and no per-user identity, just a role (and, for
store_manager keys, an assigned store_id).

Roles, from least to most privileged: analyst < store_manager < finance < admin.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status

ROLE_HIERARCHY = ["analyst", "store_manager", "finance", "admin"]


@dataclass(frozen=True)
class Identity:
    role: str
    store_id: str | None = None  # only meaningful for role == "store_manager"


def _load_api_keys() -> dict[str, Identity]:
    """API keys come from RETAILOS_API_KEYS, comma-separated entries of
    'key:role' or 'key:role:store_id' (store_id only meaningful for
    store_manager keys, e.g. 'sm-st007-key:store_manager:ST007'), falling
    back to fixed demo keys for local development/evaluation."""
    raw = os.getenv("RETAILOS_API_KEYS")
    if raw:
        keys: dict[str, Identity] = {}
        for entry in raw.split(","):
            parts = [p.strip() for p in entry.split(":")]
            if len(parts) < 2:
                continue
            key, role = parts[0], parts[1]
            store_id = parts[2] if len(parts) > 2 and parts[2] else None
            if key and role in ROLE_HIERARCHY:
                keys[key] = Identity(role=role, store_id=store_id)
        if keys:
            return keys

    return {
        "demo-analyst-key": Identity(role="analyst"),
        "demo-store-manager-key": Identity(role="store_manager", store_id="ST007"),
        "demo-finance-key": Identity(role="finance"),
        "demo-admin-key": Identity(role="admin"),
    }


API_KEYS = _load_api_keys()


def get_identity(x_api_key: str | None = Header(default=None)) -> Identity:
    """FastAPI dependency: resolve the caller's Identity from X-API-Key, or 401."""
    if not x_api_key or x_api_key not in API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-API-Key header",
        )
    return API_KEYS[x_api_key]


def get_role(identity: Identity = Depends(get_identity)) -> str:
    """FastAPI dependency: just the caller's role (most routes only need this)."""
    return identity.role


def require_role(minimum: str):
    """FastAPI dependency factory: 403 if the caller's role is below `minimum`."""

    def _check(role: str = Depends(get_role)) -> str:
        if ROLE_HIERARCHY.index(role) < ROLE_HIERARCHY.index(minimum):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' does not meet required minimum '{minimum}'",
            )
        return role

    return _check


def require_identity(minimum: str):
    """Like require_role, but returns the full Identity (role + store_id)
    for routes that need to scope results to the caller's assigned store."""

    def _check(identity: Identity = Depends(get_identity)) -> Identity:
        if ROLE_HIERARCHY.index(identity.role) < ROLE_HIERARCHY.index(minimum):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{identity.role}' does not meet required minimum '{minimum}'",
            )
        return identity

    return _check
