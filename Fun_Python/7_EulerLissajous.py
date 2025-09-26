# euler_lissajous_gif.py
"""
Euler Lissajous from two phasors:
 z(t) = e^{i a t} + R * e^{i(b t + phi)}
Saves: euler_lissajous.gif
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import animation

a = 3.0           # freq of first phasor
b = 4.0           # freq of second phasor
R = 1.2           # amplitude ratio
phi = 0.7         # phase offset
t_max = 12
n_frames = 240
n_points = 3000

t = np.linspace(0, t_max, n_points)

fig, ax = plt.subplots(figsize=(6,6))
ax.set_aspect('equal')
ax.axis('off')
line, = ax.plot([], [], lw=1.2)
point, = ax.plot([], [], 'o', markersize=3)

def init():
    ax.set_xlim(-2.6, 2.6)
    ax.set_ylim(-2.6, 2.6)
    line.set_data([], [])
    point.set_data([], [])
    return line, point

def animate(frame):
    # sweep window to create a trailing motion
    t0 = (frame / (n_frames-1)) * (t_max * 0.7)
    t_win = np.linspace(t0, t0 + 3.0, 1000)
    z = np.exp(1j * a * t_win) + R * np.exp(1j * (b * t_win + phi))
    x = z.real
    y = z.imag
    line.set_data(x, y)
    point.set_data(x[-1], y[-1])
    return line, point

anim = animation.FuncAnimation(fig, animate, init_func=init,
                               frames=n_frames, interval=30, blit=True)
writer = animation.PillowWriter(fps=25)
anim.save("euler_lissajous.gif", writer=writer)
plt.close(fig)
print("Saved euler_lissajous.gif")
