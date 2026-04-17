import socket
import threading
import time
import struct
import random

HOST = '0.0.0.0'
PORT = 5555
MAX_MESSAGES_PER_SEC = 120

game_state_lock = threading.Lock()
players = {} 
clients = {}
game_status = 'LOBBY'

next_player_id = 1

def handle_client(client_socket, client_address):
    global next_player_id, game_status
    print(f"[NEW CONNECTION] {client_address} connected.")
    
    with game_state_lock:
        player_id = next_player_id
        next_player_id = (next_player_id % 65535) + 1
        players[player_id] = {'x': 400, 'y': 300, 'dead': False}
        clients[player_id] = client_socket

    try:
        # Send Welcome Packet with the new ID
        client_socket.sendall(struct.pack('!BH', 0, player_id))
    except:
        pass

    client_socket.settimeout(5.0)
    connected = True
    last_check_time = time.time()
    message_count = 0

    while connected:
        try:
            current_time = time.time()
            if current_time - last_check_time >= 1.0:
                message_count = 0
                last_check_time = current_time
            
            message_count += 1
            if message_count > MAX_MESSAGES_PER_SEC + 30:
                print(f"[SECURITY] {client_address} Exceeded Rate Limit.")
                break
                
            command_bytes = client_socket.recv(1)
            if not command_bytes: break
            command_type = command_bytes[0]
            
            if command_type == 1:  # Move Command
                payload_data = client_socket.recv(4)
                if not payload_data: break
                
                x, y = struct.unpack('!hh', payload_data)
                
                with game_state_lock:
                    players[player_id]['x'] = x
                    players[player_id]['y'] = y
                    
                    if game_status == 'RIVALRY':
                        # Only broadcast active player locations in fully active Rivalry Mode
                        active_players = [(pid, p) for pid, p in players.items() if not p['dead']]
                        num_players = len(active_players)
                        reply = bytearray(struct.pack('!BB', 1, num_players))
                        for pid, pdata in active_players:
                            reply.extend(struct.pack('!Hhh', pid, int(pdata['x']), int(pdata['y'])))
                    else:
                        reply = bytearray(struct.pack('!BB', 1, 0)) # Don't send coordinates during Lobby to save bandwidth

                client_socket.sendall(reply)

            elif command_type == 2: # Query Lobby Status
                with game_state_lock:
                    player_ids = list(players.keys())
                    payload = bytearray(struct.pack('!BB', 2, len(player_ids)))
                    for pid in player_ids:
                        name = players[pid].get('name', f"Player {pid}")
                        name_bytes = name.encode('utf-8')[:255]
                        payload.extend(struct.pack('!HB', pid, len(name_bytes)))
                        payload.extend(name_bytes)
                client_socket.sendall(payload)

            elif command_type == 6: # Register Username
                name_len_data = client_socket.recv(1)
                if name_len_data:
                    name_len = name_len_data[0]
                    name_bytes = client_socket.recv(name_len)
                    if name_bytes:
                        with game_state_lock:
                            if player_id in players:
                                players[player_id]['name'] = name_bytes.decode('utf-8')

            elif command_type == 3: # Initiate Rivalry
                with game_state_lock:
                    if len(players) >= 2:
                        game_status = 'RIVALRY'
                        # A single global random seed synchronized to all terminals 
                        # guarantees that identical meteors and powerups spawn on all PCs!
                        seed = random.randint(0, 999999)
                        for pid in players: players[pid]['dead'] = False
                        
                        bdata = struct.pack('!BI', 3, seed)
                        for sock in clients.values():
                            try: sock.sendall(bdata)
                            except: pass

            elif command_type == 4: # I died!
                with game_state_lock:
                    players[player_id]['dead'] = True
                    alive = [pid for pid, p in players.items() if not p['dead']]
                    # If this player was the 2nd to last to die, whoever is left is the Winner
                    if len(alive) <= 1 and game_status == 'RIVALRY':
                        game_status = 'LOBBY'
                        winner = alive[0] if len(alive) == 1 else 0
                        bdata = struct.pack('!BH', 4, winner)
                        for sock in clients.values():
                            try: sock.sendall(bdata)
                            except: pass

        except socket.timeout:
            continue
        except Exception as e:
            print("[SERVER ERROR]", e)
            break

    with game_state_lock:
        if player_id in players: del players[player_id]
        if player_id in clients: del clients[player_id]
        # if connection dropped randomly while playing, they implicitly died!
        if game_status == 'RIVALRY':
            alive = [pid for pid, p in players.items() if not p['dead']]
            if len(alive) <= 1:
                game_status = 'LOBBY'
                winner = alive[0] if len(alive) == 1 else 0
                bdata = struct.pack('!BH', 4, winner)
                for sock in clients.values():
                    try: sock.sendall(bdata)
                    except: pass
            
    client_socket.close()

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(5)
    print(f"[STARTING] Rivalry Game Server listening on {HOST}:{PORT}")
    try:
        while True:
            client_socket, client_address = server.accept()
            thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
            thread.daemon = True 
            thread.start()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()

if __name__ == "__main__":
    start_server()
