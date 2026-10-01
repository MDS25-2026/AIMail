"""Grant, revoke and list admin-console access (docs/adr/0004).

Admin is app_metadata.role == "admin", which only the service key can write. This script is the one
place that holds that key for the purpose; the running backend never needs it.

Usage (from backend/, with SUPABASE_URL and SUPABASE_SERVICE_KEY in the repo-root .env):
    python scripts/admin_accounts.py add ops@example.com      # creates, or promotes an existing user
    python scripts/admin_accounts.py remove ops@example.com
    python scripts/admin_accounts.py list
"""

import argparse
import getpass
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.admin.auth import ADMIN_ROLE
from app.core.config import get_settings

MIN_PASSWORD_LENGTH = 12
PAGE_SIZE = 100
TIMEOUT_SECONDS = 20.0


def client() -> httpx.Client:
    settings = get_settings()
    if not (settings.supabase_url and settings.supabase_service_key):
        sys.exit("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in the repo-root .env")
    key = settings.supabase_service_key
    return httpx.Client(base_url=settings.supabase_url.rstrip("/") + "/auth/v1/admin",
                        headers={"apikey": key, "Authorization": f"Bearer {key}"},
                        timeout=TIMEOUT_SECONDS)


def all_users(api: httpx.Client) -> list[dict]:
    users, page = [], 1
    while True:
        response = api.get("/users", params={"page": page, "per_page": PAGE_SIZE})
        response.raise_for_status()
        batch = response.json().get("users", [])
        users += batch
        if len(batch) < PAGE_SIZE:
            return users
        page += 1


def find(api: httpx.Client, email: str) -> dict | None:
    return next((u for u in all_users(api) if (u.get("email") or "").lower() == email.lower()), None)


def is_admin(user: dict) -> bool:
    return (user.get("app_metadata") or {}).get("role") == ADMIN_ROLE


def new_password() -> str:
    # getpass needs a terminal to hide what is typed; without one it would echo the password or
    # crash. Refuse plainly instead.
    if not sys.stdin.isatty():
        sys.exit("A new admin's password is typed at a terminal, hidden. Run this in your own "
                 "terminal, not through a non-interactive shell.")
    password = getpass.getpass("Password for the new admin (min 12 characters): ")
    if len(password) < MIN_PASSWORD_LENGTH:
        sys.exit(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if getpass.getpass("Repeat it: ") != password:
        sys.exit("Passwords did not match.")
    return password


def set_role(api: httpx.Client, user_id: str, role: str | None) -> dict:
    response = api.put(f"/users/{user_id}", json={"app_metadata": {"role": role}})
    response.raise_for_status()
    return response.json()


def add(api: httpx.Client, email: str) -> None:
    user = find(api, email)
    if user is None:
        response = api.post("/users", json={"email": email, "password": new_password(),
                                             "email_confirm": True,
                                             "app_metadata": {"role": ADMIN_ROLE}})
        response.raise_for_status()
        print(f"created {email} as admin")
        return
    updated = set_role(api, user["id"], ADMIN_ROLE)
    print(f"{email} is {'now an admin' if is_admin(updated) else 'NOT an admin: check the project'}")


def remove(api: httpx.Client, email: str) -> None:
    user = find(api, email)
    if user is None:
        sys.exit(f"no user {email}")
    updated = set_role(api, user["id"], None)
    if is_admin(updated):
        sys.exit(f"{email} still has the admin role: revoke it in the Supabase dashboard")
    print(f"{email} is no longer an admin (sessions end within the hour, when their token expires)")


def show(api: httpx.Client) -> None:
    admins = [u.get("email") for u in all_users(api) if is_admin(u)]
    print("\n".join(admins) if admins else "no admins")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("add", "remove"):
        sub.add_parser(name).add_argument("email")
    sub.add_parser("list")
    args = parser.parse_args()
    with client() as api:
        try:
            {"add": lambda: add(api, args.email), "remove": lambda: remove(api, args.email),
             "list": lambda: show(api)}[args.command]()
        except httpx.HTTPStatusError as exc:
            sys.exit(f"Supabase refused: {exc.response.status_code} {exc.response.text[:200]}")


if __name__ == "__main__":
    main()
