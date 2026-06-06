import getpass

from pwdlib import PasswordHash


def main() -> None:
    password = getpass.getpass("Admin password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        raise SystemExit("Passwords do not match")
    if len(password) < 12:
        raise SystemExit("Use at least 12 characters")
    print(PasswordHash.recommended().hash(password))


if __name__ == "__main__":
    main()

