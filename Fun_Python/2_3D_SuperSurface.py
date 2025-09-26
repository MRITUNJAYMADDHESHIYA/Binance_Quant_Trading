# super_surface_3d.py
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import animation
from mpl_toolkits.mplot3d import Axes3D

# grid
u = np.linspace(0, 2*np.pi, 300)
v = np.linspace(-1, 1, 200)
U, V = np.meshgrid(u, v)

def radial(u, v, t):
    # u: angle, v: lat-like param [-1,1], t: time
    # combine superformula-like with vertical modulation
    m = 6 + 3*np.sin(0.6*t)
    a = 1.0 + 0.2*np.sin(0.9*t)
    b = 1.0 + 0.2*np.cos(1.1*t)
    part1 = np.abs(np.cos(m * u / 4) / a) ** (1.0 + 0.5*np.abs(np.cos(0.5*t)))
    part2 = np.abs(np.sin(m * u / 4) / b) ** (1.0 + 0.3*np.abs(np.sin(0.4*t)))
    r = (part1 + part2) ** (-1.0 / (0.3 + 0.3*np.sin(0.5*t)))
    # add lat-dependent thickness
    r *= (1 + 0.35 * np.exp(-3 * v**2) * np.cos(3*u + 1.2*t))
    return r

fig = plt.figure(figsize=(8,6))
ax = fig.add_subplot(111, projection='3d')
ax.axis('off')

def surface_coords(t):
    R = radial(U, V, t)
    X = R * (1 + 0.2*V) * np.cos(U)
    Y = R * (1 + 0.2*V) * np.sin(U)
    Z = 1.3 * V + 0.2 * np.sin(2*U + 0.7*t)
    return X, Y, Z

# initial plot
X, Y, Z = surface_coords(0)
surf = ax.plot_surface(X, Y, Z, rstride=3, cstride=3, linewidth=0, antialiased=True)

ax.set_xlim(-2,2)
ax.set_ylim(-2,2)
ax.set_zlim(-1.5,1.5)

def update(frame):
    ax.clear()
    ax.axis('off')
    t = frame / 80 * 2*np.pi
    X, Y, Z = surface_coords(t)
    ax.plot_surface(X, Y, Z, rstride=3, cstride=3, linewidth=0, antialiased=True)
    ax.view_init(elev=20+10*np.sin(0.2*t), azim=frame*360/80)
    return []

anim = animation.FuncAnimation(fig, update, frames=120, interval=50, blit=False)

out = "super_surface.mp4"
Writer = animation.FFMpegWriter
writer = Writer(fps=25, bitrate=1800)
anim.save(out, writer=writer)
plt.close(fig)
print(f"Saved MP4 to: {out}")
