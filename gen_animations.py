"""Generate cool 7x7 LED matrix animations as JSON files."""
import json
import os
import math
import random

MATRIX_DIR = os.path.join(os.path.dirname(__file__), 'matrix')
os.makedirs(MATRIX_DIR, exist_ok=True)

def blank():
    return [[0]*7 for _ in range(7)]

def frame(matrix, time_slot=2):
    return {"data": [row[:] for row in matrix], "time_slot": time_slot}

def save(name, frames):
    path = os.path.join(MATRIX_DIR, f"{name}.json")
    with open(path, 'w') as f:
        json.dump(frames, f)
    print(f"  {name}.json ({len(frames)} frames)")


# ── 1. Rain ──────────────────────────────────────────────────────────────────
def gen_rain():
    random.seed(42)
    frames = []
    drops = []
    for _ in range(30):
        m = blank()
        # Add new drops
        if random.random() < 0.5:
            drops.append((0, random.randint(0, 6)))
        # Draw and advance
        new_drops = []
        for r, c in drops:
            if 0 <= r < 7:
                m[r][c] = 1
            if r < 7:
                new_drops.append((r + 1, c))
        drops = new_drops
        # Keep some tail
        frames.append(frame(m, 1))
    save("rain", frames)


# ── 2. Spiral In ─────────────────────────────────────────────────────────────
def gen_spiral():
    m = blank()
    frames = []
    # Generate spiral order coords
    coords = []
    top, bottom, left, right = 0, 6, 0, 6
    while top <= bottom and left <= right:
        for c in range(left, right + 1): coords.append((top, c))
        top += 1
        for r in range(top, bottom + 1): coords.append((r, right))
        right -= 1
        if top <= bottom:
            for c in range(right, left - 1, -1): coords.append((bottom, c))
            bottom -= 1
        if left <= right:
            for r in range(bottom, top - 1, -1): coords.append((r, left))
            left += 1
    # Spiral in
    for r, c in coords:
        m[r][c] = 1
        frames.append(frame(m, 1))
    # Spiral out
    for r, c in reversed(coords):
        m[r][c] = 0
        frames.append(frame(m, 1))
    save("spiral", frames)


# ── 3. Firework ──────────────────────────────────────────────────────────────
def gen_firework():
    frames = []
    cx, cy = 3, 3
    # Rise
    for r in range(6, 2, -1):
        m = blank()
        m[r][3] = 1
        frames.append(frame(m, 2))
    # Explode
    for radius in range(1, 5):
        m = blank()
        for dr in range(-radius, radius + 1):
            for dc in range(-radius, radius + 1):
                dist = abs(dr) + abs(dc)
                if dist == radius:
                    r, c = cx + dr, cy + dc
                    if 0 <= r < 7 and 0 <= c < 7:
                        m[r][c] = 1
        frames.append(frame(m, 2))
    # Fade
    m = blank()
    for dr in [-3, -2, 2, 3]:
        for dc in [-3, -2, 2, 3]:
            r, c = cx + dr, cy + dc
            if 0 <= r < 7 and 0 <= c < 7:
                m[r][c] = 1
    frames.append(frame(m, 2))
    frames.append(frame(blank(), 3))
    save("firework", frames)


# ── 4. Snake ─────────────────────────────────────────────────────────────────
def gen_snake():
    frames = []
    # Snake goes around the border
    border = []
    for c in range(7): border.append((0, c))
    for r in range(1, 7): border.append((r, 6))
    for c in range(5, -1, -1): border.append((6, c))
    for r in range(5, 0, -1): border.append((r, 0))
    border = border * 2  # loop twice
    snake_len = 5
    for i in range(len(border) - snake_len):
        m = blank()
        for j in range(snake_len):
            r, c = border[i + j]
            m[r][c] = 1
        frames.append(frame(m, 1))
    save("snake", frames)


