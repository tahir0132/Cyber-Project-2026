from logging import lastResort
import pygame, math, random, json, sys

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
        self.best_score = best_score
        pygame.mixer.music.load("assets\sounds\Free Video Game Music - HeatleyBros - 8 Bit Let's Go.mp3")
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
            pygame.time.Clock().tick(60)

# ===================== מחלקת Game =====================
class Game:
    def __init__(self, muted=False):
        self.SCREEN_WIDTH = 800
        self.SCREEN_HEIGHT = 600
        self.screen = pygame.display.set_mode((self.SCREEN_WIDTH, self.SCREEN_HEIGHT))
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

        # player realted
        self.player = Player(384, 284, self.SCREEN_WIDTH, self.SCREEN_HEIGHT)
        self.score_font = pygame.font.Font(None, 40)

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

        # music related
        if not muted:
            pygame.mixer.music.load("assets\sounds\Free Video Game Music - HeatleyBros - 8 Bit Let's Go.mp3")
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

        score_surf = self.score_font.render(str(self.score), True, (255, 255, 255))
        score_rect = score_surf.get_rect(topleft=(20, 20))
        self.screen.blit(score_surf, score_rect)
        pygame.display.flip()

    def run(self):
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(60)
        return self.score

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

# פונקציה לשמירת ה-BestScore
def save_best_score(score, filename="best_score.json"):
    data = {"best_score": score}
    with open(filename, "w") as f:
        json.dump(data, f)

# פונקציה לטעינת ה-BestScore
def load_best_score(filename="best_score.json"):
    try:
        with open(filename, "r") as f:
            data = json.load(f)
            return data.get("best_score", 0)
    except FileNotFoundError:
        return 0

# פונקציית בדיקת התנגשות בין עיגול למלבן
def circle_rect_collision(cx, cy, r, rect):
    closest_x = max(rect.left, min(cx, rect.right))
    closest_y = max(rect.top, min(cy, rect.bottom))
    dx = cx - closest_x
    dy = cy - closest_y
    return (dx * dx + dy * dy) <= (r * r)

def main():
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("משחק מטאורים")
    muted = False
    score = load_best_score("best_score.json")

    while True:
        menu = MainMenu(screen, 800, 600, muted, score)
        muted = menu.run()
        game = Game(muted)
        lastscore = game.run()
        if lastscore > score:
            score = lastscore

if __name__ == "__main__":
    main()