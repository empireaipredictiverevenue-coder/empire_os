"""ASTRA original first-party post-publication verification, NOT deployment.

Do not run this to seek permission; it runs only after the original release
owner has staged and authorised the exact noindex Chicago page.
"""
import argparse
import json
from pathlib import Path

from empire_os.microsite_original_release_readback_v15 import (
    verify_original_owner_site_readback,
)


def main() -> None:
    cli = argparse.ArgumentParser()
    cli.add_argument("--root", type=Path, default=Path("/srv/empire_os"))
    cli.add_argument("--output", type=Path)
    args = cli.parse_args()

    result = verify_original_owner_site_readback(args.root)
    body = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        # Private evidence only. Never mutate the website or original release.
        source = Path("/home/ubuntu/empire_releases").resolve()
        target = args.output.resolve()
        if (not target.is_relative_to(source)
                or target.is_symlink()
                or target.exists()):
            raise SystemExit("Refusing non-private or overwrite evidence path")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)
    print(body, end="")


if __name__ == "__main__":
    main()
