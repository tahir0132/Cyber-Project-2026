# 🎓 Exam Readiness & Readability Report — *Meteorite Blah*
**Examiner mode: Strict | Audience: High School Student | Exam: Oral Matriculation**

---

## ✅ Part 1 — Mandatory Requirements Checklist

| # | Requirement | Status | Where It Lives |
|---|---|---|---|
| 1 | **At least 4 distinct OOP classes** | ✅ **PASS** | `mainClass.py` — `NetworkManager`, `MainMenu`, `Game`, `Background`, `Player`, `Meteor`, `Particle`, `Explosion`, `PowerUp` (9 classes total!) |
| 2 | **Client-Server architecture using TCP Sockets** | ✅ **PASS** | `secure_network.py` (score sync, port 65432) + `network_server.py` (rivalry server, port 5555) |
| 3 | **Multithreading to handle multiple clients** | ✅ **PASS** | `secure_network.py` `SecureServer.start()` → spawns a `Thread` per client; `network_server.py` `start_server()` → same pattern; `NetworkManager._sync_loop()` runs in a daemon thread |
| 4 | **OS-level integration** | ✅ **PASS** | `auth.py` → `platform.node()` (hostname), `uuid.getnode()` (MAC address); `secure_network.py` → `os.urandom()` (entropy); `json` file I/O (`users_db.json`, `best_scores.json`) |
| 5 | **Applied Cryptography** | ✅ **PASS** | `secure_network.py` → Diffie-Hellman key exchange + AES-CBC encryption; `auth.py` → SHA-256 hash + random salt |
| 6 | **Interactive GUI (Pygame)** | ✅ **PASS** | `mainClass.py` full Pygame loop with menu, game, animations, health bar, particle effects |

> [!IMPORTANT]
> **Overall verdict: FULL PASS on all 6 mandatory requirements.** Your project demonstrates every concept required. The rest of this report focuses on making sure you can *explain* it confidently.

---

## 🔧 Part 2 — Code Simplification Recommendations

These are the sections an examiner might ask about. Each one has a "Why it's tricky" note and a simplified, heavily commented version you can explain out loud.

---

### 2.1 — The `struct.pack` Binary Protocol (`mainClass.py`, `network_server.py`)

**Why it's tricky:** `struct.pack('!Bhh', 1, x, y)` looks like magic. You need to own this explanation.

**Plain English translation:**
> `struct.pack` converts Python numbers into raw bytes, just like how a ZIP code is compressed numbers. The `!` means "network byte order" (big-endian — most significant byte first, which is the standard for internet protocols). `B` means "1 unsigned byte", `h` means "2-byte signed integer", `H` means "2-byte unsigned integer", `I` means "4-byte unsigned integer".

**Simplified snippet with heavy comments you can study from:**

```python
# =====================================================================
# HOW OUR NETWORK PROTOCOL WORKS — Binary Packet Format
# =====================================================================
# Instead of sending readable text like "MOVE 100 200" (slow!),
# we pack numbers into the smallest possible bytes (fast!).
#
# This is exactly how real game engines like Minecraft or Fortnite work.
# =====================================================================

import struct

# --- SENDING A MOVE PACKET FROM CLIENT TO SERVER ---

x_position = 100
y_position = 200

# Think of this like packing a tiny box:
# '!' = use network byte order (standard for ALL internet communication)
# 'B' = 1 byte  → holds the COMMAND TYPE (e.g., 1 = "I moved")
# 'h' = 2 bytes → holds X coordinate (signed, so negative numbers work)
# 'h' = 2 bytes → holds Y coordinate (signed, so negative numbers work)
# Total packet size = 5 bytes (vs. 10+ bytes for a text string)
move_packet = struct.pack('!Bhh', 1, x_position, y_position)

print(f"Packed packet bytes: {move_packet}")  # e.g. b'\x01\x00d\x00\xc8'
print(f"Packet size: {len(move_packet)} bytes")  # 5 bytes

# --- RECEIVING ON THE SERVER SIDE: UNPACKING ---
# The server reads only 1 byte first to identify the command
command_type = move_packet[0]   # This gives us the integer 1
print(f"Command received: {command_type}")  # 1 = Move

# Then reads the next 4 bytes for x, y
x, y = struct.unpack('!hh', move_packet[1:])
print(f"Player moved to: x={x}, y={y}")   # x=100, y=200
```

