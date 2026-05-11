"""
server.py – שרת המשחק (Game Server)

Classes:
    Server        – מאזין ל-TCP ומפעיל ClientHandler לכל חיבור.
    ClientHandler – Thread ייעודי לניהול לקוח מחובר יחיד.

Imports from project modules (no inline duplication):
    protocol    – send_message, receive_message, encrypt_message,
                  decrypt_message, do_dh_handshake_server
    database    – Database
    room_manager – RoomManager, RoomSimulationThread

Author: Tahir – Cyber Project 2026 (Bagrut 5-Unit)
"""

import socket
import threading
import json
from protocol import (
    send_message, receive_message,
    encrypt_message, decrypt_message,
    do_dh_handshake_server,
)
from database import Database
from room_manager import RoomManager, RoomSimulationThread

SERVER_HOST = "0.0.0.0"
SERVER_PORT = 5555
MAX_CLIENTS = 10


class ClientHandler(threading.Thread):
    """Thread ייעודי לניהול לקוח מחובר יחיד."""

    def __init__(self, client_socket: socket.socket, client_address: tuple, db, room_manager):
        super().__init__(daemon=True)
        self._socket = client_socket
        self._address = client_address
        self._shared_key = None    # יאוכלס לאחר לחיצת יד DH
        self._db = db              # reference לאובייקט Database המשותף
        self._room_manager = room_manager  # reference לאובייקט RoomManager המשותף
        self._username = None      # יאוכלס לאחר LOGIN מוצלח
        self._room_code = None     # יאוכלס לאחר CREATE_ROOM / JOIN_ROOM
        self._on_finish = lambda: None

    def run(self):
        print(f"[SERVER - NET] Client connected: {self._address}")
        try:
            self._do_dh_handshake()
            self._message_loop()
        except (ConnectionError, OSError) as e:
            print(f"[SERVER - NET] Client {self._address} error: {e}")
        finally:
            if self._room_code is not None:
                self._room_manager.remove_client(self._room_code, self)
            self._socket.close()
            print(f"[SERVER - NET] Connection closed: {self._address}")
            self._on_finish()

    def _do_dh_handshake(self):
        """מבצע לחיצת יד DH — מואצל ל-protocol.do_dh_handshake_server()."""
        self._shared_key = do_dh_handshake_server(self._socket)
        print(f"[SERVER - NET] DH complete with {self._address} | fingerprint: {self._shared_key[:4].hex()}")

    def send_relay(self, data_dict: dict):
        """
        מצפין data_dict עם המפתח של ה-handler הזה ושולח ללקוח שלו.

        נקרא על-ידי ה-handler של ה-מקבל (לא השולח).
        כך כל לקוח מצפין עם המפתח שנגזר מלחיצת יד ה-DH שלו בלבד.

        Args:
            data_dict (dict): ההודעה לשליחה (תוצפן כאן).
        """
        if self._shared_key is None:
            return
        try:
            encrypted = encrypt_message(self._shared_key, json.dumps(data_dict))
            send_message(self._socket, encrypted)
            print(f"[SERVER - ROOM] Relay -> {self._address}: type={data_dict.get('type', '?')}")
        except (OSError, ConnectionError) as e:
            print(f"[SERVER - ROOM] Relay failed -> {self._address}: {e}")

    def _message_loop(self):
        """
        לולאת הודעות ראשית.
        כל הודעה מגיעה מוצפנת ב-AES-GCM, מפוענחת, ומנותבת לפי שדה 'type'.

        Supported message types (Auth):
            REGISTER       – רישום משתמש חדש
            LOGIN          – כניסת משתמש קיים

        Supported message types (Room — Task 3.1):
            CREATE_ROOM    – פתיחת חדר חדש
            JOIN_ROOM      – הצטרפות לחדר קיים

        Supported message types (Sync — Task 3.3):
            GAME_STATE     – Client->Server->Opponent: {score, health}
            METEOR_THREAT  – Client->Server->Opponent: {x}
            GAME_OVER      – Client->Server->Opponent: {final_score}

        Supported message types (Start — Task 3.3):
            PLAYER_READY   – Client->Server: player clicked READY
                             Server responds GAME_START when both ready,
                             else WAITING_FOR_OPPONENT.
        """
        while True:
            try:
                # שלב 1: קבל הודעה מוצפנת מהלקוח
                raw = receive_message(self._socket)
                # שלב 2: פענח: base64 -> bytes -> AES-GCM -> plaintext JSON string
                plaintext = decrypt_message(self._shared_key, raw.encode())
                message = json.loads(plaintext)
                # לוג מאובטח: מציג סוג ושם משתמש בלבד — לא מדפיסים סיסמאות!
                print(f"[SERVER - NET] Message from {self._address}: "
                      f"type={message.get('type', '?')}, user={message.get('username', '?')}")

                msg_type = message.get("type", "")
                username = message.get("username", "")
                password = message.get("password", "")

                # שלב 3: נתב לפי סוג ההודעה
                if msg_type == "REGISTER":
                    success = self._db.register_user(username, password)
                    if success:
                        # שמור את שם המשתמש — נדרש ל-CREATE_ROOM כדי שלא יחשב לאורח
                        self._username = username
                        response = {"type": "AUTH_OK", "action": "register"}
                    else:
                        response = {"type": "AUTH_FAIL", "reason": "Username already exists."}

                elif msg_type == "LOGIN":
                    success = self._db.login_user(username, password)
                    if success:
                        # שמור את שם המשתמש — נדרש ל-CREATE_ROOM ו-JOIN_ROOM
                        self._username = username
                        response = {"type": "AUTH_OK", "action": "login"}
                    else:
                        response = {"type": "AUTH_FAIL", "reason": "Invalid username or password."}

                elif msg_type == "CREATE_ROOM":
                    # לקוח מבקש לפתוח חדר חדש — חייב להיות מחובר (LOGIN)
                    if self._username is None:
                        response = {"type": "ROOM_ERROR", "reason": "Must be logged in to create a room."}
                    else:
                        # שמור handler ref (self) — לא socket — כדי לאפשר relay מוצפן
                        code = self._room_manager.create_room(self, self._username)
                        self._room_code = code
                        response = {"type": "ROOM_CREATED", "room_code": code}

                elif msg_type == "SOLO_GAME":
                    # [A2/A3] לקוח מבקש להתחיל משחק solo — חייב להיות מחובר
                    if self._username is None:
                        response = {"type": "ROOM_ERROR", "reason": "Must be logged in to play solo."}
                    else:
                        # צור חדר של שחקן אחד — אין צורך בשחקן שני
                        code = self._room_manager.create_room(self, self._username)
                        self._room_code = code
                        print(f"[SERVER - ROOM] Solo room '{code}' for '{self._username}' — starting immediately.")

                        # הפעל סימולציה מיידית (ללא המתנה ל-PLAYER_READY)
                        with self._room_manager._lock:
                            room = self._room_manager._rooms.get(code)
                            if room and "simulation" not in room:
                                room["solo"] = True   # מונע הצטרפות של שחקן שני
                                sim = RoomSimulationThread(code, room["handlers"].copy(), self._room_manager)
                                room["simulation"] = sim
                                sim.start()

                        # שלח GAME_START ישירות ללקוח — אין שחקן שני לחכות לו
                        response = {"type": "GAME_START"}

                elif msg_type == "JOIN_ROOM":
                    # לקוח מבקש להצטרף לחדר קיים לפי קוד 4 ספרות
                    if self._username is None:
                        response = {"type": "ROOM_ERROR", "reason": "Must be logged in to join a room."}
                    else:
                        code = message.get("room_code", "")
                        success = self._room_manager.join_room(code, self, self._username)
                        if success:
                            self._room_code = code
                            # החדר מלא — שלח ROOM_READY ליוצר (השחקן הראשון)
                            other = self._room_manager.get_other_handler(code, self)
                            if other:
                                other.send_relay({
                                    "type": "ROOM_READY",
                                    "opponent_username": self._username
                                })
                            opponent_name = other._username if other else "Unknown"
                            response = {
                                "type": "ROOM_JOINED",
                                "room_code": code,
                                "opponent_username": opponent_name
                            }
                        else:
                            response = {"type": "ROOM_ERROR", "reason": "Room not found or already full."}

                # ─── Phase B: Authoritative server — relay handlers removed ──────
                # GAME_STATE, METEOR_THREAT deprecated: server now owns all state.

                elif msg_type == "PLAYER_INPUT":
                    # [B3] Client sends full keys list e.g. ["LEFT", "UP"]
                    if self._room_code is None:
                        response = {"type": "ERROR", "reason": "Not in a room."}
                    else:
                        keys = message.get("keys", [])
                        with self._room_manager._lock:
                            room = self._room_manager._rooms.get(self._room_code)
                            if room and "simulation" in room:
                                room["simulation"].handle_input(self, keys)
                        response = {"type": "ACK"}

                elif msg_type == "PLAYER_READY":
                    # Client לחץ READY — סמן אותו כמוכן
                    # כששני מוכנים — שלח GAME_START לשניהם
                    if self._room_code is None:
                        response = {"type": "ERROR", "reason": "Not in a room."}
                    else:
                        both_ready = self._room_manager.mark_ready(self._room_code, self)
                        if both_ready:
                            other = self._room_manager.get_other_handler(self._room_code, self)
                            if other:
                                other.send_relay({"type": "GAME_START"})
                            print(f"[SERVER - ROOM] GAME_START for room '{self._room_code}'")
                            
                            # START THE SIMULATION THREAD
                            with self._room_manager._lock:
                                room = self._room_manager._rooms.get(self._room_code)
                                if room and "simulation" not in room:
                                    sim = RoomSimulationThread(self._room_code, room["handlers"].copy(), self._room_manager)
                                    room["simulation"] = sim
                                    sim.start()
                                    
                            response = {"type": "GAME_START"}
                        else:
                            response = {"type": "WAITING_FOR_OPPONENT"}


                elif msg_type == "LEAVE_ROOM":
                    # Client לחץ ESC במשחק — עזב את החדר; נקה את השרת
                    if self._room_code is not None:
                        self._room_manager.remove_client(self._room_code, self)
                        print(f"[SERVER - ROOM] '{self._username}' left room '{self._room_code}'.")
                        self._room_code = None
                    response = {"type": "ACK"}

                else:
                    # [B4] Unknown / deprecated type — discard silently, no crash
                    print(f"[SERVER - NET] Discarding unknown type '{msg_type}' from {self._address}")
                    response = {"type": "ACK"}

                # שלב 4: שלח תשובה מוצפנת חזרה ללקוח
                encrypted = encrypt_message(self._shared_key, json.dumps(response))
                send_message(self._socket, encrypted)
                print(f"[SERVER - NET] Response to {self._address}: {response}")

            except ValueError:
                # JSON לא תקין — הודעה פגומה או בלתי צפויה
                print(f"[SERVER - NET] Malformed message from {self._address} — dropping.")
                if self._shared_key is None:
                    # DH עדיין לא הושלם — לא ניתן להצפין תשובה
                    return
                response = {"type": "ERROR", "reason": "Malformed message."}
                encrypted = encrypt_message(self._shared_key, json.dumps(response))
                send_message(self._socket, encrypted)
                # לא מפסיקים את ה-Thread — מצפים להודעה הבאה


