import socket
import time

SERVER_IP = '127.0.0.1' # Localhost for testing
SERVER_PORT = 5555

def send_movement(client_socket, dx, dy):
    """
    Sends movement data using our custom byte-level protocol.
    Byte 0: Command Type (0x01 for Move)
    Bytes 1-2: dx (signed 16-bit integer)
    Bytes 3-4: dy (signed 16-bit integer)
    """
    try:
        # Command 1: Move
        command_type = (1).to_bytes(1, byteorder='big')
        
        # Convert movement vectors to 2-byte signed integers 
        x_bytes = dx.to_bytes(2, byteorder='big', signed=True)
        y_bytes = dy.to_bytes(2, byteorder='big', signed=True)
        
        # Construct the full packet
        packet = command_type + x_bytes + y_bytes
        
        # We use sendall() to ensure the entire buffer is sent.
        # This is critical over TCP where data might be fragmented.
        client_socket.sendall(packet)
        
    except socket.error as e:
        print(f"[ERROR] Failed to send data: {e}")

def main():
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect((SERVER_IP, SERVER_PORT))
        print("[CONNECTED] Connected to the game server.")
        
        # Simulating game loop sending sync updates
        for _ in range(5):
            print("[SYNC] Sending movement update...")
            send_movement(client, 5, -2) # Moved 5 right, 2 up
            time.sleep(0.5)  # Stay below the server's rate limit!
            
        # Simulate rate limit trigger by spamming (Anti-DoS demonstration)
        print("[TEST] Triggering Server Anti-DoS Rate Limiting...")
        for _ in range(30):
            send_movement(client, 1, 1)
            
    except ConnectionRefusedError:
        print("[ERROR] Server is not running.")
    finally:
        client.close()

if __name__ == "__main__":
    main()
