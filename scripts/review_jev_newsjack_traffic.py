"""Offline NewsJack/JEV evidence review: no provider activation or side effects."""
import argparse
import json
from pathlib import Path

from empire_os.jev_newsjack_traffic import review_newsjack_jev_traffic
from empire_os.jev_newsjack_adapters import (
    signals_from_last30days_agent_export,
    SearchIntelligenceLoopbackGSCReader,
    attach_gsc_query_page_observations,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--input-format', choices=['signal-packet', 'last30days-agent'],
                        default='signal-packet')
    parser.add_argument('--as-of', required=True)
    parser.add_argument('--sector', required=True, action='append')
    parser.add_argument('--market', required=True, action='append')
    parser.add_argument('--destination', action='append', default=[])
    parser.add_argument('--gsc-live', action='store_true',
                        help='Explicitly read existing localhost Search Intelligence GSC observations')
    parser.add_argument('--gsc-start')
    parser.add_argument('--gsc-end')
    parser.add_argument('--include-items', action='store_true')
    args = parser.parse_args()
    path = Path(args.input)
    if path.stat().st_size > 150000:
        parser.error('input too large')
    packet = json.loads(path.read_text(encoding='utf-8'))
    if args.input_format == 'last30days-agent':
        if len(args.sector) != 1 or len(args.market) != 1:
            parser.error('last30days export needs one market and one sector')
        packet = signals_from_last30days_agent_export(
            packet, sector=args.sector[0], market=args.market[0])
    if not isinstance(packet, dict) or not isinstance(packet.get('signals'), list):
        parser.error('expected object with signals array')
    gsc_receipt = None
    if args.gsc_live:
        if not (args.gsc_start and args.gsc_end):
            parser.error('--gsc-live requires --gsc-start and --gsc-end')
        signals = packet['signals']
        queries = {s['signal_id']: s['target_query'] for s in signals
                   if isinstance(s, dict) and isinstance(s.get('signal_id'), str)
                   and isinstance(s.get('target_query'), str)}
        destinations = {s['signal_id']: s['destination_url'] for s in signals
                        if isinstance(s, dict) and isinstance(s.get('signal_id'), str)
                        and isinstance(s.get('destination_url'), str)}
        gsc_receipt = attach_gsc_query_page_observations(
            signals, reader=SearchIntelligenceLoopbackGSCReader(),
            as_of=args.as_of, start_date=args.gsc_start, end_date=args.gsc_end,
            query_by_signal_id=queries, destination_by_signal_id=destinations,
            limit=50)
        packet['signals'] = gsc_receipt['signals']
    result = review_newsjack_jev_traffic(
        packet['signals'], as_of=args.as_of,
        approved_sectors=args.sector, approved_markets=args.market,
        approved_destination_urls=args.destination)
    if gsc_receipt is not None:
        result['gsc_queried'] = True
        result['gsc_rows_observed'] = gsc_receipt['gsc_rows_observed']
        result['gsc_exact_matches'] = gsc_receipt['exact_matches']
        result['news_attributed_clicks'] = None
    if not args.include_items:
        del result['candidates']
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
