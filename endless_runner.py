"""
PSYCHEDELIC ENDLESS RUNNER v3.0 - Ultimate Emoji Edition
Controls:
  SPACE / UP    = Jump (press twice for double jump)
  DOWN ARROW    = Slide (duck under flying enemies)
  LEFT/RIGHT    = Navigate menus
  ENTER/SPACE   = Select
  ESC           = Back to menu / Quit
  S             = Toggle sound
"""

import pygame
import random
import math
import sys
import json
import os
import colorsys
import struct
import array

# ─── Initialize ───────────────────────────────────────────────────────────────
pygame.init()
pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)

WIDTH, HEIGHT = 960, 580
GROUND_Y = HEIGHT - 80
FPS = 60

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("PSYCHEDELIC ENDLESS RUNNER v3.0")
clock = pygame.time.Clock()

# ─── Sound Engine (procedural synthesis) ───────────────────────────────────────
class SoundEngine:
    """Generate all sound effects procedurally - no external files needed."""
    enabled = True

    @staticmethod
    def _make_sound(samples_stereo):
        """Convert list of (left, right) float pairs [-1,1] to a pygame Sound."""
        buf = array.array('h')
        for L, R in samples_stereo:
            buf.append(max(-32767, min(32767, int(L * 32767))))
            buf.append(max(-32767, min(32767, int(R * 32767))))
        return pygame.mixer.Sound(buffer=buf)

    @staticmethod
    def _tone(freq, dur, vol=0.3, wave='sine', freq_end=None):
        """Generate a mono tone as list of floats."""
        sr = 22050
        n = int(sr * dur)
        samples = []
        for i in range(n):
            t = i / sr
            p = t / dur  # 0..1 progress
            # Frequency sweep
            if freq_end is not None:
                f = freq + (freq_end - freq) * p
            else:
                f = freq
            phase = 2 * math.pi * f * t
            if wave == 'sine':
                v = math.sin(phase)
            elif wave == 'square':
                v = 1.0 if math.sin(phase) > 0 else -1.0
            elif wave == 'saw':
                v = 2.0 * (f * t % 1.0) - 1.0
            elif wave == 'noise':
                v = random.uniform(-1, 1)
            else:
                v = math.sin(phase)
            # Envelope (attack-decay-sustain-release)
            env = 1.0
            if p < 0.05:
                env = p / 0.05
            elif p > 0.7:
                env = (1.0 - p) / 0.3
            samples.append(v * vol * env)
        return samples

    @classmethod
    def init_sounds(cls):
        try:
            # Jump - ascending chirp
            jump = cls._tone(300, 0.15, 0.25, 'sine', 600)
            cls.snd_jump = cls._make_sound([(s, s) for s in jump])

            # Double jump - higher chirp
            dj = cls._tone(500, 0.12, 0.2, 'sine', 900)
            cls.snd_double_jump = cls._make_sound([(s, s) for s in dj])

            # Coin - pleasant ding
            coin = cls._tone(880, 0.1, 0.2, 'sine')
            cls.snd_coin = cls._make_sound([(s, s) for s in coin])

            # Coin combo - ascending triple ding
            combo_samples = []
            combo_samples += cls._tone(660, 0.06, 0.2, 'sine')
            combo_samples += cls._tone(880, 0.06, 0.2, 'sine')
            combo_samples += cls._tone(1100, 0.08, 0.25, 'sine')
            cls.snd_combo = cls._make_sound([(s, s) for s in combo_samples])

            # Power-up - magical ascending arpeggio
            pu = []
            for f in [440, 554, 659, 880]:
                pu += cls._tone(f, 0.08, 0.2, 'sine')
            cls.snd_powerup = cls._make_sound([(s, s) for s in pu])

            # Hit / damage - harsh buzz
            hit = cls._tone(150, 0.2, 0.3, 'square', 80)
            cls.snd_hit = cls._make_sound([(s, s) for s in hit])

            # Death - descending dramatic
            death = cls._tone(400, 0.5, 0.3, 'saw', 80)
            cls.snd_death = cls._make_sound([(s, s) for s in death])

            # Slide - whoosh
            slide = cls._tone(200, 0.15, 0.15, 'saw', 100)
            cls.snd_slide = cls._make_sound([(s, s) for s in slide])

            # Dash - quick burst
            dash = cls._tone(300, 0.1, 0.25, 'square', 700)
            cls.snd_dash = cls._make_sound([(s, s) for s in dash])

            # Achievement - fanfare
            ach = []
            for f in [523, 659, 784, 1047]:
                ach += cls._tone(f, 0.1, 0.2, 'sine')
            ach += cls._tone(1047, 0.3, 0.15, 'sine')
            cls.snd_achievement = cls._make_sound([(s, s) for s in ach])

            # Menu select
            sel = cls._tone(600, 0.08, 0.15, 'sine')
            cls.snd_select = cls._make_sound([(s, s) for s in sel])

            # Menu navigate
            nav = cls._tone(400, 0.04, 0.1, 'sine')
            cls.snd_navigate = cls._make_sound([(s, s) for s in nav])

            # Shield break
            sb = cls._tone(800, 0.15, 0.25, 'square', 200)
            cls.snd_shield_break = cls._make_sound([(s, s) for s in sb])

            cls.available = True
        except Exception as e:
            cls.available = False

    @classmethod
    def play(cls, name):
        if not cls.enabled or not cls.available:
            return
        snd = getattr(cls, f'snd_{name}', None)
        if snd:
            snd.play()


# ─── Psychedelic Color Engine ─────────────────────────────────────────────────
class Psyche:
    t = 0.0

    @staticmethod
    def update(dt):
        Psyche.t += dt

    @staticmethod
    def hue(offset=0.0, speed=1.0):
        h = (Psyche.t * speed * 0.3 + offset) % 1.0
        r, g, b = colorsys.hsv_to_rgb(h, 0.9, 1.0)
        return (int(r * 255), int(g * 255), int(b * 255))

    @staticmethod
    def neon(offset=0.0, speed=1.0):
        h = (Psyche.t * speed * 0.3 + offset) % 1.0
        r, g, b = colorsys.hsv_to_rgb(h, 1.0, 1.0)
        return (int(r * 255), int(g * 255), int(b * 255))

    @staticmethod
    def pastel(offset=0.0, speed=1.0):
        h = (Psyche.t * speed * 0.3 + offset) % 1.0
        r, g, b = colorsys.hsv_to_rgb(h, 0.5, 1.0)
        return (int(r * 255), int(g * 255), int(b * 255))

    @staticmethod
    def pulse(min_v=0.6, max_v=1.0, speed=3.0):
        return min_v + (max_v - min_v) * (0.5 + 0.5 * math.sin(Psyche.t * speed))


# ─── Emoji Renderer ───────────────────────────────────────────────────────────
class EmojiCache:
    _cache = {}
    _font = None

    @classmethod
    def get_font(cls, size):
        if cls._font is None or cls._font.get_height() != size:
            cls._font = pygame.font.SysFont("Noto Color Emoji", size)
        return cls._font

    @classmethod
    def render(cls, emoji, size=32):
        key = (emoji, size)
        if key not in cls._cache:
            font = cls.get_font(size)
            surf = font.render(emoji, True, (255, 255, 255))
            w, h = surf.get_size()
            scale = min(size / max(w, 1), size / max(h, 1))
            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))
            if new_w != w or new_h != h:
                surf = pygame.transform.smoothscale(surf, (new_w, new_h))
            cls._cache[key] = surf
        return cls._cache[key]

    @classmethod
    def draw(cls, surface, emoji, x, y, size=32, center=True):
        surf = cls.render(emoji, size)
        if center:
            rx = x - surf.get_width() // 2
            ry = y - surf.get_height() // 2
        else:
            rx, ry = x, y
        surface.blit(surf, (int(rx), int(ry)))


# ─── Constants ────────────────────────────────────────────────────────────────
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

# Characters available for selection
CHARACTERS = [
    {"emoji": "🏃", "run": ["🏃", "🤸", "💃"], "jump": "🚀", "slide": "🛝", "name": "Runner"},
    {"emoji": "🦊", "run": ["🦊", "🦊", "🦊"], "jump": "🦊", "slide": "🦊", "name": "Fox"},
    {"emoji": "🐱", "run": ["🐱", "🐱", "🐱"], "jump": "🐱", "slide": "🐱", "name": "Cat"},
    {"emoji": "🤖", "run": ["🤖", "🤖", "🤖"], "jump": "🚀", "slide": "🤖", "name": "Robot"},
    {"emoji": "🦄", "run": ["🦄", "🦄", "🦄"], "jump": "✨", "slide": "🦄", "name": "Unicorn"},
    {"emoji": "👾", "run": ["👾", "👾", "👾"], "jump": "👾", "slide": "👾", "name": "Alien"},
    {"emoji": "🧙", "run": ["🧙", "🧙", "🧙"], "jump": "🧙", "slide": "🧙", "name": "Wizard"},
    {"emoji": "🥷", "run": ["🥷", "🥷", "🥷"], "jump": "🥷", "slide": "🥷", "name": "Ninja"},
]

