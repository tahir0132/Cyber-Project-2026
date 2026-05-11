"""
room_manager.py – Room lifecycle and server-side simulation (server-side only)

Contains the room management and authoritative game-loop thread.
Imported exclusively by server.py.

Dependencies:
    protocol  – encrypt_message, send_message (broadcast GAME_TICK)
    utils     – circle_rect_collision
    threading, random, json, time, math (stdlib)

Classes:
    RoomManager          – Creates/joins/removes game rooms; thread-safe.
    RoomSimulationThread – Daemon thread running the 30-FPS authoritative loop.

Author: Tahir – Cyber Project 2026 (Bagrut 5-Unit)
"""

import threading
import random
import json
import time
from protocol import send_message, encrypt_message
from utils import (
    circle_rect_collision,
    move_player, apply_powerup,
    SimpleRect,
    SCREEN_WIDTH, SCREEN_HEIGHT,
    PLAYER_HALF_W, PLAYER_HALF_H,
    PLAYER_SPEED,
    METEOR_RADIUS, METEOR_BASE_SPEED, METEOR_DAMAGE,
    SPAWN_INTERVAL, POWERUP_INTERVAL, DIFF_EVERY, SCORE_PER_TICK,
)




# ===================== מחלקת RoomManager =====================
class RoomManager:
    """
    מנהלת חדרי משחק (Room Manager) — Task 3.1 / Task 3.3

    שינוי מ-Task 3.1: מאחסנת ClientHandler references (לא raw sockets).
    הסיבה: לכל לקוח מפתח AES נפרד — שידור (relay) חייב לעבור דרך
    ה-handler של המקבל כדי להצפין עם המפתח הנכון.

    Attributes:
        _rooms (dict): {"1234": {"handlers": [h_A, h_B], "usernames": [str, str]}}
        _lock (threading.Lock): מגן על המילון מפני גישה בו-זמנית מ-Threads שונים.
    """

    MAX_PLAYERS_PER_ROOM = 2

    def __init__(self):
        # {room_code: {"handlers": [...], "usernames": [...]}}
        self._rooms = {}
        self._lock = threading.Lock()

    def create_room(self, handler, username: str) -> str:
        """
        יוצר חדר חדש ורושם את היוצר כשחקן הראשון.

        Args:
            handler (ClientHandler): ה-handler של הלקוח היוצר.
            username (str): שם המשתמש.

        Returns:
            str: קוד החדר, לדוגמה "1234".
        """
        with self._lock:
            while True:
                code = str(random.randint(1000, 9999))
                if code not in self._rooms:
                    break
            self._rooms[code] = {
                "handlers": [handler],
                "usernames": [username]
            }
            print(f"[SERVER - ROOM] Room '{code}' created by '{username}'.")
            return code

    def join_room(self, room_code: str, handler, username: str) -> bool:
        """
        מנסה להוסיף שחקן שני לחדר קיים.

        Returns:
            True  – הצטרף בהצלחה (החדר מלא כעת)
            False – החדר לא קיים, מלא, או שהמשתמש כבר בתוכו
        """
        with self._lock:
            room = self._rooms.get(room_code)
            if room is None:
                print(f"[SERVER - ROOM] Join failed — room '{room_code}' does not exist.")
                return False
            if room.get("solo", False):
                print(f"[SERVER - ROOM] Join failed — room '{room_code}' is a solo room.")
                return False
            if len(room["handlers"]) >= self.MAX_PLAYERS_PER_ROOM:
                print(f"[SERVER - ROOM] Join failed — room '{room_code}' is already full.")
                return False
            if handler in room["handlers"]:
                print(f"[SERVER - ROOM] Join failed — '{username}' is already in room '{room_code}'.")
                return False
            room["handlers"].append(handler)
            room["usernames"].append(username)
            print(f"[SERVER - ROOM] '{username}' joined room '{room_code}'. "
                  f"Players: {room['usernames']}")
            return True

    def get_other_handler(self, room_code: str, my_handler):
        """
        מחזיר את ה-ClientHandler של השחקן השני בחדר.
        משמש ב-Task 3.3 לשידור הודעות — ה-handler של המקבל מצפין בעצמו.

        Returns:
            ClientHandler — ה-handler של השחקן השני, או None אם עדיין לא הצטרף.
        """
        with self._lock:
            room = self._rooms.get(room_code)
            if room is None:
                return None
            for h in room["handlers"]:
                if h is not my_handler:
                    return h
            return None

    def mark_ready(self, room_code: str, handler) -> bool:
        """
        מסמן handler כמוכן למשחק. מחזיר True אם שני השחקנים מוכנים.
        ישמש ב-PLAYER_READY לשליחת GAME_START לשני הלקוחות.
        """
        with self._lock:
            room = self._rooms.get(room_code)
            if room is None:
                return False
            if "ready" not in room:
                room["ready"] = set()
            room["ready"].add(handler)
            return len(room["ready"]) >= self.MAX_PLAYERS_PER_ROOM

    def remove_client(self, room_code: str, handler):
        """
        מסיר לקוח מחדר. אם החדר מתרוקן — מוחק אותו לחלוטין.
        מנקה גם את קבוצת ה-ready כדי למנוע GAME_START מוקדם אם החדר יעשה שימוש חוזר.
        ישמש ב-Task 4.1 (Server Stability) לניהול ניתוקים.
        """
        with self._lock:
            room = self._rooms.get(room_code)
            if room is None:
                return
            if handler in room["handlers"]:
                idx = room["handlers"].index(handler)
                room["handlers"].pop(idx)
                room["usernames"].pop(idx)
                print(f"[SERVER - ROOM] Client removed from room '{room_code}'.")
            # נקה את קבוצת ה-ready — מנע GAME_START מוקדם אם החדר ימולא מחדש
            room.pop("ready", None)
            if "simulation" in room:
                room["simulation"].running = False
            if not room["handlers"]:
                del self._rooms[room_code]
                print(f"[SERVER - ROOM] Room '{room_code}' dissolved (empty).")