---

### 2.2 — The Diffie-Hellman Key Exchange (`secure_network.py`)

**Why it's tricky:** `pow(G, private_key, P)` is a "magic-looking" modular exponentiation.

**Simplified explanation you can say out loud in your exam:**

> "Diffie-Hellman works like mixing paint. Imagine I pick a secret colour (my private key) and you pick a secret colour. We both start with the same base colour (G) and mix it with our secret to get our **public colour**. We send each other our public colours. When I mix YOUR public colour with MY secret, and you mix MY public colour with YOUR secret — we both end up with the exact same final colour. An eavesdropper only ever sees the public colours and can't figure out our secrets."

```python
# =====================================================================
# DIFFIE-HELLMAN IN PLAIN ENGLISH — Step by Step
# =====================================================================

# STEP 0: Both sides agree on these two public values (not secret at all).
# P = A very large prime number (makes the math one-way hard to reverse)
# G = A "generator" base number (usually just 2)
P = 23   # (we use 2 to keep this example readable; real P is 1024 bits!)
G = 5

# ---- CLIENT SIDE ----
# STEP 1: Client picks a SECRET private number (never shared!)
client_private = 6

# STEP 2: Client calculates its PUBLIC key using: (G to the power of private) mod P
# This is a "one-way" mathematical operation — easy to compute, very hard to reverse.
client_public = pow(G, client_private, P)   # = (5^6) % 23 = 8
print(f"Client sends public key: {client_public}")

# ---- SERVER SIDE ----
# STEP 3: Server picks a SECRET private number (never shared!)
server_private = 15

# STEP 4: Server calculates its PUBLIC key
server_public = pow(G, server_private, P)   # = (5^15) % 23 = 19
print(f"Server sends public key: {server_public}")

# ---- MAGIC HAPPENS ----
# STEP 5: Client receives server_public and computes the shared secret
client_shared = pow(server_public, client_private, P)  # = (19^6) % 23 = 2

# STEP 6: Server receives client_public and computes the shared secret  
server_shared = pow(client_public, server_private, P)  # = (8^15) % 23 = 2

# RESULT: Both compute the SAME shared secret (2) without ever sending it!
print(f"Client secret: {client_shared}")  # 2
print(f"Server secret: {server_shared}")  # 2
print(f"Secrets match: {client_shared == server_shared}")  # True!

# Now BOTH sides run this shared secret through SHA-256 to get a fixed AES key:
import hashlib
secret_bytes = client_shared.to_bytes(1, 'big')  # convert int to bytes
aes_key = hashlib.sha256(secret_bytes).digest()  # 32-byte AES key!
print(f"Derived AES key (first 8 bytes): {aes_key[:8].hex()}")
```

---

### 2.3 — Hash + Salt Authentication (`auth.py`)

**This is already well-commented! But here is the simplified explanation for your exam speech:**