# ── 5. Pac-Man ───────────────────────────────────────────────────────────────
def gen_pacman():
    frames = []
    # Pac-Man open mouth (facing right)
    pac_open = [
        [0,0,1,1,1,0,0],
        [0,1,1,1,0,0,0],
        [1,1,1,0,0,0,0],
        [1,1,0,0,0,0,0],
        [1,1,1,0,0,0,0],
        [0,1,1,1,0,0,0],
        [0,0,1,1,1,0,0],
    ]
    pac_closed = [
        [0,0,1,1,1,0,0],
        [0,1,1,1,1,0,0],
        [1,1,1,1,1,0,0],
        [1,1,1,1,1,0,0],
        [1,1,1,1,1,0,0],
        [0,1,1,1,1,0,0],
        [0,0,1,1,1,0,0],
    ]
    # Dots and pac-man moving
    for step in range(8):
        # Alternate open/closed
        pac = pac_open if step % 2 == 0 else pac_closed
        m = blank()
        offset = step - 2
        for r in range(7):
            for c in range(7):
                sc = c - offset
                if 0 <= sc < 7 and pac[r][sc]:
                    m[r][c] = 1
        # Draw dots ahead
        for dc in range(offset + 5, 7):
            if 0 <= dc < 7:
                m[3][dc] = 1
        frames.append(frame(m, 2))
    save("pacman", frames)


# ── 6. Heartbeat ─────────────────────────────────────────────────────────────
def gen_heartbeat():
    small = [
        [0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0],
        [0,0,1,0,1,0,0],
        [0,0,1,1,1,0,0],
        [0,0,0,1,0,0,0],
        [0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0],
    ]
    medium = [
        [0,0,0,0,0,0,0],
        [0,0,1,0,1,0,0],
        [0,1,1,1,1,1,0],
        [0,1,1,1,1,1,0],
        [0,0,1,1,1,0,0],
        [0,0,0,1,0,0,0],
        [0,0,0,0,0,0,0],
    ]
    big = [
        [0,0,1,0,1,0,0],
        [0,1,1,1,1,1,0],
        [1,1,1,1,1,1,1],
        [1,1,1,1,1,1,1],
        [0,1,1,1,1,1,0],
        [0,0,1,1,1,0,0],
        [0,0,0,1,0,0,0],
    ]
    # Heartbeat rhythm: bump-bump...pause...bump-bump...pause
    sequence = [small, medium, big, medium, small, small, medium, big, medium, small, blank(), blank()]
    times =    [2,     2,      3,   2,      2,     4,     2,      3,   2,      2,     4,       4]
    frames = [frame(s, t) for s, t in zip(sequence, times)]
    save("heartbeat", frames)


# ── 7. Wave ──────────────────────────────────────────────────────────────────
def gen_wave():
    frames = []
    for offset in range(14):
        m = blank()
        for c in range(7):
            r = int(3 + 2.5 * math.sin((c + offset) * 0.9))
            r = max(0, min(6, r))
            m[r][c] = 1
            if r + 1 < 7: m[r+1][c] = 1
        frames.append(frame(m, 1))
    save("wave", frames)


# ── 8. Loading Spinner ───────────────────────────────────────────────────────
def gen_spinner():
    frames = []
    # 8 positions around center
    positions = [
        (1, 3), (1, 5), (3, 5), (5, 5), (5, 3), (5, 1), (3, 1), (1, 1)
    ]
    for i in range(16):
        m = blank()
        m[3][3] = 1  # center dot
        idx = i % 8
        # Draw 3 dots as tail
        for t in range(3):
            pi = (idx - t) % 8
            r, c = positions[pi]
            m[r][c] = 1
        frames.append(frame(m, 1))
    save("spinner", frames)


# ── 9. Space Invader ─────────────────────────────────────────────────────────
def gen_invader():
    inv1 = [
        [0,0,0,0,0,0,0],
        [0,0,1,0,1,0,0],
        [0,1,1,1,1,1,0],
        [1,1,0,1,0,1,1],
        [1,1,1,1,1,1,1],
        [0,1,0,1,0,1,0],
        [1,0,0,0,0,0,1],
    ]
    inv2 = [
        [0,0,0,0,0,0,0],
        [0,0,1,0,1,0,0],
        [0,1,1,1,1,1,0],
        [1,1,0,1,0,1,1],
        [1,1,1,1,1,1,1],
        [0,0,1,0,1,0,0],
        [0,1,0,0,0,1,0],
    ]
    frames = []
    for _ in range(8):
        frames.append(frame(inv1, 3))
        frames.append(frame(inv2, 3))
    save("invader", frames)


# ── 10. DNA Helix ────────────────────────────────────────────────────────────
def gen_dna():
    frames = []
    for offset in range(14):
        m = blank()
        for r in range(7):
            x1 = int(3 + 2.5 * math.sin((r + offset) * 0.8))
            x2 = int(3 - 2.5 * math.sin((r + offset) * 0.8))
            x1 = max(0, min(6, x1))
            x2 = max(0, min(6, x2))
            m[r][x1] = 1
            m[r][x2] = 1
            # Connect rungs at crossing points
            if abs(x1 - x2) <= 2:
                for c in range(min(x1, x2), max(x1, x2) + 1):
                    m[r][c] = 1
        frames.append(frame(m, 1))
    save("dna", frames)