class Server:
    """מאזינה לחיבורים TCP ומפעילה ClientHandler לכל לקוח."""

    def __init__(self, host: str = SERVER_HOST, port: int = SERVER_PORT):
        self._host = host
        self._port = port
        self._server_socket = None
        # אתחול מסד הנתונים בעת יצירת השרת
        self._db = Database()
        self._room_manager = RoomManager()
        self._client_slots = threading.BoundedSemaphore(value=MAX_CLIENTS)

    def _client_finished(self):
        self._client_slots.release()

    def _start_client_handler(self, client_socket, client_address):
        if not self._client_slots.acquire(blocking=False):
            print(f"[SERVER - NET] Rejecting {client_address}: server is full.")
            client_socket.close()
            return False

        handler = ClientHandler(client_socket, client_address, self._db, self._room_manager)
        handler._on_finish = self._client_finished
        handler.finished_callback = self._client_finished
        handler.start()
        return True

    def start(self):
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self._host, self._port))
        self._server_socket.listen(MAX_CLIENTS)
        print(f"[SERVER - NET] Listening on {self._host}:{self._port}")
        try:
            while True:
                client_socket, client_address = self._server_socket.accept()
                self._start_client_handler(client_socket, client_address)
        except KeyboardInterrupt:
            print("[SERVER - NET] Shutting down.")
        finally:
            self._server_socket.close()


if __name__ == "__main__":
    Server().start()