```python
# =====================================================================
# HASH + SALT: WHY NOT JUST STORE PASSWORDS DIRECTLY?
# =====================================================================
# BAD (NEVER DO THIS): store "password123" in your database.
# If a hacker steals your database file, they have ALL passwords!
#
# BETTER (BUT STILL BAD): store SHA256("password123") = "ef92b4..."
# A hacker can use a "Rainbow Table" — a pre-calculated list of
# common passwords and their hashes — and instantly match it!
#
# BEST (WHAT WE DO): store SHA256(RANDOM_SALT + "password123")
# The salt is a random string unique to EACH user.
# Even if two users have the same password, their stored hashes differ!
# The hacker's Rainbow Table is now completely useless.
# =====================================================================

import hashlib, os

def register_user_simplified(username, plaintext_password):
    
    # 1. Generate a random 32-byte salt (os.urandom asks the OS for random bytes)
    #    .hex() converts those bytes to a readable string of 64 hex characters.
    salt = os.urandom(32).hex()
    print(f"Generated salt: {salt}")
    
    # 2. Combine: put the salt IN FRONT of the password, then hash everything
    combined = salt + plaintext_password
    hashed = hashlib.sha256(combined.encode('utf-8')).hexdigest()
    print(f"Stored hash:    {hashed}")
    
    # 3. Store BOTH the salt and the hash in the database.
    #    The salt is NOT a secret — it just needs to be unique!
    stored_record = {"salt": salt, "hash": hashed}
    return stored_record

def login_user_simplified(plaintext_password, stored_record):
    
    # Retrieve the salt that was saved during registration
    salt = stored_record["salt"]
    
    # Re-create the hash from the entered password + saved salt
    combined = salt + plaintext_password
    test_hash = hashlib.sha256(combined.encode('utf-8')).hexdigest()
    
    # Compare: the hashes match ONLY if the password is correct!
    if test_hash == stored_record["hash"]:
        print("Login SUCCESSFUL!")
        return True
    else:
        print("Login FAILED — wrong password!")
        return False

# --- Test it ---
record = register_user_simplified("alice", "SuperSecret99!")
login_user_simplified("SuperSecret99!", record)   # Succeeds
login_user_simplified("wrongpassword", record)    # Fails
```

---

### 2.4 — Threading & Race Conditions (`network_server.py`, `secure_network.py`)

**Why it's tricky:** `threading.Lock()` and `with self.lock:` are advanced concepts.

```python
# =====================================================================
# RACE CONDITIONS AND THREAD LOCKS — THE BANK ANALOGY
# =====================================================================
# Imagine two bank tellers (threads) both checking your account balance
# at the same time. You have $100. Both read $100, both try to deduct $50.
# Both write back $50. But you should have $0! This is a "Race Condition."
#
# A Lock (also called a "Mutex") is like a physical key to a room.
# Only ONE teller can hold the key at a time.
# If one teller is inside, the other waits at the door.
# This guarantees the operation is "atomic" (all-or-nothing).
# =====================================================================

import threading

# The shared resource that multiple threads could try to write at once
score_database = {}
# The lock — only one thread can hold this at a time
score_lock = threading.Lock()

def update_score_thread_safe(username, new_score):
    
    # "with score_lock:" automatically:
    #   1. Tries to ACQUIRE (lock) the mutex
    #   2. If another thread has it, WAITS until it's released
    #   3. Runs the code block
    #   4. Automatically RELEASES the lock when done (even if an error occurs!)
    with score_lock:
        # This entire block runs atomically — no other thread can interrupt
        current_best = score_database.get(username, 0)
        if new_score > current_best:
            score_database[username] = new_score
            print(f"New high score for {username}: {new_score}")
    
    # Lock automatically released here — other threads can now proceed
```

---

### 2.5 — The `getattr()` Pattern in `draw()` (`mainClass.py` line 483)

**The problematic line:**
```python
pid_map = {p: n for p, n in getattr(self.net_manager, 'lobby_players', [])}
```

**Why it's tricky:** `getattr` with a default is an advanced Python pattern.

**Simplified replacement:**
```python
# Instead of the tricky getattr pattern, just check normally:
if hasattr(self.net_manager, 'lobby_players') and self.net_manager.lobby_players:
    pid_map = {}
    for pid, name in self.net_manager.lobby_players:
        pid_map[pid] = name
else:
    pid_map = {}   # Empty dict if no players
```

---

### 2.6 — Daemon Threads (`network_server.py` line 157)

**The line:** `thread.daemon = True`

**What to say:** 
> "A daemon thread is a background thread that is automatically killed when the main program exits. Without this, if I close the game window, the server thread would keep running forever and the program would never actually quit."

---

