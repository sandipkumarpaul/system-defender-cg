import math
import time
import random
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *

# ==========================================
# GLOBAL SETTINGS & CONSTANTS
# ==========================================
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 800
GRID_LENGTH = 600

# Constants for game balance
TANK_RADIUS = 30
BARREL_LENGTH = 40
BULLET_RADIUS = 8
BULLET_SPEED = 600.0
BOMB_RADIUS = 12
BOMB_SPEED = 300.0
BOMB_Z_VEL = 250.0
GRAVITY = 350.0
ENEMY_RADIUS = 25
BOSS_RADIUS = 35
POWERUP_INTERVAL = 8.0
MAX_POWERUPS = 3
BOSS_HIT_COOLDOWN = 0.5  # Brief invulnerability after a boss rams the player

# ==========================================
# GLOBAL STATE DICTIONARY (Mob Programming Standard)
# ==========================================
def new_game_state():
    """Returns a fresh copy of the full game state (used on launch and on restart)."""
    return {
        "in_menu": True,

        # Player
        "player_pos": [0.0, -400.0, 0.0],
        "player_angle": 90.0,  # Facing positive Y
        "turret_angle": 0.0,   # Relative to base
        "player_speed": 180.0,
        "player_hp": 100.0,
        "max_hp": 100.0,
        "bomb_count": 5,

        # Combat Entities
        "bullets": [],
        "bombs": [],
        "boss_bombs": [],
        "particles": [],
        "enemies": [],

        # Progression
        "score": 0,
        "level": 1,
        "spawn_timer": 0.0,
        "spawn_interval": 3.0,

        # Environment
        "firewalls": [],
        "powerups": [],
        "powerup_timer": POWERUP_INTERVAL,

        # UI & Control Flags
        "camera_mode": "perspective",
        "game_over": False,
        "running": True,
        "won": False,
        "hud_flash_timer": 0.0,
        "hud_flash_state": True,
        "lives": 3,
        "invincible_timer": 0.0,
        "heal_zone_cooldown": 0.0,

        # Health bar flicker
        "health_bar_flick_timer": 0.0,
        "health_bar_flick": True,
        "boss_health_bar_flick_timer": 0.0,
        "boss_health_bar_flick": True,

        # Input States
        "keys": {b"w": False, b"s": False, b"a": False, b"d": False,
                 GLUT_KEY_LEFT: False, GLUT_KEY_RIGHT: False},

        # Buff / debuff zones
        "zones": [],
        "zone_spawn_timer": 0.0,
        "zone_spawn_interval": 6.0,
        "debuff_interval": 0,

        # Sprint
        "sprint_active": False,
        "stamina": 100.0,
        "max_stamina": 100.0,
        "sprint_drain": 40.0,
        "sprint_recover": 12.0,

        # Boss A ("Pegasus")
        "bossA": {
            "alive": False,
            "pos": [0, 0, 0],
            "health": 100
        },

        # Boss B ("Chitti")
        "bossB": {
            "alive": False,
            "pos": [0, 500, 0],
            "health": 150,
            "speed_bossB": 90,
            "attack_timer": 0.0,
            "spawn_timer": 5.0,
            "orbit_angle": 0.0,
            "orbit_speed": 120.0
        },
    }

game = new_game_state()

last_time = 0
QUADRIC = None  # Shared GLU quadric, created once in main() and reused by every draw call

# ==========================================
# UTILITY FUNCTIONS
# ==========================================
def dist2d(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])

def circles_overlap(posA, radA, posB, radB):
    return dist2d(posA, posB) < (radA + radB)

def can_act():
    # True only while a round is actively being played (not paused, in the menu, or finished).
    return game["running"] and not game["in_menu"] and not game["game_over"] and not game["won"]

def damage_player(amount, cooldown=0.0):
    # Applies damage unless the player is invincible; an optional cooldown grants brief i-frames.
    if game["invincible_timer"] > 0:
        return
    game["player_hp"] = max(0.0, game["player_hp"] - amount)
    game["invincible_timer"] = cooldown

def barrel_tip():
    # Returns the world-space muzzle position and the combined base + turret firing angle.
    total_angle = math.radians(game["player_angle"] + game["turret_angle"])
    tip_x = game["player_pos"][0] + BARREL_LENGTH * math.cos(total_angle)
    tip_y = game["player_pos"][1] + BARREL_LENGTH * math.sin(total_angle)
    return tip_x, tip_y, total_angle

def fire_bullet():
    # Fires a ricocheting bullet from the turret barrel.
    tip_x, tip_y, angle = barrel_tip()
    game["bullets"].append({
        "pos": [tip_x, tip_y, 15.0],
        "vel": [BULLET_SPEED * math.cos(angle), BULLET_SPEED * math.sin(angle), 0.0],
        "bounces": 3
    })

def launch_bomb():
    # Feature 3: Launches a parabolic bomb from the turret barrel (if any are left).
    if game["bomb_count"] <= 0:
        return
    tip_x, tip_y, angle = barrel_tip()
    game["bombs"].append({
        "pos": [tip_x, tip_y, 15.0],
        "vel": [BOMB_SPEED * math.cos(angle), BOMB_SPEED * math.sin(angle), BOMB_Z_VEL]
    })
    game["bomb_count"] -= 1

def damage_enemy(e, damage, points):
    # Damages a standard enemy (shielded minions have "life"), awarding points per hit.
    e["life"] = e.get("life", 1) - damage
    if e["life"] <= 0 and e in game["enemies"]:
        game["enemies"].remove(e)
    game["score"] += points

def defeat_bossA():
    # Pegasus bursts into four shielded minions when destroyed.
    boss = game["bossA"]
    boss["alive"] = False
    boss["health"] = 0
    bx, by, _ = boss["pos"]
    for ox, oy in [(-50, 20), (50, 20), (-50, -20), (50, -20)]:
        pos = [bx + ox, by + oy, 0]
        game["enemies"].append({"pos": pos, "level": game["level"], "phase": 0.0, "color": (0, 1, 68/255), "life": 5})
        spawn_particles(pos, 8, (1, 0.87, 0))

def defeat_bossB():
    # Destroying Chitti purges the system and wins the game.
    boss = game["bossB"]
    boss["alive"] = False
    boss["health"] = 0
    bx, by, _ = boss["pos"]
    game["won"] = True
    game["enemies"] = []
    game["boss_bombs"] = []
    spawn_particles([bx, by, 0], 40, (1.0, 0.5, 1.0))

def spawn_powerup():
    # Drops a random heal or bomb power-up somewhere inside the arena.
    game["powerups"].append({
        "type": random.choice(["heal", "bomb"]),
        "pos": [random.uniform(-GRID_LENGTH + 60, GRID_LENGTH - 60),
                random.uniform(-GRID_LENGTH + 60, GRID_LENGTH - 60), 0.0],
        "rot": 0.0,
        "phase": random.uniform(0, 2 * math.pi)
    })

def init_environment():
    """Initializes the oscillating firewall obstacles."""
    # Feature 2: Dynamic "Firewall" Obstacles - Initialization
    for _ in range(20):
        game["firewalls"].append({
            "pos": [random.uniform(-550, 550), random.uniform(-550, 550), 0.0],
            "phase": random.uniform(0, 2 * math.pi),
            "amplitude": 80.0,
            "freq": random.uniform(0.8, 1.5)
        })

