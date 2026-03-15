from pathlib import Path
from PIL import Image
import numpy as np

base = Path("/Users/wesleyrufus/AI_STUDIO_LAB/projects/sandbox_project/assets/2D Isometric Village Asset Pack")
files = [
    ("tree", "Isometric Assets 2.png"),
    ("shrub", "Isometric Assets 3.png"),
    ("rock", "Isometric Assets 4.png"),
]
cell = 64

for kind, name in files:
    p = base / name
    img = Image.open(p).convert("RGBA")
    arr = np.array(img)
    h, w, _ = arr.shape
    cols = w // cell
    rows = h // cell
    print(f"\n[{kind}] {name} size={w}x{h} grid={cols}x{rows}")
    cands = []
    for y in range(rows):
        for x in range(cols):
            sub = arr[y * cell : (y + 1) * cell, x * cell : (x + 1) * cell, :]
            a = sub[:, :, 3]
            mask = a > 18
            fill = float(mask.mean())
            if fill < 0.06 or fill > 0.62:
                continue
            edge = np.concatenate([mask[0, :], mask[-1, :], mask[:, 0], mask[:, -1]])
            edge_ratio = float(edge.mean())
            ys, xs = np.where(mask)
            if len(xs) < 20:
                continue
            bw = int(xs.max() - xs.min() + 1)
            bh = int(ys.max() - ys.min() + 1)
            bbox_ratio = float((bw * bh) / (cell * cell))
            bottom = float(mask[int(cell * 0.72) :, :].mean())
            top = float(mask[: int(cell * 0.5), :].mean())

            if edge_ratio > 0.34:
                continue
            if kind == "tree" and top < 0.10:
                continue
            if kind in ("rock", "shrub") and fill > 0.45:
                continue

            score = (fill * 1.1 + bbox_ratio * 0.8 + bottom * 0.5 + top * 0.2) - edge_ratio * 1.4
            cands.append((score, x, y, fill, edge_ratio, bbox_ratio, top, bottom))

    cands.sort(reverse=True)
    for score, x, y, fill, edge, bbox, top, bottom in cands[:16]:
        print(f"  ({x},{y}) score={score:.3f} fill={fill:.3f} edge={edge:.3f} bbox={bbox:.3f} top={top:.3f} bot={bottom:.3f}")