# ── 11. Bouncing Ball ────────────────────────────────────────────────────────
def gen_bounce():
    frames = []
    x, y = 0.0, 0.0
    vx, vy = 0.8, 0.5
    for _ in range(30):
        m = blank()
        ix, iy = int(round(x)), int(round(y))
        ix = max(0, min(6, ix))
        iy = max(0, min(6, iy))
        m[iy][ix] = 1
        # Shadow/trail
        if iy + 1 < 7: m[iy+1][ix] = 1
        if ix + 1 < 7: m[iy][ix+1] = 1
        frames.append(frame(m, 1))
        x += vx
        y += vy
        if x >= 6 or x <= 0: vx = -vx
        if y >= 6 or y <= 0: vy = -vy
    save("bounce", frames)


# ── 12. Tetris ───────────────────────────────────────────────────────────────
def gen_tetris():
    frames = []
    # T-piece falling
    floor = [[0]*7 for _ in range(7)]
    # Pre-placed blocks on floor
    for c in range(7):
        floor[6][c] = 1
    floor[5][0] = 1; floor[5][1] = 1
    floor[5][5] = 1; floor[5][6] = 1

    t_piece = [(0, -1), (0, 0), (0, 1), (-1, 0)]  # T-shape
    col = 3
    for drop_row in range(0, 5):
        m = [row[:] for row in floor]
        for dr, dc in t_piece:
            r, c = drop_row + dr, col + dc
            if 0 <= r < 7 and 0 <= c < 7:
                m[r][c] = 1
        frames.append(frame(m, 2))

    # Landed
    for dr, dc in t_piece:
        r, c = 4 + dr, col + dc
        if 0 <= r < 7 and 0 <= c < 7:
            floor[r][c] = 1
    frames.append(frame(floor, 5))

    # Line clear flash
    m = [row[:] for row in floor]
    frames.append(frame(m, 3))
    # Clear bottom row
    m[6] = [0] * 7
    frames.append(frame(m, 2))
    # Gravity - shift down
    for r in range(5, 0, -1):
        m[r + 1] = m[r][:]
    m[0] = [0] * 7
    frames.append(frame(m, 3))

    save("tetris", frames)


# ── 13. Goomba ───────────────────────────────────────────────────────────────
def gen_goomba():
    # Goomba walk frame 1 (left foot forward)
    g1 = [
        [0,0,1,1,1,0,0],
        [0,1,1,1,1,1,0],
        [1,1,0,1,0,1,1],
        [1,1,1,1,1,1,1],
        [0,0,1,1,1,0,0],
        [0,1,1,0,1,1,0],
        [0,1,0,0,0,1,0],
    ]
    # Goomba walk frame 2 (right foot forward)
    g2 = [
        [0,0,1,1,1,0,0],
        [0,1,1,1,1,1,0],
        [1,1,0,1,0,1,1],
        [1,1,1,1,1,1,1],
        [0,0,1,1,1,0,0],
        [0,1,1,0,1,1,0],
        [1,0,0,0,0,0,1],
    ]
    # Goomba angry (eyebrows down)
    g3 = [
        [0,0,1,1,1,0,0],
        [0,1,1,1,1,1,0],
        [1,0,0,1,0,0,1],
        [1,1,1,1,1,1,1],
        [0,0,1,1,1,0,0],
        [0,1,1,0,1,1,0],
        [0,1,0,0,0,1,0],
    ]
    # Squished goomba (stomped!)
    squish = [
        [0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0],
        [0,1,1,1,1,1,0],
        [1,1,1,1,1,1,1],
    ]
    frames = []
    # Walk cycle
    for _ in range(4):
        frames.append(frame(g1, 3))
        frames.append(frame(g2, 3))
    # Angry
    frames.append(frame(g3, 3))
    frames.append(frame(g1, 3))
    frames.append(frame(g3, 3))
    # Stomped!
    frames.append(frame(squish, 5))
    frames.append(frame(blank(), 5))
    save("goomba", frames)


# ── Generate all ─────────────────────────────────────────────────────────────
print("Generating animations...")
gen_rain()
gen_spiral()
gen_firework()
gen_snake()
gen_pacman()
gen_heartbeat()
gen_wave()
gen_spinner()
gen_invader()
gen_dna()
gen_bounce()
gen_tetris()
gen_goomba()
print("Done! 13 animations generated.")
