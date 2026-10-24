"""
Builds the Proofread logo files from one set of shapes, so they always match:
  logo.svg      the mark (used in the app header, landing page, sidebar icon)
  wordmark.svg  mark + "Proofread" (top of the sidebar)
  favicon.png   the mark as a PNG (browser tab)

The mark: a magnifying glass whose lens is ringed by network "nodes" (AI that reads
sources), with a check mark inside (verify, rather than label something fake) and a
coral handle, on an indigo-violet tile so it works on light and dark backgrounds.

Run from the project folder:  backend/.venv/bin/python assets/make_logo.py
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
CX, CY, R = 27.0, 27.0, 11.5            # lens centre and radius (64 x 64 canvas)
NODE_ANGLES = [-90, -150, 150, -30, 105]   # degrees, clockwise from "east"; the handle sits at 45
NODE_IN, NODE_OUT, NODE_R = R + 1.5, R + 7.5, 2.3
HANDLE = ((36.5, 36.5), (49.5, 49.5))
CHECK = [(21.0, 27.5), (25.3, 31.8), (33.0, 23.5)]
CORAL, CORAL_DARK = "#fb7185", "#e11d48"
GRAD = ("#6366f1", "#8b5cf6")


def node_lines():
    for a in NODE_ANGLES:
        c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
        yield (CX + NODE_IN * c, CY + NODE_IN * s), (CX + NODE_OUT * c, CY + NODE_OUT * s)


def mark_svg(prefix: str = "pr") -> str:
    """The mark's SVG elements on a 64 x 64 canvas."""
    nodes = "".join(
        f'<line x1="{a[0]:.2f}" y1="{a[1]:.2f}" x2="{b[0]:.2f}" y2="{b[1]:.2f}" stroke="#fff" stroke-width="2.2" '
        f'stroke-linecap="round"/><circle cx="{b[0]:.2f}" cy="{b[1]:.2f}" r="{NODE_R}" fill="#fff"/>'
        for a, b in node_lines())
    (hx1, hy1), (hx2, hy2) = HANDLE
    check = " ".join(f"{x},{y}" for x, y in CHECK)
    return f'''
  <defs>
    <linearGradient id="{prefix}-tile" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{GRAD[0]}"/><stop offset="1" stop-color="{GRAD[1]}"/>
    </linearGradient>
    <linearGradient id="{prefix}-handle" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{CORAL}"/><stop offset="1" stop-color="{CORAL_DARK}"/>
    </linearGradient>
  </defs>
  <rect width="64" height="64" rx="16" fill="url(#{prefix}-tile)"/>
  {nodes}
  <line x1="{hx1}" y1="{hy1}" x2="{hx2}" y2="{hy2}" stroke="url(#{prefix}-handle)" stroke-width="7.5" stroke-linecap="round"/>
  <line x1="{CX + R * 0.72:.2f}" y1="{CY + R * 0.72:.2f}" x2="{hx1 + 1.2}" y2="{hy1 + 1.2}" stroke="#fff" stroke-width="3.5" stroke-linecap="round"/>
  <circle cx="{CX}" cy="{CY}" r="{R}" fill="rgba(255,255,255,0.16)" stroke="#fff" stroke-width="3.4"/>
  <polyline points="{check}" fill="none" stroke="#fff" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/>'''


def write_svgs():
    (HERE / "logo.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="Proofread logo">'
        f'{mark_svg("pr")}\n</svg>\n')
    (HERE / "wordmark.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 250 64" role="img" aria-label="Proofread">'
        f'{mark_svg("prw")}\n'
        '  <text x="80" y="45" font-family="Inter, -apple-system, \'Segoe UI\', Helvetica, Arial, sans-serif" '
        'font-size="36" font-weight="700" letter-spacing="-1.2" fill="#7c6cf2">Proofread</text>\n</svg>\n')


def write_favicon(size: int = 128):
    S = 1024                                   # draw big, then shrink for smooth edges
    k = S / 64
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    hexrgb = lambda h: tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))  # noqa: E731
    a, b = hexrgb(GRAD[0]), hexrgb(GRAD[1])
    grad = Image.new("RGBA", (S, S))
    gp = grad.load()
    for y in range(S):
        for x in range(S):
            t = (x + y) / (2 * S - 2)
            gp[x, y] = tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=int(16 * k), fill=255)
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)

    def round_line(p, q, width, fill):
        d.line([p[0] * k, p[1] * k, q[0] * k, q[1] * k], fill=fill, width=int(width * k))
        for x, y in (p, q):
            r = width * k / 2
            d.ellipse([x * k - r, y * k - r, x * k + r, y * k + r], fill=fill)

    for p, q in node_lines():
        round_line(p, q, 2.2, "white")
        d.ellipse([(q[0] - NODE_R) * k, (q[1] - NODE_R) * k, (q[0] + NODE_R) * k, (q[1] + NODE_R) * k], fill="white")
    round_line(*HANDLE, 7.5, CORAL)
    round_line((CX + R * 0.72, CY + R * 0.72), (HANDLE[0][0] + 1.2, HANDLE[0][1] + 1.2), 3.5, "white")
    lens = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(lens).ellipse([(CX - R) * k, (CY - R) * k, (CX + R) * k, (CY + R) * k], fill=(255, 255, 255, 41))
    img = Image.alpha_composite(img, lens)
    d = ImageDraw.Draw(img)
    d.ellipse([(CX - R) * k, (CY - R) * k, (CX + R) * k, (CY + R) * k], outline="white", width=int(3.4 * k))
    for p, q in zip(CHECK, CHECK[1:]):
        round_line(p, q, 3.4, "white")
    img.resize((size, size), Image.LANCZOS).save(HERE / "favicon.png")


if __name__ == "__main__":
    write_svgs()
    write_favicon()
    print("wrote logo.svg, wordmark.svg, favicon.png")
