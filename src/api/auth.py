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
rotation/expiry, and no per-user identity, just a role.

Roles, from least to most privileged: analyst < store_manager < finance < admin.
"""

from __future__ import annotations

import os

from fastapi import Depends, Header, HTTPException, status

ROLE_HIERARCHY = ["analyst", "store_manager", "finance", "admin"]


def _load_api_keys() -> dict[str, str]:
    """API keys come from RETAILOS_API_KEYS ('key1:role1,key2:role2'),
    falling back to fixed demo keys for local development/evaluation."""
    raw = os.getenv("RETAILOS_API_KEYS")
    if raw:
        keys: dict[str, str] = {}
        for pair in raw.split(","):
            key, _, role = pair.partition(":")
            key, role = key.strip(), role.strip()
            if key and role in ROLE_HIERARCHY:
                keys[key] = role
        if keys:
            return keys

    return {
        "demo-analyst-key": "analyst",
        "demo-store-manager-key": "store_manager",
        "demo-finance-key": "finance",
        "demo-admin-key": "admin",
    }


API_KEYS = _load_api_keys()


def get_role(x_api_key: str | None = Header(default=None)) -> str:
    """FastAPI dependency: resolve the caller's role from X-API-Key, or 401."""
    if not x_api_key or x_api_key not in API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-API-Key header",
        )
    return API_KEYS[x_api_key]


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
