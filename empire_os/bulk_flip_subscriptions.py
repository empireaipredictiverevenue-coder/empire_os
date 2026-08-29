#!/usr/bin/env python3
"""
Bulk-flip awaiting_payment si_subscription rows.

Two-stage sweep that consumes the real deposit ledger one-for-one:

  1. FLIP — for every awaiting_payment sub older than `STALE_DAYS` days, find
     one unused paid/succeeded si_charges row whose amount_cents matches
     the sub's price_cents. If found, mark the sub 'active' and record the
     charge_id in payment_ref so this deposit can never be reused for
     another sub. This is the same per-deposit consumption model
     /v1/finance/replay uses, but iterated against the existing
     si_charges ledger instead of a single new deposit.

  2. EXPIRE — for anything still awaiting_payment after step 1 AND created
     older than `STALE_DAYS` days, mark 'expired' with reason='no_payment_30d'.
     Anything recent (< STALE_DAYS) is left alone so /v1/finance/replay or
     the solana_listener can still pick it up on the next cycle.

Each deposit is consumed exactly once: we mark si_charges.payment_ref with
the matched subscription_id so a future run (or the live listener) won't
double-attribute it. The script is idempotent: re-running skips subs that
already left awaiting_payment and skips deposits that are already claimed.

Real money reality check (2026-07-29):
  si_charges has 14,857 succeeded charges at the two subscription price
  points ($299 + $599) — enough to back at most that many subscriptions.
  Anything beyond that gets expired, because there is no deposit on file
  to attribute.

Usage:
    python3 /root/empire_os/empire_os/bulk_flip_subscriptions.py
    python3 /root/empire_os/empire_os/bulk_flip_subscriptions.py --dry-run
    python3 /root/empire_os/empire_os/bulk_flip_subscriptions.py --stale-days 7
"""
import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

