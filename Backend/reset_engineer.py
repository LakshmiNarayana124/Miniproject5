from database import get_connection

with get_connection() as connection:
    user = connection.execute(
        """
        SELECT id, username, full_name, role
        FROM users
        WHERE id = 4
        """
    ).fetchone()

    if user is None:
        print("Account ID 4 not found.")
        raise SystemExit

    print("Account selected:")
    print(dict(user))

    if user["role"] != "MAINTENANCE_ENGINEER":
        print("Safety check failed. Account not deleted.")
        raise SystemExit

    confirmation = input(
        "Type DELETE to permanently delete account ID 4: "
    )

    if confirmation == "DELETE":
        connection.execute(
            """
            DELETE FROM users
            WHERE id = 4
            AND role = 'MAINTENANCE_ENGINEER'
            """
        )
        print("Account ID 4 deleted successfully.")
    else:
        print("Deletion cancelled.")