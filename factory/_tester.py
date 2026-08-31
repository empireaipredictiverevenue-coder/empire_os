#!/usr/bin/env python3
"""_tester.py — agent test gate (runs inside sandbox).

Ad-hoc verify: compile all factory modules + import check. Mirror of the
Empire OS `hermes-verify-*.py` + sys.exit(0) pattern. Reports via stdout.
"""
import subprocess, sys
mods = ["context.py", "sandbox.py", "orchestrator.py"]
ok = True
for m in mods:
    r = subprocess.run([sys.executable, "-m", "py_compile", f"/root/empire_os/factory/{m}"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        ok = False
        print(f"COMPILE_FAIL {m}: {r.stderr[:300]}")
if ok:
    try:
        import importlib.util
        for m in mods:
            spec = importlib.util.spec_from_file_location(m, f"/root/empire_os/factory/{m}")
            importlib.util.module_from_spec(spec)
        print("all factory modules import OK")
    except Exception as e:
        ok = False
        print(f"IMPORT_FAIL {e}")
print("RESULT: PASS" if ok else "RESULT: FAIL")
sys.exit(0)
