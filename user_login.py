import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

def connecting_to_database():
    connect = sqlite3.connect('silvershieldDatabase.db')
    connect.row_factory = sqlite3.Row
    return connect

def user_registration(username, password, email, phone, address):
    connect = connecting_to_database()
    cursor = connect.cursor()
    password_hash = generate_password_hash(password)
    try:
        cursor.execute("INSERT INTO users (username, password_hash, email, phone, address) VALUES (?, ?, ?, ? , ?)",
                       (username, password_hash, email, phone, address))
        connect.commit()
        print("User Registration Successful")
        return True, "User Registration Successful"
    except sqlite3.IntegrityError:
        print("Username or phone already exists")
        return False, "Username or phone already exists"
    except Exception as e:
        print(f"An error occured: {str(e)} ")
        return False, f"An error occured: {str(e)}"
    finally:
        connect.close()

def find_account(usernameOrEmail):
    connect = connecting_to_database()
    cursor = connect.cursor()
    cursor.execute(
        "SELECT username, phone FROM users WHERE username = ? OR email = ?",
        (usernameOrEmail, usernameOrEmail),
    )
    result = cursor.fetchone()
    connect.close()

    if not result:
        return None, None
    return result["username"], result["phone"]

def update_password(username, password):
    connect = connecting_to_database()
    cursor = connect.cursor()
    password_hash = generate_password_hash(password)
    cursor.execute(
        "UPDATE users SET password_hash = ? WHERE username = ?",
        (password_hash, username),
    )
    connect.commit()
    changed = cursor.rowcount == 1
    connect.close()
    return changed

def verifying_login (usernameOrEmail, password):
    connect = connecting_to_database()
    cursor = connect.cursor()
    cursor.execute("SELECT username, password_hash, phone FROM users WHERE username = ? OR email = ?", (usernameOrEmail, usernameOrEmail))
    result = cursor.fetchone()
    connect.close()

    if result and check_password_hash(result['password_hash'], password):
        phone = result['phone']
        return True, phone, result['username']
    else:
        return False, None, None