# Power-up definitions
POWERUP_TYPES = {
    "shield":  {"emoji": "🛡️", "duration": 8.0,  "color": (0, 180, 255), "name": "SHIELD"},
    "magnet":  {"emoji": "🧲", "duration": 7.0,  "color": (255, 50, 50),  "name": "MAGNET"},
    "x2":      {"emoji": "✖️",  "duration": 6.0,  "color": (255, 215, 0),  "name": "2X SCORE"},
    "slow":    {"emoji": "⏳",  "duration": 5.0,  "color": (100, 200, 255), "name": "SLOW-MO"},
    "dash":    {"emoji": "💨",  "duration": 0.3,  "color": (200, 100, 255), "name": "DASH"},
}

# Achievement definitions
ACHIEVEMENTS = [
    {"id": "first_jump",   "name": "First Jump!",     "desc": "Jump for the first time",      "emoji": "⬆️", "check": lambda s: s.get("jumps", 0) >= 1},
    {"id": "coin_10",      "name": "Coin Hunter",      "desc": "Collect 10 coins",             "emoji": "💰", "check": lambda s: s.get("total_coins", 0) >= 10},
    {"id": "coin_50",      "name": "Coin Master",      "desc": "Collect 50 coins total",       "emoji": "👑", "check": lambda s: s.get("total_coins", 0) >= 50},
    {"id": "score_500",    "name": "Getting Started",  "desc": "Score 500 points",             "emoji": "⭐", "check": lambda s: s.get("best_score", 0) >= 500},
    {"id": "score_2000",   "name": "Pro Runner",       "desc": "Score 2000 points",            "emoji": "🌟", "check": lambda s: s.get("best_score", 0) >= 2000},
    {"id": "score_5000",   "name": "Legendary!",       "desc": "Score 5000 points",            "emoji": "🏆", "check": lambda s: s.get("best_score", 0) >= 5000},
    {"id": "combo_5",      "name": "Combo King",       "desc": "Reach a 5x combo",             "emoji": "🔥", "check": lambda s: s.get("best_combo", 0) >= 5},
    {"id": "combo_10",     "name": "Combo GOD",        "desc": "Reach a 10x combo",            "emoji": "💎", "check": lambda s: s.get("best_combo", 0) >= 10},
    {"id": "double_jump",  "name": "Airborne",         "desc": "Use double jump",              "emoji": "🚀", "check": lambda s: s.get("double_jumps", 0) >= 1},
    {"id": "powerup_5",    "name": "Power Hungry",     "desc": "Collect 5 power-ups total",    "emoji": "⚡", "check": lambda s: s.get("total_powerups", 0) >= 5},
    {"id": "near_miss_10", "name": "Daredevil",        "desc": "10 near-misses total",         "emoji": "😈", "check": lambda s: s.get("near_misses", 0) >= 10},
    {"id": "lives_3",      "name": "Survivor",         "desc": "Use all 3 lives in one run",   "emoji": "❤️‍🩹", "check": lambda s: s.get("max_hits", 0) >= 2},
    {"id": "slide_20",     "name": "Low Rider",        "desc": "Slide 20 times total",         "emoji": "🛝", "check": lambda s: s.get("slides", 0) >= 20},
    {"id": "distance_1000","name": "Marathon",         "desc": "Travel 10000 distance",        "emoji": "🏅", "check": lambda s: s.get("best_distance", 0) >= 10000},
]

# High Score & Stats
SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".psyche_runner_save")

def load_save():
    try:
        with open(SAVE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"high_score": 0, "achievements": [], "stats": {}, "selected_char": 0}

