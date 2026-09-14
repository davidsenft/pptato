"""Regenerate the synthetic image fixture (optional dependency: matplotlib)."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(8, 4.5))
ax.plot([1, 2, 3, 4], [82, 91, 103, 118], color="#143E4B", marker="o", linewidth=3)
ax.set_xticks([1, 2, 3, 4], ["Q1", "Q2", "Q3", "Q4"])
ax.set_ylim(0, 130)
ax.set_ylabel("Volume index", fontsize=13)
ax.tick_params(labelsize=12)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="y", color="#DFEBEE")
fig.tight_layout()
output = Path(__file__).parent / "assets" / "volume.png"
output.parent.mkdir(exist_ok=True)
fig.savefig(output, dpi=160)
plt.close(fig)
print(output)
