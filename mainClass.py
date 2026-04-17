from logging import lastResort
import pygame, math,random, json, sys, socket, struct, threading
from secure_network import SecureClient

# ===================== Network Manager =====================
class NetworkManager:
    def __init__(self, username):
        self.username = username
        self.sock = None
        self.my_id = None
        self.other_players = {}
        self.other_players_lock = threading.Lock()
        self.lobby_players_count = 0
        self.lobby_players = []
        self.rivalry_seed = None
        self.rivalry_start_signal = False
        self.rivalry_winner = None
        self.running = True
        
    def join_server(self):
        if self.sock: return
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(2.0)
        try:
            self.sock.connect(('127.0.0.1', 5555))
        except:
            import subprocess, time, sys
            print("[MULTIPLAYER] Server not found. Starting local server...")
            subprocess.Popen([sys.executable, "network_server.py"], creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            time.sleep(1.0)
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(2.0)
            try:
                self.sock.connect(('127.0.0.1', 5555))
            except Exception as e:
                print("[MULTIPLAYER] Failed to start and connect to server.", e)
                self.sock = None
                return
        
        try:
            welcome = self.sock.recv(3)
            cmd, self.my_id = struct.unpack('!BH', welcome)
            self.sock.settimeout(1.0) 
            print(f"[MULTIPLAYER] Connected! My ID is {self.my_id}")
            
            # Send our username to server immediately
            encoded_name = self.username.encode('utf-8')[:255]
            self.sock.sendall(struct.pack('!BB', 6, len(encoded_name)) + encoded_name)
            
            self.running = True
            self.net_thread = threading.Thread(target=self._sync_loop)
            self.net_thread.daemon = True
            self.net_thread.start()
        except Exception as e:
            print("[MULTIPLAYER] Welcome msg error:", e)
            self.sock = None

    def leave_server(self):
        self.running = False
        if self.sock:
            try: self.sock.sendall(struct.pack('!B', 5))
            except: pass
            self.sock.close()
            self.sock = None
        self.my_id = None
        self.lobby_players_count = 0
        self.other_players = {}
            
    def _sync_loop(self):
        while self.running and self.sock:
            try:
                cmd_bytes = self.sock.recv(1)
                if not cmd_bytes: break
                cmd = cmd_bytes[0]
                
                if cmd == 1:
                    num_players_b = self.sock.recv(1)
                    num_players = num_players_b[0]
                    data_len = num_players * 6
                    data = b''
                    while len(data) < data_len:
                        packet = self.sock.recv(data_len - len(data))
                        if not packet: break
                        data += packet
                    new_state = {}
                    for i in range(num_players):
                        pid, px, py = struct.unpack('!Hhh', data[i*6:(i+1)*6])
                        if pid != self.my_id:
                            new_state[pid] = (px, py)
                    with self.other_players_lock:
                        self.other_players = new_state
                        
                elif cmd == 2:
                    pcount_b = self.sock.recv(1)
                    if pcount_b:
                        self.lobby_players_count = pcount_b[0]
                        self.lobby_players = []
                        for _ in range(self.lobby_players_count):
                            header = b''
                            while len(header) < 3:
                                packet = self.sock.recv(3 - len(header))
                                if not packet: break
                                header += packet
                            if len(header) < 3: break
                            pid, name_len = struct.unpack('!HB', header)
                            
                            name_b = b''
                            while len(name_b) < name_len:
                                packet = self.sock.recv(name_len - len(name_b))
                                if not packet: break
                                name_b += packet
                            if len(name_b) < name_len: break
                            name = name_b.decode('utf-8')
                            self.lobby_players.append((pid, name))
                    
                elif cmd == 3:
                    seed_b = b''
                    while len(seed_b) < 4:
                        packet = self.sock.recv(4 - len(seed_b))
                        if not packet: break
                        seed_b += packet
                    if len(seed_b) == 4:
                        self.rivalry_seed = struct.unpack('!I', seed_b)[0]
                        self.rivalry_start_signal = True
                        self.rivalry_winner = None
                    
                elif cmd == 4:
                    win_b = b''
                    while len(win_b) < 2:
                        packet = self.sock.recv(2 - len(win_b))
                        if not packet: break
                        win_b += packet
                    if len(win_b) == 2:
                        self.rivalry_winner = struct.unpack('!H', win_b)[0]
                        
            except socket.timeout:
                continue
            except Exception:
                break
                
    def send_move(self, x, y):
        if self.sock:
            try: self.sock.sendall(struct.pack('!Bhh', 1, int(x), int(y)))
            except: pass
            
    def query_lobby(self):
        if self.sock:
            try: self.sock.sendall(struct.pack('!B', 2))
            except: pass
            
    def start_rivalry(self):
        if self.sock:
            try: self.sock.sendall(struct.pack('!B', 3))
            except: pass
            
    def i_died(self):
        if self.sock:
            try: self.sock.sendall(struct.pack('!B', 4))
            except: pass

# ===================== מחלקת MainMenu =====================
class MainMenu:
    def __init__(self, screen, screen_width, screen_height, muted, best_score, net_manager):
        self.screen = screen
        self.SCREEN_WIDTH = screen_width
        self.SCREEN_HEIGHT = screen_height
        self.background = Background(screen_width, screen_height, num_stars=150)
        self.muted = muted
        self.title_font = pygame.font.Font(None, 108)
        self.button_font = pygame.font.Font(None, 48)
        self.start_button = None
        self.rivalry_button = None
        self.join_server_button = None
        self.leave_server_button = None
        self.mute_button = None
        self.best_score = best_score
        self.net_manager = net_manager
        pygame.mixer.music.load("assets/sounds/Free Video Game Music - HeatleyBros - 8 Bit Let's Go.mp3")
        pygame.mixer.music.play(-1)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_pos = pygame.mouse.get_pos()
                if self.start_button and self.start_button.collidepoint(mouse_pos):
                    return "SOLO"
                elif self.join_server_button and self.join_server_button.collidepoint(mouse_pos):
                    if self.net_manager: self.net_manager.join_server()
                elif self.leave_server_button and self.leave_server_button.collidepoint(mouse_pos):
                    if self.net_manager: self.net_manager.leave_server()
                elif self.rivalry_button and self.rivalry_button.collidepoint(mouse_pos):
                    if self.net_manager and self.net_manager.lobby_players_count >= 2:
                        self.net_manager.start_rivalry()
                elif self.mute_button and self.mute_button.collidepoint(mouse_pos):
                    self.toggle_mute()
        return None

    def toggle_mute(self):
        self.muted = not self.muted

    def draw(self):
        self.screen.fill((0, 0, 0))
        self.background.draw(self.screen)

        title_surf = self.title_font.render("MAIN MENU", True, (255, 255, 255))
        title_rect = title_surf.get_rect(center=(self.SCREEN_WIDTH // 2, 170))
        self.screen.blit(title_surf, title_rect)

        title_surf = self.button_font.render("BEST SCORE: " + str(self.best_score), True, (255, 255, 255))
        title_rect = title_surf.get_rect(center=(self.SCREEN_WIDTH // 2, self.SCREEN_HEIGHT // 2 - 240))
        self.screen.blit(title_surf, title_rect)

        start_text = "Start Game"
        start_surf = self.button_font.render(start_text, True, (255, 255, 255))
        start_rect = start_surf.get_rect(center=(self.SCREEN_WIDTH // 2, self.SCREEN_HEIGHT // 2))
        pygame.draw.rect(self.screen, (0, 128, 0), start_rect.inflate(20, 10))
        self.screen.blit(start_surf, start_rect)
        self.start_button = start_rect.inflate(20, 10)
        
        # Rivalry button
        rivalry_text = "Rivalry Mode"
        rivalry_surf = self.button_font.render(rivalry_text, True, (255, 255, 255))
        rivalry_rect = rivalry_surf.get_rect(center=(self.SCREEN_WIDTH // 2, self.SCREEN_HEIGHT // 2 + 80))
        can_rival = self.net_manager and self.net_manager.lobby_players_count >= 2
        bg_color = (0, 200, 0) if can_rival else (100, 100, 100)
        pygame.draw.rect(self.screen, bg_color, rivalry_rect.inflate(20, 10))
        self.screen.blit(rivalry_surf, rivalry_rect)
        self.rivalry_button = rivalry_rect.inflate(20, 10)

        mute_text = "Mute" if not self.muted else "Unmute"
        mute_surf = self.button_font.render(mute_text, True, (255, 255, 255))
        mute_rect = mute_surf.get_rect(topleft=(20, 20))
        pygame.draw.rect(self.screen, (128, 0, 0), mute_rect.inflate(20, 20))
        self.screen.blit(mute_surf, mute_rect)
        self.mute_button = mute_rect.inflate(20, 10)
        
        # Network Buttons (Join/Leave)
        if self.net_manager and self.net_manager.sock:
            text_surf = self.button_font.render("On a Server", True, (0, 255, 0))
            text_rect = text_surf.get_rect(topright=(self.SCREEN_WIDTH - 20, 20))
            self.screen.blit(text_surf, text_rect)
            self.join_server_button = None
            
            leave_text = "Leave Server"
            leave_surf = self.button_font.render(leave_text, True, (255, 255, 255))
            leave_rect = leave_surf.get_rect(topleft=(20, 80))
            pygame.draw.rect(self.screen, (128, 0, 0), leave_rect.inflate(20, 20))
            self.screen.blit(leave_surf, leave_rect)
            self.leave_server_button = leave_rect.inflate(20, 10)

            list_font = pygame.font.Font(None, 36)
            y_pos = text_rect.bottom + 10
            for pid, name in getattr(self.net_manager, 'lobby_players', []):
                color = (255, 255, 0) if pid == self.net_manager.my_id else (200, 200, 200)
                name_str = f"{name} (You)" if pid == self.net_manager.my_id else f"{name}"
                p_surf = list_font.render(name_str, True, color)
                p_rect = p_surf.get_rect(topright=(self.SCREEN_WIDTH - 20, y_pos))
                self.screen.blit(p_surf, p_rect)
                y_pos += 30
        else:
            self.leave_server_button = None
            join_surf = self.button_font.render("Join Server", True, (255, 255, 255))
            join_rect = join_surf.get_rect(topright=(self.SCREEN_WIDTH - 20, 20))
            pygame.draw.rect(self.screen, (0, 128, 0), join_rect.inflate(20, 20))
            self.screen.blit(join_surf, join_rect)
            self.join_server_button = join_rect.inflate(20, 10)

        pygame.display.flip()

    def run(self):
        query_timer = 0
        while True:
            self.background.update()
            
            query_timer += 1
            if query_timer >= 60:
                query_timer = 0
                if self.net_manager: self.net_manager.query_lobby()
                
            if self.net_manager and self.net_manager.rivalry_start_signal:
                self.net_manager.rivalry_start_signal = False
                return self.muted, "RIVALRY"
                
            res = self.handle_events()
            if res is not None:
                return self.muted, res
                
            if self.muted:
                pygame.mixer.music.set_volume(0)
            else:
                pygame.mixer.music.set_volume(0.05)
            self.draw()
            pygame.time.Clock().tick(60)


# ===================== מחלקת Game =====================
class Game:
    def __init__(self, muted=False, mode="SOLO", net_manager=None):
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

        self.player = Player(384, 284, self.SCREEN_WIDTH, self.SCREEN_HEIGHT)
        self.score_font = pygame.font.Font(None, 40)

        self.spawn_cooldown = 70
        self.spawn_timer = 0
        self.meteors = []
        self.meteor_speed = 4
        self.explosions = []

        self.powerup = None
        self.powerup_timer = 0
        self.powerup_spawn_cooldown = 600

        self.mode = mode
        self.net_manager = net_manager
        if self.mode == "RIVALRY" and self.net_manager:
            self.rng = random.Random(self.net_manager.rivalry_seed)
        else:
            self.rng = random.Random()
            
        self.game_over = False
        self.winner_msg = ""
        self.continue_rect = pygame.Rect(0, 0, 0, 0)

        if not muted:
            pygame.mixer.music.load("assets/sounds/Free Video Game Music - HeatleyBros - 8 Bit Let's Go.mp3")
            pygame.mixer.music.play(-1)
            pygame.mixer.music.set_volume(0.1)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                if self.mode == "RIVALRY" and not self.game_over:
                    if self.net_manager: self.net_manager.i_died()
                self.running = False
            if self.game_over and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_pos = pygame.mouse.get_pos()
                if self.continue_rect.collidepoint(mouse_pos):
                    self.running = False

    def spawn_meteor(self):
        pool = self.rng.randint(1, 5)
        if pool == 1:
            x = self.player.x
        else:
            x = self.rng.randint(64, self.SCREEN_WIDTH - 64)
        self.meteors.append(Meteor(x, y=-64))

    def spawn_powerup(self):
        power_type = self.rng.choice(["heart", "bubble", "shoe"])
        x = self.rng.randint(50, self.SCREEN_WIDTH - 50)
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
                    if not self.player.shield:
                        self.player.take_damage(meteor.damage)

    def update_powerups(self):
        self.powerup_timer += 1
        if self.powerup_timer >= self.powerup_spawn_cooldown - (self.difficulty * 30):
            self.powerup_timer = 0
            self.spawn_powerup()
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
        if self.game_over:
            return

        keys = pygame.key.get_pressed()
        self.player.update(keys)

        if self.mode == "RIVALRY" and self.net_manager:
            self.net_manager.send_move(self.player.x, self.player.y)
            if self.net_manager.rivalry_winner == self.net_manager.my_id:
                self.game_over = True
                self.winner_msg = "WINNER!"
            elif self.net_manager.rivalry_winner is not None:
                self.game_over = True
                self.winner_msg = "LOSER!"

        self.update_meteors()
        self.update_powerups()

        for explosion in self.explosions[:]:
            explosion.update()
            if not explosion.active:
                self.explosions.remove(explosion)

        if self.player.health <= 0:
            if self.mode == "RIVALRY":
                if self.net_manager: self.net_manager.i_died()
                self.game_over = True
                self.winner_msg = "LOSER!"
            else:
                self.game_over = True
                self.winner_msg = "GAME OVER"

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

        if self.mode == "RIVALRY" and self.net_manager:
            with self.net_manager.other_players_lock:
                pid_map = {p: n for p, n in getattr(self.net_manager, 'lobby_players', [])}
                for pid, (px, py) in self.net_manager.other_players.items():
                    pygame.draw.circle(self.screen, (0, 255, 255), (px, py), 20)
                    font = pygame.font.Font(None, 24)
                    p_name = pid_map.get(pid, f"P{pid}")
                    text = font.render(p_name, True, (255, 255, 255))
                    self.screen.blit(text, (px - 10, py - 35))

        self.player.draw(self.screen)
        for meteor in self.meteors:
            meteor.draw(self.screen)
        self.draw_health_bar()
        self.screen.blit(self.heartBar, (180, 530))

        score_surf = self.score_font.render(str(self.score), True, (255, 255, 255))
        score_rect = score_surf.get_rect(topleft=(20, 20))
        self.screen.blit(score_surf, score_rect)
        
        if self.game_over:
            font_big = pygame.font.Font(None, 100)
            font_small = pygame.font.Font(None, 50)
            
            msg_surf = font_big.render(self.winner_msg, True, (255, 255, 0))
            msg_rect = msg_surf.get_rect(center=(self.SCREEN_WIDTH//2, self.SCREEN_HEIGHT//2 - 50))
            self.screen.blit(msg_surf, msg_rect)
            
            cont_surf = font_small.render("Continue", True, (255, 255, 255))
            self.continue_rect = cont_surf.get_rect(center=(self.SCREEN_WIDTH//2, self.SCREEN_HEIGHT//2 + 50))
            pygame.draw.rect(self.screen, (0, 0, 200), self.continue_rect.inflate(20, 10))
            self.screen.blit(cont_surf, self.continue_rect)
            self.continue_rect = self.continue_rect.inflate(20, 10)

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
        self.shield_timer = 0
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
        # if shield is active, draw the glow effect instead of the normal player sprite
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
        self.speed = 3
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

def get_network_best_score(current_score, username):
    try:
        client = SecureClient()
        return client.send_score_and_get_best(current_score, username)
    except Exception:
        # Fallback if there's an error
        return current_score

def circle_rect_collision(cx, cy, r, rect):
    closest_x = max(rect.left, min(cx, rect.right))
    closest_y = max(rect.top, min(cy, rect.bottom))
    dx = cx - closest_x
    dy = cy - closest_y
    return (dx * dx + dy * dy) <= (r * r)

from secure_network import SecureClient
import auth

def main():
    # =================================================================
    #                    CYBERSECURITY AUTHENTICATION
    # =================================================================
    print("\n" + "="*50)
    print("       METEORITE BLAH - SECURE LOGIN TERMINAL")
    print("="*50)
    
    hw_id = auth.get_hardware_id()
    
    authenticated = False
    current_user = "Guest"
    is_guest = False

    while not authenticated:
        choice = input("Would you like to (R)egister, (L)ogin, (G)uest, or (Q)uit? ").strip().upper()
        
        if choice == 'Q':
            print("Exiting game...")
            return
            
        elif choice == 'R':
            user = input("Choose a username: ").strip()
            pwd = input("Choose a password: ").strip()
            auth.register_user(user, pwd)
            print("Please login now.\n")
            
        elif choice == 'L':
            while True:
                user = input("Username: ").strip()
                pwd = input("Password: ").strip()
                if auth.login_user(user, pwd, hw_id):
                    print(f"\nWelcome back to the game, {user}!")
                    current_user = user
                    authenticated = True
                    break
                else:
                    retry = input("Login failed. Try again? (Y/N): ").strip().upper()
                    if retry != 'Y':
                        break

        elif choice == 'G':
            # Generate a random guest name so players can identify each other in the lobby
            guest_number = random.randint(1000, 9999)
            current_user = f"Guest_{guest_number}"
            is_guest = True
            authenticated = True
            print(f"\nPlaying as guest: {current_user}")
            print("Note: Your score will NOT be saved when you exit.\n")

        else:
            print("Invalid choice, please try again.\n")
            
    print("="*50 + "\nLaunching Game...\n")

    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("משחק מטאורים")
    muted = False
    
    # Initialize Network for Lobby checks
    net_manager = NetworkManager(current_user)
    
    # Guests start with a local score of 0 and skip server sync
    if is_guest:
        score = 0
    else:
        # Send 0 just to fetch the current personal best score from the Server on startup
        score = get_network_best_score(0, current_user)

    while True:
        menu = MainMenu(screen, 800, 600, muted, score, net_manager)
        muted, mode = menu.run()
        game = Game(muted, mode, net_manager)
        lastscore = game.run()
        
        if lastscore > score:
            score = lastscore

        # Guests scores are tracked in memory only - never sent to the server
        if not is_guest:
            score = get_network_best_score(score, current_user)

if __name__ == "__main__":
    main()