# ==========================================
# DRAWING FUNCTIONS
# ==========================================
def draw_pause_menu():
    glDisable(GL_DEPTH_TEST) # Turn off depth so it draws over the 3D world

    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    # 1. Outer Border Box (Yellow)
    glColor3f(0.8, 0.6, 0.0)
    glBegin(GL_QUADS)
    glVertex2f(WINDOW_WIDTH//2 - 154, WINDOW_HEIGHT//2 - 104)
    glVertex2f(WINDOW_WIDTH//2 + 154, WINDOW_HEIGHT//2 - 104)
    glVertex2f(WINDOW_WIDTH//2 + 154, WINDOW_HEIGHT//2 + 104)
    glVertex2f(WINDOW_WIDTH//2 - 154, WINDOW_HEIGHT//2 + 104)
    glEnd()

    # 2. Inner Menu Background (Dark Grey)
    glColor3f(0.1, 0.1, 0.1)
    glBegin(GL_QUADS)
    glVertex2f(WINDOW_WIDTH//2 - 150, WINDOW_HEIGHT//2 - 100)
    glVertex2f(WINDOW_WIDTH//2 + 150, WINDOW_HEIGHT//2 - 100)
    glVertex2f(WINDOW_WIDTH//2 + 150, WINDOW_HEIGHT//2 + 100)
    glVertex2f(WINDOW_WIDTH//2 - 150, WINDOW_HEIGHT//2 + 100)
    glEnd()

    # 3. Clickable Resume Button (Green)
    glColor3f(0.0, 0.8, 0.2)
    glBegin(GL_QUADS)
    glVertex2f(WINDOW_WIDTH//2 - 80, WINDOW_HEIGHT//2 - 40)
    glVertex2f(WINDOW_WIDTH//2 + 80, WINDOW_HEIGHT//2 - 40)
    glVertex2f(WINDOW_WIDTH//2 + 80, WINDOW_HEIGHT//2 + 10)
    glVertex2f(WINDOW_WIDTH//2 - 80, WINDOW_HEIGHT//2 + 10)
    glEnd()

    # Menu Text
    draw_text_centered(WINDOW_WIDTH//2, WINDOW_HEIGHT//2 + 50, "GAME PAUSED", 1.0, 1.0, 1.0)
    draw_text_centered(WINDOW_WIDTH//2, WINDOW_HEIGHT//2 - 20, "RESUME", 0.0, 0.0, 0.0)
    draw_text_centered(WINDOW_WIDTH//2, WINDOW_HEIGHT//2 - 80, "(Press ESC or Click to resume)", 0.6, 0.6, 0.6)

    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

    glEnable(GL_DEPTH_TEST)  # Turn it back on for the 3D game!


def draw_menu():
    # Draws the 2D main menu screen.
    glDisable(GL_DEPTH_TEST)  # Turn off depth testing for the 2D menu

    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    # Title
    draw_text_centered(WINDOW_WIDTH//2, WINDOW_HEIGHT - 150, "SYSTEM DEFENDER", 0.0, 0.8, 0.8)
    draw_text_centered(WINDOW_WIDTH//2, WINDOW_HEIGHT - 180, "Purge the malware. Protect the motherboard.", 1.0, 1.0, 1.0)

    # Controls Manual
    draw_text(WINDOW_WIDTH//2 - 150, WINDOW_HEIGHT - 280, "--- CONTROLS MANUAL ---", 1.0, 1.0, 0.0)
    draw_text(WINDOW_WIDTH//2 - 150, WINDOW_HEIGHT - 320, "W / S : Move Forward / Backward", 1.0, 1.0, 1.0)
    draw_text(WINDOW_WIDTH//2 - 150, WINDOW_HEIGHT - 350, "A / D : Rotate Tank Base", 1.0, 1.0, 1.0)
    draw_text(WINDOW_WIDTH//2 - 150, WINDOW_HEIGHT - 380, "Left / Right Arrows : Rotate Turret", 1.0, 1.0, 1.0)
    draw_text(WINDOW_WIDTH//2 - 150, WINDOW_HEIGHT - 410, "Left Mouse / Enter : Fire Bullet", 1.0, 1.0, 1.0)
    draw_text(WINDOW_WIDTH//2 - 150, WINDOW_HEIGHT - 440, "Spacebar / Right Mouse : Launch Bomb", 1.0, 1.0, 1.0)
    draw_text(WINDOW_WIDTH//2 - 150, WINDOW_HEIGHT - 470, "E : Toggle Sprint (Uses Stamina)", 1.0, 1.0, 1.0)
    draw_text(WINDOW_WIDTH//2 - 150, WINDOW_HEIGHT - 500, "V : Toggle Drone Camera", 1.0, 1.0, 1.0)
    draw_text(WINDOW_WIDTH//2 - 150, WINDOW_HEIGHT - 530, "ESC : Pause / Resume Game", 1.0, 1.0, 1.0)
    draw_text(WINDOW_WIDTH//2 - 150, WINDOW_HEIGHT - 560, "R : Restart Game", 1.0, 1.0, 1.0)

    # Start Button Box
    glColor3f(0.0, 0.6, 0.2)
    glBegin(GL_QUADS)
    glVertex2f(WINDOW_WIDTH//2 - 100, 150)
    glVertex2f(WINDOW_WIDTH//2 + 100, 150)
    glVertex2f(WINDOW_WIDTH//2 + 100, 200)
    glVertex2f(WINDOW_WIDTH//2 - 100, 200)
    glEnd()

    draw_text_centered(WINDOW_WIDTH//2, 168, "CLICK TO START", 1.0, 1.0, 1.0)
    draw_text_centered(WINDOW_WIDTH//2, 120, "(Or Press ENTER)", 0.6, 0.6, 0.6)

    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    
    glEnable(GL_DEPTH_TEST)  # Turn it back on for the 3D game!
    
def draw_text(x, y, text, r=1.0, g=1.0, b=1.0, font=None):
    # Renders text on the screen in a 2D overlay.
    if font is None: font = GLUT_BITMAP_HELVETICA_18
    glColor3f(r, g, b)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glRasterPos2f(x, y)
    for ch in text:
        glutBitmapCharacter(font, ord(ch))

    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

def text_width(text, font=None):
    # Pixel width of a string rendered with a GLUT bitmap font.
    if font is None: font = GLUT_BITMAP_HELVETICA_18
    return sum(glutBitmapWidth(font, ord(ch)) for ch in text)

def draw_text_centered(cx, y, text, r=1.0, g=1.0, b=1.0, font=None):
    # Renders text horizontally centered on cx.
    draw_text(cx - text_width(text, font) // 2, y, text, r, g, b, font)

def pause_button_rect():
    # Screen-space bounds (x_min, x_max, y_min, y_max) of the HUD pause button.
    return WINDOW_WIDTH - 150, WINDOW_WIDTH - 20, 20, 60

def draw_player():
    # Draws the player's tank using a hierarchical model.
    if game["invincible_timer"] > 0 and game["hud_flash_state"]:
        return  # Blink when invincible after losing a life

    glPushMatrix()
    glTranslatef(game["player_pos"][0], game["player_pos"][1], game["player_pos"][2])
    glRotatef(game["player_angle"], 0, 0, 1)

    # --- Main Hull ---
    glColor3f(0.0, 0.55, 0.55)
    glPushMatrix()
    glScalef(1.8, 1.1, 0.55)
    glutSolidCube(TANK_RADIUS)
    glPopMatrix()

    # --- Front Armor Plate ---
    glColor3f(0.0, 0.75, 0.75)
    glPushMatrix()
    glTranslatef(TANK_RADIUS * 0.9, 0, 0)
    glScalef(0.25, 0.85, 0.48)
    glutSolidCube(TANK_RADIUS)
    glPopMatrix()

    # --- Left Track ---
    glColor3f(0.1, 0.1, 0.1)
    glPushMatrix()
    glTranslatef(0, TANK_RADIUS * 0.72, -TANK_RADIUS * 0.05)
    glScalef(2.05, 0.36, 0.42)
    glutSolidCube(TANK_RADIUS)
    glPopMatrix()

    # --- Right Track ---
    glPushMatrix()
    glTranslatef(0, -TANK_RADIUS * 0.72, -TANK_RADIUS * 0.05)
    glScalef(2.05, 0.36, 0.42)
    glutSolidCube(TANK_RADIUS)
    glPopMatrix()

    # --- Turret ---
    glPushMatrix()
    glTranslatef(0, 0, TANK_RADIUS * 0.38)
    glRotatef(game["turret_angle"], 0, 0, 1)

    # Turret ring base
    glColor3f(0.0, 0.25, 0.78)
    glPushMatrix()
    glScalef(0.78, 0.78, 0.52)
    glutSolidCube(TANK_RADIUS)
    glPopMatrix()

    # Turret dome (flattened box on top)
    glColor3f(0.05, 0.38, 0.95)
    glPushMatrix()
    glTranslatef(0, 0, TANK_RADIUS * 0.22)
    glScalef(0.58, 0.58, 0.26)
    glutSolidCube(TANK_RADIUS)
    glPopMatrix()

    # Barrel — fixed: glRotatef(90, 0, 1, 0) aligns cylinder to firing direction (+X local)
    glColor3f(0.18, 0.18, 0.18)
    glPushMatrix()
    glTranslatef(TANK_RADIUS * 0.38, 0, 0)  # Start at turret edge
    glRotatef(90, 0, 1, 0)
    gluCylinder(QUADRIC, 4, 3, BARREL_LENGTH, 8, 1)
    glPopMatrix()

    glPopMatrix()
    glPopMatrix()

def draw_firewalls():
    # Draws the oscillating firewall obstacles.
    for fw in game["firewalls"]:
        glPushMatrix()
        glTranslatef(fw["pos"][0], fw["pos"][1], fw["pos"][2] - 40)  # Center of 80-height cube
        glColor3f(0.8, 0.4, 0.1)
        glScalef(1.0, 1.0, 2.0)
        glutSolidCube(40)
        glPopMatrix()

def draw_projectiles():
    # Draws all active bullets and bombs.
    # Linear Bullets
    glColor3f(1.0, 1.0, 0.0)
    for b in game["bullets"]:
        glPushMatrix()
        glTranslatef(b["pos"][0], b["pos"][1], b["pos"][2])
        gluSphere(QUADRIC, BULLET_RADIUS, 8, 8)
        glPopMatrix()

    # Feature 3: Parabolic Bombs
    glColor3f(1.0, 0.2, 0.2)
    for b in game["bombs"]:
        glPushMatrix()
        glTranslatef(b["pos"][0], b["pos"][1], b["pos"][2])
        gluSphere(QUADRIC, BOMB_RADIUS, 10, 10)
        glPopMatrix()

    # Boss Bombs
    glColor3f(1.0, 0.0, 1.0) # Purple
    for b in game["boss_bombs"]:
        glPushMatrix()
        glTranslatef(b["pos"][0], b["pos"][1], b["pos"][2])
        gluSphere(QUADRIC, BOMB_RADIUS, 10, 10)
        glPopMatrix()

def draw_enemies():
    # Draws all standard enemies with their hierarchical model.
    for e in game["enemies"]:
        glPushMatrix()
        glTranslatef(e["pos"][0], e["pos"][1], ENEMY_RADIUS)
        is_evasive = e["level"] >= 4

        # Body
        if is_evasive:
            glColor3f(0.68, 0.0, 0.88)
        else:
            glColor3f(0.85, 0.05, 0.05)

        # Allows for custom colors, used by bosses when spawning minions.
        try:
            r, g, b = e["color"]
            glColor3f(r, g, b)
        except KeyError:
            pass

        gluSphere(QUADRIC, ENEMY_RADIUS, 14, 14)

        # Antenna shaft
        glColor3f(0.2, 0.2, 0.2)
        glPushMatrix()
        glTranslatef(0, 0, ENEMY_RADIUS * 0.7)
        gluCylinder(QUADRIC, 1.5, 0.5, ENEMY_RADIUS * 0.9, 6, 1)
        glPopMatrix()

        # Antenna tip (glowing)
        if is_evasive:
            glColor3f(0.9, 0.0, 1.0)
        else:
            glColor3f(1.0, 1.0, 0.0)
        glPushMatrix()
        glTranslatef(0, 0, ENEMY_RADIUS * 1.6)
        gluSphere(QUADRIC, 3.5, 6, 6)
        glPopMatrix()

        # 3 legs each side
        if is_evasive:
            glColor3f(0.45, 0.0, 0.6)
        else:
            glColor3f(0.5, 0.05, 0.05)
        for side in [1, -1]:
            for i in range(3):
                glPushMatrix()
                glRotatef(side * 90 + (i - 1) * 30, 0, 0, 1)
                glRotatef(40, 0, 1, 0)
                gluCylinder(QUADRIC, 2.5, 1.0, ENEMY_RADIUS * 0.85, 5, 1)
                glPopMatrix()

        glPopMatrix()

def draw_particles():
    # Draws all active particles for explosions.
    for p in game["particles"]:
        glPushMatrix()
        glTranslatef(p["pos"][0], p["pos"][1], p["pos"][2])
        r_ratio = max(0, p["life"] / p["max_life"])
        glColor3f(p["color"][0], p["color"][1], p["color"][2])
        glScalef(r_ratio, r_ratio, r_ratio)
        gluSphere(QUADRIC, 6, 5, 5)  # Low poly to save resources
        glPopMatrix()

def draw_powerups():
    # Draws all hovering power-ups (heal, bomb).
    for p in game["powerups"]:
        glPushMatrix()
        glTranslatef(p["pos"][0], p["pos"][1], p["pos"][2] + 20)
        glRotatef(p["rot"], 0, 0, 1)  # Continuous rotation

        if p["type"] == "heal":
            glColor3f(0.0, 1.0, 0.4)
            glutSolidCube(20)
        elif p["type"] == "bomb":
            glColor3f(1.0, 0.5, 0.0)
            gluSphere(QUADRIC, 12, 8, 8)

        glPopMatrix()

def draw_bossA():
    # Draws the "Pegasus" boss model.
    if not game["bossA"]["alive"]:
        return

    glPushMatrix()
    glTranslatef(game["bossA"]["pos"][0], game["bossA"]["pos"][1], BOSS_RADIUS)
    # --- UPDATED: Clamp minimum size to 50% ---
    sizeFactor = 0.5 + (game["bossA"]["health"] / 200.0) 
    glScalef(sizeFactor, sizeFactor, sizeFactor)
    


    glColor3f(0.25, 0.70, 0.35)
    gluSphere(QUADRIC, BOSS_RADIUS, 14, 14)

    glColor3f(1, 1, 1)
    glPushMatrix()
    glScalef(0.6, 0.6, 0.5)
    glTranslatef(0, 0, 40)
    gluSphere(QUADRIC, 50, 14, 14)
    glPopMatrix()

    glPushMatrix()
    glColor3f(0.2, 0.2, 0.2)
    glTranslatef(0, 0, 50)
    gluCylinder(QUADRIC, 1.5, 0.5, BOSS_RADIUS * 0.8, 6, 1)
    glColor3f(1, 0, 0)
    glTranslatef(0, 0, 20)
    gluSphere(QUADRIC, 5, 6, 6)
    glPopMatrix()

    glPopMatrix()



def draw_bossB():
    # Draws the "Chitti" boss model.
    if not game["bossB"]["alive"]:
        return

    b = game["bossB"]

    glPushMatrix()
    glTranslatef(b["pos"][0], b["pos"][1], 80)

    # Central sphere
    glColor3f(0.7, 0.1, 1.0)
    gluSphere(QUADRIC, 40, 16, 16)

    glColor3f(0.2, 0.8, 1.0)

    # Orbiting cubes
    for i in range(6):
        angle = math.radians(b["orbit_angle"]) + i * (2 * math.pi / 6)

        x = 90 * math.cos(angle)
        y = 90 * math.sin(angle)

        glPushMatrix()
        glTranslatef(x, y, 0)
        glRotatef(b["orbit_angle"], 1, 1, 0)
        glutSolidCube(15)
        glPopMatrix()

    glColor3f(0.8, 0.8, 0.8)

    # Legs
    for i in range(3):
        glPushMatrix()
        glRotatef(i * 120, 0, 0, 1)
        glTranslatef(0, 60, -20)
        glRotatef(90, 1, 0, 0)
        gluCylinder(QUADRIC, 4, 2, 40, 8, 1)
        glPopMatrix()

    glPopMatrix()  



# ==========================================
# PHYSICS & LOGIC UPDATE (The idle loop)
# ==========================================
def update_player(dt):
    # Handles all player-related logic: movement, rotation, and collisions.
    if game["game_over"]: return

    # Base rotation
    if game["keys"][b"a"]: game["player_angle"] += 120 * dt
    if game["keys"][b"d"]: game["player_angle"] -= 120 * dt

    # Turret rotation (Feature 1)
    if game["keys"][GLUT_KEY_LEFT]: game["turret_angle"] += 150 * dt
    if game["keys"][GLUT_KEY_RIGHT]: game["turret_angle"] -= 150 * dt

    # Floor Zone Logic: Speed modifiers and healing in colored quadrants.
    px, py = game["player_pos"][0], game["player_pos"][1]
    
    in_corrupted = (px > 100 and py > 100) or (px < -100 and py < -100)
    in_secure = (px > 100 and py < -100) or (px < -100 and py > 100)
    
    zone_multiplier = 1.0
    if in_corrupted:
        zone_multiplier = 0.5  # Red zones cut speed in half
    elif in_secure:
        zone_multiplier = 1.0  # Green zones have normal speed
        game["heal_zone_cooldown"] -= dt
        if game["heal_zone_cooldown"] <= 0:
            game["player_hp"] = min(game["max_hp"], game["player_hp"] + 2)
            game["heal_zone_cooldown"] = 1.0  # Heals 2 HP per second

    # Movement
    rad = math.radians(game["player_angle"])
    move_dir = 0
    if game["keys"][b"w"]: move_dir = 1
    if game["keys"][b"s"]: move_dir = -1

    if move_dir != 0:
        speed = game["player_speed"]

        # Sprinting logic
        if game["sprint_active"] and game["stamina"] > 0:
             speed *= 2.0
             game["stamina"] -= game["sprint_drain"] * dt
             game["stamina"] = max(0, game["stamina"])

        # Apply the floor zone multiplier and direction
        speed *= move_dir * zone_multiplier

        game["player_pos"][0] += speed * dt * math.cos(rad)
        game["player_pos"][1] += speed * dt * math.sin(rad)

    # Stamina slowly recovers while sprint is switched off.
    if not game["sprint_active"]:
        game["stamina"] = min(game["max_stamina"], game["stamina"] + game["sprint_recover"] * dt)

    # Clamp player position to stay within the arena bounds.
    game["player_pos"][0] = max(-GRID_LENGTH + TANK_RADIUS, min(GRID_LENGTH - TANK_RADIUS, game["player_pos"][0]))
    game["player_pos"][1] = max(-GRID_LENGTH + TANK_RADIUS, min(GRID_LENGTH - TANK_RADIUS, game["player_pos"][1]))

    # Player collision with firewalls.
    FW_HALF = 20
    for fw in game["firewalls"]:
        if fw["pos"][2] < 5:
            continue
        fw_x, fw_y = fw["pos"][0], fw["pos"][1]
        
        # Refresh px, py with the newly updated positions after movement
        current_px, current_py = game["player_pos"][0], game["player_pos"][1]
        
        closest_x = max(fw_x - FW_HALF, min(current_px, fw_x + FW_HALF))
        closest_y = max(fw_y - FW_HALF, min(current_py, fw_y + FW_HALF))
        dist = math.hypot(current_px - closest_x, current_py - closest_y)
        
        if dist == 0:
            dx, dy = current_px - fw_x, current_py - fw_y
            if abs(dx) >= abs(dy):
                game["player_pos"][0] = fw_x + math.copysign(FW_HALF + TANK_RADIUS, dx)
            else:
                game["player_pos"][1] = fw_y + math.copysign(FW_HALF + TANK_RADIUS, dy)
        elif dist < TANK_RADIUS:
            overlap = TANK_RADIUS - dist
            game["player_pos"][0] += (current_px - closest_x) / dist * overlap
            game["player_pos"][1] += (current_py - closest_y) / dist * overlap

def update_environment(dt):
    # Updates environmental elements like firewalls and powerups.
    for fw in game["firewalls"]:
        fw["phase"] += fw["freq"] * dt
        # Oscillate Z between 0 and amplitude
        fw["pos"][2] = fw["amplitude"] * (math.sin(fw["phase"]) + 1) / 2.0

    # Periodically drop a new power-up somewhere in the arena.
    game["powerup_timer"] -= dt
    if game["powerup_timer"] <= 0:
        game["powerup_timer"] = POWERUP_INTERVAL
        if len(game["powerups"]) < MAX_POWERUPS:
            spawn_powerup()

    # Powerups Hover and Pickup Logic
    for p in game["powerups"][:]:
        p["rot"] += 90 * dt
        p["phase"] += 2.0 * dt
        p["pos"][2] = 10 * math.sin(p["phase"])  # Hover up and down

        # Pickup collision
        if dist2d(game["player_pos"], p["pos"]) < (TANK_RADIUS + 20):
            if p["type"] == "heal":
                game["player_hp"] = min(game["max_hp"], game["player_hp"] + 30)
            elif p["type"] == "bomb":
                game["bomb_count"] += 2
            game["powerups"].remove(p)

def update_projectiles(dt):
    # Updates all projectiles (bullets and bombs).
    # Bullets: Linear movement and ricochet physics.
    for b in game["bullets"][:]:
        b["pos"][0] += b["vel"][0] * dt
        b["pos"][1] += b["vel"][1] * dt

        # X-bounds ricochet with position snapping to prevent getting stuck.
        if b["pos"][0] > GRID_LENGTH - BULLET_RADIUS:
            b["pos"][0] = GRID_LENGTH - BULLET_RADIUS  # Snap safely inside
            b["vel"][0] *= -1
            b["bounces"] -= 1
        elif b["pos"][0] < -GRID_LENGTH + BULLET_RADIUS:
            b["pos"][0] = -GRID_LENGTH + BULLET_RADIUS # Snap safely inside
            b["vel"][0] *= -1
            b["bounces"] -= 1
            
        # Y-bounds ricochet with position snapping.
        if b["pos"][1] > GRID_LENGTH - BULLET_RADIUS:
            b["pos"][1] = GRID_LENGTH - BULLET_RADIUS  # Snap safely inside
            b["vel"][1] *= -1
            b["bounces"] -= 1
        elif b["pos"][1] < -GRID_LENGTH + BULLET_RADIUS:
            b["pos"][1] = -GRID_LENGTH + BULLET_RADIUS # Snap safely inside
            b["vel"][1] *= -1
            b["bounces"] -= 1
        
        # Bullet collision with firewalls.
        FW_HALF = 20
        for fw in game["firewalls"]:
            if fw["pos"][2] < 5:
                continue
            fw_x, fw_y = fw["pos"][0], fw["pos"][1]
            px, py = b["pos"][0], b["pos"][1]
            closest_x = max(fw_x - FW_HALF, min(px, fw_x + FW_HALF))
            closest_y = max(fw_y - FW_HALF, min(py, fw_y + FW_HALF))
            dist = math.hypot(px - closest_x, py - closest_y)
            if dist == 0:
                dx, dy = px - fw_x, py - fw_y
                if abs(dx) >= abs(dy):
                    b["pos"][0] = fw_x + math.copysign(FW_HALF + BULLET_RADIUS, dx)
                else:
                    b["pos"][1] = fw_y + math.copysign(FW_HALF + BULLET_RADIUS, dy)
            elif dist < BULLET_RADIUS:
                dx = px - closest_x
                dy = py - closest_y

                if abs(dx) > abs(dy):
                    b["vel"][0] *= -1
                else:
                    b["vel"][1] *= -1

        # DESPAWN BULLET IF OUT OF BOUNCES
        if b["bounces"] <= 0:
            if b in game["bullets"]: 
                game["bullets"].remove(b)
        

    # Bombs: Parabolic trajectory with gravity.
    for b in game["bombs"][:]:
        b["pos"][0] += b["vel"][0] * dt
        b["pos"][1] += b["vel"][1] * dt
        b["pos"][2] += b["vel"][2] * dt

        b["vel"][2] -= GRAVITY * dt  # Apply gravity on Z

        # Check for direct mid-air impact with basic enemies.
        hit_enemy_mid_air = False
        for e in game["enemies"]:
            if dist2d(b["pos"], e["pos"]) < (BOMB_RADIUS + ENEMY_RADIUS):
                hit_enemy_mid_air = True
                break

        # Check for mid-air impact with bosses.
        if game["bossA"]["alive"]:
            current_scale = 0.5 + (game["bossA"]["health"] / 200.0)
            if dist2d(b["pos"], game["bossA"]["pos"]) < (BOMB_RADIUS + BOSS_RADIUS * current_scale):
                hit_enemy_mid_air = True
                
        if game["bossB"]["alive"] and dist2d(b["pos"], game["bossB"]["pos"]) < (BOMB_RADIUS + 40):
            hit_enemy_mid_air = True

        # Explode if it hits the floor OR hits an enemy/boss.
        if b["pos"][2] <= 0 or hit_enemy_mid_air:  
            spawn_particles(b["pos"], 25, (1.0, 0.5, 0.0)) # Bigger particle explosion
            
            # Damage Standard Enemies (Area of Effect).
            for e in game["enemies"][:]:
                if dist2d(b["pos"], e["pos"]) < 120:
                    damage_enemy(e, 2, 75)  # Bombs do double life damage to shielded enemies
                    spawn_particles(e["pos"], 5, (1.0, 0.0, 0.0))

            # Damage Boss A (Pegasus).
            if game["bossA"]["alive"] and dist2d(b["pos"], game["bossA"]["pos"]) < 120:
                game["bossA"]["health"] -= 20  # Massive Damage!
                spawn_particles(game["bossA"]["pos"], 15, (1.0, 1.0, 0.0))
                if game["bossA"]["health"] <= 0:
                    defeat_bossA()

            # Damage Boss B (Chitti).
            if game["bossB"]["alive"] and dist2d(b["pos"], game["bossB"]["pos"]) < 120:
                game["bossB"]["health"] -= 20  # Massive Damage!
                bx, by, bz = game["bossB"]["pos"]
                spawn_particles([bx, by, 0], 15, (0.8, 0.2, 1.0))
                if game["bossB"]["health"] <= 0:
                    defeat_bossB()

            # Finally, remove the bomb after it explodes.
            if b in game["bombs"]: game["bombs"].remove(b)

    # Boss Bombs: Target the player
    for b in game["boss_bombs"][:]:
        b["pos"][0] += b["vel"][0] * dt
        b["pos"][1] += b["vel"][1] * dt
        b["pos"][2] += b["vel"][2] * dt
        b["vel"][2] -= GRAVITY * dt 

        hit_player_mid_air = dist2d(b["pos"], game["player_pos"]) < (BOMB_RADIUS + TANK_RADIUS)

        # Explode on floor or if it directly hits the player
        if b["pos"][2] <= 0 or hit_player_mid_air:
            spawn_particles(b["pos"], 25, (0.8, 0.2, 1.0))
            
            # Check Area of Effect against player
            if dist2d(b["pos"], game["player_pos"]) < 120:
                damage_player(20)

            if b in game["boss_bombs"]: game["boss_bombs"].remove(b)

def update_enemies(dt):
    # Updates standard enemy AI and collision.
    px, py = game["player_pos"][0], game["player_pos"][1]

    for e in game["enemies"][:]:
        dx = px - e["pos"][0]
        dy = py - e["pos"][1]
        dist = math.hypot(dx, dy)

        if dist > 0:
            # Basic linear homing AI.
            speed = 80 + (game["level"] * 10)
            vx = (dx / dist) * speed
            vy = (dy / dist) * speed

            # Advanced Evasive maneuvers for higher level enemies.
            if e["level"] >= 4:
                e["phase"] += 3.0 * dt
                perp_x = -vy / speed
                perp_y = vx / speed
                evade_mag = math.sin(e["phase"]) * 80
                vx += perp_x * evade_mag
                vy += perp_y * evade_mag

            e["pos"][0] += vx * dt
            e["pos"][1] += vy * dt

        # Collision with the player.
        if dist < (TANK_RADIUS + ENEMY_RADIUS):
            damage_player(15)
            game["enemies"].remove(e)
            spawn_particles(e["pos"], 5, (1.0, 0.0, 0.0))

def update_particles(dt):
    # Updates particle physics (movement, gravity, lifetime).
    for p in game["particles"][:]:
        p["life"] -= dt
        p["pos"][0] += p["vel"][0] * dt
        p["pos"][1] += p["vel"][1] * dt
        p["pos"][2] += p["vel"][2] * dt
        p["vel"][2] -= GRAVITY * dt

        if p["pos"][2] < 0:
            p["pos"][2] = 0
            p["vel"][2] *= -0.3  # Bounce

        if p["life"] <= 0:
            game["particles"].remove(p)

def update_bossA(dt):
    # Updates Boss A ("Pegasus") AI and collision.
    if not game["bossA"]["alive"]:
        return

    e = game["bossA"]
    px, py = game["player_pos"][0], game["player_pos"][1]

    dx = px - e["pos"][0]
    dy = py - e["pos"][1]
    dist = math.hypot(dx, dy)

    # Move toward player.
    if dist > 0:
        dx /= dist
        dy /= dist

        # Speed increases as health decreases.
        speed = 100

        if e["health"] <= 30:
            speed = 150
        elif e["health"] <= 70:
            speed = 120

        e["pos"][0] += dx * speed * dt
        e["pos"][1] += dy * speed * dt

    # Collision with player.
    # --- UPDATED: Sync ramming hitbox with visual scale ---
    current_scale = 0.5 + (e["health"] / 200.0)
    hitbox_radius = (ENEMY_RADIUS * 1.5) * current_scale
    
    if dist < (TANK_RADIUS + hitbox_radius):
        damage_player(20, BOSS_HIT_COOLDOWN)

        # Push player away on collision.
        if dist > 0:
            push_x = dx * 20
            push_y = dy * 20

            game["player_pos"][0] += push_x
            game["player_pos"][1] += push_y

        spawn_particles(e["pos"], 5, (1.0, 0.0, 0.0))

def update_bossB(dt):
    # Updates Boss B ("Chitti") AI, attacks, and collision.
    if not game["bossB"]["alive"]:
        return

    b = game["bossB"]

    speed = b["speed_bossB"]

    # Speed increases as health decreases.
    if b["health"] <= 50:
        speed = 150
    elif b["health"] <= 100:
        speed = 120
    px, py = game["player_pos"][0], game["player_pos"][1]

    
    dx = px - b["pos"][0]
    dy = py - b["pos"][1]
    dist = math.hypot(dx, dy)

    if dist > 0:
        dx /= dist
        dy /= dist

        b["pos"][0] += dx * speed * dt
        b["pos"][1] += dy * speed * dt

    
    b["orbit_angle"] += b["orbit_speed"] * dt


    # Collision with player.
    if dist < (TANK_RADIUS + ENEMY_RADIUS * 1.5):
        damage_player(20, BOSS_HIT_COOLDOWN)

        # Push player away on collision.
        if dist > 0:
            push_x = dx * 20
            push_y = dy * 20

            game["player_pos"][0] += push_x
            game["player_pos"][1] += push_y

        spawn_particles(b["pos"], 5, (1.0, 0.0, 0.0))

    # Fires bombs at the player on a timer.
    b["attack_timer"] -= dt
    if b["attack_timer"] <= 0:
        b["attack_timer"] = 1.8

        angle = math.atan2(dy, dx)

        game["boss_bombs"].append({
            "pos": [b["pos"][0], b["pos"][1], 20],
            "vel": [
                250 * math.cos(angle),
                250 * math.sin(angle),
                200
            ]
        })

    # Spawns minion enemies on a timer.
    b["spawn_timer"] -= dt
    if b["spawn_timer"] <= 0:
        b["spawn_timer"] = 5.0

        for i in range(3):
            ang = i * (2 * math.pi / 3)

            spawn_pos = [
                b["pos"][0] + 80 * math.cos(ang),
                b["pos"][1] + 80 * math.sin(ang),
                0
            ]

            game["enemies"].append({
                "pos": spawn_pos,
                "level": game["level"],
                "phase": 0.0,
                "color":[1,1,0]
            })       

def check_combat_collisions():
    # Handles all bullet-related collisions.
    for b in game["bullets"][:]:
        hit = False
        # Bullets vs Standard Enemies
        for e in game["enemies"][:]:
            if circles_overlap(b["pos"], BULLET_RADIUS, e["pos"], ENEMY_RADIUS):
                damage_enemy(e, 1, 50)
                spawn_particles(e["pos"], 8, (1.0, 0.2, 0.2))
                hit = True
                break

        # Bullets vs Boss A
        if game["bossA"]["alive"]:
            # --- UPDATED: Sync hitbox with visual scale ---
            current_scale = 0.5 + (game["bossA"]["health"] / 200.0)
            hitbox_radius = (ENEMY_RADIUS * 1.5) * current_scale
            
            if circles_overlap(b["pos"], BULLET_RADIUS, game["bossA"]["pos"], hitbox_radius):
                game["bossA"]["health"] -= 2
                if game["bossA"]["health"] <= 0:
                    defeat_bossA()
                hit = True
        
        # Bullets vs Boss B
        if game["bossB"]["alive"]:
            if circles_overlap(b["pos"], BULLET_RADIUS, game["bossB"]["pos"], 40):
                game["bossB"]["health"] -= 2

                bx, by, bz = game["bossB"]["pos"]
                spawn_particles([bx, by, 0], 10, (0.8, 0.2, 1.0))

                if game["bossB"]["health"] <= 0:
                    defeat_bossB()

                hit = True

        # Remove bullet if it hit anything.
        if hit and b in game["bullets"]:
            game["bullets"].remove(b)

def manage_progression(dt):
    # Manages game difficulty, level progression, and enemy spawning rules.
    if game["game_over"] or game["won"] or not game["running"]: return
    # Feature 6: Level Progression
    thresholds = [0, 400, 1000, 2000, 3500]
    for i, t in enumerate(thresholds):
        if game["score"] >= t:
            game["level"] = i + 1
            if game["level"] == 4:
                game["bossA"]["alive"] = game["bossA"]["health"] > 0

    # Stop standard spawning if a boss is active.
    if game["bossA"]["alive"] or game["bossB"]["alive"]:
        return
    
    # Spawn Boss B at level 5.
    if game["level"] >= 5 and not game["bossB"]["alive"]:
        game["bossB"]["alive"] = True

    # Standard enemy spawning logic.
    game["spawn_interval"] = max(0.5, 3.0 - (game["level"] * 0.4))
    game["spawn_timer"] -= dt
    if game["spawn_timer"] <= 0:
        game["spawn_timer"] = game["spawn_interval"]
        if len(game["enemies"]) < 15:
            # Spawn at edges
            side = random.choice([1, -1])
            if random.random() > 0.5:
                pos = [side * GRID_LENGTH, random.uniform(-GRID_LENGTH, GRID_LENGTH), 0]
            else:
                pos = [random.uniform(-GRID_LENGTH, GRID_LENGTH), side * GRID_LENGTH, 0]
            game["enemies"].append({"pos": pos, "level": game["level"], "phase": 0.0})

# Helper to spawn particles
def spawn_particles(pos, count, color):
    # Creates a number of particles at a given position with a specific color.
    if len(game["particles"]) > 100: return  # Performance cap
    for _ in range(count):
        ang = random.uniform(0, 2 * math.pi)
        speed = random.uniform(50, 200)
        game["particles"].append({
            "pos": list(pos),
            "vel": [speed * math.cos(ang), speed * math.sin(ang), random.uniform(50, 150)],
            "life": 0.8, "max_life": 0.8, "color": color
        })

def restart_game():
    # Resets the entire game state to its initial values (this also releases any held keys).
    game.update(new_game_state())
    game["in_menu"] = False
    init_environment()

# Main Idle Loop
def idle():
    # The main game loop, called continuously by GLUT.
    global last_time
    current_time = time.perf_counter()
    # Frame-rate independent timing, capped to prevent physics glitches at low FPS.
    # The clock always advances so resuming from the menu or pause never causes a time jump.
    dt = min(current_time - last_time, 0.05)
    last_time = current_time

    if game["in_menu"] or not game["running"]:
        return  # Freeze the game engine while the menu or pause screen is open

    if game["game_over"] or game["won"]:
        # Round is over: freeze gameplay but let the final explosion finish animating.
        update_particles(dt)
        glutPostRedisplay()
        return

    if game["player_hp"] <= 0:
        # Handle player death and lives system.
        game["lives"] -= 1
        if game["lives"] <= 0:
            game["game_over"] = True
            game["bossA"]["alive"] = False
            game["bossB"]["alive"] = False
            game["enemies"] = []
            game["boss_bombs"] = []
        else:
            game["player_hp"] = game["max_hp"]
            game["invincible_timer"] = 2.5

    # Update all game systems in order.
    if game["invincible_timer"] > 0:
        game["invincible_timer"] -= dt
    
    if game["health_bar_flick_timer"] > 0:
        game["health_bar_flick_timer"] -= dt

    if game["boss_health_bar_flick_timer"] > 0:
        game["boss_health_bar_flick_timer"] -= dt

    if game["debuff_interval"] > 0:
        game["debuff_interval"] -= dt
        if game["debuff_interval"] <= 0:
            game["player_speed"] = 180

    update_player(dt)
    update_environment(dt)

    game["zone_spawn_timer"] -= dt
    if game["zone_spawn_timer"] <= 0:
        game["zone_spawn_timer"] = game["zone_spawn_interval"]
        if len(game["zones"]) < 5:
            spawn_zone()
    update_zones(dt)
    update_bossB(dt)
    update_projectiles(dt)
    update_enemies(dt)
    update_particles(dt)
    update_bossA(dt)
    check_combat_collisions()
    manage_progression(dt)

    # HUD Flash Timer for invincibility effect.
    game["hud_flash_timer"] -= dt
    if game["hud_flash_timer"] <= 0:
        game["hud_flash_timer"] = 0.4
        game["hud_flash_state"] = not game["hud_flash_state"]

    glutPostRedisplay()

# ==========================================
# INPUT HANDLING
# ==========================================
def keyboardListener(key, x, y):
    # Handles key press events.
    key = key.lower()
    glutPostRedisplay()  # Menus and the pause screen only redraw on input

    # Menu Input
    if game["in_menu"]:
        if key == b'\r':  # Enter key starts the game
            game["in_menu"] = False
        return  # Ignore all other keyboard input while in menu

    if key in game["keys"]: game["keys"][key] = True

    # Feature 5: Tactical Drone Camera Toggle
    if key == b"v":
        game["camera_mode"] = "drone" if game["camera_mode"] == "perspective" else "perspective"

    if key == b"r":
        restart_game()

    # ESC Key for Pause (only while a round is in progress)
    if key == b'\x1b' and not game["game_over"] and not game["won"]:  # \x1b is the byte-string for the ESC key
        game["running"] = not game["running"]

    # Everything below is a gameplay action and is ignored while paused or after the round ends.
    if not can_act():
        return

    # Feature 3: Parabolic Bomb Launch
    if key == b" ":
        launch_bomb()

    # Sprint Toggle mapped to 'e'
    if key == b'e':
        game["sprint_active"] = not game["sprint_active"]
        if game["sprint_active"]:
            game["stamina"] = max(0, game["stamina"] - 5)

    # Mouseless Firing with the Enter/Return Key.
    if key == b'\r':  # \r is the byte-string for the Enter key
        fire_bullet()

def keyboardUpListener(key, x, y):
    # Handles key release events.
    key = key.lower()

    if key in game["keys"]: game["keys"][key] = False

def specialKeyListener(key, x, y):
    # Handles special key (e.g., arrow keys) press events.
    if key in game["keys"]: 
        game["keys"][key] = True

def specialKeyUpListener(key, x, y):
    # Handles special key release events.
    if key in game["keys"]: game["keys"][key] = False

def mouseListener(button, state, x, y):
    # Handles mouse click events.
    converted_y = WINDOW_HEIGHT - y  # Match OpenGL coordinates
    glutPostRedisplay()

    # Menu Input: Click to start.
    if game["in_menu"]:
        if button == GLUT_LEFT_BUTTON and state == GLUT_DOWN:
            # If they click anywhere in the bottom half of the screen, start the game
            if converted_y <= WINDOW_HEIGHT // 2:
                game["in_menu"] = False
        return

    # Click anywhere to resume while paused.
    if not game["running"] and not game["game_over"] and not game["won"]:
        if button == GLUT_LEFT_BUTTON and state == GLUT_DOWN:
            game["running"] = True
        return  # If paused, ignore all other clicks

    if not can_act() or state != GLUT_DOWN:
        return

    # Clickable pause button (bottom right).
    if button == GLUT_LEFT_BUTTON:
        x_min, x_max, y_min, y_max = pause_button_rect()
        if x_min <= x <= x_max and y_min <= converted_y <= y_max:
            game["running"] = False
            return

    # Left click: Fire Bullet
    if button == GLUT_LEFT_BUTTON:
        fire_bullet()

    # Right click: Launch Bomb
    if button == GLUT_RIGHT_BUTTON:
        launch_bomb()

def reshape(width, height):
    # Keeps the viewport, HUD layout and mouse hit-testing in sync with the real window size.
    global WINDOW_WIDTH, WINDOW_HEIGHT
    WINDOW_WIDTH, WINDOW_HEIGHT = max(1, width), max(1, height)
    glutPostRedisplay()

# ==========================================
# RENDERING
# ==========================================
def setupCamera():
    # Configures the 3D camera projection and view.
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()

    if game["camera_mode"] == "drone":
        # Feature 5: Top-down Orthographic/Perspective Hybrid
        gluPerspective(70, WINDOW_WIDTH / WINDOW_HEIGHT, 0.1, 3000)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        # Look straight down from high Z
        gluLookAt(0, 0, 1400, 0, 0, 0, 0, 1, 0)
    else:
        # Standard Perspective behind player
        gluPerspective(60, WINDOW_WIDTH / WINDOW_HEIGHT, 0.1, 3000)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        rad = math.radians(game["player_angle"])
        cam_x = game["player_pos"][0] - 250 * math.cos(rad)
        cam_y = game["player_pos"][1] - 250 * math.sin(rad)
        cam_z = 150
        gluLookAt(cam_x, cam_y, cam_z,
                  game["player_pos"][0], game["player_pos"][1], 0,
                  0, 0, 1)

def draw_heart_shape(cx, cy, size):
    # Draws a heart shape using points, for the lives indicator.
    # Use template-approved point sizing and rendering
    glPointSize(5) 
    glBegin(GL_POINTS)
    
    # Increase steps slightly since we are drawing dots instead of a solid polygon
    steps = 45 
    for i in range(steps):
        t = 2 * math.pi * i / steps
        x = size * (math.sin(t) ** 3)
        y = size * (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)) / 13.0
        glVertex2f(cx + x, cy + y)
    
    glEnd()

def draw_lives():
    # Draws the player's remaining lives as hearts in the HUD.
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    for i in range(3):
        cx = 28 + i * 40
        cy = WINDOW_HEIGHT - 175
        if i < game["lives"]:
            glColor3f(1.0, 0.15, 0.15)
        else:
            glColor3f(0.3, 0.08, 0.08)
        draw_heart_shape(cx, cy, 13)

    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

# Draws the player's health bar in the HUD.
def drawHealthBar():
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)

    # --- Draw in modelview ---
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    ratio = game["player_hp"]/game["max_hp"]
    factor = 3
    width = ratio * 100 * factor

    # Dark background so missing health stays visible
    glColor3f(0.1, 0.1, 0.1)
    glBegin(GL_QUADS)
    glVertex2f(17, WINDOW_HEIGHT - 37)
    glVertex2f(23 + 100 * factor, WINDOW_HEIGHT - 37)
    glVertex2f(23 + 100 * factor, WINDOW_HEIGHT - 63)
    glVertex2f(17, WINDOW_HEIGHT - 63)
    glEnd()

    # Foreground: green / yellow / flashing red depending on health
    if game["player_hp"] > 70:
        glColor3f(0, 1, 0)
    elif game["player_hp"] > 30:
        glColor3f(1, 1, 0)
    else:
        if game["health_bar_flick"]:
            glColor3f(1, 0, 0)
        else:
            glColor3f(1, 1, 0)
        if game["health_bar_flick_timer"] <= 0:
            game["health_bar_flick_timer"] = 0.1
            game["health_bar_flick"] = not game["health_bar_flick"]
    glBegin(GL_QUADS)
    glVertex2f(20, WINDOW_HEIGHT - 40)
    glVertex2f(20 + width, WINDOW_HEIGHT - 40)
    glVertex2f(20 + width, WINDOW_HEIGHT - 60)
    glVertex2f(20, WINDOW_HEIGHT - 60)
    glEnd()

    # Restore matrices
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

def drawBossAHealthBar():
    # Draws Boss A's health bar in the HUD.
    if not game["bossA"]["alive"]:
        return

    draw_text(WINDOW_WIDTH - 160, WINDOW_HEIGHT - 30, "Pegasus Boss", 1, 1, 1)

    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    health = game["bossA"]["health"]
    ratio = health / 100.0
    max_width = 300
    width = ratio * max_width

    # fixed right side position
    right_x = WINDOW_WIDTH - 20
    left_x = right_x - width
    y = WINDOW_HEIGHT - 40

    # color logic
    if health > 70:
        glColor3f(0, 1, 0)
    elif health > 30:
        glColor3f(1, 1, 0)
    else:
        if game["boss_health_bar_flick"]:
            glColor3f(1, 0, 0)
        else:
            glColor3f(1, 1, 0)

        if game["boss_health_bar_flick_timer"] <= 0:
            game["boss_health_bar_flick_timer"] = 0.1
            game["boss_health_bar_flick"] = not game["boss_health_bar_flick"]

    glBegin(GL_QUADS)
    glVertex2f(left_x, y)
    glVertex2f(right_x, y)
    glVertex2f(right_x, y - 20)
    glVertex2f(left_x, y - 20)
    glEnd()

    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)



def drawBossBHealthBar():
    # Draws Boss B's health bar in the HUD.
    if not game["bossB"]["alive"]:
        return

    draw_text(WINDOW_WIDTH - 160, WINDOW_HEIGHT - 30, "Chitti The Robot", 1, 1, 1)

    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    health = game["bossB"]["health"]
    ratio = health / 150.0  
    max_width = 300
    width = ratio * max_width

   
    right_x = WINDOW_WIDTH - 20
    left_x = right_x - width
    y = WINDOW_HEIGHT - 40

   
    if health > 100:
        glColor3f(0, 1, 0)
       
    elif health > 50:
        glColor3f(1, 1, 0)
        
    else:
        if game["boss_health_bar_flick"]:
            glColor3f(1, 0, 0)
        else:
            glColor3f(1, 1, 0)

        if game["boss_health_bar_flick_timer"] <= 0:
            game["boss_health_bar_flick_timer"] = 0.1
            game["boss_health_bar_flick"] = not game["boss_health_bar_flick"]
        
    glBegin(GL_QUADS)
    glVertex2f(left_x, y)
    glVertex2f(right_x, y)
    glVertex2f(right_x, y - 20)
    glVertex2f(left_x, y - 20)
    glEnd()

    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)


def draw_zones():
    # Iterates through and draws all active buff/debuff zones.
    for z in game["zones"]:
        if z["type"] == "buff":
            draw_buff_zone(z)
        elif z["type"] == "debuff":
            draw_debuff_zone(z)
        elif z["type"] == "sprint":
            draw_sprint_zone(z)


def spawn_zone():
    # Spawns a new random zone (buff, debuff, or sprint) on the map.
    types = ["buff", "debuff", "sprint"]

    ztype = random.choice(types)

    pos = [
        random.uniform(-GRID_LENGTH + 60, GRID_LENGTH - 60),
        random.uniform(-GRID_LENGTH + 60, GRID_LENGTH - 60),
        0
    ]

    game["zones"].append({
        "type": ztype,
        "pos": pos,
        "rot": 0.0,
        "life": 12.0
    })


def update_zones(dt):
    # Updates the logic for all zones, including player interaction.
    px, py, pz = game["player_pos"]
    if game["stamina"] <= 0:
        game["sprint_active"] = False

    for z in game["zones"][:]:
        z["rot"] += 80 * dt
        z["pos"][2] = 10 * math.sin(time.time() * 3 + z["rot"])

        z["life"] -= dt
        if z["life"] <= 0:
            game["zones"].remove(z)
            continue
        dx = px - z["pos"][0]
        dy = py - z["pos"][1]
        if (abs(dx) < 40 and abs(dy) < 40):
            if z["type"] == "buff":
                game["player_hp"] += 5
                if game["player_hp"] >= 100:
                    game["player_hp"] = 100

            elif z["type"] == "sprint":
                game["stamina"] += 20
                if game["stamina"] >= game["max_stamina"]:
                    game["stamina"] = game["max_stamina"]

            elif z["type"] == "debuff":
                game["debuff_interval"] = 2
                game["player_speed"] = 80
            game["zones"].remove(z)



def draw_buff_zone(z):
    # Draws the visual model for a "buff" (healing) zone.
    glPushMatrix()
    glTranslatef(z["pos"][0], z["pos"][1], 25)

    
    glRotatef(-90, 1, 0, 0)

    
    glRotatef(z["rot"], 0, 1, 0)

    glColor3f(0.2, 1.0, 0.2)

    glPushMatrix()
    glScalef(0.2, 1.2, 0.2)
    glutSolidCube(40)
    glPopMatrix()

    
    glPushMatrix()
    glScalef(1.2, 0.2, 0.2)
    glutSolidCube(40)
    glPopMatrix()

    glPopMatrix()


def draw_debuff_zone(z):
    # Draws the visual model for a "debuff" (slowing) zone.
    glPushMatrix()
    glTranslatef(z["pos"][0], z["pos"][1], 25)

    
    glRotatef(-90, 1, 0, 0)

    
    glRotatef(z["rot"], 0, 1, 0)

   
    glColor3f(1.0, 0.1, 0.1)

    glPushMatrix()
    glRotatef(45, 0, 0, 1)
    glScalef(0.3, 1.5, 0.3)
    glutSolidCube(40)
    glPopMatrix()

    glPushMatrix()
    glRotatef(-45, 0, 0, 1)
    glScalef(0.3, 1.5, 0.3)
    glutSolidCube(40)
    glPopMatrix()

   

    glPopMatrix()

    

def draw_sprint_zone(z):
    # Draws the visual model for a "sprint" (stamina refill) zone.
    glPushMatrix()
    glTranslatef(z["pos"][0], z["pos"][1], 25)

    
    glRotatef(-90, 1, 0, 0)

    glRotatef(z["rot"], 0, 1, 0)

    glColor3f(0.2, 0.6, 1.0)

   
    glPushMatrix()
    glRotatef(20, 0, 0, 1)
    glScalef(0.3, 1.5, 0.3)
    glutSolidCube(30)
    glPopMatrix()

    glPushMatrix()
    glRotatef(-20, 0, 0, 1)
    glTranslatef(10, -10, 0)
    glScalef(0.3, 1.0, 0.3)
    glutSolidCube(30)
    glPopMatrix()

    glPopMatrix()

def draw_sprint_bar():
    # Draws the player's stamina bar in the HUD.
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)

   
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    ratio = game["stamina"]/game["max_stamina"]
    factor = 3
    width = ratio * 100 * factor

    x = 20
    y = 30

    draw_text(x, y + 30, "Stamina", 1, 1, 1)

    # 1. Draw the Dark Background FIRST
    glColor3f(0.1, 0.1, 0.1)
    glBegin(GL_QUADS)
    glVertex2f(x - 3, y - 3)
    glVertex2f(x + 3 + 100*factor, y - 3)
    glVertex2f(x + 3 + 100*factor, y + 20 + 3)
    glVertex2f(x - 3, y + 20 + 3)
    glEnd()

    # 2. Draw the Blue Fill SECOND (on top)
    glColor3f(0, 0, 1)
    glBegin(GL_QUADS)
    glVertex2f(x, y)
    glVertex2f(x + width, y)
    glVertex2f(x + width, y + 20)
    glVertex2f(x, y + 20)
    glEnd()

   
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)


def draw_pause_button():
    # Draws the clickable pause/resume button in the HUD.
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    # Bounding box for Bottom-Right corner
    box_x_min, box_x_max, box_y_min, box_y_max = pause_button_rect()

    if game["running"]:
        glColor3f(0.8, 0.6, 0.0)  # Yellow for PAUSE
        text = "PAUSE (ESC)"
    else:
        glColor3f(0.0, 0.8, 0.2)  # Green for RESUME
        text = "RESUME"

    # Draw Button Quad
    glBegin(GL_QUADS)
    glVertex2f(box_x_min, box_y_min)
    glVertex2f(box_x_max, box_y_min)
    glVertex2f(box_x_max, box_y_max)
    glVertex2f(box_x_min, box_y_max)
    glEnd()

    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

    # Draw Text on top of the button (Black text)
    draw_text_centered((box_x_min + box_x_max) // 2, box_y_min + 15, text, 0, 0, 0)


def showScreen():
    # The main GLUT display function, responsible for rendering every frame.
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glViewport(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)

    # If in the menu, only draw the menu and skip the 3D world.
    if game["in_menu"]:
        draw_menu()
        glutSwapBuffers()
        return

    setupCamera()

    # Draw the colored quadrants on the floor.
    glBegin(GL_QUADS)

    # Neutral center square: x=[-100,100], y=[-100,100]
    glColor3f(0.3, 0.3, 0.3)
    glVertex3f(-100, 100, 0); glVertex3f(100, 100, 0); glVertex3f(100, -100, 0); glVertex3f(-100, -100, 0)

    # Neutral top arm: x=[-100,100], y=[100,GRID_LENGTH]
    glVertex3f(-100, 100, 0); glVertex3f(100, 100, 0); glVertex3f(100, GRID_LENGTH, 0); glVertex3f(-100, GRID_LENGTH, 0)

    # Neutral bottom arm: x=[-100,100], y=[-GRID_LENGTH,-100]
    glVertex3f(-100, -100, 0); glVertex3f(100, -100, 0); glVertex3f(100, -GRID_LENGTH, 0); glVertex3f(-100, -GRID_LENGTH, 0)

    # Neutral right arm: x=[100,GRID_LENGTH], y=[-100,100]
    glVertex3f(100, -100, 0); glVertex3f(GRID_LENGTH, -100, 0); glVertex3f(GRID_LENGTH, 100, 0); glVertex3f(100, 100, 0)

    # Neutral left arm: x=[-GRID_LENGTH,-100], y=[-100,100]
    glVertex3f(-GRID_LENGTH, -100, 0); glVertex3f(-100, -100, 0); glVertex3f(-100, 100, 0); glVertex3f(-GRID_LENGTH, 100, 0)

    # Q1: x=[100,GRID_LENGTH], y=[100,GRID_LENGTH]
    glColor3f(0.5 + (game["level"] * 0.05), 0.05, 0.05)
    glVertex3f(100, 100, 0); glVertex3f(GRID_LENGTH, 100, 0); glVertex3f(GRID_LENGTH, GRID_LENGTH, 0); glVertex3f(100, GRID_LENGTH, 0)

    # Q3: x=[-GRID_LENGTH,-100], y=[-GRID_LENGTH,-100]
    glVertex3f(-GRID_LENGTH, -GRID_LENGTH, 0); glVertex3f(-100, -GRID_LENGTH, 0); glVertex3f(-100, -100, 0); glVertex3f(-GRID_LENGTH, -100, 0)

    # Q2: x=[-GRID_LENGTH,-100], y=[100,GRID_LENGTH]
    glColor3f(0.05, 0.4 - (game["level"] * 0.05), 0.1)
    glVertex3f(-GRID_LENGTH, 100, 0); glVertex3f(-100, 100, 0); glVertex3f(-100, GRID_LENGTH, 0); glVertex3f(-GRID_LENGTH, GRID_LENGTH, 0)

    # Q4: x=[100,GRID_LENGTH], y=[-GRID_LENGTH,-100]
    glVertex3f(100, -GRID_LENGTH, 0); glVertex3f(GRID_LENGTH, -GRID_LENGTH, 0); glVertex3f(GRID_LENGTH, -100, 0); glVertex3f(100, -100, 0)

    glEnd()

    # Draw all game objects in a specific order for correct layering.
    draw_firewalls()
    draw_powerups()

    draw_zones()
    if not game["game_over"]: draw_player()
    draw_enemies()
    draw_bossA()
    draw_bossB()
    draw_projectiles()
    draw_particles()

    # Draw all Heads-Up Display (HUD) elements on top of the 3D world.
    # Depth testing is off so overlapping 2D layers (bar fill over bar background,
    # button label over button) always draw in painter's order.
    glDisable(GL_DEPTH_TEST)

    draw_text(20, WINDOW_HEIGHT - 30, "Player", 1, 1, 1)
    drawHealthBar()
    drawBossAHealthBar()
    drawBossBHealthBar()
    draw_sprint_bar()
    draw_lives()

    draw_text(20, WINDOW_HEIGHT - 90, f"SCORE: {game['score']}", 1, 1, 1)
    draw_text(20, WINDOW_HEIGHT - 120, f"THREAT LEVEL: {game['level']}", 1, 0.8, 0)
    draw_text(20, WINDOW_HEIGHT - 150, f"BOMBS: {game['bomb_count']} (Press SPACE)", 1, 0.5, 0.5)

    if game["camera_mode"] == "drone":
        draw_text_centered(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 40, "[ TACTICAL DRONE VIEW ]", 0.2, 0.8, 0.8)

    # Display game over or win messages.
    if game["game_over"]:
        draw_text_centered(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 20, "SYSTEM FAILURE", 1, 0, 0)
        draw_text_centered(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 20, f"Final Score: {game['score']}", 1, 1, 1)
        draw_text_centered(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 55, "Press R to Restart", 1, 0.85, 0.0)

    if game["won"]:
        draw_text_centered(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 20, "SYSTEM SAFE", 0, 1, 0)
        draw_text_centered(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 20, f"Final Score: {game['score']}", 1, 1, 1)
        draw_text_centered(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 55, "Press R to Restart", 1, 0.85, 0.0)

    # Pause controls are drawn last so the pause overlay sits above everything else.
    if not game["game_over"] and not game["won"]:
        if game["running"]:
            draw_pause_button()  # Show small corner button when playing
        else:
            draw_pause_menu()    # Show big center menu when paused

    glEnable(GL_DEPTH_TEST)

    # Swap the back buffer with the front buffer to display the rendered image.
    glutSwapBuffers()

# ==========================================
# MAIN LOOP
# ==========================================
def main():
    # Initializes GLUT, creates the window, and registers all callback functions.
    global last_time, QUADRIC
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(WINDOW_WIDTH, WINDOW_HEIGHT)
    glutInitWindowPosition(50, 50)
    glutCreateWindow(b"System Defender")

    glEnable(GL_DEPTH_TEST)  # Enable depth testing for correct 3D rendering.

    # A single quadric is reused for every sphere/cylinder; allocating one per draw call leaks memory.
    QUADRIC = gluNewQuadric()

    init_environment()
    last_time = time.perf_counter()

    # Register GLUT callbacks.
    glutDisplayFunc(showScreen)
    glutReshapeFunc(reshape)
    glutKeyboardFunc(keyboardListener)
    glutKeyboardUpFunc(keyboardUpListener)
    glutSpecialFunc(specialKeyListener)
    glutSpecialUpFunc(specialKeyUpListener)
    glutMouseFunc(mouseListener)
    glutIdleFunc(idle)

    # Start the GLUT main event loop.
    glutMainLoop()

if __name__ == "__main__":
    main()
