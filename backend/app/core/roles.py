"""Who is an admin: app_metadata.role, which only the service key can write (docs/adr/0004).

One definition for the dashboard session and the admin console, which both carry Supabase tokens.
"""

ADMIN_ROLE = "admin"


def is_admin_claims(claims: dict) -> bool:
    return (claims.get("app_metadata") or {}).get("role") == ADMIN_ROLE
