"""Command line administration for users and API keys.

Run from the repository root::

    python -m backend.cli user create --email you@example.org --admin
    python -m backend.cli key create you@example.org --name bootstrap

This is how the first admin key is minted on a fresh deployment, where nobody
has a browser session yet.

Note this is a privilege boundary: anyone who can run it can mint an admin key.
That was already true of anyone with write access to the database file, but a
convenient command makes it worth stating.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Dict, List, Optional


def _init_repo():
    """Resolve the database exactly as the server does.

    Any divergence here and the CLI silently administers a *different* database
    than the running server, which is a memorably confusing failure.
    """
    from .persistence.factory import (
        default_sqlite_url,
        get_designs_repository,
        init_designs_repository_from_url,
    )
    from .settings import raw_settings

    url = (raw_settings.database or "").strip() or default_sqlite_url()
    init_designs_repository_from_url(url)
    repo = get_designs_repository()
    if not repo.is_enabled():
        print(
            f"No usable database (DATABASE={url!r}). Users and API keys are "
            "unavailable without persistence.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return repo


def _resolve_user(repo, ref: str) -> Dict[str, Any]:
    """Look up a user by email, `provider:identifier`, or numeric id."""
    ref = ref.strip()
    row: Optional[Dict[str, Any]] = None
    if ref.isdigit():
        row = repo.get_user_by_id(int(ref))
    elif "@" in ref and ":" not in ref:
        row = repo.get_user_by_email(ref)
    elif ":" in ref:
        provider, _, identifier = ref.partition(":")
        row = repo.get_user_by_identity(provider, identifier)
    else:
        for user in repo.list_users():
            for ident in repo.list_user_identities(int(user["id"])):
                if (ident.get("identifier") or "").lower() == ref.lower():
                    row = user
                    break
            if row:
                break
    if row is None:
        print(f"No such user: {ref!r}", file=sys.stderr)
        raise SystemExit(1)
    return row


def _print_table(rows: List[Dict[str, Any]], columns: List[str]) -> None:
    if not rows:
        print("(none)")
        return
    widths = {
        c: max(len(c), max(len(str(r.get(c) or "")) for r in rows)) for c in columns
    }
    print("  ".join(c.ljust(widths[c]) for c in columns))
    print("  ".join("-" * widths[c] for c in columns))
    for r in rows:
        print("  ".join(str(r.get(c) or "").ljust(widths[c]) for c in columns))


def cmd_user_list(args) -> int:
    repo = _init_repo()
    _print_table(
        repo.list_users(),
        ["id", "email", "display_name", "is_admin", "api_key_count", "last_login_at"],
    )
    return 0


def cmd_user_show(args) -> int:
    repo = _init_repo()
    user = _resolve_user(repo, args.user)
    for key in (
        "id",
        "email",
        "display_name",
        "is_admin",
        "is_active",
        "created_at",
        "last_login_at",
    ):
        print(f"{key:14} {user.get(key)}")
    print("\nidentities:")
    _print_table(
        repo.list_user_identities(int(user["id"])),
        ["provider", "identifier", "email", "last_login_at"],
    )
    print("\napi keys:")
    from .api_keys import decorate_key

    keys = [decorate_key(k) for k in repo.list_api_keys(int(user["id"]))]
    _print_table(keys, ["id", "name", "key_prefix", "status", "expires_at", "last_used_at"])
    return 0


def cmd_user_create(args) -> int:
    repo = _init_repo()
    email = (args.email or "").strip().lower()
    if not email or "@" not in email:
        print("--email must be a real address", file=sys.stderr)
        return 1
    if repo.get_user_by_email(email):
        print(f"User already exists: {email}", file=sys.stderr)
        return 1
    # Seed via the normal login path so identity linking stays in one place.
    row = repo.upsert_login_identity(
        provider=args.provider,
        identifier=email,
        email=email,
        display_name=args.name,
        is_admin=bool(args.admin),
    )
    if row is None:
        print("Failed to create user", file=sys.stderr)
        return 1
    print(f"Created user id={row['id']} email={row['email']} is_admin={row['is_admin']}")
    return 0


def cmd_user_link_identity(args) -> int:
    repo = _init_repo()
    user = _resolve_user(repo, args.user)
    email = user.get("email")
    if not email:
        print(
            "That user has no verified email, so an identity cannot be linked to "
            "it by email. Create the user with --email first.",
            file=sys.stderr,
        )
        return 1
    row = repo.upsert_login_identity(
        provider=args.provider,
        identifier=args.identifier,
        email=email,
        is_admin=bool(user.get("is_admin")),
    )
    if row is None or int(row["id"]) != int(user["id"]):
        print("Failed to link identity to that user", file=sys.stderr)
        return 1
    print(f"Linked {args.provider}:{args.identifier} -> user {user['id']} ({email})")
    return 0


def cmd_user_set_admin(args) -> int:
    repo = _init_repo()
    user = _resolve_user(repo, args.user)
    want = bool(args.on)
    repo.set_user_admin(int(user["id"]), want)
    print(f"user {user['id']} is_admin={want}")
    if want:
        print(
            "Note: BINDERDASH_ADMIN_USERS is re-applied at every startup and login, "
            "so add them there to make this stick.",
            file=sys.stderr,
        )
    return 0


def cmd_key_create(args) -> int:
    repo = _init_repo()
    user = _resolve_user(repo, args.user)
    from .api_keys import expiry_from_days, generate_key

    token, key_hash, key_prefix = generate_key()
    row = repo.create_api_key(
        user_id=int(user["id"]),
        name=args.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        expires_at=expiry_from_days(args.expires_days),
    )
    if row is None:
        print("Failed to create API key", file=sys.stderr)
        return 1
    # Token alone on stdout, so `... > key.txt` yields just the key.
    print(token)
    print(
        f"Created key id={row['id']} name={row['name']} for {user.get('email') or user['id']}.\n"
        "This is the only time it is shown -- it is stored hashed.",
        file=sys.stderr,
    )
    return 0


def cmd_key_list(args) -> int:
    repo = _init_repo()
    from .api_keys import decorate_key

    if args.all:
        rows = repo.list_api_keys(None)
    else:
        user = _resolve_user(repo, args.user)
        rows = repo.list_api_keys(int(user["id"]))
    _print_table(
        [decorate_key(r) for r in rows],
        ["id", "user_id", "name", "key_prefix", "status", "expires_at", "last_used_at"],
    )
    return 0


def cmd_key_revoke(args) -> int:
    repo = _init_repo()
    if not repo.revoke_api_key(int(args.key_id)):
        print(f"No active key with id {args.key_id}", file=sys.stderr)
        return 1
    print(f"Revoked key {args.key_id}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m backend.cli")
    sub = parser.add_subparsers(dest="group", required=True)

    user = sub.add_parser("user", help="manage users").add_subparsers(
        dest="action", required=True
    )
    user.add_parser("list", help="list users").set_defaults(func=cmd_user_list)

    p = user.add_parser("show", help="show one user")
    p.add_argument("user", help="email, provider:identifier, username, or id")
    p.set_defaults(func=cmd_user_show)

    p = user.add_parser("create", help="create a user")
    p.add_argument("--email", required=True)
    p.add_argument("--name", default=None)
    p.add_argument("--provider", default="local")
    p.add_argument("--admin", action="store_true")
    p.set_defaults(func=cmd_user_create)

    p = user.add_parser("link-identity", help="attach another login to a user")
    p.add_argument("user")
    p.add_argument("--provider", required=True, choices=["local", "pam", "google"])
    p.add_argument("--identifier", required=True)
    p.set_defaults(func=cmd_user_link_identity)

    p = user.add_parser("set-admin", help="grant or revoke admin")
    p.add_argument("user")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--on", action="store_true")
    group.add_argument("--off", dest="on", action="store_false")
    p.set_defaults(func=cmd_user_set_admin)

    key = sub.add_parser("key", help="manage API keys").add_subparsers(
        dest="action", required=True
    )

    p = key.add_parser("create", help="mint a key (shown once)")
    p.add_argument("user")
    p.add_argument("--name", required=True)
    p.add_argument("--expires-days", type=int, default=None)
    p.set_defaults(func=cmd_key_create)

    p = key.add_parser("list", help="list keys")
    p.add_argument("user", nargs="?", default=None)
    p.add_argument("--all", action="store_true")
    p.set_defaults(func=cmd_key_list)

    p = key.add_parser("revoke", help="revoke a key by id")
    p.add_argument("key_id")
    p.set_defaults(func=cmd_key_revoke)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "all", False) is False and getattr(args, "user", None) is None:
        if args.func is cmd_key_list:
            print("Give a user, or pass --all", file=sys.stderr)
            return 1
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
