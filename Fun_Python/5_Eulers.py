# euler_spiral_gif.py
"""
Exponential spiral animation using Euler's formula:
 z(t) = exp((a + i b) t) = exp(a t) * (cos(b t) + i sin(b t))
Saves: euler_spiral.gif
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import animation


a        = 0.3      #radius growth rate
b        = 8.0       #angular frequency
t_max    = 10.0      
n_frames = 180
n_points = 5000

t_vals   = np.linspace(0, t_max, n_points)  # start, stop, how many points

fig, ax  = plt.subplots(figsize=(6,6))
ax.set_aspect('equal')
ax.axis('off')

line,  = ax.plot([], [], lw=1.4)
point, = ax.plot([], [], marker='o', markersize=4)

def init():
    ax.set_xlim(-np.exp(a*t_max)-0.5, np.exp(a*t_max)+0.5)
    ax.set_ylim(-np.exp(a*t_max)-0.5, np.exp(a*t_max)+0.5)
    line.set_data([], [])
    point.set_data([], [])
    return line, point

def animate(frame):
    t_end = t_max * (0.4 + 0.6 * frame / (n_frames-1))
    t = np.linspace(0, t_end, n_points)
    z = np.exp((a + 1j * b) * t)   # Euler's formula used here
    x = z.real
    y = z.imag
    cut = int(len(t) * (0.15 + 0.85 * (frame/(n_frames-1))))
    line.set_data(x[:cut], y[:cut])
    point.set_data(x[cut-1], y[cut-1])
    return line, point


anim = animation.FuncAnimation(fig, animate, init_func=init, frames=n_frames, interval=30, blit=True)
writer = animation.PillowWriter(fps=25)
anim.save("euler_spiral.gif", writer=writer)
plt.close(fig)
print("Saved euler_spiral.gif")