## 🗺️ Part 3 — Project Map (Plain English Data Flow)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PROGRAM STARTUP                             │
│                       (mainClass.py → main())                      │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  1. AUTHENTICATION (auth.py)                                       │
│     • Asks: Register or Login?                                     │
│     • get_hardware_id() → reads OS hostname + MAC address          │
│     • register_user() → generates random SALT, hashes password,   │
│       saves {salt, hash} to users_db.json                          │
│     • login_user() → recomputes hash, compares, validates HW ID   │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  2. SCORE RETRIEVAL (secure_network.py → SecureClient)             │
│                                                                     │
│  CLIENT                          SERVER (port 65432)               │
│  ──────                          ─────────────────                 │
│  Generate private DH key ──────► Accept connection                 │
│  Send client_public_key  ──────► Receive client_public             │
│                          ◄────── Send server_public_key            │
│  Receive server_public            Compute shared_secret            │
│  Compute shared_secret            Derive AES key (SHA-256)         │
│  Derive AES key (SHA-256)                                          │
│  Encrypt {score, user}   ──────► Decrypt payload                  │
│  (AES-CBC)                        Check/update best_scores.json    │
│                          ◄────── Encrypt {best_score}              │
│  Decrypt {best_score}             (AES-CBC)                        │
│  Display score on screen                                            │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  3. MAIN MENU (mainClass.py → MainMenu)                            │
│     • Draws animated starfield background (Background class)      │
│     • Shows: Start Game / Rivalry Mode / Join/Leave Server        │
│     • Every 60 frames, calls net_manager.query_lobby()            │
│       → sends command "2" to server → gets player list back       │
│     • If rivalry_start_signal received → launches Game(RIVALRY)   │
└─────────────────────────────────────────────────────────────────────┘
                                │
              ┌─────────────────┴──────────────────┐
              ▼                                     ▼
┌─────────────────────────┐           ┌─────────────────────────────┐
│  SOLO MODE              │           │  RIVALRY MODE               │
│  (Game class)           │           │  (Game class, mode=RIVALRY) │
│                         │           │                             │
│  • Random seed: local   │           │  • Shared seed from server  │
│  • Meteors spawn alone  │           │  • All players see SAME     │
│  • Score tracked        │           │    meteors, same powerups   │
│  • No network           │           │  • Player positions synced  │
│                         │           │    via network_server:5555  │
│                         │           │  • First to die = LOSER     │
└─────────────────────────┘           └─────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  4. GAME LOOP (mainClass.py → Game)                                │
│  Each frame (60 FPS):                                              │
│     handle_events() → reads keyboard/mouse input                  │
│     update()        → moves player, spawns/moves meteors,         │
│                       checks collisions, sends position if online │
│     draw()          → renders everything to screen                │
│     clock.tick(60)  → caps to 60 frames per second                │
│                                                                     │
│  Game Classes Used:                                                │
│    Player   → handles WASD movement, shield, animations, damage   │
│    Meteor   → falls from top, animated sprite, damages player      │
│    Explosion → spawns 30 Particle objects, each fades out         │
│    PowerUp  → heart (heal), bubble (shield), shoe (speed boost)   │
│    Background → animated scrolling starfield                      │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  5. MULTIPLAYER RIVAL SERVER (network_server.py, port 5555)        │
│                                                                     │
│  Server runs in background, handles multiple clients with threads  │
│                                                                     │
│  Command Protocol (binary):                                        │
│   CMD 0 → Server sends: welcome packet with player ID             │
│   CMD 1 → Client sends: my position (x, y)                        │
│            Server replies: all other players' positions            │
│   CMD 2 → Client asks: who's in the lobby?                        │
│            Server replies: list of (player_id, username) pairs    │
│   CMD 3 → Client says: start rivalry!                             │
│            Server broadcasts: random seed to ALL clients           │
│   CMD 4 → Client says: I died!                                    │
│            Server broadcasts: winner ID to ALL clients             │
│   CMD 5 → Client says: I'm leaving                                │
│   CMD 6 → Client sends: my username                               │
│                                                                     │
│  Security: Rate limiter (>120 msgs/sec = kick) prevents DDoS      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🐞 Part 4 — Robustness: Issues Found & Fixes

### Issue 4.1 — `network_server.py`: Bare `except:` on Welcome Packet (line 31-32)

**Problem:** If the welcome packet send fails, control falls through with no cleanup. The error is silently swallowed.

**Current code:**
```python
try:
    client_socket.sendall(struct.pack('!BH', 0, player_id))
except:
    pass
```

