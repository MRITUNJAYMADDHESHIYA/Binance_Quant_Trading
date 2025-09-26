# fourier_rose.py
"""
Fourier Rose: z(theta) = sum_{k=1..N} (1/k) * exp(i k theta)
Saves: fourier_rose.png (static high-res image)
"""
import numpy as np
import matplotlib.pyplot as plt

N = 80         # number of harmonics
samples = 3000

theta = np.linspace(0, 2*np.pi, samples)
z = np.zeros_like(theta, dtype=np.complex128)

for k in range(1, N+1):
    z += (1.0/k) * np.exp(1j * k * theta)   # Euler's formula: e^{ikθ}

x = z.real
y = z.imag

plt.figure(figsize=(8,8), dpi=150)
plt.plot(x, y, linewidth=0.7)
plt.gca().set_aspect('equal', adjustable='box')
plt.axis('off')
plt.title(f"Fourier Rose: sum 1/k e^(i k θ), k=1..{N}")
plt.savefig("fourier_rose.png", bbox_inches='tight', pad_inches=0.05)
plt.close()
print("Saved fourier_rose.png")
