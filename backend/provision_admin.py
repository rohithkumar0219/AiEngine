
from getpass import getpass

from auth.database import initialize_database
from auth.service import provision_admin


def main():
    print("\n=== AI-Engine Administrator Provisioning ===\n")

    initialize_database()

    email = input("Administrator email: ").strip()
    tenant_id = input("Tenant ID: ").strip()

    password = getpass("Administrator password: ")
    confirmation = getpass("Confirm password: ")

    if password != confirmation:
        print("Error: Passwords do not match.")
        return

    try:
        admin_id = provision_admin(
            email=email,
            password=password,
            tenant_id=tenant_id,
        )

        print("\nAdministrator created successfully.")
        print("Admin ID:", admin_id)
        print("Tenant ID:", tenant_id)
        print("Role: tenant_admin")

    except ValueError as exc:
        print("\nProvisioning failed:", str(exc))

    except Exception:
        print("\nProvisioning failed. Check the backend logs.")


if __name__ == "__main__":
    main()
