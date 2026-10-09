"""Manual, observe-only exporter of buyer research into private OKF v0.2."""
from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path
import json

from empire_os.okf_adapter import export_private_bundle, catalogue_summary


def main() -> int:
    p = ArgumentParser()
    p.add_argument("--scout-receipt", type=Path, required=True)
    p.add_argument("--output-root", type=Path, required=True)
    p.add_argument("--max-records", type=int, default=30)
    args = p.parse_args()
    result = export_private_bundle(
        args.scout_receipt, args.output_root,
        now=datetime.now(timezone.utc), limit=args.max_records,
    )
    result["advisory_catalogue"] = catalogue_summary(Path(result["bundle_path"]))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
