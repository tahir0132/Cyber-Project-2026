"""
utils.py – Pure-Python utility helpers (no Pygame, no network)

Shared by both client.py and server.py without importing Pygame.

Constants:
    SCREEN_WIDTH / SCREEN_HEIGHT   – canonical game resolution
    PLAYER_SPEED, PLAYER_HALF_W/H  – server-side player physics
    METEOR_RADIUS, METEOR_BASE_SPEED, METEOR_DAMAGE
    SPAWN_INTERVAL, POWERUP_INTERVAL, DIFF_EVERY, SCORE_PER_TICK

Types:
    SimpleRect – namedtuple(left, right, top, bottom) for circle_rect_collision

Functions:
    circle_rect_collision  – Circle-vs-AABB collision test (geometry only)
    move_player            – Apply pressed-key list to a player-state dict
    apply_powerup          – Apply a powerup type to a player-state dict
    save_best_score        – Persist best score to a JSON file on disk
    load_best_score        – Read best score from a JSON file on disk

Author: Tahir – Cyber Project 2026 (Bagrut 5-Unit)
"""

import math
import json
from collections import namedtuple

# ── Server-side game constants (shared by room_manager + any future module) ──
SCREEN_WIDTH      = 800
SCREEN_HEIGHT     = 600
PLAYER_SPEED      = 10          # px/tick — mirrors client Player.movement()
PLAYER_HALF_W     = 20          # half-width  for server collision box
PLAYER_HALF_H     = 20          # half-height for server collision box
METEOR_RADIUS     = 20          # px
METEOR_BASE_SPEED = 4           # px/tick at difficulty 1
METEOR_DAMAGE     = 10          # HP per meteor hit
SPAWN_INTERVAL    = 70          # ticks between meteor spawns  (~1.1s @ 60 FPS)
POWERUP_INTERVAL  = 600         # ticks between powerup spawns (~10 s @ 60 FPS)
DIFF_EVERY        = 600         # ticks per difficulty level   (~10 s @ 60 FPS)
SCORE_PER_TICK    = 1

# Duck-typed rect accepted by circle_rect_collision (no Pygame on server)
SimpleRect = namedtuple("SimpleRect", ["left", "right", "top", "bottom"])


# ===================== Collision Helper =====================

def circle_rect_collision(cx, cy, r, rect):
    """
    Check collision between a circle and an axis-aligned bounding box.

    Uses the 'closest point on rectangle' algorithm:
    find the point on the rectangle nearest to the circle center,
    then check if the squared distance is within the circle's squared radius.

    Args:
        cx  (float): Circle centre x-coordinate.
        cy  (float): Circle centre y-coordinate.
        r   (float): Circle radius.
        rect       : Any object with .left, .right, .top, .bottom attributes
                     (e.g. a pygame.Rect — but this function does NOT import Pygame).

    Returns:
        bool: True if the circle and rectangle overlap, False otherwise.
    """
    closest_x = max(rect.left, min(cx, rect.right))
    closest_y = max(rect.top,  min(cy, rect.bottom))
    dx = cx - closest_x
    dy = cy - closest_y
    return (dx * dx + dy * dy) <= (r * r)



# ===================== Player Physics =====================

def move_player(state):
    """
    Apply the player's current keys list to their x/y position.
    Mirrors client Player.movement() exactly, using string key names.

    Args:
        state (dict): player-state dict with keys:
                      x, y, speed, keys (list[str])
                      Modified in-place.
    """
    keys  = state["keys"]
    x, y  = state["x"], state["y"]
    spd   = state["speed"]
    has_l = "A" in keys
    has_r = "D" in keys
    has_u = "W" in keys
    has_d = "S" in keys

    if has_l and x > 45:
        if has_u and y > 50:
            x -= spd / math.sqrt(2); y -= spd / math.sqrt(2)
        elif has_d and y < SCREEN_HEIGHT - 50:
            x -= spd / math.sqrt(2); y += spd / math.sqrt(2)
        else:
            x -= spd
    elif has_r and x < SCREEN_WIDTH - 40:
        if has_u and y > 50:
            x += spd / math.sqrt(2); y -= spd / math.sqrt(2)
        elif has_d and y < SCREEN_HEIGHT - 50:
            x += spd / math.sqrt(2); y += spd / math.sqrt(2)
        else:
            x += spd
    elif has_u and y > 50:
        if not has_d:
            y -= spd
    elif has_d and y < SCREEN_HEIGHT - 50:
        y += spd

    state["x"] = x
    state["y"] = y


def apply_powerup(state, ptype):
    """
    Apply a powerup to a player-state dict.

    Args:
        state (dict): player-state dict with health, shield, shield_timer, speed.
                      Modified in-place.
        ptype (str):  "heart" | "bubble" | "shoe"
    """
    if ptype == "heart":
        state["health"] = 100
    elif ptype == "bubble":
        state["shield"]       = True
        state["shield_timer"] = 300   # 10 s at 30 FPS
    elif ptype == "shoe":
        state["speed"] = min(state["speed"] * 1.1, PLAYER_SPEED * 2.0)


# ===================== Score Persistence =====================

def save_best_score(score, filename="best_score.json"):
    """Save the best score to a JSON file on disk.

    Args:
        score    (int): The score value to persist.
        filename (str): Target file path (default: 'best_score.json').
    """
    data = {"best_score": score}
    with open(filename, "w") as f:
        json.dump(data, f)


def load_best_score(filename="best_score.json"):
    """Load the best score from a JSON file.

    Args:
        filename (str): Source file path (default: 'best_score.json').

    Returns:
        int: The stored best score, or 0 if the file does not exist.
    """
    try:
        with open(filename, "r") as f:
            data = json.load(f)
            return data.get("best_score", 0)
    except FileNotFoundError:
        return 0
