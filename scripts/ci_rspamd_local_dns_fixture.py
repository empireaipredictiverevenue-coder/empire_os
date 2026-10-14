"""Disposable DNS-authoritative fixture for Rspamd's real auth modules.

NETWORK-NONE container ONLY: binds 127.0.0.1:5353, answers only
reserved fixture domains; never forwards queries or changes production DNS.
No real DKIM keys: generated ephemeral container-only for test.
"""
from __future__ import annotations

import argparse
import base64
from pathlib import Path
import sys

from dnslib import DNSRecord, QTYPE, RR, TXT, RCODE, A
from dnslib.server import BaseResolver, DNSServer

GOOD = "verified.receiver.test."
BAD = "forged.receiver.test."
SELECTOR = "s1._domainkey.verified.receiver.test."
MAX_TXT = 255


class FixtureResolver(BaseResolver):
    def __init__(self, public_key_der: bytes):
        if len(public_key_der) < 100:
            raise ValueError("bounded RSA public key required")
        self.public_key = base64.b64encode(public_key_der).decode("ascii")

    def resolve(self, request: DNSRecord, handler):
        reply = request.reply()
        query = request.q
        name = str(query.qname).lower()
        rtype = QTYPE[query.qtype]
        records = {
            (GOOD, "TXT"): "v=spf1 ip4:127.0.0.1 -all",
            (BAD, "TXT"): "v=spf1 -all",
            ("_dmarc." + GOOD, "TXT"): "v=DMARC1; p=reject; adkim=s; aspf=s",
            ("_dmarc." + BAD, "TXT"): "v=DMARC1; p=none; adkim=s; aspf=s",
            (SELECTOR, "TXT"): f"v=DKIM1; k=rsa; p={self.public_key}",
        }
        txt = records.get((name, rtype))
        if txt:
            # dnslib TXT accepts a list of <=255-octet chunks; DNS TXT
            # may contain a multi-string logical single record (DKIM key).
            chunks = [txt[n:n+MAX_TXT] for n in range(0,len(txt),MAX_TXT)]
            reply.add_answer(RR(query.qname, QTYPE.TXT, ttl=30, rdata=TXT(chunks)))
        elif name in (GOOD, BAD) and rtype == "A":
            reply.add_answer(RR(query.qname, QTYPE.A, ttl=30, rdata=A("127.0.0.1")))
        else:
            reply.header.rcode = RCODE.NXDOMAIN
        return reply


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--serve-ci-fixture",action="store_true")
    p.add_argument("--public-der",type=Path)
    a=p.parse_args(argv)
    if not a.serve_ci_fixture or a.public_der is None:
        print("FIXTURE_DNS_NOT_REQUESTED")
        return 0
    if a.public_der.is_symlink() or not a.public_der.is_file():
        raise ValueError("owner generated RSA public fixture file required")
    public = a.public_der.read_bytes()
    server = DNSServer(FixtureResolver(public), port=5353, address="127.0.0.1", tcp=False)
    server.start_thread()
    print("OFFLINE_AUTHORITATIVE_DNS_FIXTURE_ACTIVE",flush=True)
    import time
    while True: time.sleep(10)


if __name__=="__main__":
    raise SystemExit(main())
