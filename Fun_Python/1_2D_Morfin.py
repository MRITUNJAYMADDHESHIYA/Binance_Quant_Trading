# superflower_gif.py
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import animation
from PIL import Image

theta = np.linspace(0, 2 * np.pi, 2000)
n_frames = 120
out_path = "superflower.gif"

def superflower(theta, a, b, m, n1, n2, n3):
    part1 = np.abs(np.cos(m * theta / 4) / a) ** n2
    part2 = np.abs(np.sin(m * theta / 4) / b) ** n3
    # radial superformula-like response
    r = (part1 + part2) ** (-1.0 / n1)
    # small harmonic extra to make shape unique
    r *= (1 + 0.18 * np.sin(6 * theta) + 0.05 * np.sin(12 * theta))
    return r

fig, ax = plt.subplots(figsize=(6, 6))
ax.set_aspect('equal')
ax.axis('off')
line, = ax.plot([], [], linewidth=1.3)

def init():
    ax.set_xlim(-3, 3)
    ax.set_ylim(-3, 3)
    line.set_data([], [])
    return (line,)

def animate(i):
    t = i / n_frames * 2 * np.pi
    a = 1.0 + 0.35 * np.sin(0.7 * t)
    b = 1.0 + 0.28 * np.cos(0.9 * t + 1.0)
    m = 6 + 4 * np.sin(0.5 * t)        # symmetry parameter
    n1 = 0.3 + 0.45 * (1 + np.sin(0.6 * t))
    n2 = 1.0 + 0.9 * np.abs(np.cos(0.4 * t))
    n3 = 1.2 + 0.6 * np.abs(np.sin(0.3 * t + 0.5))

    r = superflower(theta, a, b, m, n1, n2, n3)
    x = r * np.cos(theta)
    y = r * np.sin(theta)

    # draw partial trace to create motion feel
    idx_cut = int(len(theta) * (0.25 + 0.75 * (0.5 + 0.5*np.sin(t))))
    line.set_data(x[:idx_cut], y[:idx_cut])
    return (line,)

anim = animation.FuncAnimation(fig, animate, init_func=init,
                               frames=n_frames, interval=40, blit=True)
writer = animation.PillowWriter(fps=25)
anim.save(out_path, writer=writer)
plt.close(fig)

print(f"Saved GIF to: {out_path}")
