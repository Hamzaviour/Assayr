"""Regenerate assayr.ico from the frontend favicon (maintainer tool; the .ico is committed).

Needs Playwright with Chromium and Pillow: python deploy/windows/make-icon.py
"""

import io
import pathlib

from PIL import Image
from playwright.sync_api import sync_playwright

here = pathlib.Path(__file__).parent
svg = (here.parents[1] / "frontend" / "public" / "favicon.svg").read_text(encoding="utf-8")
sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
frames = []
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    for size in sizes:
        page = browser.new_page(viewport={"width": size, "height": size})
        page.set_content(
            f'<html><body style="margin:0;background:transparent">'
            f'{svg.replace('width="64" height="64"', f'width="{size}" height="{size}"')}</body></html>'
        )
        png = page.screenshot(omit_background=True, clip={"x": 0, "y": 0, "width": size, "height": size})
        frames.append(Image.open(io.BytesIO(png)).convert("RGBA"))
        page.close()
    browser.close()
frames[-1].save(here / "assayr.ico", format="ICO", sizes=[(s, s) for s in sizes], append_images=frames[:-1])
print("wrote", here / "assayr.ico")
