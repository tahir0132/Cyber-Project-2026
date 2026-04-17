"""
Secure Client-Server Architecture using Sockets, Threading, Diffie-Hellman, and AES.
"""

import socket
import threading
import json
import hashlib
import os

# NOTE: You will need to install the 'pycryptodome' library for AES encryption.
# In your terminal, run: pip install pycryptodome
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# ==========================================
# Diffie-Hellman (DH) Math Explanation:
# ==========================================
# 1. Both parties agree on a large prime number (P) and a generator (G).
# 2. Server picks a secret private key (s_priv). Client picks a secret (c_priv).
# 3. Server calculates its public key: s_pub = (G ** s_priv) % P
# 4. Client calculates its public key: c_pub = (G ** c_priv) % P
# 5. They exchange s_pub and c_pub over the insecure network.
# 6. Server computes shared secret: shared = (c_pub ** s_priv) % P
# 7. Client computes shared secret: shared = (s_pub ** c_priv) % P
# The math guarantees both compute the EXACT SAME shared secret!
# An eavesdropper only sees P, G, s_pub, c_pub, and cannot easily compute the secret.
#
# NOTE: For a high school project, we use a standard large prime.
# ==========================================

# A standard 1024-bit prime (RFC 2409) suitable for DH
P = 0xFFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE386BFB5A899FA5AE9F24117C4B1FE649286651ECE65381FFFFFFFFFFFFFFFF
G = 2 # Standard generator