DB_PATH = os.environ.get(
    "EMPIRE_DB",
    "/root/empire_os/empire_os.db",
)
STALE_DAYS_DEFAULT = 7


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(level: str, msg: str, **fields):
    rec = {
        "ts": now_iso(),
        "level": level,
        "msg": msg,
        **fields,
    }
    print(json.dumps(rec), flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stale-days", type=int, default=STALE_DAYS_DEFAULT,
                    help=f"Sub older than this many days with no matching "
                         f"deposit gets expired (default {STALE_DAYS_DEFAULT}).")
    ap.add_argument("--dry-run", action="store_true",
                    help="Compute what would change but commit nothing.")
    ap.add_argument("--limit", type=int, default=0,
                    help="Max rows to process (0 = all).")
    args = ap.parse_args()

    log("INFO", "bulk_flip_start",
        db=DB_PATH, stale_days=args.stale_days, dry_run=args.dry_run,
        limit=args.limit)

    cnx = sqlite3.connect(DB_PATH, timeout=60)
    cnx.row_factory = sqlite3.Row
    cnx.execute("PRAGMA journal_mode=WAL")
    cnx.execute("PRAGMA synchronous=NORMAL")

    flipped_count = 0
    expired_count = 0
    skipped_recent = 0
    skipped_no_deposit = 0
    already_terminal = 0
    mrr_cents_realized = 0  # only counts subs that actually flipped

    try:
        # ── Step 1: collect awaiting_payment subs ──────────────────────────
        subs = cnx.execute(
            """
            SELECT subscription_id, tenant_id, plan, price_cents,
                   payment_ref, source, created_at
            FROM si_subscription
            WHERE status = 'awaiting_payment'
            ORDER BY created_at ASC
            """
        ).fetchall()

        if args.limit and len(subs) > args.limit:
            subs = subs[: args.limit]

        log("INFO", "awaiting_payment_loaded", total=len(subs))

        # ── Step 2: build deposit inventory ────────────────────────────────
        # We pull every paid/succeeded si_charges row that has not yet been
        # attributed to a si_subscription (payment_ref empty or not pointing
        # at any current sub). Index by amount_cents in a FIFO list so we
        # consume oldest deposits first.
        deposit_rows = cnx.execute(
            """
            SELECT ch.charge_id, ch.amount_cents,
                   COALESCE(ch.paid_at, ch.created_at) AS effective_at
            FROM si_charges ch
            WHERE ch.status IN ('paid', 'succeeded')
              AND (
                ch.payment_ref IS NULL OR ch.payment_ref = ''
                OR NOT EXISTS (
                    SELECT 1 FROM si_subscription s
                    WHERE s.subscription_id = ch.payment_ref
                )
              )
            ORDER BY COALESCE(ch.paid_at, ch.created_at) ASC, ch.id ASC
            """
        ).fetchall()

        # FIFO list of charge_ids per amount
        from collections import defaultdict
        deposit_pool = defaultdict(list)
        for r in deposit_rows:
            deposit_pool[r["amount_cents"]].append(r["charge_id"])

        log("INFO", "deposits_indexed",
            distinct_amounts=len(deposit_pool),
            deposit_count_total=sum(len(v) for v in deposit_pool.values()),
            awaiting_by_amount={
                int(pc): int(n) for pc, n in cnx.execute(
                    "SELECT price_cents, COUNT(*) FROM si_subscription "
                    "WHERE status='awaiting_payment' GROUP BY price_cents"
                ).fetchall()
            })

        # ── Step 3: iterate subs ───────────────────────────────────────────
        flipped_by_amount = defaultdict(int)

        for sub in subs:
            sid = sub["subscription_id"]
            price = sub["price_cents"]
            created_at = sub["created_at"]
            plan = sub["plan"] or ""

            # Re-check status under a fresh transaction. Another worker may
            # have flipped it while we iterated.
            cur_status = cnx.execute(
                "SELECT status FROM si_subscription WHERE subscription_id=?",
                (sid,),
            ).fetchone()
            if cur_status is None:
                continue
            if cur_status["status"] != "awaiting_payment":
                already_terminal += 1
                continue

            # Compute age in days. SQLite stores 'YYYY-MM-DD HH:MM:SS'.
            try:
                created_dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    created_dt = datetime.strptime(created_at[:10], "%Y-%m-%d")
                except ValueError:
                    log("WARN", "bad_created_at", subscription_id=sid,
                        created_at=created_at)
                    continue
            age_days = (datetime.now(timezone.utc).replace(tzinfo=None) - created_dt).days

            if age_days < args.stale_days:
                # Recent: leave alone so listener / replay can match a
                # future deposit.
                skipped_recent += 1
                continue

            # Try to claim one deposit for this sub.
            claimed_charge_id = None
            pool = deposit_pool.get(price) or []
            if pool:
                claimed_charge_id = pool.pop(0)

            if claimed_charge_id:
                # ── FLIP: real deposit exists ─────────────────────────────
                if not args.dry_run:
                    cnx.execute(
                        "UPDATE si_charges SET payment_ref = ? "
                        "WHERE charge_id = ?",
                        (sid, claimed_charge_id),
                    )
                    cnx.execute(
                        """
                        UPDATE si_subscription
                        SET status = 'active',
                            payment_ref = ?
                        WHERE subscription_id = ?
                          AND status = 'awaiting_payment'
                        """,
                        (f"deposit:{claimed_charge_id}", sid),
                    )
                flipped_count += 1
                flipped_by_amount[price] += 1
                mrr_cents_realized += int(price)
                log("DEBUG", "flipped", subscription_id=sid, plan=plan,
                    price_cents=price, age_days=age_days,
                    charge_id=claimed_charge_id)
            else:
                # No deposit available — this sub is stale AND unfunded.
                # Expire it so it stops cluttering the funnel.
                if not args.dry_run:
                    cnx.execute(
                        """
                        UPDATE si_subscription
                        SET status = 'expired',
                            payment_ref = COALESCE(payment_ref, '') || ?
                        WHERE subscription_id = ?
                          AND status = 'awaiting_payment'
                        """,
                        (f" | expired:no_payment_30d", sid),
                    )
                expired_count += 1
                log("DEBUG", "expired", subscription_id=sid, plan=plan,
                    price_cents=price, age_days=age_days)

        if not args.dry_run:
            cnx.commit()

        # ── Step 4: post-state ─────────────────────────────────────────────
        post = {
            r["status"]: r["n"]
            for r in cnx.execute(
                "SELECT status, COUNT(*) AS n "
                "FROM si_subscription GROUP BY status ORDER BY status"
            ).fetchall()
        }
        remaining_awaiting = post.get("awaiting_payment", 0)

        summary = {
            "ok": True,
            "dry_run": args.dry_run,
            "stale_days_threshold": args.stale_days,
            "considered": len(subs),
            "flipped_count": flipped_count,
            "expired_count": expired_count,
            "skipped_recent": skipped_recent,
            "skipped_no_deposit_kept": skipped_no_deposit,
            "already_terminal_skipped": already_terminal,
            "remaining_awaiting": remaining_awaiting,
            "post_state": post,
            "mrr_cents_realized": mrr_cents_realized,
            "mrr_usdc_realized": mrr_cents_realized / 100.0,
        }
        log("INFO", "bulk_flip_done", **summary)

        return 0

    except Exception as e:
        log("ERROR", "bulk_flip_failed", err=str(e)[:400])
        cnx.rollback()
        return 1
    finally:
        cnx.close()


if __name__ == "__main__":
    sys.exit(main())