"""Generate complex, high-frame-count 7x7 LED matrix animations."""
import json
import os
import math
import random

MATRIX_DIR = os.path.join(os.path.dirname(__file__), 'matrix')
os.makedirs(MATRIX_DIR, exist_ok=True)

def blank():
    return [[0]*7 for _ in range(7)]

def frame(matrix, time_slot=1):
    return {"data": [row[:] for row in matrix], "time_slot": time_slot}

def save(name, frames):
    path = os.path.join(MATRIX_DIR, f"{name}.json")
    with open(path, 'w') as f:
        json.dump(frames, f)
    print(f"  {name}.json ({len(frames)} frames)")


# ── 1. Game of Life ──────────────────────────────────────────────────────────
def gen_life():
    """Conway's Game of Life - starts from a random seed, runs 80 generations."""
    random.seed(7)
    grid = [[1 if random.random() < 0.4 else 0 for _ in range(7)] for _ in range(7)]
    frames = []
    for _ in range(80):
        frames.append(frame(grid, 2))
        new = blank()
        for r in range(7):
            for c in range(7):
                n = 0
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dr == 0 and dc == 0: continue
                        nr, nc = (r + dr) % 7, (c + dc) % 7
                        n += grid[nr][nc]
                if grid[r][c]:
                    new[r][c] = 1 if n in (2, 3) else 0
                else:
                    new[r][c] = 1 if n == 3 else 0
        grid = new
    save("gameoflife", frames)


# ── 2. Starfield ─────────────────────────────────────────────────────────────
def gen_starfield():
    """3D starfield flying through space - stars grow from center outward."""
    random.seed(99)
    stars = []
    for _ in range(30):
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(0.03, 0.12)
        stars.append([3.0, 3.0, angle, speed, random.uniform(0, 3)])

    frames = []
    for t in range(60):
        m = blank()
        for s in stars:
            s[4] += s[3]
            x = 3 + s[4] * math.cos(s[2])
            y = 3 + s[4] * math.sin(s[2])
            ix, iy = int(round(x)), int(round(y))
            if 0 <= ix < 7 and 0 <= iy < 7:
                m[iy][ix] = 1
            # Respawn if out of bounds
            if ix < -1 or ix > 7 or iy < -1 or iy > 7:
                s[2] = random.uniform(0, 2 * math.pi)
                s[3] = random.uniform(0.03, 0.12)
                s[4] = 0
        frames.append(frame(m, 1))
    save("starfield", frames)


# ── 3. Matrix Rain (full cyberpunk) ──────────────────────────────────────────
def gen_matrix_rain():
    """Dense Matrix-style rain with variable-length streams and staggered starts."""
    random.seed(13)
    # Each column has a stream: head position, length, speed, delay
    streams = []
    for c in range(7):
        streams.append({
            'col': c,
            'head': -random.randint(0, 10),
            'length': random.randint(3, 6),
            'speed': random.choice([1, 1, 2]),
        })
    frames = []
    for t in range(60):
        m = blank()
        for s in streams:
            h = s['head']
            for i in range(s['length']):
                r = h - i
                if 0 <= r < 7:
                    m[r][s['col']] = 1
            s['head'] += s['speed']
            # Reset when fully off-screen
            if s['head'] - s['length'] > 7:
                s['head'] = -random.randint(0, 6)
                s['length'] = random.randint(3, 6)
                s['speed'] = random.choice([1, 1, 2])
        frames.append(frame(m, 1))
    save("matrix_rain", frames)


# ── 4. Plasma / Lava Lamp ───────────────────────────────────────────────────
def gen_plasma():
    """Animated plasma effect using overlapping sine waves with threshold."""
    frames = []
    for t in range(60):
        m = blank()
        for r in range(7):
            for c in range(7):
                v = math.sin(r * 0.7 + t * 0.3)
                v += math.sin(c * 0.8 + t * 0.2)
                v += math.sin((r + c) * 0.5 + t * 0.15)
                v += math.sin(math.sqrt(float((r - 3)**2 + (c - 3)**2)) * 0.8 - t * 0.25)
                m[r][c] = 1 if v > 0.5 else 0
        frames.append(frame(m, 1))
    save("plasma", frames)