def derive_aes_key(shared_secret):
    """
    AES requires a fixed-size 16, 24, or 32-byte key. 
    We hash the shared DH byte-string using SHA-256 to get a fixed 32-byte key for AES-256.
    """
    secret_bytes = shared_secret.to_bytes((shared_secret.bit_length() + 7) // 8, byteorder='big')
    return hashlib.sha256(secret_bytes).digest()

def aes_encrypt(plaintext, key):
    """
    Encrypts a string using AES in CBC (Cipher Block Chaining) mode.
    """
    # 1. Create a random 16-byte Initialization Vector (IV).
    # This ensures that identical plaintexts encrypt to different ciphertexts.
    iv = os.urandom(16)
    
    # 2. Create the AES cipher object with the derived key and IV.
    cipher = AES.new(key, AES.MODE_CBC, iv)
    
    # 3. Pad the plaintext so its length is an exact multiple of the AES block size (16 bytes).
    padded_data = pad(plaintext.encode('utf-8'), AES.block_size)
    
    # 4. Encrypt the data.
    ciphertext = cipher.encrypt(padded_data)
    
    # 5. Prepend IV to ciphertext so the receiver can extract it and decrypt properly.
    return iv + ciphertext

def aes_decrypt(ciphertext_with_iv, key):
    """
    Decrypts AES CBC encrypted data.
    """
    # 1. Extract the first 16-bytes to get the IV.
    iv = ciphertext_with_iv[:16]
    actual_ciphertext = ciphertext_with_iv[16:]
    
    # 2. Re-create the cipher object using the exact same key and IV.
    cipher = AES.new(key, AES.MODE_CBC, iv)
    
    # 3. Decrypt the text and remove the padding.
    decrypted_padded = cipher.decrypt(actual_ciphertext)
    plaintext = unpad(decrypted_padded, AES.block_size)
    
    return plaintext.decode('utf-8')

# ==========================================
# SERVER LOGIC (Multithreaded)
# ==========================================
class SecureServer:
    def __init__(self, host='127.0.0.1', port=65432):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # Allows reusing the port quickly after restarts
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        
        # Load the initial best score from the local system (server-side ONLY)
        self.best_score = self.load_best_score()
        
        # Thread lock array to prevent 'Race Conditions' where two clients
        # might try to overwrite the best_score file at the exact same moment.
        self.lock = threading.Lock()
        
        # Server's private Diffie-Hellman key (kept secret!)
        self.private_key_int = int.from_bytes(os.urandom(32), byteorder='big')
        
    def load_best_score(self):
        try:
            with open("best_scores.json", "r") as f:
                return json.load(f)
        except Exception:
            return {}
            
    def save_best_score(self, scores_dict):
        with open("best_scores.json", "w") as f:
            json.dump(scores_dict, f)

    def start(self):
        """Starts the server in an infinite loop listening for clients."""
        self.server_socket.listen(5)
        print(f"[*] Secure Server listening on {self.host}:{self.port}")
        try:
            while True:
                # Blocks until a new client connects
                client_sock, addr = self.server_socket.accept()
                print(f"[*] Connection accepted from {addr}")
                
                # Create a entirely new Thread to handle this client
                # so the main thread can go back to waiting for more clients.
                client_thread = threading.Thread(target=self.handle_client, args=(client_sock,))
                client_thread.start()
        except KeyboardInterrupt:
            print("\n[*] Server shutting down.")
            self.server_socket.close()

    def handle_client(self, client_sock):
        """Handles the cryptology exchange and data processing for a single client."""
        try:
            # 1. KEY EXCHANGE: Receive client's public key
            client_pub_bytes = client_sock.recv(4096)
            if not client_pub_bytes:
                return
            client_pub_int = int.from_bytes(client_pub_bytes, byteorder='big')
            
            # 2. KEY EXCHANGE: Send server's public computational key
            server_pub_int = pow(G, self.private_key_int, P)
            # Send the bytes representing the integer public key
            client_sock.sendall(server_pub_int.to_bytes((server_pub_int.bit_length() + 7) // 8, byteorder='big'))
            
            # 3. COMPUTE SHARED SECRET MATH: (Client_Pub ^ Server_Priv) mod P
            shared_secret = pow(client_pub_int, self.private_key_int, P)
            aes_key = derive_aes_key(shared_secret)
            
            # 4. RECEIVE ENCRYPTED PAYLOAD
            encrypted_payload = client_sock.recv(4096)
            if encrypted_payload:
                decrypted_json = aes_decrypt(encrypted_payload, aes_key)
                data = json.loads(decrypted_json)
                
                # Verify if it's sending a new score with a username
                username = data.get("username", "Unknown")
                if "new_score" in data:
                    new_score = data["new_score"]
                    
                    # Thread-safe write update using Locks
                    with self.lock:
                        current_best = self.best_score.get(username, 0)
                        if new_score > current_best:
                            print(f"[+] New high score achieved by {username}: {new_score}")
                            self.best_score[username] = new_score
                            self.save_best_score(self.best_score)
                
                # Send the specific user's tracked best score back to the client, encrypted
                personal_best = self.best_score.get(username, 0)
                response = json.dumps({"best_score": personal_best})
                encrypted_response = aes_encrypt(response, aes_key)
                client_sock.sendall(encrypted_response)
                
        except Exception as e:
            print(f"[-] Error handling client: {e}")
        finally:
            client_sock.close()

# ==========================================
# CLIENT LOGIC
# ==========================================
class SecureClient:
    def __init__(self, host='127.0.0.1', port=65432):
        self.host = host
        self.port = port
        
        # Client's private Diffie-Hellman key (kept secret locally on player's PC!)
        self.private_key_int = int.from_bytes(os.urandom(32), byteorder='big')

    def send_score_and_get_best(self, current_score, username="Unknown"):
        """Connects to server, exchanges keys, encrypts the score + username, and gets the personal best score."""
        client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        try:
            client_sock.connect((self.host, self.port))
            
            # 1. KEY EXCHANGE: Compute & Send client's public key
            client_pub_int = pow(G, self.private_key_int, P)
            client_sock.sendall(client_pub_int.to_bytes((client_pub_int.bit_length() + 7) // 8, byteorder='big'))
            
            # 2. KEY EXCHANGE: Receive server's public key
            server_pub_bytes = client_sock.recv(4096)
            server_pub_int = int.from_bytes(server_pub_bytes, byteorder='big')
            
            # 3. COMPUTE SHARED SECRET MATH: (Server_Pub ^ Client_Priv) mod P
            shared_secret = pow(server_pub_int, self.private_key_int, P)
            aes_key = derive_aes_key(shared_secret)
            
            # 4. ENCRYPT AND SEND PAYLOAD (the score and username)
            payload = json.dumps({"new_score": current_score, "username": username})
            encrypted_payload = aes_encrypt(payload, aes_key)
            client_sock.sendall(encrypted_payload)
            
            # 5. RECEIVE AND DECRYPT RESPONSE
            encrypted_response = client_sock.recv(4096)
            decrypted_response = aes_decrypt(encrypted_response, aes_key)
            data = json.loads(decrypted_response)
            
            return data.get("best_score", current_score)
            
        except ConnectionRefusedError:
            print("[-] Could not connect to the server. Is it running?")
            return current_score
        except Exception as e:
            print(f"[-] Connection error: {e}")
            return current_score
        finally:
            client_sock.close()

if __name__ == "__main__":
    # Test script utility
    print("=== Secure Network Tester ===")
    choice = input("Run as (S)erver or (C)lient? ").lower()
    if choice == 's':
        server = SecureServer()
        server.start()
    elif choice == 'c':
        client = SecureClient()
        user = input("Enter your username: ")
        score = input("Enter a score to send (simulate game over): ")
        best = client.send_score_and_get_best(int(score), user)
        print(f"Server acknowledged! The personal best score for {user} is now: {best}")
