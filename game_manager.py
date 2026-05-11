"""
game_manager.py – מודול ניהול המשחק (Game Manager Module)

This module contains the GameManager class, which is the top-level controller
for the entire Pygame application. It owns the Pygame initialization, the
main menu → game → score loop, and all supporting game-object classes.

Classes defined here:
    GameManager  – Top-level application controller (Pygame init + main loop)
    MainMenu     – Title screen with start and mute buttons
    Game         – Core gameplay loop (meteors, player, score, difficulty)
    Background   – Scrolling star-field backdrop
    Player       – Player sprite with movement, animation, and power-ups
    Meteor       – Falling meteor obstacle
    Particle     – Single particle used by Explosion
    Explosion    – Particle-burst effect on meteor collision
    PowerUp      – Collectible power-up item (heart / bubble / shoe)

Author: Tahir – Cyber Project 2026 (Bagrut 5-Unit)
"""

import pygame
import math
import random
import json
import sys
import time
from network_handler import NetworkHandler
from utils import circle_rect_collision, save_best_score, load_best_score
from game_objects import Background, Player, Meteor, Particle, Explosion, PowerUp

# ─── Server connection constants ───────────────────────────────────────────────
SERVER_IP   = "127.0.0.1"
SERVER_PORT = 5555


# ===================== מחלקת GameManager =====================
class GameManager:
    """
    Top-level application controller for the Meteorite game.

    Responsibilities:
        1. Initialize the Pygame engine and display surface exactly once.
        2. Manage the main application loop: Main-Menu → Game → score check.
        3. Persist the best score to disk between sessions.

    This class exists so that mainClass.py remains a minimal entry point
    (import + run), satisfying the Bagrut OOP separation requirement.

    Attributes:
        SCREEN_WIDTH  (int): Window width in pixels.
        SCREEN_HEIGHT (int): Window height in pixels.
        screen        (pygame.Surface): The primary display surface.
        muted         (bool): Whether sound is currently muted.
        best_score    (int): The highest score recorded across sessions.
    """

    def __init__(self):
        """
        Initialize Pygame, create the display window, and load the
        persisted best score from disk.
        """
        pygame.init()
        self.SCREEN_WIDTH = 800
        self.SCREEN_HEIGHT = 600
        self.screen = pygame.display.set_mode(
            (self.SCREEN_WIDTH, self.SCREEN_HEIGHT)
        )
        pygame.display.set_caption("משחק מטאורים")
        self.muted = False
        self.best_score = load_best_score("best_score.json")
        # יאוכלס על-ידי AuthScreen לפני כניסה לתפריט הראשי
        self.credentials = None
        # יאוכלס על-ידי LobbyScreen — {"action": "create"} או {"action": "join", "room_code": "1234"}
        self.room_choice  = None
        # NetworkHandler — יאוכלס ב-run() לאחר חיבור מוצלח
        self.network_handler = None

    def run(self):
        """
        Execute the main application loop — Task 3.4.

        Flow:
            1.  Connect NetworkHandler + DH handshake (synchronous).
            2.  Auth loop: show AuthScreen, send LOGIN/REGISTER, retry on AUTH_FAIL.
            3.  Start background listen thread.
            4.  Lobby loop: show LobbyScreen, send CREATE_ROOM/JOIN_ROOM,
                wait inside WaitingScreen for ROOM_READY + GAME_START.
            5.  Main game loop: MainMenu → Game → update best_score → repeat.
        """
        # ── שלב 1: חיבור לשרת + לחיצת יד Diffie-Hellman (סינכרוני) ─────────
        print(f"[CLIENT - NET] Connecting to {SERVER_IP}:{SERVER_PORT}...")
        nh = NetworkHandler(SERVER_IP, SERVER_PORT)
        nh.connect()          # DH handshake מתבצע כאן — מפתח AES נגזר
        self.network_handler = nh

        # ── שלב 2: לולאת אימות (ניסיון חוזר עד AUTH_OK) ───────────────────
        # auth_error מועבר בחזרה ל-AuthScreen אם השרת דחה את הפרטים
        auth_error = ""
        while True:
            auth = AuthScreen(self.screen, self.SCREEN_WIDTH, self.SCREEN_HEIGHT)
            auth.error_msg = auth_error          # הצג שגיאת שרת אם קיימת
            self.credentials = auth.run()        # בלוק עד לחיצת Submit תקינה

            # שלח REGISTER / LOGIN — סינכרוני לפני start_listening()
            response = nh.send_auth(self.credentials)
            if response.get("type") == "AUTH_OK":
                print(f"[CLIENT - NET] Auth OK for '{self.credentials['username']}'")
                break
            # השרת דחה → הצג את הסיבה בפעם הבאה
            auth_error = f"Server: {response.get('reason', 'Authentication failed.')}"

        # ── שלב 3: הפעל Thread אזנה ברקע (רק אחרי אימות מוצלח) ────────────
        nh.start_listening()

        # ── שלב 4: לולאת לובי (ניסיון חוזר אם JOIN נכשל) ──────────────────
        lobby_error = ""
        while True:
            lobby = LobbyScreen(
                self.screen, self.SCREEN_WIDTH, self.SCREEN_HEIGHT,
                self.credentials["username"]
            )
            lobby.error_msg = lobby_error        # שגיאת שרת מניסיון קודם
            self.room_choice = lobby.run()

            # שלח CREATE_ROOM או JOIN_ROOM דרך התור
            if self.room_choice["action"] == "create":
                nh.send({"type": "CREATE_ROOM"})
            else:
                nh.send({
                    "type":      "JOIN_ROOM",
                    "room_code": self.room_choice["room_code"]
                })

            # WaitingScreen: מנהל את כל שלבי ההמתנה עד GAME_START
            waiting = WaitingScreen(
                self.screen, self.SCREEN_WIDTH, self.SCREEN_HEIGHT,
                self.room_choice, nh
            )
            result = waiting.run()   # מחזיר "start" או "error"

            if result == "start":
                break                # יצאנו — אפשר להתחיל משחק
            # ROOM_ERROR → חזור ללובי עם הסיבה
            lobby_error = waiting.error_msg

        # ── שלב 5: לולאת משחק ראשית ────────────────────────────────────────
        while True:
            menu = MainMenu(
                self.screen,
                self.SCREEN_WIDTH,
                self.SCREEN_HEIGHT,
                self.muted,
                self.best_score,
            )
            self.muted = menu.run()

            game = Game(self.screen, self.muted, network_handler=nh)
            last_score = game.run()

            if last_score > self.best_score:
                self.best_score = last_score


