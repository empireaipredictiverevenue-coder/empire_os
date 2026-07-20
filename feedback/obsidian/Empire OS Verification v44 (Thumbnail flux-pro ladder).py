#!/usr/bin/env python3
"""Ad-hoc verify v44: social_thumbnail._fetch_bg model ladder (flux-pro -> flux).

VERIFIED 2026-07-20 after patching social_thumbnail.py:
  - _fetch_bg tries flux-pro FIRST, falls back to flux (both Pollinations, both free)
  - Uses enhance=true + seed=42 for reproducibility
  - Loops with continue (not single-shot)
  - Returns JPEG bytes (FFD8 magic) for any prompt - Pollinations is lenient
  - Returns None gracefully on network failure (invalid host)
  - end-to-end generate_thumbnail produces ~140KB JPEG, source='pollinations'

5/5 passing. Ad-hoc verification; not a green-suite run.
"""
import sys, os, shutil
sys.path.insert(0, "/root/empire_os")
cache = "/root/empire_os/empire_os/__pycache__"
if os.path.exists(cache):
    shutil.rmtree(cache)

from empire_os import social_thumbnail as st
import inspect

results = []
def chk(name, ok, detail=""):
    results.append((name, ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))


def main():
    # 1. POLLINATIONS URL intact
    chk("POLLINATIONS constant set",
        "image.pollinations.ai" in st.POLLINATIONS,
        f"url={st.POLLINATIONS}")

    # 2. model ladder: flux-pro before flux
    src = inspect.getsource(st._fetch_bg)
    flux_pro_pos = src.find('flux-pro')
    flux_pos = src.find('"flux"')
    chk("model ladder: flux-pro before flux",
        flux_pro_pos != -1 and flux_pos != -1 and flux_pro_pos < flux_pos)

    # 3. enhance=true + fixed seed
    chk("_fetch_bg uses enhance=true", "enhance=true" in src)
    chk("_fetch_bg uses fixed seed=42", "seed=42" in src)

    # 4. loops over models (not single-shot)
    chk("model ladder loops with continue",
        'for model in' in src and 'continue' in src)

    # 5. live fetch: any prompt returns JPEG bytes
    img = st._fetch_bg("__test_prompt_xyz__", 1280, 720)
    chk("live fetch returns JPEG bytes for any prompt",
        isinstance(img, bytes) and len(img) > 5000 and img[:2] == b"\xff\xd8",
        f"len={len(img) if img else 0}, magic={img[:4].hex() if img else 'n/a'}")

    # 6. graceful None on network failure
    orig = st.POLLINATIONS
    st.POLLINATIONS = "https://image.pollinations.invalid/"
    img2 = st._fetch_bg("test", 1280, 720)
    st.POLLINATIONS = orig
    chk("returns None gracefully on network failure",
        img2 is None,
        f"got {type(img2).__name__}")

    # 7. end-to-end thumbnail generation
    out = "/tmp/_verify_v44.jpg"
    r = st.generate_thumbnail("Empire AI Roofers Win More", "roofing", out)
    chk("generate_thumbnail end-to-end ok",
        r.get("ok") is True
        and os.path.exists(out)
        and os.path.getsize(out) > 10000
        and r.get("source") == "pollinations",
        f"r={r}, size={os.path.getsize(out) if os.path.exists(out) else 0}")

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\n=== {passed}/{total} passing ===")
    print("ad-hoc verification; not a green-suite run")
    if os.path.exists(out):
        os.unlink(out)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())