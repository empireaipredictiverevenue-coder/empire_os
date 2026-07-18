#!/usr/bin/env python3
"""
Assemble + publish showcase pages for all 8 new products.
Run AFTER the 8 product modules land. Imports each module, reads its SPEC dict,
renders a designed showcase page (Google Fonts, AEO-ready) and pushes to the
container /srv/aeo/products/{sku}/.
"""
import sys, subprocess, importlib
sys.path.insert(0, "/root/empire_os")
import product_spec as ps

MODULES = [
    "vertical_feed", "aeo_monitor", "aeo_refresh",
    "business_dir", "verify_business", "settlement_gateway",
    "synthetic_service", "agent_copilot",
]

def main():
    ok = 0
    for mod in MODULES:
        try:
            m = importlib.import_module(mod)
            spec = getattr(m, "SPEC", None)
            if not spec:
                print(f"  SKIP {mod}: no SPEC dict")
                continue
            p = ps.publish(spec, surface_root="/tmp/aeo_products")
            # push to container
            subprocess.run(["incus", "file", "push", "--recursive",
                            f"/tmp/aeo_products/products/{spec['sku']}",
                            "empire-hub", f"/srv/aeo/products/"],
                           capture_output=True, timeout=30)
            print(f"  OK {mod} -> /products/{spec['sku']}/ ({spec['name']})")
            ok += 1
        except Exception as e:
            print(f"  FAIL {mod}: {str(e)[:80]}")
    print(f"published {ok}/{len(MODULES)} product showcases")
    return ok

if __name__ == "__main__":
    main()
