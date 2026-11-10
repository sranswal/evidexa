"""Safe Local Development User Bootstrap Utility.

Allows creating or resetting a local developer / administrator account in development.
Protected against running in production environments.
"""

from __future__ import annotations

import argparse
import sys

from document_intelligence.core.config import settings
from document_intelligence.domain.identifiers import generate_id, utc_now
from document_intelligence.domain.models.auth import SystemRole
from document_intelligence.infrastructure.persistence.database import SessionLocal
from document_intelligence.infrastructure.persistence.models import UserModel
from document_intelligence.infrastructure.repositories.auth_repository import AuthRepository
from document_intelligence.modules.auth.password import PasswordService


def bootstrap_user(
    email: str,
    username: str,
    password: str,
    full_name: str,
    role: SystemRole = SystemRole.SYSTEM_ADMIN,
) -> None:
    if settings.app_env.lower() == "production":
        print("[ERROR] Cannot bootstrap development users in production environment.")
        sys.exit(1)

    if len(password) < 8:
        print("[ERROR] Password must be at least 8 characters long.")
        sys.exit(1)

    hasher = PasswordService()
    hashed_pw = hasher.hash_password(password)

    session = SessionLocal()
    try:
        repo = AuthRepository(session)
        now = utc_now()

        existing_user = repo.get_user_by_email(email.lower()) or repo.get_user_by_username(
            username.lower()
        )
        if existing_user:
            print(
                f"User '{existing_user.username}' ({existing_user.email}) already exists. Updating password and activating..."
            )
            existing_user.hashed_password = hashed_pw
            existing_user.full_name = full_name
            existing_user.is_active = True
            existing_user.system_role = role.value
            existing_user.updated_at = now
            session.commit()
            print(
                f"[SUCCESS] Updated user '{existing_user.username}' [Role: {existing_user.system_role}]"
            )
            return

        # Create new user
        new_user = UserModel(
            id=generate_id(),
            email=email.strip().lower(),
            username=username.strip().lower(),
            hashed_password=hashed_pw,
            full_name=full_name.strip(),
            is_active=True,
            system_role=role.value,
            created_at=now,
            updated_at=now,
        )
        repo.create_user(new_user)

        # Ensure default organization membership
        default_org = repo.get_or_create_default_org()
        repo.add_org_membership(
            default_org.id,
            new_user.id,
            role="ADMIN" if role == SystemRole.SYSTEM_ADMIN else "MEMBER",
        )

        session.commit()
        print(
            f"[SUCCESS] Bootstrapped new user '{new_user.username}' ({new_user.email}) [Role: {new_user.system_role}]"
        )
        print(f"Assigned to organization '{default_org.name}' ({default_org.id}).")
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap a local development user for EVIDEXA.")
    parser.add_argument("--email", default="examiner@evidexa.local", help="User email address")
    parser.add_argument("--username", default="examiner", help="User username")
    parser.add_argument(
        "--password", default="Investigator#2026", help="User password (min 8 chars)"
    )
    parser.add_argument(
        "--full-name", default="Lead Examiner Sarah Vance", help="Full display name"
    )
    parser.add_argument(
        "--role",
        choices=["SYSTEM_ADMIN", "USER"],
        default="SYSTEM_ADMIN",
        help="System administrative role",
    )

    args = parser.parse_args()
    bootstrap_user(
        email=args.email,
        username=args.username,
        password=args.password,
        full_name=args.full_name,
        role=SystemRole[args.role],
    )


if __name__ == "__main__":
    main()