# ===================== מחלקת MainMenu =====================
class MainMenu:
    def __init__(self, screen, screen_width, screen_height, muted, best_score):
        self.screen = screen
        self.SCREEN_WIDTH = screen_width
        self.SCREEN_HEIGHT = screen_height
        self.background = Background(screen_width, screen_height, num_stars=150)
        self.muted = muted
        self.title_font = pygame.font.Font(None, 108)
        self.button_font = pygame.font.Font(None, 48)
        self.start_button = None
        self.mute_button = None
        self.clock = pygame.time.Clock()
        self.best_score = best_score
        pygame.mixer.music.load("assets\\sounds\\Free Video Game Music - HeatleyBros - 8 Bit Let's Go.mp3")
        pygame.mixer.music.play(-1)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                save_best_score(self.best_score, "best_score.json")
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                save_best_score(self.best_score, "best_score.json")
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_pos = pygame.mouse.get_pos()
                if self.start_button.collidepoint(mouse_pos):
                    return True
                elif self.mute_button.collidepoint(mouse_pos):
                    self.toggle_mute()
        return False

    def toggle_mute(self):
        self.muted = not self.muted

    def draw(self):
        self.screen.fill((0, 0, 0))
        self.background.draw(self.screen)

        # Draw title
        title_surf = self.title_font.render("MAIN MENU", True, (255, 255, 255))
        title_rect = title_surf.get_rect(center=(self.SCREEN_WIDTH // 2, 170))
        self.screen.blit(title_surf, title_rect)

        # Draw BestScore
        title_surf = self.button_font.render("BEST SCORE: " + str(self.best_score), True, (255, 255, 255))
        title_rect = title_surf.get_rect(center=(self.SCREEN_WIDTH // 2, self.SCREEN_HEIGHT // 2 - 240))
        self.screen.blit(title_surf, title_rect)

        # Draw start button
        start_text = "Start Game"
        start_surf = self.button_font.render(start_text, True, (255, 255, 255))
        start_rect = start_surf.get_rect(center=(self.SCREEN_WIDTH // 2, self.SCREEN_HEIGHT // 2))
        pygame.draw.rect(self.screen, (0, 128, 0), start_rect.inflate(20, 10))
        self.screen.blit(start_surf, start_rect)
        self.start_button = start_rect.inflate(20, 10)

        # Draw mute button
        mute_text = "Mute" if not self.muted else "Unmute"
        mute_surf = self.button_font.render(mute_text, True, (255, 255, 255))
        mute_rect = mute_surf.get_rect(topleft=(20, 20))
        pygame.draw.rect(self.screen, (128, 0, 0), mute_rect.inflate(20, 20))
        self.screen.blit(mute_surf, mute_rect)
        self.mute_button = mute_rect.inflate(20, 10)

        pygame.display.flip()

    def run(self):
        while True:
            self.background.update()
            if self.handle_events():
                return self.muted
            if self.muted:
                pygame.mixer.music.set_volume(0)
            else:
                pygame.mixer.music.set_volume(0.05)
            self.draw()
            self.clock.tick(60)



# ===================== מחלקת AuthScreen =====================
class AuthScreen:
    """
    מסך התחברות והרשמה.
    מציג שדות קלט ל-Username ו-Password.
    תומך בשני מצבים: 'login' ו-'register', הניתנים להחלפה בלחיצת כפתור.

    מחזיר dict עם:
        {"action": "login" / "register", "username": str, "password": str}
    """

    def __init__(self, screen, screen_width, screen_height):
        self.screen = screen
        self.SCREEN_WIDTH = screen_width
        self.SCREEN_HEIGHT = screen_height
        self.background = Background(screen_width, screen_height, num_stars=150)
        self.clock = pygame.time.Clock()

        self.mode = "register"      # מצב נוכחי: 'login' או 'register'
        self.username = ""       # תוכן שדה ה-Username
        self.password = ""       # תוכן שדה ה-Password
        self.confirm_password = "" # תוכן שדה אימות סיסמה (מוצג רק בהרשמה)
        self.active_field = "username"  # איזה שדה מקבל קלט כרגע
        self.error_msg = ""      # הודעת שגיאה (ריקה = אין שגיאה)

        self.title_font  = pygame.font.Font(None, 90)
        self.label_font  = pygame.font.Font(None, 38)
        self.button_font = pygame.font.Font(None, 46)
        self.small_font  = pygame.font.Font(None, 30)

        # Rects מוגדרים ב-draw() וישמשו ל-collision ב-handle_events()
        self.username_rect  = None
        self.password_rect  = None
        self.confirm_rect   = None
        self.submit_button  = None
        self.switch_button  = None

        # מצמוץ סמן (cursor blink)
        self.cursor_timer   = 0
        self.cursor_visible = True

    def handle_events(self):
        """מעבד אירועים ומחזיר dict עם פרטי ההתחברות, או None אם אין עדיין."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()

            # --- קליקים ---
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse = pygame.mouse.get_pos()
                if self.username_rect and self.username_rect.collidepoint(mouse):
                    self.active_field = "username"
                elif self.password_rect and self.password_rect.collidepoint(mouse):
                    self.active_field = "password"
                elif self.mode == "register" and self.confirm_rect and self.confirm_rect.collidepoint(mouse):
                    self.active_field = "confirm_password"
                elif self.submit_button and self.submit_button.collidepoint(mouse):
                    return self._submit()
                elif self.switch_button and self.switch_button.collidepoint(mouse):
                    self._switch_mode()

            # --- הקלדה ---
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_TAB:
                    # Tab מחליף בין השדות
                    if self.active_field == "username":
                        self.active_field = "password"
                    elif self.active_field == "password":
                        self.active_field = "confirm_password" if self.mode == "register" else "username"
                    else:
                        self.active_field = "username"
                elif event.key == pygame.K_RETURN:
                    return self._submit()
                elif event.key == pygame.K_BACKSPACE:
                    if self.active_field == "username":
                        self.username = self.username[:-1]
                    elif self.active_field == "password":
                        self.password = self.password[:-1]
                    elif self.active_field == "confirm_password":
                        self.confirm_password = self.confirm_password[:-1]
                elif event.unicode and event.unicode.isprintable() and len(event.unicode) == 1:
                    # הוסף תו — מקסימום 20 תווים לכל שדה
                    # isprintable() מסנן תווי בקרה כגון \x00, \t וכו'
                    if self.active_field == "username" and len(self.username) < 20:
                        self.username += event.unicode
                    elif self.active_field == "password" and len(self.password) < 20:
                        self.password += event.unicode
                    elif self.active_field == "confirm_password" and len(self.confirm_password) < 20:
                        self.confirm_password += event.unicode

        return None

    def _submit(self):
        """בודק תקינות קלט ומחזיר את פרטי ההתחברות."""
        username = self.username.strip()
        password = self.password

        # --- בדיקה 1: שדות לא ריקים ---
        if not username or not password:
            self.error_msg = "Username and password cannot be empty!"
            return None

        # --- בדיקה 2: כללי שם משתמש ---
        if len(username) < 3:
            self.error_msg = "Username must be at least 3 characters."
            return None
        if " " in username:
            self.error_msg = "Username cannot contain spaces."
            return None

        # --- בדיקה 3: חוזק סיסמה (Register בלבד) ---
        # Login אינו בודק חוזק — המשתמש כבר נרשם בעבר
        if self.mode == "register":
            if password != self.confirm_password:
                self.error_msg = "Passwords do not match."
                return None
            if len(password) < 6:
                self.error_msg = "Password must be at least 6 characters."
                return None
            if not any(c.isupper() for c in password):
                self.error_msg = "Password must have at least one uppercase letter."
                return None
            if not any(c.isdigit() for c in password):
                self.error_msg = "Password must have at least one number."
                return None

        return {
            "action": self.mode,
            "username": username,
            "password": password,
        }

    def _switch_mode(self):
        """מחליף בין מצב Login ל-Register ומנקה שגיאות."""
        self.mode = "register" if self.mode == "login" else "login"
        self.error_msg = ""
        self.confirm_password = "" # נקה סיסמת אימות במעבר מצבים
        if self.active_field == "confirm_password":
            self.active_field = "password"

    def draw(self):
        self.screen.fill((0, 0, 0))
        self.background.draw(self.screen)

        cx = self.SCREEN_WIDTH // 2
        field_w, field_h = 400, 48
        field_x = cx - field_w // 2

        # --- כותרת ---
        title_text = "LOGIN" if self.mode == "login" else "REGISTER"
        title_surf = self.title_font.render(title_text, True, (255, 255, 255))
        self.screen.blit(title_surf, title_surf.get_rect(center=(cx, 100)))

        # --- שדה Username ---
        # מרווחים שונים בהתאם למצב כדי שהכל ייכנס במסך יפה
        un_y = 170 if self.mode == "register" else 195
        label = self.label_font.render("Username:", True, (200, 200, 200))
        self.screen.blit(label, (field_x, un_y - 30))
        # צבע שדה: כחול אם פעיל, אפור כהה אם לא
        un_color = (0, 80, 160) if self.active_field == "username" else (50, 50, 50)
        self.username_rect = pygame.Rect(field_x, un_y, field_w, field_h)
        pygame.draw.rect(self.screen, un_color, self.username_rect)
        pygame.draw.rect(self.screen, (255, 255, 255), self.username_rect, 2)
        un_surf = self.label_font.render(self.username, True, (255, 255, 255))
        self.screen.blit(un_surf, (field_x + 8, un_y + 8))
        # סמן מהבהב
        if self.active_field == "username" and self.cursor_visible:
            cursor_x = field_x + 8 + un_surf.get_width()
            pygame.draw.rect(self.screen, (255, 255, 255), (cursor_x, un_y + 6, 2, 36))

        # --- שדה Password ---
        pw_y = 265 if self.mode == "register" else 300
        label = self.label_font.render("Password:", True, (200, 200, 200))
        self.screen.blit(label, (field_x, pw_y - 30))
        pw_color = (0, 80, 160) if self.active_field == "password" else (50, 50, 50)
        self.password_rect = pygame.Rect(field_x, pw_y, field_w, field_h)
        pygame.draw.rect(self.screen, pw_color, self.password_rect)
        pygame.draw.rect(self.screen, (255, 255, 255), self.password_rect, 2)
        # סיסמה מוצגת כ-***
        pw_surf = self.label_font.render("*" * len(self.password), True, (255, 255, 255))
        self.screen.blit(pw_surf, (field_x + 8, pw_y + 8))
        if self.active_field == "password" and self.cursor_visible:
            cursor_x = field_x + 8 + pw_surf.get_width()
            pygame.draw.rect(self.screen, (255, 255, 255), (cursor_x, pw_y + 6, 2, 36))

        # --- שדה Confirm Password (רק בהרשמה) ---
        if self.mode == "register":
            cpw_y = 360
            label = self.label_font.render("Confirm Password:", True, (200, 200, 200))
            self.screen.blit(label, (field_x, cpw_y - 30))
            cpw_color = (0, 80, 160) if self.active_field == "confirm_password" else (50, 50, 50)
            self.confirm_rect = pygame.Rect(field_x, cpw_y, field_w, field_h)
            pygame.draw.rect(self.screen, cpw_color, self.confirm_rect)
            pygame.draw.rect(self.screen, (255, 255, 255), self.confirm_rect, 2)
            cpw_surf = self.label_font.render("*" * len(self.confirm_password), True, (255, 255, 255))
            self.screen.blit(cpw_surf, (field_x + 8, cpw_y + 8))
            if self.active_field == "confirm_password" and self.cursor_visible:
                cursor_x = field_x + 8 + cpw_surf.get_width()
                pygame.draw.rect(self.screen, (255, 255, 255), (cursor_x, cpw_y + 6, 2, 36))

        # --- כפתור Submit ---
        btn_y = 445 if self.mode == "register" else 400
        submit_text = "Login" if self.mode == "login" else "Register"
        submit_surf = self.button_font.render(submit_text, True, (255, 255, 255))
        self.submit_button = submit_surf.get_rect(center=(cx, btn_y)).inflate(40, 14)
        pygame.draw.rect(self.screen, (0, 128, 0), self.submit_button)
        self.screen.blit(submit_surf, submit_surf.get_rect(center=self.submit_button.center))

        # --- כפתור החלפת מצב ---
        switch_y = 505 if self.mode == "register" else 460
        switch_text = "No account? Register" if self.mode == "login" else "Have an account? Login"
        switch_surf = self.small_font.render(switch_text, True, (100, 180, 255))
        self.switch_button = switch_surf.get_rect(center=(cx, switch_y))
        self.screen.blit(switch_surf, self.switch_button)

        # --- הודעת שגיאה ---
        err_y = 555 if self.mode == "register" else 510
        if self.error_msg:
            err_surf = self.small_font.render(self.error_msg, True, (255, 80, 80))
            self.screen.blit(err_surf, err_surf.get_rect(center=(cx, err_y)))

        pygame.display.flip()

    def run(self):
        """לולאה ראשית — רצה עד שהמשתמש לוחץ Submit עם שדות תקינים."""
        while True:
            self.background.update()

            # עדכון מצמוץ הסמן (כל 30 פריימים)
            self.cursor_timer += 1
            if self.cursor_timer >= 30:
                self.cursor_timer = 0
                self.cursor_visible = not self.cursor_visible

            result = self.handle_events()
            if result is not None:
                return result

            self.draw()
            self.clock.tick(60)


# ===================== מחלקת WaitingScreen =====================
class WaitingScreen:
    """
    מסך המתנה — Task 3.4.

    מנהל ארבעה מצבים עד לקבלת GAME_START מהשרת:
        'connecting'       – ממתין ל-ROOM_CREATED / ROOM_JOINED / ROOM_ERROR
        'waiting_opponent' – יוצר החדר ממתין לשחקן שני (ROOM_READY relay)
        'ready_prompt'     – שני שחקנים בחדר; מציג כפתור READY
        'waiting_start'    – PLAYER_READY נשלח; ממתין ל-GAME_START

    Returns:
        "start" – התקבל GAME_START; המשחק יכול להתחיל.
        "error" – התקבל ROOM_ERROR; ה-caller חוזר ללובי.
    """

    def __init__(self, screen, screen_width, screen_height,
                 room_choice: dict, network_handler):
        self.screen       = screen
        self.SCREEN_WIDTH  = screen_width
        self.SCREEN_HEIGHT = screen_height
        self.room_choice   = room_choice   # {"action": "create"} / {"action": "join", ...}
        self.nh            = network_handler
        self.background    = Background(screen_width, screen_height, num_stars=150)
        self.clock         = pygame.time.Clock()

        self.title_font  = pygame.font.Font(None, 72)
        self.label_font  = pygame.font.Font(None, 38)
        self.button_font = pygame.font.Font(None, 46)
        self.small_font  = pygame.font.Font(None, 30)
        self.code_font   = pygame.font.Font(None, 96)

        self.state             = "connecting"
        self.room_code         = room_choice.get("room_code", "")
        self.opponent_username = ""
        self.error_msg         = ""
        self.status_msg        = "Connecting"

        # כפתור READY — מוגדר ב-draw() ומשמש ב-handle_events()
        self.ready_button = None

        # אנימציית נקודות: ⬤ ⬤ ⬤
        self._dot_timer = 0
        self._dot_count = 0

    # ─────────────────────────────────────────────────────────────
    def _tick_dots(self):
        """מעדכן את אנימציית הנקודות (כל 20 פריימים)."""
        self._dot_timer += 1
        if self._dot_timer >= 20:
            self._dot_timer = 0
            self._dot_count = (self._dot_count + 1) % 4

    # ─────────────────────────────────────────────────────────────
    def handle_events(self):
        """מעבד אירועי Pygame. מחזיר False אם יש QUIT."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.state == "ready_prompt" and self.ready_button:
                    if self.ready_button.collidepoint(pygame.mouse.get_pos()):
                        # שלח PLAYER_READY לשרת דרך התור
                        self.nh.send({"type": "PLAYER_READY"})
                        self.state      = "waiting_start"
                        self.status_msg = "Waiting for opponent to be ready"
        return True

    # ─────────────────────────────────────────────────────────────
    def poll_network(self):
        """
        קורא הודעות נכנסות מהתור ומעדכן state בהתאם.

        Returns:
            "start" – GAME_START התקבל → אפשר להתחיל משחק.
            "error" – ROOM_ERROR התקבל → חזור ללובי.
            None    – אין הודעה שמסיימת את ה-WaitingScreen.
        """
        while True:
            msg = self.nh.receive()
            if msg is None:
                break
            msg_type = msg.get("type", "")

            if msg_type == "ROOM_CREATED":
                # יוצר החדר קיבל אישור + קוד
                self.room_code  = msg.get("room_code", "????")
                self.state      = "waiting_opponent"
                self.status_msg = "Waiting for opponent to join"

            elif msg_type == "ROOM_JOINED":
                # מצטרף קיבל אישור — שני שחקנים בחדר
                self.room_code         = msg.get("room_code", self.room_code)
                self.opponent_username = msg.get("opponent_username", "Opponent")
                self.state             = "ready_prompt"
                self.status_msg        = ""

            elif msg_type == "ROOM_READY":
                # Relay שמגיע ליוצר כשהשחקן השני הצטרף
                self.opponent_username = msg.get("opponent_username", "Opponent")
                self.state             = "ready_prompt"
                self.status_msg        = ""

            elif msg_type == "WAITING_FOR_OPPONENT":
                # רק אחד לחץ READY עדיין
                self.status_msg = "Waiting for opponent to be ready"

            elif msg_type == "GAME_START":
                print("[CLIENT - NET] GAME_START received — entering game loop.")
                return "start"

            elif msg_type == "ROOM_ERROR":
                self.error_msg = msg.get("reason", "Room error — please try again.")
                return "error"

        return None

    # ─────────────────────────────────────────────────────────────
    def draw(self):
        self.screen.fill((0, 0, 0))
        self.background.draw(self.screen)
        cx = self.SCREEN_WIDTH // 2
        dots = "." * self._dot_count

        if self.state == "connecting":
            title = self.title_font.render("Connecting", True, (255, 255, 255))
            self.screen.blit(title, title.get_rect(center=(cx, 160)))
            sub = self.label_font.render(dots, True, (180, 180, 180))
            self.screen.blit(sub, sub.get_rect(center=(cx, 230)))

        elif self.state == "waiting_opponent":
            title = self.title_font.render("LOBBY", True, (255, 255, 255))
            self.screen.blit(title, title.get_rect(center=(cx, 110)))

            lbl = self.label_font.render("Share this code with your friend:",
                                         True, (180, 180, 180))
            self.screen.blit(lbl, lbl.get_rect(center=(cx, 185)))

            # תיבה בולטת עם קוד החדר
            code_surf = self.code_font.render(self.room_code, True, (255, 220, 50))
            code_rect = code_surf.get_rect(center=(cx, 285))
            box = code_rect.inflate(48, 24)
            pygame.draw.rect(self.screen, (25, 25, 60), box, border_radius=14)
            pygame.draw.rect(self.screen, (100, 100, 200), box, 2, border_radius=14)
            self.screen.blit(code_surf, code_rect)

            wait_surf = self.small_font.render(
                self.status_msg + dots, True, (130, 130, 130))
            self.screen.blit(wait_surf, wait_surf.get_rect(center=(cx, 380)))

        elif self.state == "ready_prompt":
            title = self.title_font.render("READY?", True, (100, 220, 100))
            self.screen.blit(title, title.get_rect(center=(cx, 120)))

            opp = self.label_font.render(
                f"Opponent: {self.opponent_username}", True, (180, 220, 255))
            self.screen.blit(opp, opp.get_rect(center=(cx, 205)))

            room_lbl = self.small_font.render(
                f"Room: {self.room_code}", True, (110, 110, 110))
            self.screen.blit(room_lbl, room_lbl.get_rect(center=(cx, 255)))

            # כפתור READY
            ready_surf = self.button_font.render("READY", True, (255, 255, 255))
            self.ready_button = ready_surf.get_rect(center=(cx, 355)).inflate(60, 20)
            pygame.draw.rect(self.screen, (0, 160, 80),
                             self.ready_button, border_radius=10)
            self.screen.blit(ready_surf,
                             ready_surf.get_rect(center=self.ready_button.center))

        elif self.state == "waiting_start":
            title = self.title_font.render("WAITING", True, (255, 255, 255))
            self.screen.blit(title, title.get_rect(center=(cx, 150)))

            opp = self.label_font.render(
                f"Opponent: {self.opponent_username}", True, (180, 220, 255))
            self.screen.blit(opp, opp.get_rect(center=(cx, 240)))

            wait_surf = self.label_font.render(
                self.status_msg + dots, True, (140, 140, 140))
            self.screen.blit(wait_surf, wait_surf.get_rect(center=(cx, 310)))

        # שגיאה (מצב error — לפני החזרה ל-caller)
        if self.error_msg:
            err = self.small_font.render(self.error_msg, True, (255, 80, 80))
            self.screen.blit(err, err.get_rect(center=(cx, 490)))

        pygame.display.flip()

    # ─────────────────────────────────────────────────────────────
    def run(self):
        """
        לולאה ראשית — רצה עד קבלת GAME_START (מחזיר "start")
        או ROOM_ERROR (מחזיר "error").
        """
        while True:
            self.background.update()
            self._tick_dots()
            self.handle_events()

            result = self.poll_network()
            if result is not None:
                return result

            self.draw()
            self.clock.tick(60)


# ===================== מחלקת LobbyScreen =====================
class LobbyScreen:
    """
    מסך לובי — מוצג לאחר התחברות מוצלחת (Task 3.2).

    מציג שני כפתורים: 'Create Room' ו-'Join Room'.
    לחיצה על 'Join Room' מציגה שדה קלט בן 4 ספרות.
    ESC מהשדה חוזר לתצוגת הכפתורים הראשית.

    מחזיר:
        {"action": "create"}                     – השחקן רוצה לפתוח חדר חדש
        {"action": "join", "room_code": "1234"}  – השחקן רוצה להצטרף לחדר קיים
    """

    def __init__(self, screen, screen_width, screen_height, username: str):
        self.screen = screen
        self.SCREEN_WIDTH = screen_width
        self.SCREEN_HEIGHT = screen_height
        self.username = username
        self.background = Background(screen_width, screen_height, num_stars=150)
        self.clock = pygame.time.Clock()

        self.title_font  = pygame.font.Font(None, 90)
        self.label_font  = pygame.font.Font(None, 38)
        self.button_font = pygame.font.Font(None, 46)
        self.small_font  = pygame.font.Font(None, 30)

        # מצב UI
        self.show_join_input = False  # True = מציג את שדה קלט הקוד
        self.room_code_input = ""     # מה שהמשתמש הקליד (ספרות בלבד, עד 4)
        self.error_msg = ""

        # מצמוץ סמן — אותו דפוס כמו ב-AuthScreen
        self.cursor_timer   = 0
        self.cursor_visible = True

        # Rects — מוגדרים ב-draw(), ישמשו ל-collision ב-handle_events()
        self.create_button  = None
        self.join_button    = None
        self.confirm_button = None
        self.code_rect      = None

    def handle_events(self):
        """מעבד אירועים ומחזיר dict עם הבחירה, או None אם עדיין לא נבחר."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if self.show_join_input:
                    # ESC מסגור שדה הקוד — חוזר לתצוגת הכפתורים
                    self.show_join_input = False
                    self.room_code_input = ""
                    self.error_msg = ""
                else:
                    pygame.quit()
                    sys.exit()

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse = pygame.mouse.get_pos()
                if not self.show_join_input:
                    if self.create_button and self.create_button.collidepoint(mouse):
                        return {"action": "create"}
                    if self.join_button and self.join_button.collidepoint(mouse):
                        self.show_join_input = True
                        self.error_msg = ""
                else:
                    if self.confirm_button and self.confirm_button.collidepoint(mouse):
                        return self._submit_join()

            if event.type == pygame.KEYDOWN and self.show_join_input:
                if event.key == pygame.K_RETURN:
                    return self._submit_join()
                elif event.key == pygame.K_BACKSPACE:
                    self.room_code_input = self.room_code_input[:-1]
                elif event.unicode.isdigit() and len(self.room_code_input) < 4:
                    # מקבל ספרות בלבד — קוד חדר הוא מספרי תמיד
                    self.room_code_input += event.unicode

        return None

    def _submit_join(self):
        """מאמת שהקוד הוא בדיוק 4 ספרות ומחזיר את תוצאת הבחירה."""
        if len(self.room_code_input) != 4:
            self.error_msg = "Room code must be exactly 4 digits."
            return None
        return {"action": "join", "room_code": self.room_code_input}

    def draw(self):
        self.screen.fill((0, 0, 0))
        self.background.draw(self.screen)
        cx = self.SCREEN_WIDTH // 2

        # --- כותרת ---
        title_surf = self.title_font.render("LOBBY", True, (255, 255, 255))
        self.screen.blit(title_surf, title_surf.get_rect(center=(cx, 100)))

        # --- הודעת ברוך הבא ---
        welcome = self.label_font.render(f"Welcome, {self.username}!", True, (100, 210, 100))
        self.screen.blit(welcome, welcome.get_rect(center=(cx, 175)))

        if not self.show_join_input:
            # --- כפתור Create Room ---
            create_surf = self.button_font.render("Create Room", True, (255, 255, 255))
            self.create_button = create_surf.get_rect(center=(cx, 300)).inflate(40, 14)
            pygame.draw.rect(self.screen, (0, 100, 180), self.create_button)
            self.screen.blit(create_surf, create_surf.get_rect(center=self.create_button.center))

            # --- כפתור Join Room ---
            join_surf = self.button_font.render("Join Room", True, (255, 255, 255))
            self.join_button = join_surf.get_rect(center=(cx, 395)).inflate(40, 14)
            pygame.draw.rect(self.screen, (0, 140, 60), self.join_button)
            self.screen.blit(join_surf, join_surf.get_rect(center=self.join_button.center))

        else:
            # --- תצוגת שדה קלט קוד חדר ---
            prompt = self.label_font.render("Enter 4-digit Room Code:", True, (200, 200, 200))
            self.screen.blit(prompt, prompt.get_rect(center=(cx, 270)))

            field_w, field_h = 210, 56
            field_x = cx - field_w // 2
            field_y = 305
            self.code_rect = pygame.Rect(field_x, field_y, field_w, field_h)
            # צבע שדה: כחול כהה — עקבי עם AuthScreen
            pygame.draw.rect(self.screen, (0, 80, 160), self.code_rect)
            pygame.draw.rect(self.screen, (255, 255, 255), self.code_rect, 2)

            code_surf = self.button_font.render(self.room_code_input, True, (255, 255, 255))
            self.screen.blit(code_surf, (field_x + 10, field_y + 8))

            # סמן מהבהב
            if self.cursor_visible:
                cursor_x = field_x + 10 + code_surf.get_width()
                pygame.draw.rect(self.screen, (255, 255, 255),
                                 (cursor_x, field_y + 6, 2, 44))

            # --- כפתור אישור ---
            confirm_surf = self.button_font.render("Join", True, (255, 255, 255))
            self.confirm_button = confirm_surf.get_rect(center=(cx, 415)).inflate(40, 14)
            pygame.draw.rect(self.screen, (0, 140, 60), self.confirm_button)
            self.screen.blit(confirm_surf, confirm_surf.get_rect(center=self.confirm_button.center))

            # רמז ESC
            esc_surf = self.small_font.render("Press ESC to go back", True, (110, 110, 110))
            self.screen.blit(esc_surf, esc_surf.get_rect(center=(cx, 470)))

        # --- הודעת שגיאה ---
        if self.error_msg:
            err_surf = self.small_font.render(self.error_msg, True, (255, 80, 80))
            self.screen.blit(err_surf, err_surf.get_rect(center=(cx, 515)))

        pygame.display.flip()

    def run(self):
        """לולאה ראשית — רצה עד שהמשתמש בוחר Create או Join עם קוד תקין."""
        while True:
            self.background.update()

            # מצמוץ סמן (כל 30 פריימים)
            self.cursor_timer += 1
            if self.cursor_timer >= 30:
                self.cursor_timer = 0
                self.cursor_visible = not self.cursor_visible

            result = self.handle_events()
            if result is not None:
                return result

            self.draw()
            self.clock.tick(60)


# ===================== מחלקת Game =====================
class Game:
    def __init__(self, screen, muted=False, network_handler=None):
        self.SCREEN_WIDTH = 800
        self.SCREEN_HEIGHT = 600
        self.screen = screen
        self.background = Background(self.SCREEN_WIDTH, self.SCREEN_HEIGHT, num_stars=150)
        self.heartBar = pygame.image.load("assets/imgs/heartBar.png")
        self.heartBar = pygame.transform.scale(self.heartBar, (400, 73))
        self.BLACK = (0, 0, 0)
        pygame.display.set_caption("משחק מטאורים")
        self.clock = pygame.time.Clock()
        self.running = True
        self.frame_count = 0
        self.difficulty = 1
        self.score = 0
        self.scoreCooldown = 60
        self.score_timer = 0

        # player related
        self.player = Player(384, 284, self.SCREEN_WIDTH, self.SCREEN_HEIGHT)
        self.score_font = pygame.font.Font(None, 40)
        self.hud_font   = pygame.font.Font(None, 28)

        # meteor related
        self.spawn_cooldown = 70
        self.spawn_timer = 0
        self.meteors = []
        self.meteor_speed = 4
        self.explosions = []

        # powerup related
        self.powerup = None
        self.powerup_timer = 0
        self.powerup_spawn_cooldown = 600  # כל 10 שניות

        # ── Task 3.5: network state ───────────────────────────────────────────
        # nh=None → offline mode (MainMenu / solo play still works)
        self.nh = network_handler
        self._net_timer = 0          # throttle: send GAME_STATE every 6 frames (~10 Hz)

        # Opponent state received from server via OPPONENT_STATE relay
        self.opponent_score  = 0
        self.opponent_health = 100   # assume full health until first update

        # Set to True when OPPONENT_GAME_OVER arrives — we won!
        self.opponent_game_over   = False
        self.opponent_final_score = 0
        # ─────────────────────────────────────────────────────────────────────

        # music related
        if not muted:
            pygame.mixer.music.load("assets\\sounds\\Free Video Game Music - HeatleyBros - 8 Bit Let's Go.mp3")
            pygame.mixer.music.play(-1)
            pygame.mixer.music.set_volume(0.1)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                self.running = False

    def spawn_meteor(self):
        pool = random.randint(1, 5)
        if pool == 1:
            x = self.player.x
        else:
            x = random.randint(64, self.SCREEN_WIDTH - 64)
        self.meteors.append(Meteor(x, y=-64))
        # Task 3.5: שלח את ה-x של המטאור לשרת — יועבר כ-INCOMING_METEOR ליריב
        if self.nh is not None:
            self.nh.send({"type": "METEOR_THREAT", "x": x})

    def spawn_powerup(self):
        # בוחרים סוג אקראי מתוך שלושת האפשרויות
        power_type = random.choice(["heart", "bubble", "shoe"])
        x = random.randint(50, self.SCREEN_WIDTH - 50)
        y = -40
        self.powerup = PowerUp(x, y, power_type)

    def update_meteors(self):
        self.spawn_timer += 1
        if self.spawn_timer >= self.spawn_cooldown:
            self.spawn_meteor()
            self.spawn_timer = 0

        for meteor in self.meteors[:]:
            meteor.update(self.meteor_speed)
            if meteor.y > self.SCREEN_HEIGHT:
                self.meteors.remove(meteor)
            else:
                if circle_rect_collision(self.player.x, self.player.y - 10, self.player.player_offset_x - 128 * self.player.scale, meteor.rect):
                    self.explosions.append(Explosion(*meteor.rect.center))
                    self.meteors.remove(meteor)
                    # אם לשחקן יש מגן (bubble), הוא לא יקבל נזק
                    if not self.player.shield:
                        self.player.take_damage(meteor.damage)

    def update_powerups(self):
        self.powerup_timer += 1
        if self.powerup_timer >= self.powerup_spawn_cooldown - (self.difficulty * 30):
            self.powerup_timer = 0
            self.spawn_powerup()
        # אם יש יכולת פעילה, עדכן אותה
        if self.powerup:
            self.powerup.update()
            if self.powerup.y > self.SCREEN_HEIGHT:
                self.powerup = None
            else:
                if circle_rect_collision(self.player.x, self.player.y - 10, self.player.player_offset_x - 128 * self.player.scale, self.powerup.get_rect()):
                    self.player.apply_powerup(self.powerup.type)
                    self.powerup = None

    def increaseDiff(self):
        self.difficulty += 1
        print("Difficulty:", self.difficulty)
        self.meteor_speed *= 1.2
        if self.spawn_cooldown >= 20:
            self.spawn_cooldown -= 10

    def update_score(self):
        self.score_timer += 1
        if self.score_timer >= self.scoreCooldown:
            self.score_timer = 0
            self.score += 1 * self.difficulty

    def build_score_payload(self):
        """
        Construct a JSON-serializable dictionary representing the
        current score state, ready to be placed on the network queue.

        Returns:
            dict: A payload with the following keys:
                - 'type'      (str):   Always 'score_update'.
                - 'score'     (int):   The player's current score.
                - 'timestamp' (float): Unix epoch time when the
                                       payload was created.

        Note:
            This method does NOT send the payload. It only builds the
            dict so that the NetworkHandler can consume it later
            (Task 2.x / Phase 2).
        """
        return {
            "type": "score_update",
            "score": self.score,
            "timestamp": time.time(),
        }

    # ── Task 3.5: network send ────────────────────────────────────────────────
    def _send_network_state(self):
        """
        שולח GAME_STATE (score + health) לשרת כל 6 פריימים (~10 Hz).
        שולח רק אם NetworkHandler מחובר — שומר על תאימות עם מצב offline.
        """
        if self.nh is None:
            return
        self._net_timer += 1
        if self._net_timer >= 6:          # 60 FPS / 6 = 10 updates per second
            self._net_timer = 0
            self.nh.send({
                "type":   "GAME_STATE",
                "score":  self.score,
                "health": self.player.health,
            })

    # ── Task 3.5: network receive ─────────────────────────────────────────────
    def _poll_network(self):
        """
        מרוקן את תור ההודעות הנכנסות בכל פריים (לא חוסם).

        Handlers:
            OPPONENT_STATE    – עדכן opponent_score / opponent_health
            INCOMING_METEOR   – ספאון מטאור נוסף מה-x שנשלח ע"י היריב
            OPPONENT_GAME_OVER – היריב מת; סמן ניצחון ועצור את הלולאה
        """
        if self.nh is None:
            return
        while True:
            msg = self.nh.receive()
            if msg is None:
                break
            msg_type = msg.get("type", "")

            if msg_type == "OPPONENT_STATE":
                self.opponent_score  = msg.get("score",  0)
                self.opponent_health = msg.get("health", 0)

            elif msg_type == "INCOMING_METEOR":
                # היריב ספאון מטאור — אנחנו מקבלים אותו בקואורדינטת x שלו
                x = msg.get("x", self.SCREEN_WIDTH // 2)
                # clamp — מבטיח שהמטאור תמיד על המסך
                x = max(32, min(x, self.SCREEN_WIDTH - 32))
                self.meteors.append(Meteor(x, y=-64))
                print(f"[CLIENT - GAME] Incoming meteor from opponent at x={x}")

            elif msg_type == "OPPONENT_GAME_OVER":
                self.opponent_game_over   = True
                self.opponent_final_score = msg.get("final_score", 0)
                print(f"[CLIENT - GAME] Opponent lost with score {self.opponent_final_score} — we win!")
                self.running = False      # סיים את הלולאה שלנו

    # ─────────────────────────────────────────────────────────────────────────
    def update(self):
        keys = pygame.key.get_pressed()
        self.player.update(keys)
        self.update_meteors()
        self.update_powerups()

        for explosion in self.explosions[:]:
            explosion.update()
            if not explosion.active:
                self.explosions.remove(explosion)

        if self.player.health <= 0:
            self.running = False
        if self.difficulty < 10:
            self.frame_count += 1
            if self.frame_count >= 600:
                self.frame_count = 0
                self.increaseDiff()
        self.background.update()
        self.update_score()

        # Task 3.5: שלח מצב + קבל הודעות מהשרת כל פריים
        self._send_network_state()
        self._poll_network()

    def draw_health_bar(self):
        full_width = 350
        damage_taken = self.player.max_health - self.player.health
        current_width = full_width - (damage_taken / self.player.max_health * full_width)
        bar_height = 25
        bar_x = (self.SCREEN_WIDTH - full_width) // 2
        bar_y = self.SCREEN_HEIGHT - bar_height - 20
        pygame.draw.rect(self.screen, (75, 75, 75), (bar_x, bar_y, full_width, bar_height))
        pygame.draw.rect(self.screen, (damage_taken * 2.55, 255 - damage_taken * 2.55, 0), (bar_x, bar_y, current_width, bar_height))
        pygame.draw.rect(self.screen, (0, 0, 0), (bar_x, bar_y, full_width, bar_height), 2)

    def _draw_opponent_hud(self):
        """
        Task 3.5: מציג מידע על היריב בפינה הימנית העליונה.
        מוצג רק כאשר NetworkHandler מחובר.
        """
        if self.nh is None:
            return
        pad = 8
        box_w, box_h = 170, 54
        box_x = self.SCREEN_WIDTH - box_w - pad
        box_y = pad

        # רקע שקוף למחצה
        hud_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        hud_surf.fill((0, 0, 0, 150))
        self.screen.blit(hud_surf, (box_x, box_y))
        pygame.draw.rect(self.screen, (80, 80, 120),
                         (box_x, box_y, box_w, box_h), 1)

        # כותרת
        lbl = self.hud_font.render("OPPONENT", True, (180, 180, 255))
        self.screen.blit(lbl, (box_x + pad, box_y + 4))

        # ניקוד יריב
        score_txt = self.hud_font.render(
            f"Score: {self.opponent_score}", True, (220, 220, 220))
        self.screen.blit(score_txt, (box_x + pad, box_y + 22))

        # פס חיים יריב (אדום → ירוק)
        bar_x  = box_x + pad
        bar_y  = box_y + 40
        bar_w  = box_w - pad * 2
        bar_h  = 8
        ratio  = max(0, min(self.opponent_health / 100, 1))
        filled = int(bar_w * ratio)
        r = int(255 * (1 - ratio))
        g = int(255 * ratio)
        pygame.draw.rect(self.screen, (50, 50, 50),  (bar_x, bar_y, bar_w, bar_h))
        pygame.draw.rect(self.screen, (r, g, 0),     (bar_x, bar_y, filled, bar_h))
        pygame.draw.rect(self.screen, (120, 120, 120),(bar_x, bar_y, bar_w, bar_h), 1)

    def draw(self):
        self.screen.fill(self.BLACK)
        self.background.draw(self.screen)

        for explosion in self.explosions:
            explosion.draw(self.screen)

        if self.powerup:
            self.powerup.draw(self.screen)

        self.player.draw(self.screen)
        for meteor in self.meteors:
            meteor.draw(self.screen)
        self.draw_health_bar()
        self.screen.blit(self.heartBar, (180, 530))

        # ניקוד שחקן מקומי
        score_surf = self.score_font.render(str(self.score), True, (255, 255, 255))
        score_rect = score_surf.get_rect(topleft=(20, 20))
        self.screen.blit(score_surf, score_rect)

        # Task 3.5: HUD יריב
        self._draw_opponent_hud()

        pygame.display.flip()

    def run(self):
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(60)

        # Task 3.5: הודע לשרת על סיום המשחק עם הניקוד הסופי
        # השרת יעביר OPPONENT_GAME_OVER ליריב
        if self.nh is not None and not self.opponent_game_over:
            # שלח רק אם אנחנו שמתנו — לא אם הסיבה היא שהיריב מת
            self.nh.send({"type": "GAME_OVER", "final_score": self.score})
            print(f"[CLIENT - GAME] Sent GAME_OVER with score={self.score}")

        return self.score


# ===================== Game Object Classes =====================
# Moved to game_objects.py — imported at the top of this file.
# Background, Player, Meteor, Particle, Explosion, PowerUp

# Moved to utils.py — imported at the top of this file.
# circle_rect_collision, save_best_score, load_best_score
