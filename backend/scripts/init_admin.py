#!/usr/bin/env python3
import argparse
import getpass
import os
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
os.chdir(BASE_DIR)
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.core.database import Base, SessionLocal, engine
from app.core.security import get_password_hash
from app.models.user import User


def prompt_username() -> str:
    while True:
        username = input("Admin username: ").strip()
        if username:
            return username
        print("Username cannot be empty.")


def prompt_password() -> str:
    while True:
        password = getpass.getpass("Admin password: ").strip()
        if not password:
            print("Password cannot be empty.")
            continue

        confirm_password = getpass.getpass("Confirm password: ").strip()
        if password != confirm_password:
            print("Passwords do not match, please try again.")
            continue

        return password


def create_initial_admin(username: str, password: str) -> int:
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            if existing_user.is_cancel:
                print(
                    f"Cannot create admin: username '{username}' already exists as a cancelled user. "
                    "Please choose another username or restore that user manually."
                )
            else:
                print(f"Cannot create admin: username '{username}' already exists.")
            return 1

        existing_admin = db.query(User).filter(
            User.role == "admin",
            User.is_cancel == False,
        ).first()
        if existing_admin:
            print(
                f"An active admin already exists: '{existing_admin.username}'. "
                "Use the system user management to create additional admins."
            )
            return 1

        admin = User(
            username=username,
            password_hash=get_password_hash(password),
            role="admin",
            enabled=True,
            is_cancel=False,
            can_view_all=True,
            view_all_requested=False,
        )
        db.add(admin)
        db.commit()
        print(f"Initial admin created successfully: '{username}'")
        return 0
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create the initial admin user for this deployment.",
    )
    parser.add_argument("--username", help="Admin username")
    parser.add_argument("--password", help="Admin password")
    args = parser.parse_args()

    username = (args.username or "").strip() or prompt_username()
    password = (args.password or "").strip() or prompt_password()

    return create_initial_admin(username, password)


if __name__ == "__main__":
    raise SystemExit(main())