# ── 5. Maze Generator (animated recursive backtrack) ─────────────────────────
def gen_maze():
    """Watch a maze being carved in real-time."""
    # 7x7 grid: walls=1, paths=0. Start all walls.
    maze = [[1]*7 for _ in range(7)]
    frames = []
    visited = set()
    stack = [(1, 1)]
    maze[1][1] = 0
    visited.add((1, 1))
    frames.append(frame(maze, 1))

    directions = [(0, 2), (0, -2), (2, 0), (-2, 0)]
    random.seed(42)

    while stack:
        r, c = stack[-1]
        random.shuffle(directions)
        found = False
        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            if 0 < nr < 7 and 0 < nc < 7 and (nr, nc) not in visited:
                # Carve wall between
                maze[r + dr // 2][c + dc // 2] = 0
                maze[nr][nc] = 0
                visited.add((nr, nc))
                stack.append((nr, nc))
                found = True
                frames.append(frame(maze, 1))
                break
        if not found:
            stack.pop()
            frames.append(frame(maze, 1))

    # Flash the completed maze
    for _ in range(5):
        frames.append(frame(maze, 3))
        frames.append(frame([[1]*7 for _ in range(7)], 3))
    save("maze", frames)


# ── 6. Particle Explosion ───────────────────────────────────────────────────
def gen_particle_explosion():
    """Multiple particles explode from center with physics (gravity + bounce)."""
    random.seed(55)
    particles = []
    for _ in range(12):
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(0.5, 1.5)
        particles.append({
            'x': 3.0, 'y': 3.0,
            'vx': speed * math.cos(angle),
            'vy': speed * math.sin(angle),
        })

    frames = []
    for t in range(50):
        m = blank()
        for p in particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['vy'] += 0.08  # gravity
            # Bounce off walls
            if p['x'] < 0: p['x'] = 0; p['vx'] *= -0.7
            if p['x'] > 6: p['x'] = 6; p['vx'] *= -0.7
            if p['y'] < 0: p['y'] = 0; p['vy'] *= -0.7
            if p['y'] > 6: p['y'] = 6; p['vy'] *= -0.7
            ix, iy = int(round(p['x'])), int(round(p['y']))
            if 0 <= ix < 7 and 0 <= iy < 7:
                m[iy][ix] = 1
        frames.append(frame(m, 1))

    # Second explosion
    for p in particles:
        p['x'] = 3.0; p['y'] = 3.0
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(0.8, 2.0)
        p['vx'] = speed * math.cos(angle)
        p['vy'] = speed * math.sin(angle)
    for t in range(50):
        m = blank()
        for p in particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['vy'] += 0.06
            p['vx'] *= 0.97  # drag
            p['vy'] *= 0.97
            if p['x'] < 0: p['x'] = 0; p['vx'] *= -0.6
            if p['x'] > 6: p['x'] = 6; p['vx'] *= -0.6
            if p['y'] < 0: p['y'] = 0; p['vy'] *= -0.6
            if p['y'] > 6: p['y'] = 6; p['vy'] *= -0.6
            ix, iy = int(round(p['x'])), int(round(p['y']))
            if 0 <= ix < 7 and 0 <= iy < 7:
                m[iy][ix] = 1
        frames.append(frame(m, 1))
    save("particles", frames)


# ── 7. Clock Digits Countdown ────────────────────────────────────────────────
def gen_countdown():
    """Cinematic 10→0 countdown with wipe transitions."""
    DIGITS_3x5 = {
        0: [[1,1,1],[1,0,1],[1,0,1],[1,0,1],[1,1,1]],
        1: [[0,1,0],[1,1,0],[0,1,0],[0,1,0],[1,1,1]],
        2: [[1,1,1],[0,0,1],[1,1,1],[1,0,0],[1,1,1]],
        3: [[1,1,1],[0,0,1],[1,1,1],[0,0,1],[1,1,1]],
        4: [[1,0,1],[1,0,1],[1,1,1],[0,0,1],[0,0,1]],
        5: [[1,1,1],[1,0,0],[1,1,1],[0,0,1],[1,1,1]],
        6: [[1,1,1],[1,0,0],[1,1,1],[1,0,1],[1,1,1]],
        7: [[1,1,1],[0,0,1],[0,0,1],[0,0,1],[0,0,1]],
        8: [[1,1,1],[1,0,1],[1,1,1],[1,0,1],[1,1,1]],
        9: [[1,1,1],[1,0,1],[1,1,1],[0,0,1],[1,1,1]],
    }

    def digit_frame(n):
        m = blank()
        if n >= 10:
            d1, d2 = DIGITS_3x5[n // 10], DIGITS_3x5[n % 10]
            for r in range(5):
                for c in range(3):
                    m[r + 1][c] = d1[r][c]
                    m[r + 1][c + 4] = d2[r][c]
        else:
            d = DIGITS_3x5[n]
            for r in range(5):
                for c in range(3):
                    m[r + 1][c + 2] = d[r][c]
        return m

    frames = []
    for n in range(10, -1, -1):
        dm = digit_frame(n)
        # Wipe in from left
        for col in range(7):
            m = blank()
            for r in range(7):
                for c in range(col + 1):
                    m[r][c] = dm[r][c]
            frames.append(frame(m, 1))
        # Hold
        frames.append(frame(dm, 4))
        # Flash on last number
        if n == 0:
            for _ in range(6):
                frames.append(frame(dm, 2))
                frames.append(frame(blank(), 2))
    save("countdown", frames)


# ── 8. Running Man ───────────────────────────────────────────────────────────
def gen_running_man():
    """Stick figure running animation with scrolling ground."""
    f1 = [
        [0,0,0,1,0,0,0],
        [0,0,1,1,1,0,0],
        [0,0,0,1,0,0,0],
        [0,0,1,1,0,0,0],
        [0,0,0,1,0,0,0],
        [0,0,1,0,1,0,0],
        [0,1,0,0,0,1,0],
    ]
    f2 = [
        [0,0,0,1,0,0,0],
        [0,0,1,1,1,0,0],
        [0,1,0,1,0,0,0],
        [0,0,0,1,0,0,0],
        [0,0,1,0,1,0,0],
        [0,1,0,0,0,1,0],
        [0,0,0,0,0,0,0],
    ]
    f3 = [
        [0,0,0,1,0,0,0],
        [0,0,1,1,1,0,0],
        [0,0,0,1,0,1,0],
        [0,0,0,1,0,0,0],
        [0,0,1,0,1,0,0],
        [0,0,0,0,0,0,0],
        [0,0,1,0,0,1,0],
    ]
    f4 = [
        [0,0,0,1,0,0,0],
        [0,0,1,1,1,0,0],
        [0,0,0,1,0,0,0],
        [0,0,0,1,1,0,0],
        [0,0,0,1,0,0,0],
        [0,0,1,0,1,0,0],
        [0,1,0,0,0,1,0],
    ]
    run_frames = [f1, f2, f3, f4]
    frames = []
    for cycle in range(15):
        for rf in run_frames:
            m = [row[:] for row in rf]
            # Scrolling ground dots
            offset = (cycle * 4 + run_frames.index(rf)) % 3
            for c in range(0, 7, 3):
                gc = (c + offset) % 7
                # No ground row since man takes full height — skip
            frames.append(frame(m, 2))
    save("running_man", frames)


# ── 9. Morphing Shapes ──────────────────────────────────────────────────────
def gen_morph():
    """Circle → Square → Diamond → Star → Circle, smooth morphing."""
    def circle():
        m = blank()
        for r in range(7):
            for c in range(7):
                dist = math.sqrt((r - 3)**2 + (c - 3)**2)
                if 2.0 <= dist <= 3.2:
                    m[r][c] = 1
        return m

    def square():
        m = blank()
        for r in range(1, 6):
            m[r][1] = m[r][5] = 1
        for c in range(1, 6):
            m[1][c] = m[5][c] = 1
        return m

    def diamond():
        m = blank()
        pts = [(0,3),(1,2),(1,4),(2,1),(2,5),(3,0),(3,6),(4,1),(4,5),(5,2),(5,4),(6,3)]
        for r, c in pts:
            m[r][c] = 1
        return m

    def star():
        m = blank()
        pts = [(0,3),(1,2),(1,3),(1,4),(2,3),(3,0),(3,1),(3,2),(3,3),(3,4),(3,5),(3,6),
               (4,3),(5,2),(5,3),(5,4),(6,3),(2,1),(2,5),(4,1),(4,5)]
        for r, c in pts:
            if 0 <= r < 7 and 0 <= c < 7:
                m[r][c] = 1
        return m

    def filled():
        m = blank()
        for r in range(7):
            for c in range(7):
                if math.sqrt((r - 3)**2 + (c - 3)**2) <= 3:
                    m[r][c] = 1
        return m

    def cross():
        m = blank()
        for i in range(7):
            m[3][i] = 1
            m[i][3] = 1
        return m

    def morph_transition(a, b, steps=8):
        """Create transition frames between two shapes."""
        frames = []
        # Hold source
        frames.append(frame(a, 3))
        # Dissolve: randomly swap pixels
        random.seed(hash(str(a)) & 0xFFFFFF)
        diff_pixels = []
        for r in range(7):
            for c in range(7):
                if a[r][c] != b[r][c]:
                    diff_pixels.append((r, c))
        random.shuffle(diff_pixels)
        chunk = max(1, len(diff_pixels) // steps)
        current = [row[:] for row in a]
        for i in range(0, len(diff_pixels), chunk):
            batch = diff_pixels[i:i + chunk]
            for r, c in batch:
                current[r][c] = b[r][c]
            frames.append(frame(current, 1))
        return frames

    shapes = [circle(), square(), diamond(), star(), cross(), filled(), circle()]
    frames = []
    for i in range(len(shapes) - 1):
        frames.extend(morph_transition(shapes[i], shapes[i + 1]))
    # Hold final
    frames.append(frame(shapes[-1], 5))
    save("morph", frames)


# ── 10. Pong ─────────────────────────────────────────────────────────────────
def gen_pong():
    """Two-paddle Pong game simulation with scoring."""
    DIGITS_3x5 = {
        0: [[1,1,1],[1,0,1],[1,0,1],[1,0,1],[1,1,1]],
        1: [[0,1,0],[1,1,0],[0,1,0],[0,1,0],[1,1,1]],
        2: [[1,1,1],[0,0,1],[1,1,1],[1,0,0],[1,1,1]],
        3: [[1,1,1],[0,0,1],[1,1,1],[0,0,1],[1,1,1]],
    }

    bx, by = 3.0, 3.0
    bvx, bvy = 0.7, 0.5
    p1 = 2  # left paddle top row (3 tall)
    p2 = 2  # right paddle top row
    s1, s2 = 0, 0
    frames = []

    for t in range(120):
        m = blank()
        # Draw paddles
        for i in range(3):
            if 0 <= p1 + i < 7: m[p1 + i][0] = 1
            if 0 <= p2 + i < 7: m[p2 + i][6] = 1
        # Draw ball
        ibx, iby = int(round(bx)), int(round(by))
        if 0 <= ibx < 7 and 0 <= iby < 7:
            m[iby][ibx] = 1

        frames.append(frame(m, 1))

        # Move ball
        bx += bvx
        by += bvy

        # Top/bottom bounce
        if by <= 0: by = 0; bvy = abs(bvy)
        if by >= 6: by = 6; bvy = -abs(bvy)

        # Paddle collision
        if bx <= 1 and p1 <= int(round(by)) <= p1 + 2:
            bvx = abs(bvx); bx = 1
        if bx >= 5 and p2 <= int(round(by)) <= p2 + 2:
            bvx = -abs(bvx); bx = 5

        # Score
        if bx < 0:
            s2 = min(3, s2 + 1)
            bx, by = 3.0, 3.0; bvx = 0.7; bvy = random.choice([-0.5, 0.5])
            # Show score
            sm = blank()
            d = DIGITS_3x5.get(s1, DIGITS_3x5[0])
            for r in range(5):
                for c in range(3):
                    sm[r + 1][c] = d[r][c]
            d = DIGITS_3x5.get(s2, DIGITS_3x5[0])
            for r in range(5):
                for c in range(3):
                    sm[r + 1][c + 4] = d[r][c]
            for _ in range(5):
                frames.append(frame(sm, 2))
        if bx > 6:
            s1 = min(3, s1 + 1)
            bx, by = 3.0, 3.0; bvx = -0.7; bvy = random.choice([-0.5, 0.5])
            sm = blank()
            d = DIGITS_3x5.get(s1, DIGITS_3x5[0])
            for r in range(5):
                for c in range(3):
                    sm[r + 1][c] = d[r][c]
            d = DIGITS_3x5.get(s2, DIGITS_3x5[0])
            for r in range(5):
                for c in range(3):
                    sm[r + 1][c + 4] = d[r][c]
            for _ in range(5):
                frames.append(frame(sm, 2))

        # AI paddle tracking
        target = int(round(by))
        if p1 + 1 < target: p1 = min(4, p1 + 1)
        elif p1 + 1 > target: p1 = max(0, p1 - 1)
        if p2 + 1 < target: p2 = min(4, p2 + 1)
        elif p2 + 1 > target: p2 = max(0, p2 - 1)

    save("pong", frames)


# ── Generate all ─────────────────────────────────────────────────────────────
random.seed(42)
print("Generating complex animations...")
gen_life()
gen_starfield()
gen_matrix_rain()
gen_plasma()
gen_maze()
gen_particle_explosion()
gen_countdown()
gen_running_man()
gen_morph()
gen_pong()
print("Done! 10 complex animations generated.")