def save_game(data):
    try:
        with open(SAVE_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass

SAVE_DATA = load_save()

# ─── Fonts ────────────────────────────────────────────────────────────────────
font_huge   = pygame.font.SysFont("DejaVu Sans", 56, bold=True)
font_large  = pygame.font.SysFont("DejaVu Sans", 38, bold=True)
font_medium = pygame.font.SysFont("DejaVu Sans", 24, bold=True)
font_small  = pygame.font.SysFont("DejaVu Sans", 18)
font_tiny   = pygame.font.SysFont("DejaVu Sans", 14)
font_combo  = pygame.font.SysFont("DejaVu Sans", 42, bold=True)


# ═══════════════════════════════════════════════════════════════════════════════
# FLOATING TEXT (damage numbers, combo popups)
# ═══════════════════════════════════════════════════════════════════════════════
class FloatingText:
    def __init__(self, x, y, text, color, size=24, duration=1.0, emoji=None):
        self.x = x
        self.y = y
        self.text = text
        self.color = color
        self.size = size
        self.duration = duration
        self.timer = 0
        self.emoji = emoji
        self.vy = -60

    @property
    def alive(self):
        return self.timer < self.duration

    def update(self, dt):
        self.timer += dt
        self.y += self.vy * dt
        self.vy *= 0.98

    def draw(self, surface, cam_x=0):
        alpha = max(0, 1.0 - self.timer / self.duration)
        sx = self.x - cam_x
        font = pygame.font.SysFont("DejaVu Sans", self.size, bold=True)
        color = tuple(int(c * alpha) for c in self.color)
        if self.emoji:
            wobble = 1.0 + 0.2 * math.sin(self.timer * 10)
            EmojiCache.draw(surface, self.emoji, sx, self.y - 15, size=int(20 * wobble))
        txt = font.render(self.text, True, color)
        surface.blit(txt, (int(sx - txt.get_width() // 2), int(self.y)))


# ═══════════════════════════════════════════════════════════════════════════════
# ACHIEVEMENT POPUP
# ═══════════════════════════════════════════════════════════════════════════════
class AchievementPopup:
    def __init__(self, achievement):
        self.ach = achievement
        self.timer = 0
        self.duration = 3.0
        self.y_offset = -80  # starts above screen

    @property
    def alive(self):
        return self.timer < self.duration

    def update(self, dt):
        self.timer += dt
        # Slide in, stay, slide out
        if self.timer < 0.4:
            self.y_offset = -80 + (80 * (self.timer / 0.4))
        elif self.timer > self.duration - 0.5:
            p = (self.duration - self.timer) / 0.5
            self.y_offset = 0 - (80 * (1 - p))
        else:
            self.y_offset = 0

    def draw(self, surface):
        x = WIDTH // 2
        y = 10 + self.y_offset
        # Background panel
        panel_w, panel_h = 320, 60
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 180))
        border_color = Psyche.neon(self.timer, speed=2.0)
        pygame.draw.rect(panel, border_color, (0, 0, panel_w, panel_h), 2, border_radius=10)
        surface.blit(panel, (x - panel_w // 2, int(y)))

        EmojiCache.draw(surface, self.ach["emoji"], x - panel_w // 2 + 30, int(y + 30), size=28)
        title_txt = font_small.render("ACHIEVEMENT UNLOCKED!", True, Psyche.neon(0.3))
        surface.blit(title_txt, (x - panel_w // 2 + 55, int(y + 8)))
        name_txt = font_medium.render(self.ach["name"], True, WHITE)
        surface.blit(name_txt, (x - panel_w // 2 + 55, int(y + 28)))


# ═══════════════════════════════════════════════════════════════════════════════
# PARTICLE SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════
class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "size", "hue_offset", "emoji")

    def __init__(self, x, y, vx, vy, life, size, hue_offset=0.0, emoji=None):
        self.x = x; self.y = y
        self.vx = vx; self.vy = vy
        self.life = life; self.max_life = life
        self.size = size; self.hue_offset = hue_offset
        self.emoji = emoji

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 250 * dt
        self.life -= dt

    def draw(self, surface, cam_x=0):
        alpha = max(0, self.life / self.max_life)
        sx = self.x - cam_x; sy = self.y
        if self.emoji:
            s = int(self.size * (0.5 + 0.5 * alpha) * 2)
            if s > 4:
                EmojiCache.draw(surface, self.emoji, sx, sy, size=s)
        else:
            s = max(1, int(self.size * alpha))
            color = Psyche.neon(self.hue_offset, speed=2.0)
            pygame.draw.circle(surface, color, (int(sx), int(sy)), s)

    @property
    def alive(self):
        return self.life > 0


class ParticleSystem:
    def __init__(self):
        self.particles = []

    def emit(self, x, y, count=3):
        for _ in range(count):
            vx = random.uniform(-60, -20)
            vy = random.uniform(-80, -10)
            life = random.uniform(0.3, 0.7)
            size = random.uniform(2, 5)
            emoji = random.choice(["✨", "💫", "🌟", "🌸"]) if random.random() < 0.4 else None
            self.particles.append(Particle(x, y, vx, vy, life, size, random.random(), emoji))

    def emit_burst(self, x, y, count=30):
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(50, 250)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            life = random.uniform(0.4, 1.0)
            size = random.uniform(3, 8)
            emoji = random.choice(["💥", "🔥", "✨", "💫", "🎉", "💖", "💜", "🧡", "💚"])
            emoji = emoji if random.random() < 0.5 else None
            self.particles.append(Particle(x, y, vx, vy, life, size, random.random(), emoji))

    def emit_rainbow_trail(self, x, y):
        vx = random.uniform(-80, -30)
        vy = random.uniform(-50, -5)
        life = random.uniform(0.2, 0.5)
        size = random.uniform(3, 7)
        emoji = random.choice(["🌈", "✨", "💫", "🌸", "🍒", "💎"])
        emoji = emoji if random.random() < 0.3 else None
        self.particles.append(Particle(x, y, vx, vy, life, size, (Psyche.t * 2) % 1.0, emoji))

    def emit_powerup(self, x, y, color_hue):
        for _ in range(20):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(80, 200)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            life = random.uniform(0.5, 1.0)
            size = random.uniform(3, 8)
            emoji = random.choice(["⭐", "✨", "💫", "🌟", "⚡"])
            self.particles.append(Particle(x, y, vx, vy, life, size, color_hue, emoji))

    def update(self, dt):
        for p in self.particles:
            p.update(dt)
        self.particles = [p for p in self.particles if p.alive]

    def draw(self, surface, cam_x=0):
        for p in self.particles:
            p.draw(surface, cam_x)


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN EFFECTS
# ═══════════════════════════════════════════════════════════════════════════════
class ScreenFX:
    def __init__(self):
        self.flash_timer = 0
        self.flash_color = WHITE
        self.flash_duration = 0
        self.shake_amount = 0

    def flash(self, color, duration=0.15):
        self.flash_color = color
        self.flash_timer = 0
        self.flash_duration = duration

    def shake(self, amount=10):
        self.shake_amount = amount

    def update(self, dt):
        if self.flash_timer < self.flash_duration:
            self.flash_timer += dt
        if self.shake_amount > 0.5:
            self.shake_amount *= 0.88
        else:
            self.shake_amount = 0

    def get_shake_offset(self):
        if self.shake_amount > 0.5:
            return (random.uniform(-self.shake_amount, self.shake_amount),
                    random.uniform(-self.shake_amount, self.shake_amount))
        return (0, 0)

    def draw_overlay(self, surface):
        if self.flash_timer < self.flash_duration:
            alpha = int(120 * (1.0 - self.flash_timer / self.flash_duration))
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((*self.flash_color[:3], alpha))
            surface.blit(overlay, (0, 0))


# ═══════════════════════════════════════════════════════════════════════════════
# PLAYER (with lives, power-ups, dash)
# ═══════════════════════════════════════════════════════════════════════════════
class Player:
    WIDTH = 40
    HEIGHT_SLIDE = 28
    HEIGHT_STAND = 54
    JUMP_VELOCITY = -580
    GRAVITY = 1600
    DOUBLE_JUMP_VEL = -480
    DASH_SPEED = 1200
    DASH_DURATION = 0.25
    MAX_LIVES = 3
    INVINCIBLE_DURATION = 2.0

    def __init__(self, x, y, char_idx=0):
        self.x = x
        self.base_y = y
        self.y = y - self.HEIGHT_STAND
        self.vy = 0
        self.width = self.WIDTH
        self.height = self.HEIGHT_STAND
        self.on_ground = True
        self.jumps_left = 2
        self.sliding = False
        self.slide_timer = 0
        self.slide_duration = 0.6
        self.leg_timer = 0
        self.alive = True
        self.death_timer = 0
        self.hue_offset = random.uniform(0, 1)

        # Lives system
        self.lives = self.MAX_LIVES
        self.invincible_timer = 0
        self.hits_taken = 0

        # Dash
        self.dash_timer = 0
        self.dash_cooldown = 0

        # Power-ups
        self.active_powers = {}  # type -> remaining time

        # Character
        self.char_idx = char_idx
        self.char = CHARACTERS[char_idx]

        # Stats for this run
        self.run_jumps = 0
        self.run_double_jumps = 0
        self.run_slides = 0

    @property
    def rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def has_power(self, ptype):
        return ptype in self.active_powers and self.active_powers[ptype] > 0

    def jump(self):
        if self.jumps_left > 0 and self.alive:
            if self.on_ground or self.jumps_left == 2:
                self.vy = self.JUMP_VELOCITY
                self.on_ground = False
                self.jumps_left -= 1
                self.sliding = False
                self.height = self.HEIGHT_STAND
                self.y = self.base_y - self.HEIGHT_STAND
                self.run_jumps += 1
                SoundEngine.play("jump")
            elif self.jumps_left == 1:
                self.vy = self.DOUBLE_JUMP_VEL
                self.jumps_left -= 1
                self.run_double_jumps += 1
                SoundEngine.play("double_jump")

    def slide(self):
        if self.on_ground and not self.sliding and self.alive:
            self.sliding = True
            self.slide_timer = self.slide_duration
            self.height = self.HEIGHT_SLIDE
            self.y = self.base_y - self.HEIGHT_SLIDE
            self.run_slides += 1
            SoundEngine.play("slide")

    def start_dash(self):
        if self.dash_cooldown <= 0 and self.alive and not self.dash_timer > 0:
            self.dash_timer = self.DASH_DURATION
            self.dash_cooldown = 1.5
            self.invincible_timer = max(self.invincible_timer, self.DASH_DURATION)
            SoundEngine.play("dash")

    def take_hit(self):
        """Returns True if actually hit (not shielded/invincible)."""
        if self.invincible_timer > 0:
            return False
        if self.has_power("shield"):
            del self.active_powers["shield"]
            self.invincible_timer = 0.5
            SoundEngine.play("shield_break")
            return False

        self.lives -= 1
        self.hits_taken += 1
        self.invincible_timer = self.INVINCIBLE_DURATION
        SoundEngine.play("hit")

        if self.lives <= 0:
            self.alive = False
            self.death_timer = 0
            SoundEngine.play("death")
            return True
        return True

    def update(self, dt):
        if not self.alive:
            self.death_timer += dt
            return

        # Invincibility countdown
        if self.invincible_timer > 0:
            self.invincible_timer -= dt

        # Dash
        if self.dash_timer > 0:
            self.dash_timer -= dt
        if self.dash_cooldown > 0:
            self.dash_cooldown -= dt

        # Power-up timers
        expired = []
        for ptype, time_left in self.active_powers.items():
            self.active_powers[ptype] -= dt
            if self.active_powers[ptype] <= 0:
                expired.append(ptype)
        for p in expired:
            del self.active_powers[p]

        # Gravity
        if not self.on_ground:
            self.vy += self.GRAVITY * dt
            self.y += self.vy * dt
            floor_y = self.base_y - self.height
            if self.y >= floor_y:
                self.y = floor_y
                self.vy = 0
                self.on_ground = True
                self.jumps_left = 2

        if self.sliding:
            self.slide_timer -= dt
            if self.slide_timer <= 0:
                self.sliding = False
                self.height = self.HEIGHT_STAND
                self.y = self.base_y - self.HEIGHT_STAND

        if self.on_ground and not self.sliding:
            self.leg_timer += dt * 12

    def draw(self, surface, cam_x=0):
        sx = self.x - cam_x
        cy = self.y + self.height // 2

        # Blinking when invincible
        if self.invincible_timer > 0 and int(self.invincible_timer * 10) % 2 == 0:
            # Draw faint
            if self.invincible_timer < 0.3 or int(self.invincible_timer * 15) % 3 == 0:
                pass  # skip frame (blink)
            else:
                self._draw_character(surface, sx, cy, 0.4)
            # Shield visual
            if self.has_power("shield"):
                self._draw_shield(surface, sx, cy)
            return

        if not self.alive:
            EmojiCache.draw(surface, "💀", sx + self.width // 2, cy, size=36)
            return

        self._draw_character(surface, sx, cy, 1.0)

        # Shield bubble
        if self.has_power("shield"):
            self._draw_shield(surface, sx, cy)

        # Dash afterimage
        if self.dash_timer > 0:
            for i in range(3):
                ax = sx - 15 - i * 12
                self._draw_character(surface, ax, cy, 0.2 - i * 0.05)

    def _draw_character(self, surface, sx, cy, alpha_mult=1.0):
        wobble = 1.0 + 0.08 * math.sin(Psyche.t * 6 + self.hue_offset * 10)
        emoji_size = int(38 * wobble)

        if self.sliding:
            EmojiCache.draw(surface, self.char["slide"], sx + self.width // 2, cy, size=emoji_size)
        elif not self.on_ground:
            EmojiCache.draw(surface, self.char["jump"], sx + self.width // 2, cy, size=emoji_size)
        else:
            cycle = int(self.leg_timer / 2) % len(self.char["run"])
            EmojiCache.draw(surface, self.char["run"][cycle], sx + self.width // 2, cy, size=emoji_size)

        # Aura glow
        if alpha_mult > 0.5:
            aura_color = Psyche.neon(self.hue_offset, speed=2.0)
            pulse_r = int(25 + 8 * math.sin(Psyche.t * 5))
            aura_surf = pygame.Surface((pulse_r * 2, pulse_r * 2), pygame.SRCALPHA)
            pygame.draw.circle(aura_surf, (*aura_color, 40), (pulse_r, pulse_r), pulse_r)
            surface.blit(aura_surf, (int(sx + self.width // 2 - pulse_r), int(cy - pulse_r)))

    def _draw_shield(self, surface, sx, cy):
        shield_r = 35 + int(3 * math.sin(Psyche.t * 4))
        shield_surf = pygame.Surface((shield_r * 2, shield_r * 2), pygame.SRCALPHA)
        color = Psyche.neon(0.5, speed=1.5)
        pygame.draw.circle(shield_surf, (*color, 50), (shield_r, shield_r), shield_r)
        pygame.draw.circle(shield_surf, (*color, 100), (shield_r, shield_r), shield_r, 2)
        surface.blit(shield_surf, (int(sx + self.width // 2 - shield_r), int(cy - shield_r)))


# ═══════════════════════════════════════════════════════════════════════════════
# OBSTACLES
# ═══════════════════════════════════════════════════════════════════════════════
class Obstacle:
    TYPES = {
        "spike":  {"w": 32, "h": 40, "emoji": "💀"},
        "crate":  {"w": 38, "h": 38, "emoji": "📦"},
        "tall":   {"w": 30, "h": 68, "emoji": "👾"},
        "double": {"w": 52, "h": 38, "emoji": "🧱"},
    }

    def __init__(self, x, obs_type="spike"):
        self.x = x
        self.type = obs_type
        info = self.TYPES[obs_type]
        self.width = info["w"]
        self.height = info["h"]
        self.y = GROUND_Y - self.height
        self.passed = False
        self.emoji = info["emoji"]
        self.hue_offset = random.uniform(0, 1)
        self.wobble_phase = random.uniform(0, math.pi * 2)
        self.near_missed = False

    @property
    def rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def draw(self, surface, cam_x=0):
        sx = self.x - cam_x
        cx = sx + self.width // 2
        cy = self.y + self.height // 2
        wobble = 1.0 + 0.1 * math.sin(Psyche.t * 4 + self.wobble_phase)
        emoji_size = int(min(self.width, self.height) * 1.1 * wobble)
        EmojiCache.draw(surface, self.emoji, cx, cy, size=emoji_size)
        # Glow
        glow_color = Psyche.neon(self.hue_offset, speed=1.5)
        glow_r = int(max(self.width, self.height) * 0.7 * wobble)
        glow_surf = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (*glow_color, 30), (glow_r, glow_r), glow_r)
        surface.blit(glow_surf, (int(cx - glow_r), int(cy - glow_r)))


class FlyingObstacle:
    def __init__(self, x, y_offset=-70):
        self.x = x
        self.y = GROUND_Y + y_offset
        self.width = 42
        self.height = 28
        self.wing_timer = random.uniform(0, math.pi * 2)
        self.passed = False
        self.emoji = random.choice(["🦅", "🦇", "🪽", "🔮", "👽"])
        self.hue_offset = random.uniform(0, 1)
        self.near_missed = False

    @property
    def rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def update(self, dt):
        self.wing_timer += dt * 10

    def draw(self, surface, cam_x=0):
        sx = self.x - cam_x
        cx = sx + self.width // 2
        cy = self.y + self.height // 2 + math.sin(self.wing_timer) * 5
        wobble = 1.0 + 0.12 * math.sin(Psyche.t * 5 + self.hue_offset * 7)
        emoji_size = int(34 * wobble)
        EmojiCache.draw(surface, self.emoji, cx, cy, size=emoji_size)
        glow_color = Psyche.neon(self.hue_offset, speed=2.0)
        for i in range(3):
            tx = cx - 10 - i * 8
            ty = cy + math.sin(self.wing_timer + i) * 4
            r = max(1, int(3 - i))
            pygame.draw.circle(surface, glow_color, (int(tx), int(ty)), r)


class Coin:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.radius = 12
        self.collected = False
        self.bob_timer = random.uniform(0, math.pi * 2)
        self.emoji = random.choice(["💰", "⭐", "💎", "🌟", "🏷️"])

    @property
    def rect(self):
        return pygame.Rect(self.x - self.radius, self.y - self.radius,
                           self.radius * 2, self.radius * 2)

    def update(self, dt):
        self.bob_timer += dt * 5

    def draw(self, surface, cam_x=0):
        if self.collected:
            return
        sx = self.x - cam_x
        sy = self.y + math.sin(self.bob_timer) * 6
        wobble = 1.0 + 0.15 * math.sin(Psyche.t * 4 + self.bob_timer)
        EmojiCache.draw(surface, self.emoji, sx, sy, size=int(24 * wobble))


class PowerUp:
    def __init__(self, x, y, ptype):
        self.x = x
        self.y = y
        self.ptype = ptype
        info = POWERUP_TYPES[ptype]
        self.emoji = info["emoji"]
        self.collected = False
        self.bob_timer = random.uniform(0, math.pi * 2)
        self.radius = 16
        self.hue_offset = random.uniform(0, 1)

    @property
    def rect(self):
        return pygame.Rect(self.x - self.radius, self.y - self.radius,
                           self.radius * 2, self.radius * 2)

    def update(self, dt):
        self.bob_timer += dt * 4

    def draw(self, surface, cam_x=0):
        if self.collected:
            return
        sx = self.x - cam_x
        sy = self.y + math.sin(self.bob_timer) * 8
        # Spinning glow ring
        ring_r = 22 + int(4 * math.sin(Psyche.t * 3 + self.hue_offset))
        ring_color = Psyche.neon(self.hue_offset, speed=1.5)
        ring_surf = pygame.Surface((ring_r * 2, ring_r * 2), pygame.SRCALPHA)
        pygame.draw.circle(ring_surf, (*ring_color, 60), (ring_r, ring_r), ring_r)
        pygame.draw.circle(ring_surf, (*ring_color, 120), (ring_r, ring_r), ring_r, 2)
        surface.blit(ring_surf, (int(sx - ring_r), int(sy - ring_r)))
        # Rotating sparkles
        for i in range(4):
            angle = Psyche.t * 3 + i * math.pi / 2
            spark_x = sx + math.cos(angle) * 18
            spark_y = sy + math.sin(angle) * 18
            pygame.draw.circle(surface, Psyche.neon(i * 0.25, speed=2), (int(spark_x), int(spark_y)), 2)
        EmojiCache.draw(surface, self.emoji, sx, sy, size=28)


# ═══════════════════════════════════════════════════════════════════════════════
# BACKGROUND
# ═══════════════════════════════════════════════════════════════════════════════
class Background:
    def __init__(self):
        self.clouds = []
        for _ in range(8):
            self.clouds.append({
                "x": random.uniform(0, WIDTH * 2),
                "y": random.uniform(30, 180),
                "speed": random.uniform(15, 35),
                "emoji": random.choice(["☁️", "⛅", "🌤️"]),
            })
        self.stars = []
        for _ in range(40):
            self.stars.append({
                "x": random.uniform(0, WIDTH),
                "y": random.uniform(0, GROUND_Y - 50),
                "phase": random.uniform(0, math.pi * 2),
                "speed": random.uniform(1, 4),
                "emoji": random.choice(["✨", "⭐", "🌟", "💫"]),
                "size": random.randint(10, 18),
            })
        self.ground_offset = 0
        self.bg_hue_shift = 0
        self.ground_emojis = ["🌿", "🍀", "🌸", "🌺", "🍄", "🌵", "🌺", "🍀",
                              "🌿", "🌸", "🌺", "🍀", "🍄", "🌿", "🌸", "🌺"]
        random.shuffle(self.ground_emojis)

    def update(self, dt, game_speed):
        self.bg_hue_shift += dt * 0.05
        for c in self.clouds:
            c["x"] -= c["speed"] * dt * (game_speed / 400)
            if c["x"] < -60:
                c["x"] = WIDTH + random.uniform(0, 200)
                c["y"] = random.uniform(30, 180)
                c["emoji"] = random.choice(["☁️", "⛅", "🌤️"])
        for s in self.stars:
            s["phase"] += dt * s["speed"]
        self.ground_offset = (self.ground_offset + game_speed * dt) % 50

    def draw(self, surface):
        # Psychedelic sky
        h1 = (Psyche.t * 0.08 + self.bg_hue_shift * 0.1) % 1.0
        h2 = (h1 + 0.15) % 1.0
        r1, g1, b1 = colorsys.hsv_to_rgb(h1, 0.4, 0.95)
        r2, g2, b2 = colorsys.hsv_to_rgb(h2, 0.3, 1.0)
        sky_top = (int(r1*255), int(g1*255), int(b1*255))
        sky_bot = (int(r2*255), int(g2*255), int(b2*255))
        for i in range(GROUND_Y):
            t = i / max(GROUND_Y - 1, 1)
            color = tuple(int(a + (b-a)*t) for a, b in zip(sky_top, sky_bot))
            pygame.draw.line(surface, color, (0, i), (WIDTH, i))

        # Sun
        sun_x, sun_y = WIDTH - 100, int(60 + 20 * math.sin(Psyche.t * 0.5))
        for ring in range(5, 0, -1):
            ring_hue = (Psyche.t * 0.5 + ring * 0.15) % 1.0
            rr, rg, rb = colorsys.hsv_to_rgb(ring_hue, 0.6, 1.0)
            r = 30 + ring * 10
            ring_surf = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            pygame.draw.circle(ring_surf, (int(rr*255),int(rg*255),int(rb*255), 40), (r,r), r)
            surface.blit(ring_surf, (sun_x - r, sun_y - r))
        EmojiCache.draw(surface, "☀️", sun_x, sun_y, size=40)

        # Stars
        for s in self.stars:
            brightness = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(s["phase"]))
            if brightness > 0.6:
                wobble = 1.0 + 0.2 * math.sin(s["phase"] * 2)
                EmojiCache.draw(surface, s["emoji"], s["x"], s["y"], size=int(s["size"] * wobble))

        # Clouds
        for c in self.clouds:
            wobble = 1.0 + 0.08 * math.sin(Psyche.t * 2 + c["x"] * 0.01)
            EmojiCache.draw(surface, c["emoji"], c["x"] + 40, c["y"] + 20, size=int(32 * wobble))

        # Ground
        ground_hue = (Psyche.t * 0.15) % 1.0
        gr, gg, gb = colorsys.hsv_to_rgb(ground_hue, 0.6, 0.85)
        ground_col = (int(gr*255), int(gg*255), int(gb*255))
        pygame.draw.rect(surface, ground_col, (0, GROUND_Y, WIDTH, HEIGHT - GROUND_Y))
        pygame.draw.line(surface, Psyche.neon(0, speed=1.0), (0, GROUND_Y), (WIDTH, GROUND_Y), 3)
        dr, dg, db = colorsys.hsv_to_rgb((ground_hue + 0.3) % 1.0, 0.5, 0.6)
        pygame.draw.rect(surface, (int(dr*255),int(dg*255),int(db*255)), (0, GROUND_Y+20, WIDTH, HEIGHT-GROUND_Y-20))

        # Ground tiles
        start_x = -int(self.ground_offset)
        tile_spacing = 50
        for i in range(-1, WIDTH // tile_spacing + 3):
            tx = start_x + i * tile_spacing
            idx = (i + int(self.ground_offset / tile_spacing)) % len(self.ground_emojis)
            wobble = 1.0 + 0.1 * math.sin(Psyche.t * 3 + i * 0.5)
            EmojiCache.draw(surface, self.ground_emojis[idx], tx, GROUND_Y + 10, size=int(18 * wobble))


# ═══════════════════════════════════════════════════════════════════════════════
# GAME
# ═══════════════════════════════════════════════════════════════════════════════
class Game:
    STATE_MENU      = 0
    STATE_CHAR_SEL  = 1
    STATE_PLAYING   = 2
    STATE_DEAD      = 3
    STATE_ACHIEV    = 4

    def __init__(self):
        self.high_score = SAVE_DATA.get("high_score", 0)
        self.state = self.STATE_MENU
        self.bg = Background()
        self.particles = ParticleSystem()
        self.floating_texts = []
        self.achievement_popups = []
        self.screen_fx = ScreenFX()
        self.menu_sel = 0
        self.char_sel = SAVE_DATA.get("selected_char", 0)
        self.ach_scroll = 0
        self.unlocked_achievements = SAVE_DATA.get("achievements", [])
        self.stats = SAVE_DATA.get("stats", {})
        self.reset()

    def reset(self):
        self.player = Player(120, GROUND_Y, self.char_sel)
        self.obstacles = []
        self.flying_obstacles = []
        self.coins = []
        self.powerups = []
        self.score = 0
        self.display_score = 0  # for animated counter
        self.coin_count = 0
        self.distance = 0
        self.game_speed = 400
        self.min_speed = 400
        self.max_speed = 900
        self.spawn_timer = 1.5
        self.fly_spawn_timer = 3.0
        self.coin_spawn_timer = 4.0
        self.powerup_spawn_timer = 8.0
        self.difficulty_timer = 0
        self.cam_x = 0
        # Combo system
        self.combo = 0
        self.combo_timer = 0
        self.combo_decay = 2.0
        self.best_combo = 0
        # Wave system
        self.wave = 1
        self.wave_timer = 0
        self.wave_display_timer = 0
        self.wave_speed_bonus = 0
        # Near miss tracking
        self.near_miss_count = 0

    def handle_input(self, event):
        if event.type != pygame.KEYDOWN:
            return

        if self.state == self.STATE_MENU:
            if event.key in (pygame.K_UP, pygame.K_DOWN):
                self.menu_sel = (self.menu_sel + 1) % 4
                SoundEngine.play("navigate")
            elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                SoundEngine.play("select")
                if self.menu_sel == 0:  # Play
                    self.state = self.STATE_PLAYING
                    self.reset()
                elif self.menu_sel == 1:  # Characters
                    self.state = self.STATE_CHAR_SEL
                elif self.menu_sel == 2:  # Achievements
                    self.state = self.STATE_ACHIEV
                    self.ach_scroll = 0
                elif self.menu_sel == 3:  # Quit
                    self._save_and_quit()

        elif self.state == self.STATE_CHAR_SEL:
            if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                self.char_sel = (self.char_sel + (1 if event.key == pygame.K_RIGHT else -1)) % len(CHARACTERS)
                SoundEngine.play("navigate")
            elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                SAVE_DATA["selected_char"] = self.char_sel
                save_game(SAVE_DATA)
                SoundEngine.play("select")
                self.state = self.STATE_MENU
            elif event.key == pygame.K_ESCAPE:
                self.state = self.STATE_MENU

        elif self.state == self.STATE_ACHIEV:
            if event.key == pygame.K_ESCAPE or event.key in (pygame.K_SPACE, pygame.K_RETURN):
                self.state = self.STATE_MENU
            elif event.key == pygame.K_DOWN:
                self.ach_scroll = min(self.ach_scroll + 1, max(0, len(ACHIEVEMENTS) - 6))
            elif event.key == pygame.K_UP:
                self.ach_scroll = max(0, self.ach_scroll - 1)

        elif self.state == self.STATE_PLAYING:
            if event.key in (pygame.K_SPACE, pygame.K_UP):
                self.player.jump()
            elif event.key == pygame.K_DOWN:
                self.player.slide()
            elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                self.player.start_dash()
            elif event.key == pygame.K_s:
                SoundEngine.enabled = not SoundEngine.enabled
            elif event.key == pygame.K_ESCAPE:
                self.state = self.STATE_MENU

        elif self.state == self.STATE_DEAD:
            if event.key in (pygame.K_SPACE, pygame.K_RETURN) and self.player.death_timer > 0.5:
                self.state = self.STATE_PLAYING
                self.reset()
            elif event.key == pygame.K_ESCAPE:
                self.state = self.STATE_MENU

    def _check_near_miss(self, obs_rect):
        """Check if player barely dodged an obstacle."""
        pr = self.player.rect
        expanded = pr.inflate(16, 16)  # slightly larger hitbox for near-miss
        if not expanded.colliderect(obs_rect):
            return False
        if not pr.colliderect(obs_rect):  # actual collision would be separate
            return True
        return False

    def _check_achievements(self):
        all_stats = dict(self.stats)
        all_stats["jumps"] = all_stats.get("jumps", 0) + self.player.run_jumps
        all_stats["double_jumps"] = all_stats.get("double_jumps", 0) + self.player.run_double_jumps
        all_stats["slides"] = all_stats.get("slides", 0) + self.player.run_slides
        all_stats["total_coins"] = all_stats.get("total_coins", 0) + self.coin_count
        all_stats["best_score"] = max(all_stats.get("best_score", 0), self.score)
        all_stats["best_combo"] = max(all_stats.get("best_combo", 0), self.best_combo)
        all_stats["best_distance"] = max(all_stats.get("best_distance", 0), self.distance)
        all_stats["total_powerups"] = all_stats.get("total_powerups", 0)
        all_stats["near_misses"] = all_stats.get("near_misses", 0) + self.near_miss_count
        all_stats["max_hits"] = max(all_stats.get("max_hits", 0), self.player.hits_taken)

        for ach in ACHIEVEMENTS:
            if ach["id"] not in self.unlocked_achievements:
                if ach["check"](all_stats):
                    self.unlocked_achievements.append(ach["id"])
                    self.achievement_popups.append(AchievementPopup(ach))
                    SoundEngine.play("achievement")
                    self.screen_fx.flash((255, 255, 100), 0.3)

        self.stats = all_stats

    def _save_progress(self):
        SAVE_DATA["high_score"] = self.high_score
        SAVE_DATA["achievements"] = self.unlocked_achievements
        SAVE_DATA["stats"] = self.stats
        SAVE_DATA["selected_char"] = self.char_sel
        save_game(SAVE_DATA)

    def _save_and_quit(self):
        self._check_achievements()
        self._save_progress()
        pygame.quit()
        sys.exit()

    def spawn_obstacle(self):
        x = WIDTH + self.cam_x + random.uniform(20, 80)
        difficulty = min(1.0, (self.game_speed - self.min_speed) / (self.max_speed - self.min_speed))
        types = ["spike", "crate"]
        if difficulty > 0.3:
            types.append("tall")
        if difficulty > 0.5:
            types.append("double")
        self.obstacles.append(Obstacle(x, random.choice(types)))

    def spawn_flying_obstacle(self):
        x = WIDTH + self.cam_x + random.uniform(20, 80)
        y_off = random.choice([-70, -50, -90, -110])
        self.flying_obstacles.append(FlyingObstacle(x, y_off))

    def spawn_coins(self):
        x = WIDTH + self.cam_x + random.uniform(40, 100)
        y = GROUND_Y - random.uniform(60, 160)
        count = random.randint(3, 6)
        for i in range(count):
            self.coins.append(Coin(x + i * 35, y))

    def spawn_powerup(self):
        x = WIDTH + self.cam_x + random.uniform(40, 100)
        y = GROUND_Y - random.uniform(80, 180)
        ptype = random.choice(list(POWERUP_TYPES.keys()))
        self.powerups.append(PowerUp(x, y, ptype))

    def check_collisions(self):
        pr = self.player.rect
        hit = False

        for obs in self.obstacles:
            if not obs.near_missed and self._check_near_miss(obs.rect):
                obs.near_missed = True
                self.near_miss_count += 1
                bonus = 25
                self.score += bonus
                self.floating_texts.append(FloatingText(
                    self.player.x + 20, self.player.y - 10,
                    f"NEAR MISS +{bonus}", (255, 255, 0), 20, 0.8, "😈"))
            if pr.colliderect(obs.rect):
                actually_hit = self.player.take_hit()
                if actually_hit and not self.player.alive:
                    hit = True
                elif actually_hit:
                    self.screen_fx.flash((255, 50, 50), 0.2)
                    self.screen_fx.shake(8)
                    self.combo = 0
                obs.near_missed = True

        for obs in self.flying_obstacles:
            if not obs.near_missed and self._check_near_miss(obs.rect):
                obs.near_missed = True
                self.near_miss_count += 1
                bonus = 25
                self.score += bonus
                self.floating_texts.append(FloatingText(
                    self.player.x + 20, self.player.y - 10,
                    f"NEAR MISS +{bonus}", (255, 255, 0), 20, 0.8, "😈"))
            if pr.colliderect(obs.rect):
                actually_hit = self.player.take_hit()
                if actually_hit and not self.player.alive:
                    hit = True
                elif actually_hit:
                    self.screen_fx.flash((255, 50, 50), 0.2)
                    self.screen_fx.shake(8)
                    self.combo = 0
                obs.near_missed = True

        # Coins (magnet effect)
        magnet_range = 150 if self.player.has_power("magnet") else 0
        for coin in self.coins:
            if coin.collected:
                continue
            # Magnet attraction
            if magnet_range > 0:
                dx = self.player.x + self.player.width//2 - coin.x
                dy = self.player.y + self.player.height//2 - coin.y
                dist = math.sqrt(dx*dx + dy*dy)
                if 0 < dist < magnet_range:
                    speed = 600 * (1 - dist/magnet_range)
                    coin.x += (dx/dist) * speed * (1/60)
                    coin.y += (dy/dist) * speed * (1/60)

            if pr.colliderect(coin.rect):
                coin.collected = True
                self.coin_count += 1
                # Combo
                self.combo += 1
                self.combo_timer = self.combo_decay
                self.best_combo = max(self.best_combo, self.combo)
                multiplier = self._get_score_multiplier()
                pts = 50 * multiplier
                self.score += pts
                self.particles.emit_burst(coin.x, coin.y, 12)
                self.floating_texts.append(FloatingText(
                    coin.x, coin.y - 15, f"+{pts}", (255, 215, 0), 22, 0.7, "💰"))
                if self.combo >= 3:
                    SoundEngine.play("combo")
                else:
                    SoundEngine.play("coin")

        # Power-ups
        for pu in self.powerups:
            if not pu.collected and pr.colliderect(pu.rect):
                pu.collected = True
                info = POWERUP_TYPES[pu.ptype]
                self.player.active_powers[pu.ptype] = info["duration"]
                self.particles.emit_powerup(pu.x, pu.y, pu.hue_offset)
                self.screen_fx.flash(info["color"], 0.2)
                self.floating_texts.append(FloatingText(
                    pu.x, pu.y - 20, info["name"], info["color"], 28, 1.5, info["emoji"]))
                SoundEngine.play("powerup")
                self.stats["total_powerups"] = self.stats.get("total_powerups", 0) + 1

        return hit

    def _get_score_multiplier(self):
        mult = 1
        if self.player.has_power("x2"):
            mult *= 2
        # Combo bonus: every 3 combo = +1x
        if self.combo >= 3:
            mult += self.combo // 3
        return mult

    def update(self, dt):
        Psyche.update(dt)
        self.screen_fx.update(dt)

        # Update floating texts
        for ft in self.floating_texts:
            ft.update(dt)
        self.floating_texts = [ft for ft in self.floating_texts if ft.alive]

        # Update achievement popups
        for ap in self.achievement_popups:
            ap.update(dt)
        self.achievement_popups = [ap for ap in self.achievement_popups if ap.alive]

        if self.state == self.STATE_DEAD:
            self.player.death_timer += dt
            self.particles.update(dt)
            self.bg.update(dt, 200)
            return
        if self.state != self.STATE_PLAYING:
            self.bg.update(dt, 200)
            return

        # Slow-mo power-up
        speed_mult = 0.5 if self.player.has_power("slow") else 1.0
        effective_speed = self.game_speed * speed_mult

        # Dash speed boost
        if self.player.dash_timer > 0:
            effective_speed *= 2.0

        # Difficulty scaling
        self.difficulty_timer += dt
        self.game_speed = min(self.max_speed, self.min_speed + self.difficulty_timer * 8)

        # Wave system
        self.wave_timer += dt
        if self.wave_timer > 20 + self.wave * 5:
            self.wave += 1
            self.wave_timer = 0
            self.wave_display_timer = 2.0
            self.game_speed = min(self.max_speed, self.game_speed + 20)
            self.screen_fx.flash(Psyche.neon(0, speed=1.0), 0.3)
            self.floating_texts.append(FloatingText(
                WIDTH // 2 + self.cam_x, HEIGHT // 3,
                f"WAVE {self.wave}", Psyche.neon(0), 40, 2.0, "🌊"))
        if self.wave_display_timer > 0:
            self.wave_display_timer -= dt

        # Score
        self.distance += effective_speed * dt
        self.score = int(self.distance / 10) + self.coin_count * 50
        # Animated score display
        self.display_score += (self.score - self.display_score) * min(1, dt * 10)

        # Combo decay
        if self.combo_timer > 0:
            self.combo_timer -= dt
            if self.combo_timer <= 0:
                self.combo = 0

        self.player.update(dt)

        # Rainbow trail
        if self.player.on_ground and not self.player.sliding:
            self.particles.emit_rainbow_trail(self.player.x, GROUND_Y - 5)
        elif not self.player.on_ground:
            self.particles.emit_rainbow_trail(self.player.x + 15, self.player.y + self.player.height)
        self.particles.update(dt)

        # Spawning
        self.spawn_timer -= dt * speed_mult
        if self.spawn_timer <= 0:
            self.spawn_obstacle()
            difficulty = min(1.0, (self.game_speed - self.min_speed) / (self.max_speed - self.min_speed))
            self.spawn_timer = random.uniform(1.0, 2.2 - difficulty * 0.8)

        self.fly_spawn_timer -= dt * speed_mult
        if self.fly_spawn_timer <= 0:
            self.spawn_flying_obstacle()
            self.fly_spawn_timer = random.uniform(2.5, 5.0)

        self.coin_spawn_timer -= dt
        if self.coin_spawn_timer <= 0:
            self.spawn_coins()
            self.coin_spawn_timer = random.uniform(3.0, 6.0)

        self.powerup_spawn_timer -= dt
        if self.powerup_spawn_timer <= 0:
            self.spawn_powerup()
            self.powerup_spawn_timer = random.uniform(8.0, 15.0)

        # Move objects
        for obs in self.obstacles:
            obs.x -= effective_speed * dt
        self.obstacles = [o for o in self.obstacles if o.x + o.width > self.cam_x - 100]

        for obs in self.flying_obstacles:
            obs.x -= effective_speed * 0.9 * dt
            obs.update(dt)
        self.flying_obstacles = [o for o in self.flying_obstacles if o.x + o.width > self.cam_x - 100]

        for c in self.coins:
            c.x -= effective_speed * dt
            c.update(dt)
        self.coins = [c for c in self.coins if c.x > self.cam_x - 100 and not c.collected]

        for pu in self.powerups:
            pu.x -= effective_speed * dt
            pu.update(dt)
        self.powerups = [pu for pu in self.powerups if pu.x > self.cam_x - 100 and not pu.collected]

        self.cam_x = self.player.x - 120

        # Collision
        if self.check_collisions():
            self.particles.emit_burst(
                self.player.x + self.player.width//2,
                self.player.y + self.player.height//2, 50)
            self.screen_fx.shake(15)
            self.state = self.STATE_DEAD
            if self.score > self.high_score:
                self.high_score = self.score
            self._check_achievements()
            self._save_progress()

        self.bg.update(dt, effective_speed)

    def draw(self):
        sx, sy = self.screen_fx.get_shake_offset()
        buf = pygame.Surface((WIDTH, HEIGHT))
        self.bg.draw(buf)

        for c in self.coins:
            c.draw(buf, self.cam_x)
        for pu in self.powerups:
            pu.draw(buf, self.cam_x)
        for obs in self.obstacles:
            obs.draw(buf, self.cam_x)
        for obs in self.flying_obstacles:
            obs.draw(buf, self.cam_x)

        if self.state != self.STATE_DEAD or self.player.death_timer < 0.3:
            self.player.draw(buf, self.cam_x)

        self.particles.draw(buf, self.cam_x)
        for ft in self.floating_texts:
            ft.draw(buf, self.cam_x)

        if self.state == self.STATE_PLAYING:
            self._draw_hud(buf)

        screen.fill(BLACK)
        screen.blit(buf, (int(sx), int(sy)))

        # Screen effects overlay
        self.screen_fx.draw_overlay(screen)

        # Achievement popups (on top of everything)
        for ap in self.achievement_popups:
            ap.draw(screen)

        if self.state == self.STATE_MENU:
            self._draw_menu()
        elif self.state == self.STATE_CHAR_SEL:
            self._draw_char_select()
        elif self.state == self.STATE_DEAD:
            self._draw_game_over()
        elif self.state == self.STATE_ACHIEV:
            self._draw_achievements_screen()

        pygame.display.flip()

    def _draw_hud(self, surface):
        # Score (animated)
        score_color = Psyche.neon(0, speed=1.0)
        score_txt = font_medium.render(f"Score: {int(self.display_score)}", True, score_color)
        surface.blit(score_txt, (20, 12))

        # Lives (hearts)
        for i in range(Player.MAX_LIVES):
            hx = 20 + i * 30
            hy = 46
            if i < self.player.lives:
                EmojiCache.draw(surface, "❤️", hx + 10, hy, size=22)
            else:
                EmojiCache.draw(surface, "🖤", hx + 10, hy, size=22)

        # Coins
        EmojiCache.draw(surface, "💰", 140, 48, size=20)
        coin_txt = font_small.render(f"x{self.coin_count}", True, Psyche.neon(0.15))
        surface.blit(coin_txt, (154, 40))

        # High score
        hs_txt = font_small.render(f"Best: {self.high_score}", True, Psyche.neon(0.3, speed=0.8))
        surface.blit(hs_txt, (WIDTH - hs_txt.get_width() - 20, 12))

        # Wave
        wave_txt = font_small.render(f"Wave {self.wave}", True, Psyche.neon(0.6, speed=1.2))
        surface.blit(wave_txt, (WIDTH - wave_txt.get_width() - 20, 34))

        # Speed bar (rainbow)
        speed_pct = (self.game_speed - self.min_speed) / (self.max_speed - self.min_speed)
        bar_w, bar_h = 100, 10
        bar_x = WIDTH - bar_w - 20
        bar_y = 58
        for i in range(bar_w):
            t = i / bar_w
            h = (Psyche.t * 0.5 + t) % 1.0
            r, g, b = colorsys.hsv_to_rgb(h, 0.8, 0.9)
            pygame.draw.line(surface, (int(r*255),int(g*255),int(b*255)),
                           (bar_x+i, bar_y), (bar_x+i, bar_y+bar_h))
        fill_w = int(bar_w * speed_pct)
        if bar_w - fill_w > 0:
            dark = pygame.Surface((bar_w - fill_w, bar_h), pygame.SRCALPHA)
            dark.fill((0, 0, 0, 150))
            surface.blit(dark, (bar_x + fill_w, bar_y))
        pygame.draw.rect(surface, Psyche.neon(0, speed=2), (bar_x, bar_y, bar_w, bar_h), 2, border_radius=3)

        # Combo display
        if self.combo >= 2:
            combo_scale = min(1.5, 1.0 + 0.1 * self.combo)
            combo_size = int(28 * combo_scale)
            combo_font = pygame.font.SysFont("DejaVu Sans", combo_size, bold=True)
            combo_color = Psyche.neon(self.combo * 0.2, speed=3)
            combo_txt = combo_font.render(f"x{self.combo} COMBO!", True, combo_color)
            cx = WIDTH // 2 - combo_txt.get_width() // 2
            surface.blit(combo_txt, (cx, 15))
            # Combo timer bar
            if self.combo_timer > 0:
                ct_pct = self.combo_timer / self.combo_decay
                ct_w = 120
                ct_x = WIDTH // 2 - ct_w // 2
                ct_y = 15 + combo_size + 4
                pygame.draw.rect(surface, (80, 80, 80), (ct_x, ct_y, ct_w, 4), border_radius=2)
                pygame.draw.rect(surface, combo_color, (ct_x, ct_y, int(ct_w * ct_pct), 4), border_radius=2)

        # Active power-ups
        pu_x = 20
        pu_y = HEIGHT - 35
        for ptype, time_left in self.player.active_powers.items():
            info = POWERUP_TYPES[ptype]
            EmojiCache.draw(surface, info["emoji"], pu_x + 14, pu_y, size=22)
            # Timer bar
            pct = time_left / info["duration"]
            bar_w = 50
            pygame.draw.rect(surface, (60, 60, 60), (pu_x + 30, pu_y + 6, bar_w, 6), border_radius=3)
            pygame.draw.rect(surface, info["color"], (pu_x + 30, pu_y + 6, int(bar_w * pct), 6), border_radius=3)
            name_txt = font_tiny.render(info["name"], True, info["color"])
            surface.blit(name_txt, (pu_x + 30, pu_y - 8))
            pu_x += 100

        # Dash cooldown
        if self.player.dash_cooldown > 0:
            dash_pct = 1.0 - (self.player.dash_cooldown / 1.5)
            EmojiCache.draw(surface, "💨", WIDTH - 60, HEIGHT - 30, size=20)
            dw = 40
            dx = WIDTH - 50
            dy = HEIGHT - 22
            pygame.draw.rect(surface, (60, 60, 60), (dx, dy, dw, 5), border_radius=2)
            pygame.draw.rect(surface, (200, 100, 255), (dx, dy, int(dw * dash_pct), 5), border_radius=2)
        else:
            EmojiCache.draw(surface, "💨", WIDTH - 60, HEIGHT - 30, size=20)
            ready = font_tiny.render("READY", True, (200, 100, 255))
            surface.blit(ready, (WIDTH - 55, HEIGHT - 18))

        # Jump indicators
        for i in range(self.player.jumps_left):
            EmojiCache.draw(surface, "⬆️", 20 + i * 28, HEIGHT - 60, size=20)

    def _draw_menu(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 80))
        screen.blit(overlay, (0, 0))

        # Rainbow title
        for offset, color_shift in [(3, 0.05), (0, 0)]:
            h = (Psyche.t * 0.4 + color_shift) % 1.0
            r, g, b = colorsys.hsv_to_rgb(h, 0.9, 1.0)
            title = font_huge.render("PSYCHEDELIC RUNNER", True, (int(r*255),int(g*255),int(b*255)))
            screen.blit(title, (WIDTH//2 - title.get_width()//2 + offset, 60))

        ver = font_tiny.render("v3.0 ULTIMATE EDITION", True, (150, 150, 180))
        screen.blit(ver, (WIDTH//2 - ver.get_width()//2, 125))

        # Decorative emojis
        deco = ["🌈", "✨", "🔥", "💥", "🌟", "💎", "🔥", "✨", "🌈"]
        for i, em in enumerate(deco):
            wobble = 1.0 + 0.2 * math.sin(Psyche.t * 4 + i * 0.7)
            EmojiCache.draw(screen, em, WIDTH//2 - 157 + i * 35, 160, size=int(28 * wobble))

        # Menu items
        items = [
            ("🎮  PLAY", "Start running!"),
            ("🎭  CHARACTERS", f"Playing as: {CHARACTERS[self.char_sel]['emoji']} {CHARACTERS[self.char_sel]['name']}"),
            ("🏆  ACHIEVEMENTS", f"{len(self.unlocked_achievements)}/{len(ACHIEVEMENTS)} unlocked"),
            ("🚪  QUIT", "See you next time!"),
        ]
        y = 200
        for i, (label, desc) in enumerate(items):
            selected = (i == self.menu_sel)
            if selected:
                # Selection highlight
                hl = pygame.Surface((400, 50), pygame.SRCALPHA)
                hl.fill((255, 255, 255, 25))
                pygame.draw.rect(hl, Psyche.neon(i * 0.2, speed=2), (0, 0, 400, 50), 2, border_radius=10)
                screen.blit(hl, (WIDTH//2 - 200, y - 5))
                EmojiCache.draw(screen, "👉", WIDTH//2 - 220, y + 20, size=24)
                color = Psyche.neon(i * 0.2, speed=2)
            else:
                color = (180, 180, 200)
            txt = font_medium.render(label, True, color)
            screen.blit(txt, (WIDTH//2 - txt.get_width()//2, y))
            desc_txt = font_tiny.render(desc, True, (140, 140, 160) if not selected else (200, 200, 220))
            screen.blit(desc_txt, (WIDTH//2 - desc_txt.get_width()//2, y + 26))
            y += 58

        # High score
        if self.high_score > 0:
            EmojiCache.draw(screen, "🏆", WIDTH//2 - 80, 455, size=22)
            hs = font_small.render(f"High Score: {self.high_score}", True, Psyche.neon(0.6, speed=0.8))
            screen.blit(hs, (WIDTH//2 - hs.get_width()//2 + 15, 447))

        # Sound indicator
        snd_txt = "🔊 Sound ON" if SoundEngine.enabled else "🔇 Sound OFF  [S]"
        snd = font_tiny.render(snd_txt, True, (120, 120, 140))
        screen.blit(snd, (WIDTH - snd.get_width() - 15, HEIGHT - 25))

        # Controls hint
        hint = font_tiny.render("↑↓ Navigate  |  SPACE Select  |  S Toggle Sound", True, (100, 100, 120))
        screen.blit(hint, (WIDTH//2 - hint.get_width()//2, HEIGHT - 25))

    def _draw_char_select(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        screen.blit(overlay, (0, 0))

        title = font_large.render("SELECT YOUR CHARACTER", True, Psyche.neon(0, speed=1.5))
        screen.blit(title, (WIDTH//2 - title.get_width()//2, 30))

        hint = font_small.render("← → to choose  |  SPACE to confirm  |  ESC to go back", True, (180, 180, 200))
        screen.blit(hint, (WIDTH//2 - hint.get_width()//2, 75))

        # Character grid (2 rows of 4)
        cols, cell_w, cell_h = 4, 200, 170
        start_x = WIDTH//2 - (cols * cell_w)//2
        start_y = 110

        for i, char in enumerate(CHARACTERS):
            row, col = divmod(i, cols)
            cx = start_x + col * cell_w + cell_w // 2
            cy = start_y + row * cell_h + cell_h // 2
            selected = (i == self.char_sel)

            # Card background
            card_w, card_h = 180, 150
            card = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
            if selected:
                card.fill((255, 255, 255, 30))
                border = Psyche.neon(i * 0.1, speed=2)
                pygame.draw.rect(card, border, (0, 0, card_w, card_h), 3, border_radius=15)
                # Glow
                glow = pygame.Surface((card_w + 20, card_h + 20), pygame.SRCALPHA)
                pygame.draw.rect(glow, (*border, 30), (0, 0, card_w + 20, card_h + 20), border_radius=20)
                screen.blit(glow, (cx - card_w//2 - 10, cy - card_h//2 - 10))
            else:
                card.fill((0, 0, 0, 80))
                pygame.draw.rect(card, (80, 80, 100), (0, 0, card_w, card_h), 1, border_radius=15)
            screen.blit(card, (cx - card_w//2, cy - card_h//2))

            # Character emoji (big, animated)
            wobble = 1.0 + (0.1 if selected else 0.03) * math.sin(Psyche.t * 4 + i * 0.8)
            EmojiCache.draw(screen, char["emoji"], cx, cy - 20, size=int(56 * wobble))

            # Name
            name_color = Psyche.neon(i * 0.15, speed=1.5) if selected else (160, 160, 180)
            name_txt = font_small.render(char["name"], True, name_color)
            screen.blit(name_txt, (cx - name_txt.get_width()//2, cy + 35))

            if selected:
                EmojiCache.draw(screen, "✅", cx + 70, cy - 55, size=22)

    def _draw_game_over(self):
        t = min(1.0, self.player.death_timer / 0.5)
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, int(130 * t)))
        screen.blit(overlay, (0, 0))
        if t < 0.5:
            return

        EmojiCache.draw(screen, "💀", WIDTH//2 - 180, 135, size=38)
        go = font_huge.render("GAME OVER", True, Psyche.neon(0, speed=2))
        screen.blit(go, (WIDTH//2 - go.get_width()//2, 105))

        EmojiCache.draw(screen, "⭐", WIDTH//2 - 130, 200, size=26)
        sc = font_large.render(f"Score: {self.score}", True, Psyche.neon(0.2, speed=1.5))
        screen.blit(sc, (WIDTH//2 - sc.get_width()//2 + 10, 185))

        EmojiCache.draw(screen, "💰", WIDTH//2 - 100, 248, size=22)
        cc = font_medium.render(f"Coins: {self.coin_count}", True, Psyche.neon(0.4, speed=1.2))
        screen.blit(cc, (WIDTH//2 - cc.get_width()//2 + 10, 240))

        # Wave reached
        wave_txt = font_small.render(f"Wave: {self.wave}  |  Best Combo: x{self.best_combo}", True, Psyche.neon(0.5, speed=1.0))
        screen.blit(wave_txt, (WIDTH//2 - wave_txt.get_width()//2, 275))

        if self.score >= self.high_score and self.score > 0:
            if pygame.time.get_ticks() % 600 < 400:
                EmojiCache.draw(screen, "🎉", WIDTH//2 - 140, 308, size=26)
                EmojiCache.draw(screen, "🎉", WIDTH//2 + 140, 308, size=26)
                nh = font_medium.render("NEW HIGH SCORE!", True, Psyche.neon(0.5, speed=2))
                screen.blit(nh, (WIDTH//2 - nh.get_width()//2, 300))

        # Raining death emojis
        death_emojis = ["💀", "☠️", "💥", "👀", "😵", "💢"]
        for i in range(8):
            ex = WIDTH//2 + math.sin(Psyche.t * 2 + i * 1.3) * 200
            ey = (Psyche.t * 60 + i * 80) % (HEIGHT + 40) - 20
            EmojiCache.draw(screen, death_emojis[i % len(death_emojis)], ex, ey, size=20)

        if self.player.death_timer > 0.5:
            if pygame.time.get_ticks() % 1000 < 700:
                restart = font_small.render("SPACE to Restart  |  ESC for Menu", True, Psyche.neon(0.7))
                screen.blit(restart, (WIDTH//2 - restart.get_width()//2, 370))
                EmojiCache.draw(screen, "🔄", WIDTH//2 - 190, 378, size=20)

    def _draw_achievements_screen(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        screen.blit(overlay, (0, 0))

        title = font_large.render("ACHIEVEMENTS", True, Psyche.neon(0, speed=1.5))
        screen.blit(title, (WIDTH//2 - title.get_width()//2, 15))

        count_txt = font_small.render(f"{len(self.unlocked_achievements)} / {len(ACHIEVEMENTS)}", True, (200, 200, 220))
        screen.blit(count_txt, (WIDTH//2 - count_txt.get_width()//2, 58))

        # Progress bar
        pct = len(self.unlocked_achievements) / max(len(ACHIEVEMENTS), 1)
        bar_w = 300
        bar_x = WIDTH//2 - bar_w//2
        pygame.draw.rect(screen, (60, 60, 80), (bar_x, 82, bar_w, 8), border_radius=4)
        if pct > 0:
            for i in range(int(bar_w * pct)):
                h = (Psyche.t * 0.5 + i / bar_w) % 1.0
                r, g, b = colorsys.hsv_to_rgb(h, 0.8, 0.9)
                pygame.draw.line(screen, (int(r*255),int(g*255),int(b*255)),
                               (bar_x + i, 82), (bar_x + i, 90))

        # List (show 6 at a time)
        visible = ACHIEVEMENTS[self.ach_scroll:self.ach_scroll + 6]
        y = 100
        for ach in visible:
            unlocked = ach["id"] in self.unlocked_achievements
            card = pygame.Surface((WIDTH - 100, 55), pygame.SRCALPHA)
            card.fill((255, 255, 255, 15) if unlocked else (0, 0, 0, 60))
            border = Psyche.neon(AchievementPopup.__init__.__code__.co_freevars[0] if False else 0, speed=1) if unlocked else (60, 60, 80)
            if not unlocked:
                border = (60, 60, 80)
            pygame.draw.rect(card, border, (0, 0, WIDTH - 100, 55), 1, border_radius=8)
            screen.blit(card, (50, y))

            EmojiCache.draw(screen, ach["emoji"] if unlocked else "🔒", 80, y + 28, size=24)
            name_color = WHITE if unlocked else (100, 100, 120)
            name = font_small.render(ach["name"], True, name_color)
            screen.blit(name, (100, y + 5))
            desc_color = (180, 180, 200) if unlocked else (80, 80, 100)
            desc = font_tiny.render(ach["desc"], True, desc_color)
            screen.blit(desc, (100, y + 28))
            if unlocked:
                check = font_small.render("✓", True, (100, 255, 100))
                screen.blit(check, (WIDTH - 120, y + 15))
            y += 62

        hint = font_tiny.render("↑↓ Scroll  |  SPACE/ESC Back", True, (120, 120, 140))
        screen.blit(hint, (WIDTH//2 - hint.get_width()//2, HEIGHT - 25))


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    SoundEngine.init_sounds()
    game = Game()
    running = True

    while running:
        dt = clock.tick(FPS) / 1000.0
        dt = min(dt, 0.05)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game._save_and_quit()
            elif event.type == pygame.KEYDOWN:
                game.handle_input(event)

        game.update(dt)
        game.draw()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()