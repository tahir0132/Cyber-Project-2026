"""
game_objects.py – Game entity classes (Pygame only, no network)

All visual and physical game objects live here.
This module is imported by client.py (game_manager.py) only.
server.py must NOT import this module — use utils.py for shared logic.

Classes:
    Background  – Scrolling star-field backdrop
    Player      – Player sprite with movement, animation, and power-ups
    Meteor      – Falling meteor obstacle with animated sprite
    Particle    – Single particle used by Explosion burst
    Explosion   – Particle-burst effect on meteor collision
    PowerUp     – Collectible power-up item (heart / bubble / shoe)

Author: Tahir – Cyber Project 2026 (Bagrut 5-Unit)
"""

import pygame
import math
import random


# ===================== מחלקת רקע =====================
class Background:
    def __init__(self, width, height, num_stars=100):
        self.width = width
        self.height = height
        self.num_stars = num_stars
        self.stars = []
        for _ in range(self.num_stars):
            x = random.randint(0, self.width)
            y = random.randint(0, self.height)
            speed = random.uniform(0.5, 2.0)
            size = random.randint(1, 3)
            self.stars.append([x, y, speed, size])

    def update(self):
        for star in self.stars:
            star[1] -= star[2]
            if star[1] < 0:
                star[0] = random.randint(0, self.width)
                star[1] = self.height
                star[2] = random.uniform(0.5, 2.0)
                star[3] = random.randint(1, 3)

    def draw(self, surface):
        for star in self.stars:
            x, y, speed, size = star
            pygame.draw.circle(surface, (255, 255, 255), (int(x), int(y)), size)


