"""Grant or revoke the administrator role (Team A13 in Release 1).

Usage: script/backend.sh admin <email> [--revoke]

Administrators can never be group members (§6.2 access isolation), so an account that is
in a group must leave it before it can be promoted.
"""

import argparse
import logging
import os
import sys

import psycopg

from roomly.config import Settings
from roomly.mapper import MembershipMapper, UserMapper

logger = logging.getLogger("roomly.admin")


def set_admin(database_url: str, email: str, *, revoke: bool) -> str:
    email = email.strip().lower()
    with psycopg.connect(database_url) as conn:
        user = UserMapper(conn).find_by_email(email)
        if user is None:
            raise LookupError("no live account with that email")
        if not revoke and MembershipMapper(conn).current_for_user(user.id):
            raise PermissionError("that account is in a group; administrators cannot be group members")
        UserMapper(conn).set_role(email, "user" if revoke else "admin")
        return str(user.id)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("email")
    parser.add_argument("--revoke", action="store_true", help="make the account a regular user again")
    args = parser.parse_args()
    settings = Settings.from_env(os.environ)
    logging.basicConfig(level="INFO", format="%(levelname)s %(name)s: %(message)s")
    try:
        user_id = set_admin(settings.database_url, args.email, revoke=args.revoke)
    except (LookupError, PermissionError) as exc:
        logger.error("%s", exc)
        sys.exit(1)
    logger.info("user=%s is now %s", user_id, "a regular user" if args.revoke else "an administrator")


if __name__ == "__main__":
    main()
