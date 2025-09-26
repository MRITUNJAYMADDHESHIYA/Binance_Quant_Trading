# domain_coloring.py
import numpy as np
import matplotlib.pyplot as plt

# define complex function
def f(z):
    # a more 'unique' function mixing exponential, polynomial and trig
    return np.exp(np.sin(2*z)) / (1 + 0.5*z**4) + 0.5*np.tan(z/2)

# grid in complex plane
res = 1200
x = np.linspace(-3, 3, res)
y = np.linspace(-3, 3, res)
X, Y = np.meshgrid(x, y)
Z = X + 1j*Y

W = f(Z)

# HSV-like coloring: hue = arg, value = magnitude mapped
arg = np.angle(W)
mag = np.abs(W)

hue = (arg + np.pi) / (2*np.pi)  # 0..1
logmag = np.log1p(mag)
value = np.clip(logmag / np.percentile(logmag, 98), 0, 1)

# create RGB via matplotlib's hsv_to_rgb
import matplotlib.colors as mcolors
HSV = np.stack([hue, np.ones_like(hue)*0.9, value], axis=-1)
RGB = mcolors.hsv_to_rgb(HSV)

plt.figure(figsize=(8,8))
plt.imshow(RGB, extent=(x.min(), x.max(), y.min(), y.max()), origin='lower')
plt.xlabel("Re")
plt.ylabel("Im")
plt.title("Domain coloring of f(z) = exp(sin(2z))/(1+0.5 z^4) + 0.5 tan(z/2)")
plt.tight_layout()
plt.savefig("domain_coloring.png", dpi=300)
plt.close()
print("Saved image to domain_coloring.png")