# ===================== מחלקת RoomSimulationThread =====================
class RoomSimulationThread(threading.Thread):
    """
    Thread שמריץ את הסימולציה של החדר בקצב קבוע (30 FPS).
    זהו ה"שרת הסמכותי" (Authoritative Server) — Phase B.

    Server owns: player positions, meteors, powerup, health, score, game-over.
    Client owns: rendering, animation, sound.
    """

    def __init__(self, room_code, handlers, room_manager):
        super().__init__(daemon=True)
        self.room_code    = room_code
        self.handlers     = handlers        # list[ClientHandler]
        self.room_manager = room_manager
        self.running      = True
        self.input_lock   = threading.Lock()
        self._tick        = 0

        # ── Per-player authoritative state ──────────────────────────────
        start_xs = [200, 600]   # p1 left, p2 right
        self.players_state = {}
        for i, h in enumerate(handlers):
            self.players_state[h] = {
                "x":            float(start_xs[i % 2]),
                "y":            300.0,
                "health":       100,
                "score":        0,
                "shield":       False,
                "shield_timer": 0,
                "speed":        float(PLAYER_SPEED),
                "keys":         [],      # [B2] updated by handle_input()
            }

        # ── Shared simulation state ──────────────────────────────────────
        self.meteors    = []    # list of {"x", "y", "radius"}
        self.powerup    = None  # {"x", "y", "type"} | None
        self.difficulty = 1

    # ── [B2] Store incoming keys list safely ────────────────────────────
    def handle_input(self, handler, keys):
        """
        Store the player's pressed-keys list.
        Called from ClientHandler._message_loop() on PLAYER_INPUT.

        Args:
            handler : ClientHandler that sent the input.
            keys    : list[str]  e.g. ["LEFT", "UP"]
                      (normalised to list if a bare str arrives before B3)
        """
        with self.input_lock:
            if handler not in self.players_state:
                return
            if isinstance(keys, str):
                keys = [keys] if keys else []
            self.players_state[handler]["keys"] = keys
            print(f"[SERVER - SIM] Room {self.room_code}: "
                  f"{handler._username} input -> {keys}")

    # ── Main loop ───────────────────────────────────────────────────────
    def run(self):
        print(f"[SERVER - SIM] Simulation started for room '{self.room_code}'")
        while self.running:
            tick_start  = time.time()
            self._tick += 1

            self._update_difficulty()

            with self.input_lock:
                for state in self.players_state.values():
                    self._move_player(state)

            self._update_meteors()
            self._update_powerup()
            self._detect_collisions()

            if self._tick % 60 == 0:
                for state in self.players_state.values():
                    if state["health"] > 0:
                        state["score"] += SCORE_PER_TICK * self.difficulty

            if self._check_game_over():
                break

            self._broadcast_tick()

            elapsed   = time.time() - tick_start
            time.sleep(max(0.0, (1.0 / 60.0) - elapsed))

        print(f"[SERVER - SIM] Simulation stopped for room '{self.room_code}'")

    # ── Helpers ─────────────────────────────────────────────────────────

    def _update_difficulty(self):
        if self._tick % DIFF_EVERY == 0 and self._tick > 0:
            self.difficulty += 1
            print(f"[SERVER - SIM] Room {self.room_code}: difficulty -> {self.difficulty}")

    def _move_player(self, state):
        """Delegate to utils.move_player (pure function, no Pygame)."""
        move_player(state)

    def _update_meteors(self):
        """Spawn a meteor every SPAWN_INTERVAL ticks; move & cull existing."""
        meteor_speed = METEOR_BASE_SPEED + (self.difficulty - 1)
        for m in self.meteors:
            m["y"] += meteor_speed
        self.meteors = [m for m in self.meteors if m["y"] < SCREEN_HEIGHT + 60]

        if self._tick % SPAWN_INTERVAL == 0:
            nx = random.randint(40, SCREEN_WIDTH - 40)
            self.meteors.append({"x": float(nx), "y": float(-METEOR_RADIUS * 2),
                                  "radius": METEOR_RADIUS})
            print(f"[SERVER - SIM] Room {self.room_code}: meteor spawned x={nx}")

    def _update_powerup(self):
        """Spawn one powerup every POWERUP_INTERVAL ticks; move it down."""
        if self.powerup is not None:
            self.powerup["y"] += 3
            if self.powerup["y"] > SCREEN_HEIGHT + 40:
                self.powerup = None
        elif self._tick % POWERUP_INTERVAL == 0 and self._tick > 0:
            ptype = random.choice(["heart", "bubble", "shoe"])
            self.powerup = {"x": float(random.randint(40, SCREEN_WIDTH - 40)),
                            "y": -20.0, "type": ptype}
            print(f"[SERVER - SIM] Room {self.room_code}: powerup spawned ({ptype})")

    def _detect_collisions(self):
        """Meteor -> player and powerup -> player collisions."""
        for h, state in self.players_state.items():
            if state["health"] <= 0:
                continue
            px, py = state["x"], state["y"]
            
            # The player is treated as a circle (as in the original Pygame code)
            player_cx = px
            player_cy = py - 10
            player_r  = 0  # Original code: 64 - 128*0.5 = 0 (point collision)

            # Meteor hits (Meteor is visually 128x128 pixels, drawn from top-left)
            hit = []
            for m in self.meteors:
                m_rect = SimpleRect(m["x"], m["x"] + 128, m["y"], m["y"] + 128)
                if circle_rect_collision(player_cx, player_cy, player_r, m_rect):
                    hit.append(m)
                    
            for m in hit:
                self.meteors.remove(m)
                if not state["shield"]:
                    state["health"] = max(0, state["health"] - METEOR_DAMAGE)
                    print(f"[SERVER - SIM] Room {self.room_code}: "
                          f"{h._username} hit! HP={state['health']}")

            # Powerup pickup (PowerUp is visually ~102x102 pixels, drawn from top-left)
            if self.powerup is not None:
                pu    = self.powerup
                purect = SimpleRect(pu["x"], pu["x"] + 102,
                                    pu["y"], pu["y"] + 102)
                if circle_rect_collision(player_cx, player_cy, player_r, purect):
                    self._apply_powerup(h, state, pu["type"])
                    self.powerup = None

        # Decrement shield timers
        for state in self.players_state.values():
            if state["shield"]:
                state["shield_timer"] -= 1
                if state["shield_timer"] <= 0:
                    state["shield"] = False

    def _apply_powerup(self, handler, state, ptype):
        """Delegate to utils.apply_powerup, then log."""
        apply_powerup(state, ptype)
        print(f"[SERVER - SIM] Room {self.room_code}: "
              f"{handler._username} picked up '{ptype}'")

    def _check_game_over(self):
        """Returns True and broadcasts GAME_OVER if any player is dead."""
        dead = [h for h, s in self.players_state.items() if s["health"] <= 0]
        if not dead:
            return False

        alive = [h for h in self.handlers if h not in dead]
        winner = alive[0]._username if alive else self.handlers[0]._username
        print(f"[SERVER - SIM] Room {self.room_code}: GAME_OVER — winner={winner}")

        for h in list(self.players_state.keys()):
            my_s      = self.players_state[h]
            opp_score = next((s["score"] for oh, s in self.players_state.items()
                              if oh is not h), 0)
            h.send_relay({"type": "GAME_OVER", "winner": winner,
                          "my_score": my_s["score"], "opponent_score": opp_score})
        self.running = False
        return True

    def _broadcast_tick(self):
        """Send a GAME_TICK snapshot to every connected handler."""
        for h in list(self.players_state.keys()):
            my_s     = self.players_state[h]
            opp_dict = next(
                ({"x": s["x"], "y": s["y"], "health": s["health"],
                  "score": s["score"], "shield": s["shield"]}
                 for oh, s in self.players_state.items() if oh is not h),
                None
            )
            tick_msg = {
                "type": "GAME_TICK",
                "my": {"x": my_s["x"], "y": my_s["y"],
                        "health": my_s["health"], "score": my_s["score"],
                        "shield": my_s["shield"]},
                "opponent":   opp_dict,
                "meteors":    [{"x": m["x"], "y": m["y"]} for m in self.meteors],
                "powerup":    ({"x": self.powerup["x"], "y": self.powerup["y"],
                                "type": self.powerup["type"]}
                               if self.powerup else None),
                "difficulty": self.difficulty,
            }
            h.send_relay(tick_msg)
