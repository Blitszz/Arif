"""
Download MLBB hero portrait images into ./templates for vision matching.

Uses the public mlbb.io hero list (CDN URLs from akmweb.youngjoygame.com).
Filenames match hero_data.json keys exactly (required for VisionEngine).

Run: python fetch_hero_templates.py
"""

from __future__ import annotations

import json
import pathlib
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
HERO_DATA = ROOT / "hero_data.json"
OUT_DIR = ROOT / "templates"
API_URL = "https://mlbb.io/api/hero/all-heroes"
USER_AGENT = "Mozilla/5.0 (compatible; MLBB-Drafter/1.0)"


def normalize(name: str) -> str:
    return "".join(c.lower() for c in name if c.isalnum())


def load_url_map() -> dict[str, str]:
    req = urllib.request.Request(API_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    heroes = payload.get("data") or []
    url_by_norm: dict[str, str] = {}
    for h in heroes:
        name = h.get("hero_name")
        url = h.get("img_src")
        if not name or not url:
            continue
        key = normalize(name)
        url_by_norm[key] = str(url)
    return url_by_norm


def download_file(url: str, dest: pathlib.Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    dest.write_bytes(data)


def main() -> int:
    hero_data = json.loads(HERO_DATA.read_text(encoding="utf-8"))
    names = sorted(hero_data.keys(), key=str.lower)
    url_by_norm = load_url_map()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ok = 0
    failed: list[tuple[str, str]] = []

    for i, display_name in enumerate(names):
        key = normalize(display_name)
        url = url_by_norm.get(key)
        if not url:
            failed.append((display_name, "no API URL"))
            continue
        dest = OUT_DIR / f"{display_name}.png"
        try:
            download_file(url, dest)
            ok += 1
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, TimeoutError) as e:
            failed.append((display_name, str(e)))
        if (i + 1) % 20 == 0:
            print(f"  ... {i + 1}/{len(names)}")
        time.sleep(0.08)

    print(f"Done. Saved {ok} images to {OUT_DIR}")
    if failed:
        print(f"Failed ({len(failed)}):")
        for name, err in failed[:25]:
            print(f"  - {name}: {err}")
        if len(failed) > 25:
            print(f"  ... and {len(failed) - 25} more")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