**Better approach:**
```python
try:
    # The welcome message tells the new client their assigned Player ID
    client_socket.sendall(struct.pack('!BH', 0, player_id))
except Exception as welcome_error:
    # If we can't even say hello, this connection is broken — remove and leave
    print(f"[SERVER] Failed to send welcome to {client_address}: {welcome_error}")
    with game_state_lock:
        if player_id in players: del players[player_id]
        if player_id in clients: del clients[player_id]
    client_socket.close()
    return   # Exit the handler function entirely
```

---

### Issue 4.2 — `network_server.py`: Username receive has no length validation (lines 89-96)

**Problem:** If a malicious client sends `name_len = 255` then disconnects, `recv(255)` might return fewer bytes without error checking.

**Current code:**
```python
name_len = name_len_data[0]
name_bytes = client_socket.recv(name_len)
if name_bytes:
    ...
```

**Better approach:**
```python
name_len = name_len_data[0]
# Receive in a loop until we have ALL the bytes we expect
name_bytes = b''
while len(name_bytes) < name_len:
    chunk = client_socket.recv(name_len - len(name_bytes))
    if not chunk:
        break   # Client disconnected mid-send
    name_bytes += chunk

# Only process if we received the full name
if len(name_bytes) == name_len:
    with game_state_lock:
        if player_id in players:
            players[player_id]['name'] = name_bytes.decode('utf-8', errors='replace')
```

---

### Issue 4.3 — `mainClass.py`: Bare `except:` in `join_server()` (line 26)

**Current code:**
```python
try:
    self.sock.connect(('127.0.0.1', 5555))
except:        # <-- catches EVERYTHING, even keyboard interrupts
    ...
```

**Better approach:**
```python
try:
    self.sock.connect(('127.0.0.1', 5555))
except (ConnectionRefusedError, OSError) as e:
    # Only catch actual network errors, not things like KeyboardInterrupt
    print(f"[MULTIPLAYER] Could not connect: {e}")
    ...
```

---

### Issue 4.4 — `mainClass.py`: `SecureClient` is imported twice

Line 3: `from secure_network import SecureClient`
Line 795: `from secure_network import SecureClient` ← duplicate!

**Fix:** Delete line 795. The import at line 3 is sufficient.

---

### Issue 4.5 — `mainClass.py`: `from logging import lastResort` (line 1)

This import is **unused** in the codebase. Remove it to keep the code clean.

---

## 📋 Part 5 — Exam Cheat Sheet (Key Talking Points)

| Concept | One-Sentence Explanation |
|---|---|
| **TCP Socket** | A reliable, connection-based "phone call" between two computers that guarantees data arrives in order. |
| **UDP Socket** | Like sending a postcard — faster, but no guarantee it arrives. *(Not used here — TCP is used.)* |
| **Threading** | Running two pieces of code "at the same time" so the game doesn't freeze while waiting for network data. |
| **Diffie-Hellman** | A way for two parties to agree on a secret key over a public network without ever sending the key itself. |
| **AES-CBC** | A symmetric encryption algorithm that scrambles data using only the shared secret key. |
| **Salt + Hash** | Randomness added to a password before hashing, making rainbow table attacks impossible. |
| **SHA-256** | A one-way "fingerprint" function — same input always gives same output, but you can't reverse it. |
| **Race Condition** | When two threads try to modify the same data at the same time, causing unpredictable results. Solved with a Lock. |
| **OS Integration** | Using Python's `platform`, `uuid`, `os` modules to interact with the operating system's hardware and file system. |
| **Pygame** | A library that gives Python the ability to draw graphics on screen and respond to keyboard/mouse events. |

---

> [!TIP]
> **For your oral exam:** Practice explaining the DH key exchange using the "mixing paint" analogy. Examiners love when students can explain cryptographic concepts without jargon.

> [!NOTE]
> **Port separation is a strength!** You have TWO servers on TWO ports: port **65432** for encrypted score storage (SecureServer) and port **5555** for real-time multiplayer (network_server). This is a professional architectural decision — mention it!
