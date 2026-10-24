"""Screen-record a UI walkthrough (needs `playwright` and the app running on port 8000).

Usage: python scripts/record_demo.py out.webm
"""

import shutil
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

STEPS = [
    ("hr", "hybrid_rerank", "How many days of annual leave do we get, and how many can be carried forward?"),
    ("employee", "hybrid_rerank", "How many days of annual leave do Northwind employees get?"),
    ("finance", "hybrid_rerank", "According to NVIDIA's 10-K, what factors could limit customers' data center expansion?"),
    ("research", "hybrid_rerank", "In the ColBERT paper, what interaction mechanism is introduced?"),
    ("research", "hybrid_rerank", "What top-1 accuracy does ColBERT reach on ImageNet?"),
]

out = Path(sys.argv[1])
tmp = out.parent / "_video"
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1280, "height": 800}, record_video_dir=str(tmp),
                        record_video_size={"width": 1280, "height": 800})
    page = ctx.new_page()
    page.goto("http://127.0.0.1:8000/")
    page.wait_for_timeout(2500)
    for role, mode, question in STEPS:
        page.select_option(".role select", role)
        page.select_option(".composer select", mode)
        page.fill(".composer input", "")
        page.type(".composer input", question, delay=25)
        n = page.locator(".msg.bot").count()
        page.click(".composer button")
        page.wait_for_function(f"document.querySelectorAll('.msg.bot:not(.thinking)').length > {n}", timeout=300000)
        page.wait_for_timeout(2500)
        chip = page.locator(".msg.bot").last.locator(".chip")
        if chip.count():
            chip.first.click()
            page.wait_for_timeout(3500)
            page.click(".source-head button")
        page.wait_for_timeout(1000)
    page.select_option(".role select", "admin")
    page.wait_for_timeout(500)
    page.click("nav button:has-text('Admin')")
    page.wait_for_timeout(3000)
    page.mouse.wheel(0, 600)
    page.wait_for_timeout(2500)
    video = page.video.path()
    ctx.close()
    b.close()
shutil.move(video, out)
shutil.rmtree(tmp, ignore_errors=True)
print(f"wrote {out}")
