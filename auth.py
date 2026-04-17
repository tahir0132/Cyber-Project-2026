import hashlib
import os
import platform
import uuid
import json
import re

# =====================================================================
#                        CYBERSECURITY TUTORIAL
#                 Secure Login and Registration System
# =====================================================================
#
# EDUCATIONAL NOTE - WHY USE A SALT?
# ----------------------------------
# A "Rainbow Table" is a massive, precomputed database of plaintext 
# passwords and their corresponding hash values. If a hacker steals 
# a database that only contains simple hashes of passwords, they can
# just look up the hash in their Rainbow Table to find the password.
# 
# A "Salt" is a random sequence of characters added to the password 
# BEFORE it gets hashed. 
# 
# How it stops Rainbow Tables:
# Because the salt is unique for every user, the resulting hash is 
# completely unique, even if two users have the same password ("123456").
# To crack it, the attacker would need an entirely new Rainbow Table 
# for EVERY possible salt, which takes too much computing power and 
# storage to calculate. 
#
# Remember: Salt = Randomness = Unpredictability!
# =====================================================================

DATABASE_FILE = "users_db.json"

def load_db():
    if not os.path.exists(DATABASE_FILE):
        return {}
    with open(DATABASE_FILE, "r") as f:
        return json.load(f)

def save_db(db):
    with open(DATABASE_FILE, "w") as f:
        json.dump(db, f, indent=4)

# =====================================================================
#                     SERVER-SIDE AUTHENTICATION
# =====================================================================

def register_user(username, plaintext_password):
    """
    Simulates a server receiving a registration request.
    It securely hashes the password with a generated salt before storing.
    """
    # 0. Check for strict password complexity
    if len(plaintext_password) < 8 or not re.search(r"[A-Z]", plaintext_password) \
        or not re.search(r"[a-z]", plaintext_password) \
        or not re.search(r"[0-9]", plaintext_password) \
        or not re.search(r"[^A-Za-z0-9]", plaintext_password):
        print("Error: Password must be at least 8 characters long, contain an uppercase letter, a lowercase letter, a number, and a special character.")
        return False
        
    db = load_db()
    for existing_user in db.keys():
        if existing_user.lower() == username.lower():
            print("Error: Username already exists! Please choose a different name.")
            return False
        
    # 1. Generate a unique, random salt (32 bytes = 64 hex characters)
    salt = os.urandom(32).hex()
    
    # 2. Combine the salt with the password, and hash them together
    # Using SHA-256 for a strong, one-way cryptographic hash
    combined_data = salt + plaintext_password
    hashed_password = hashlib.sha256(combined_data.encode('utf-8')).hexdigest()
    
    # 3. Store the salt AND the hash. 
    # (The salt is not a secret, it just needs to be unique!)
    db[username] = {
        "salt": salt,
        "hash": hashed_password
    }
    save_db(db)
    print(f"User '{username}' registered successfully!")
    return True

def login_user(username, plaintext_password, hardware_id):
    """
    Simulates a server verifying a login attempt.
    Also demonstrates hardware binding for an extra layer of security.
    """
    db = load_db()
    
    # Check if the user exists case-insensitively
    actual_username = None
    for existing_user in db.keys():
        if existing_user.lower() == username.lower():
            actual_username = existing_user
            break

    if not actual_username:
        print("Error: User not found!")
        return False
        
    user_record = db[actual_username]
    salt = user_record["salt"]
    stored_hash = user_record["hash"]
    
    # To verify, we must re-create the hash using the provided password
    # and the STORED salt exactly how we did during registration.
    combined_data = salt + plaintext_password
    test_hash = hashlib.sha256(combined_data.encode('utf-8')).hexdigest()
    
    if test_hash == stored_hash:
        print(f"Login successful for '{username}'!")
        print(f"-> Server validated Hardware Fingerprint: {hardware_id}")
        return True
    else:
        print("Error: Invalid password!")
        return False

# =====================================================================
#                     CLIENT-SIDE EXTRACTION
# =====================================================================

def get_hardware_id():
    """
    Extracts a hardware identifier using Python's OS and Platform modules.
    This creates a basic fingerprint of the device playing the game.
    We would send this from the Pygame client to the server during login.
    """
    # 1. Get the network hostname using the OS platform module
    hostname = platform.node()
    
    # 2. Extract the system MAC address
    # uuid.getnode() safely queries the OS for the hardware network address
    mac_address_raw = uuid.getnode()
    
    # Format the MAC address nicely for readability (e.g., 0A:1B:2C:3D:4E:5F)
    mac_address = ':'.join(("%012X" % mac_address_raw)[i:i+2] for i in range(0, 12, 2))
    
    # Combine hostname and MAC to create a unique device fingerprint
    hardware_id = f"{hostname}-{mac_address}"
    return hardware_id

# =====================================================================
#                           DEMONSTRATION
# =====================================================================
if __name__ == "__main__":
    
    print("\n--- 1. Client Generated Hardware ID ---")
    hw_id = get_hardware_id()
    print("Extracted Fingerprint:", hw_id)
    
    print("\n--- 2. Server Registration ---")
    register_user("student1", "MySecretPassword123!")
    
    print("\n--- 3. Server Login Attack Simulation ---")
    
    # Wrong password attempt
    print("Attempting login with WRONG password:")
    login_user("student1", "Hacker123", hw_id)
    
    print("\nAttempting login with CORRECT password:")
    # Correct password attempt
    login_user("student1", "MySecretPassword123!", hw_id)
    
    print("\nCheck 'users_db.json' to see how the data is safely stored in plaintext!")
