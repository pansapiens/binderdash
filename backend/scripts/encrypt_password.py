#!/usr/bin/env python3
"""
Password encryption utility for binderdash local authentication.

This script helps generate bcrypt hashes for passwords to be used in the
LOCAL_USERS environment variable.

Usage:
    python encrypt_password.py <username>                    # Interactive password prompt
    python encrypt_password.py <username> --password <pass>  # Password as argument
    echo <password> | python encrypt_password.py <username>  # Password from stdin
    python encrypt_password.py --help                        # Show help

Examples:
    # Interactive mode (default) - password will be prompted
    python encrypt_password.py alice

    # Password as command line argument
    python encrypt_password.py alice --password mypassword123

    # Password from stdin (useful for scripts)
    echo mypassword123 | python encrypt_password.py alice

    # Verify a password against a hash
    python encrypt_password.py --verify mypassword123 '$2b$12$...'
"""

import argparse
import getpass
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_repo_root))

try:
    from backend.auth_providers.passwords import get_password_hash, verify_password
except ImportError:
    print("Error: could not import password helpers. Install dependencies:")
    print("  cd backend && uv pip install -r requirements.txt")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Generate bcrypt password hashes for binderdash LOCAL_USERS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s alice                                    # Interactive password prompt
  %(prog)s alice --password mypassword123           # Password as argument
  echo mypassword123 | %(prog)s alice               # Password from stdin
  %(prog)s --verify mypassword123 '$2b$12$...'      # Verify password
        """,
    )

    parser.add_argument(
        "username",
        nargs="?",
        help="Username for generating LOCAL_USERS entry (password will be prompted interactively)",
    )

    parser.add_argument(
        "--password",
        "-p",
        help="Password to hash (if not provided, will prompt interactively or read from stdin)",
    )

    parser.add_argument(
        "--verify",
        "-v",
        nargs=2,
        metavar=("PASSWORD", "HASH"),
        help="Verify a password against a hash",
    )

    args = parser.parse_args()

    # Handle verification
    if args.verify:
        password, hash_str = args.verify
        if verify_password(password, hash_str):
            print("✓ Password matches hash")
            return 0
        else:
            print("✗ Password does not match hash")
            return 1

    # Check if username is provided
    if not args.username:
        parser.print_help()
        return 1

    # Get password
    if args.password:
        # Password provided as argument
        password = args.password
    else:
        # Try to read from stdin first (for piping)
        try:
            # Check if stdin has data (non-blocking)
            import sys
            import os

            if os.isatty(sys.stdin.fileno()):
                # stdin is a terminal, prompt interactively
                password = getpass.getpass(
                    f"Enter password for user '{args.username}': "
                )
                if not password:
                    print("Error: No password entered")
                    return 1
            else:
                # stdin is piped, read from it
                password = sys.stdin.read().strip()
                if not password:
                    print("Error: No password provided via stdin")
                    return 1
        except Exception:
            # Fallback to interactive prompt
            password = getpass.getpass(f"Enter password for user '{args.username}': ")
            if not password:
                print("Error: No password entered")
                return 1

    # Generate hash
    try:
        password_hash = get_password_hash(password)

        print(f"\nAdd this to your .env file:")
        print(f"LOCAL_USERS='{args.username}:{password_hash}'")

        print(f"\nTo add multiple users, separate with commas:")
        print(f"LOCAL_USERS='user1:hash1,user2:hash2,user3:hash3'")

        return 0

    except Exception as e:
        print(f"Error generating hash: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
