"""Offline NewsJack/JEV evidence review: no provider activation or side effects."""
import argparse
import json
from pathlib import Path

from empire_os.jev_newsjack_traffic import review_newsjack_jev_traffic


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--as-of', required=True)
    parser.add_argument('--sector', required=True, action='append')
    parser.add_argument('--market', required=True, action='append')
    parser.add_argument('--destination', action='append', default=[])
    parser.add_argument('--include-items', action='store_true')
    args = parser.parse_args()
    path = Path(args.input)
    if path.stat().st_size > 150000:
        parser.error('input too large')
    packet = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(packet, dict) or not isinstance(packet.get('signals'), list):
        parser.error('expected object with signals array')
    result = review_newsjack_jev_traffic(
        packet['signals'], as_of=args.as_of,
        approved_sectors=args.sector, approved_markets=args.market,
        approved_destination_urls=args.destination)
    if not args.include_items:
        del result['candidates']
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
