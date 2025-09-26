# euler_domain_coloring.py
"""
Domain coloring of f(z) = exp(i z^2).
Hue = arg(f) = Im(z^2).  We'll wrap hue and add brightness modulation.
Saves: euler_domain_coloring.png
"""
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

res  = 1200
x    = np.linspace(-2.5, 2.5, res)
y    = np.linspace(-2.5, 2.5, res)
X, Y = np.meshgrid(x, y)
Z    = X + 1j*Y

W   = np.exp(1j * Z**2)          # Euler used: exp(i * z^2)
arg = np.angle(W)                # between -pi and pi
hue = (arg + np.pi) / (2*np.pi)  # normalize to [0,1]

# brightness: use a gentle function of Im(z^2) to create bands and contrast
im_z2 = (Z**2).imag
value = 0.5 + 0.5 * np.tanh(0.6 * im_z2)   # smooth contrast
saturation = 0.95

HSV = np.stack([hue, np.full_like(hue, saturation), value], axis=-1)
RGB = mcolors.hsv_to_rgb(HSV)

plt.figure(figsize=(8,8), dpi=150)
plt.imshow(RGB, extent=(x[0], x[-1], y[0], y[-1]), origin='lower')
plt.xlabel("Re(z)"); plt.ylabel("Im(z)")
plt.title(r"Domain coloring: $f(z)=e^{i z^2}$")
plt.axis('on')
plt.savefig("euler_domain_coloring.png", bbox_inches='tight', dpi=150)
plt.close()
print("Saved euler_domain_coloring.png")