# ===================== מחלקת Player =====================
class Player:
    def __init__(self, x, y, sW, sH):
        self.x = x
        self.y = y
        self.SCREEN_WIDTH = sW
        self.SCREEN_HEIGHT = sH
        self.speed = 10
        self.max_health = 100
        self.health = self.max_health
        self.shield = False
        self.shield_timer = 0  # זמן שמגן הבועה נשאר פעיל (בפריימים)
        self.scale = 0.5

        self.player_setup()
        self.glow_setup()
        self.rect = self.frames[0].get_rect(center=(x, y))
        self.player_offset_x = self.frames[0].get_width() // 2
        self.player_offset_y = self.frames[0].get_height() // 2

    def player_setup(self):
        self.frames = [
            pygame.image.load("assets/imgs/player/player1.png"),
            pygame.image.load("assets/imgs/player/player2.png"),
            pygame.image.load("assets/imgs/player/player3.png"),
            pygame.image.load("assets/imgs/player/player4.png"),
        ]
        self.frames = [pygame.transform.scale(img, (int(img.get_width()*self.scale), int(img.get_height()*self.scale))) for img in self.frames]
        self.current_frame = 0
        self.frame_delay = 15
        self.frame_count = 0

    def glow_setup(self):
        self.glow_images = [
            pygame.image.load("assets/imgs/player/glow/glow1.png"),
            pygame.image.load("assets/imgs/player/glow/glow2.png"),
            pygame.image.load("assets/imgs/player/glow/glow3.png"),
            pygame.image.load("assets/imgs/player/glow/glow4.png"),
        ]
        self.glow_images = [pygame.transform.scale(img, (int(img.get_width()*self.scale), int(img.get_height()*self.scale))) for img in self.glow_images]
        self.glow_size = [self.scale * 1.1, self.scale * 1.2, self.scale * 1.3, self.scale * 1.2]
        self.glow_offsets_x = []
        self.glow_offsets_y = []
        for i in range(len(self.glow_images)):
            img = self.glow_images[i]
            scale = self.glow_size[i]
            self.glow_offsets_x.append(img.get_width() * scale // 2)
            self.glow_offsets_y.append(img.get_height() * scale // 2)
        self.current_glow_frame = 0
        self.frame_glow_count = 0

    def movement(self, keys):
        if keys[pygame.K_a] and self.x > 45:
            if keys[pygame.K_w] and self.y > 50:
                self.x -= self.speed/math.sqrt(2)
                self.y -= self.speed/math.sqrt(2)
            elif keys[pygame.K_s] and self.y < self.SCREEN_HEIGHT - self.player_offset_y:
                self.x -= self.speed/math.sqrt(2)
                self.y += self.speed/math.sqrt(2)
            else:
                self.x -= self.speed
        elif keys[pygame.K_d] and self.x < self.SCREEN_WIDTH - 40:
            if keys[pygame.K_w] and self.y > 50:
                self.x += self.speed/math.sqrt(2)
                self.y -= self.speed/math.sqrt(2)
            elif keys[pygame.K_s] and self.y < self.SCREEN_HEIGHT - self.player_offset_y:
                self.x += self.speed/math.sqrt(2)
                self.y += self.speed/math.sqrt(2)
            else:
                self.x += self.speed
        elif keys[pygame.K_w] and self.y > 50:
            if not keys[pygame.K_s]:
                self.y -= self.speed
        elif keys[pygame.K_s] and self.y < self.SCREEN_HEIGHT - 50:
            self.y += self.speed

    def animations(self):
        self.frame_count += 1
        if self.frame_count >= self.frame_delay:
            self.frame_count = 0
            self.current_frame = (self.current_frame + 1) % len(self.frames)

        self.frame_glow_count += 1
        if self.frame_glow_count >= self.frame_delay * 2:
            self.frame_glow_count = 0
            self.current_glow_frame = (self.current_glow_frame + 1) % len(self.glow_images)

    def update(self, keys):
        self.movement(keys)
        self.animations()
        self.rect.center = (self.x, self.y)

        # עדכון מגן בועה, אם מופעל
        if self.shield:
            self.shield_timer -= 1
            if self.shield_timer <= 0:
                self.shield = False

    def take_damage(self, damage):
        self.health = max(0, self.health - damage)
        print("Player health:", self.health)

    def apply_powerup(self, power_type):
        if power_type == "heart":
            self.health = self.max_health
            print("Heart powerup: Health restored!")
        elif power_type == "bubble":
            self.shield = True
            self.shield_timer = 300  # לדוגמה, 5 שניות (300 פריימים ב-60FPS)
            print("Bubble powerup: Shield activated!")
        elif power_type == "shoe":
            self.speed = self.speed * 1.1
            print("Shoe powerup: Speed increased to", self.speed)

    def draw(self, screen):
        # אם יש מגן, ציור הילה (bubble shield) מסביב לשחקן
        if self.shield:
            glow_offset_x = self.glow_offsets_x[self.current_glow_frame]
            glow_offset_y = self.glow_offsets_y[self.current_glow_frame]
            screen.blit(self.glow_images[self.current_glow_frame], (self.x - glow_offset_x, self.y - glow_offset_y))
        else:
            screen.blit(self.frames[self.current_frame], (self.x - self.player_offset_x, self.y - self.player_offset_y))


# ====================== מחלקת Meteor ======================
class Meteor:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.speed = 4
        self.damage = 10
        self.frames = [
            pygame.image.load("assets/imgs/meteor/meteor1.png"),
            pygame.image.load("assets/imgs/meteor/meteor2.png"),
            pygame.image.load("assets/imgs/meteor/meteor3.png"),
            pygame.image.load("assets/imgs/meteor/meteor4.png")
        ]
        self.scale = 0.5
        self.frames = [pygame.transform.scale(img, (int(img.get_width()*self.scale), int(img.get_height()*self.scale))) for img in self.frames]
        self.rect = self.frames[0].get_rect(topleft=(x, y))
        self.current_frame = 0
        self.frame_delay = 10
        self.frame_counter = 0

    def update(self, speed=4):
        self.speed = speed
        self.y += self.speed
        self.rect.topleft = (self.x, self.y)
        self.frame_counter += 1
        if self.frame_counter >= self.frame_delay:
            self.frame_counter = 0
            self.current_frame = (self.current_frame + 1) % len(self.frames)

    def draw(self, screen):
        screen.blit(self.frames[self.current_frame], (self.x, self.y))


# ===================== מחלקת חלקיקים (ל-Burst) =====================
class Particle:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(1, 5)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.lifetime = 30
        self.age = 0

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.age += 1
        return self.age >= self.lifetime

    def draw(self, screen):
        alpha = 255 - (self.age / self.lifetime) * 255
        size = random.randint(2, 4)
        surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
        color = (random.randint(200, 255), 0, 0, int(alpha))
        pygame.draw.circle(surf, color, (size, size), size)
        screen.blit(surf, (int(self.x) - size, int(self.y) - size))


# ===================== מחלקת Explosion (ל-Burst) =====================
class Explosion:
    def __init__(self, x, y):
        self.particles = [Particle(x, y) for _ in range(30)]
        self.active = True

    def update(self):
        for particle in self.particles[:]:
            if particle.update():
                self.particles.remove(particle)
        if not self.particles:
            self.active = False

    def draw(self, screen):
        for particle in self.particles:
            particle.draw(screen)


# ===================== מחלקת PowerUp (יכולות) =====================
class PowerUp:
    def __init__(self, x, y, power_type):
        self.x = x
        self.y = y
        self.speed = 3  # מהירות נפילה
        self.type = power_type
        self.scale = 0.4
        self.bubble = pygame.image.load("assets/imgs/powerups/bubble.png")
        self.bubble = pygame.transform.scale(self.bubble, (int(self.bubble.get_width() * self.scale), int(self.bubble.get_height() * self.scale)))
        self.shoe = pygame.image.load("assets/imgs/powerups/shoe.png")
        self.shoe = pygame.transform.scale(self.shoe, (int(self.shoe.get_width() * self.scale), int(self.shoe.get_height() * self.scale)))
        self.heart = pygame.image.load("assets/imgs/powerups/heart.png")
        self.heart = pygame.transform.scale(self.heart, (int(self.heart.get_width() * self.scale), int(self.heart.get_height() * self.scale)))

    def update(self):
        self.y += self.speed

    def draw(self, screen):
        if self.type == "heart":
            screen.blit(self.heart, (self.x, self.y))
        elif self.type == "bubble":
            screen.blit(self.bubble, (self.x, self.y))
        elif self.type == "shoe":
            screen.blit(self.shoe, (self.x, self.y))

    def get_rect(self):
        return pygame.Rect(self.x, self.y, self.bubble.get_width(), self.bubble.get_height())
