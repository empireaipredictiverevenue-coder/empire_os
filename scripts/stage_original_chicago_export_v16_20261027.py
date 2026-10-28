"""One private, hash-pinned ASTRA Chicago website export for owner review.

NEVER deploys, authorises SEO, publishes branding or rewrites live routes.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from empire_os.microsite_original_site_export_v16 import prepare_chicago_original_owner_export


def main() -> None:
    p=argparse.ArgumentParser(description="Stage one original website review candidate")
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--private-dir", type=Path, required=True)
    args=p.parse_args()
    root=Path("/home/ubuntu/empire_releases").resolve()
    stage=args.private_dir.resolve()
    src=args.source.resolve()
    if (not stage.is_relative_to(root) or src.is_symlink()
            or stage.is_relative_to(Path("/srv/empire_os").resolve())
            or stage.exists()):
        raise SystemExit("Refusing non-private/symlink/overwrite export target")
    raw, receipt=prepare_chicago_original_owner_export(src.read_bytes())
    stage.mkdir(parents=True,mode=0o700)
    page=stage/"chicago_owner_review_export.html"
    page.write_bytes(raw)
    receipt["staged_html_path"]=str(page)
    receipt["private_review_only"]=True
    packet=stage/"owner_export_receipt.json"
    packet.write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n")
    if sha256(page.read_bytes()).hexdigest() != receipt["owner_reviewed_html_sha256"]:
        raise SystemExit("Staged HTML digest readback failed")
    print(json.dumps(receipt,sort_keys=True))


if __name__=="__main__":
    main()
