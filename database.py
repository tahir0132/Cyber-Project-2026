"""
database.py – SQLite3 persistence layer (server-side only)

Contains the Database class that handles all user data operations.
Imported exclusively by server.py — not by client.py.

Dependencies: stdlib only (sqlite3, hashlib, os, threading)

Classes:
    Database – Manages user registration and login against a SQLite3 DB.

Author: Tahir – Cyber Project 2026 (Bagrut 5-Unit)
"""

import sqlite3
import hashlib
import os
import threading

# נתיב ברירת מחדל לקובץ מסד הנתונים — תמיד ליד server.py
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game_database.db")


# ===================== מחלקת Database =====================
class Database:
    """
    מנהלת את כל פעולות ה-SQLite3 עבור שרת המשחק.

    Responsibilities:
        - אתחול מסד הנתונים ויצירת טבלאות נדרשות בעת הפעלת השרת.
        - מתן מתודות לביצוע שאילתות (Task 2.5: REGISTER ו-LOGIN).

    Attributes:
        _db_path (str): נתיב מלא לקובץ ה-.db.
        _lock (threading.Lock): נעילה לשימוש בTask 4.2 (מניעת תנאי מרוץ).
    """

    def __init__(self, db_path: str = DB_PATH):
        """
        מתחבר למסד הנתונים ומאתחל את הסכימה.

        Args:
            db_path (str): נתיב לקובץ ה-.db.
                           ברירת מחדל: game_database.db ליד server.py.
        """
        self._db_path = db_path
        # Lock מוגדר כאן — ישמש בTask 4.2 לעטוף כל כתיבה ל-DB
        self._lock = threading.Lock()
        self._initialize()

    def _initialize(self):
        """
        יוצר את טבלת Users אם היא עדיין לא קיימת.

        Schema:
            Username      TEXT  PRIMARY KEY  – מזהה ייחודי לכל שחקן
            Salt          TEXT  NOT NULL     – מחרוזת hex אקראית שנוצרת בהרשמה
            Password_Hash TEXT  NOT NULL     – תוצאת SHA-256 של (Salt + Password)

        Note:
            שימוש ב-IF NOT EXISTS מבטיח שהפעלה חוזרת של השרת לא תמחק נתונים קיימים.
            כל שאילתה מציגה לוג [SERVER - DB] לנראות במהלך הגנת הבגרות.
        """
        print(f"[SERVER - DB] Connecting to database: {self._db_path}")
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            # יצירת הטבלה — IF NOT EXISTS מונע כשל אם הטבלה כבר קיימת
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Users (
                    Username      TEXT PRIMARY KEY NOT NULL,
                    Salt          TEXT NOT NULL,
                    Password_Hash TEXT NOT NULL
                )
            """)
            conn.commit()
            print("[SERVER - DB] Users table verified / created successfully.")
        finally:
            # תמיד סגור את החיבור, גם אם יש שגיאה
            conn.close()

    def register_user(self, username: str, password: str) -> bool:
        """
        רושם משתמש חדש ב-DB.

        Flow:
            1. צור Salt אקראי (16 בייטים, hex) — שונה לכל משתמש.
            2. חשב SHA-256 של (Salt + Password).
            3. שמור Username, Salt, Hash בטבלת Users.

        Returns:
            True  — נרשם בהצלחה
            False — שם המשתמש כבר קיים (IntegrityError על ה-PRIMARY KEY)
        """
        salt = os.urandom(16).hex()   # Salt אקראי — לעולם לא נשלח ברשת
        password_hash = hashlib.sha256((salt + password).encode()).hexdigest()
        print(f"[SERVER - DB] Registering user: {username}")
        with self._lock:              # מנע תנאי מרוץ בין Threads
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                # שאילתה מפרמטרת — מונעת SQL Injection
                cursor.execute(
                    "INSERT INTO Users (Username, Salt, Password_Hash) VALUES (?, ?, ?)",
                    (username, salt, password_hash)
                )
                conn.commit()
                print(f"[SERVER - DB] User '{username}' registered successfully.")
                return True
            except sqlite3.IntegrityError:
                # Username הוא PRIMARY KEY — כפל מפעיל IntegrityError
                print(f"[SERVER - DB] Registration failed — '{username}' already exists.")
                return False
            finally:
                conn.close()

    def login_user(self, username: str, password: str) -> bool:
        """
        מאמת משתמש קיים.

        Flow:
            1. שלוף Salt ו-Hash מהטבלה לפי Username.
            2. חשב SHA-256 של (Salt + הסיסמה שהתקבלה).
            3. השווה ל-Hash השמור — אם זהים, ההתחברות מאושרת.

        Returns:
            True  — פרטים נכונים
            False — שם משתמש לא קיים או סיסמה שגויה
        """
        print(f"[SERVER - DB] Login attempt: {username}")
        with self._lock:              # מנע תנאי מרוץ בין Threads (Task 4.2)
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.cursor()
                # שאילתה מפרמטרת — מונעת SQL Injection
                cursor.execute(
                    "SELECT Salt, Password_Hash FROM Users WHERE Username = ?",
                    (username,)
                )
                row = cursor.fetchone()
            finally:
                conn.close()

        if row is None:
            print(f"[SERVER - DB] Login failed — user '{username}' not found.")
            return False

        stored_salt, stored_hash = row
        # חשב מחדש את ה-Hash עם ה-Salt שנשמר ב-DB
        input_hash = hashlib.sha256((stored_salt + password).encode()).hexdigest()

        if input_hash == stored_hash:
            print(f"[SERVER - DB] Login successful: {username}")
            return True
        else:
            print(f"[SERVER - DB] Login failed — wrong password for '{username}'.")
            return False
