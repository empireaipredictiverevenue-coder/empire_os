"""Smoke tests for the branded email template system.

Run:
    cd /root/empire_os
    python3 -m empire_os.templates.email.tests
"""
from __future__ import annotations

import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path

# Make sure we can import the package from the host
sys.path.insert(0, "/root/empire_os")

from empire_os.templates.email import (
    render, render_subject, list_all, list_outreach, list_internal,
    avenue_ids, get_avenue, AVENUES,
    NEON_GREEN, CYAN, COMPANY_URL,
)


class _SafeHTMLParser(HTMLParser):
    """Lightweight HTML validator. Tracks balanced tags, no external deps."""

    VOID = {"br", "hr", "img", "meta", "link", "input", "area", "base", "col", "embed", "source", "track", "wbr"}

    def __init__(self):
        super().__init__()
        self.stack: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if not self.stack:
            self.errors.append(f"closing </{tag}> with empty stack")
            return
        if self.stack[-1] != tag:
            self.errors.append(f"mismatched </{tag}>, expected </{self.stack[-1]}>")
            return
        self.stack.pop()


class TestBrand(unittest.TestCase):

    def test_brand_palette_present(self):
        # Sanity: brand strings are well-formed hex
        for color in (NEON_GREEN, CYAN):
            self.assertRegex(color, r"^#[0-9a-fA-F]{6}$", f"bad hex: {color}")

    def test_avenues_registered(self):
        ids = avenue_ids()
        self.assertIn("leadgen", ids)
        self.assertIn("paypercall", ids)
        self.assertIn("default", ids)
        for aid in ids:
            a = get_avenue(aid)
            self.assertIn("name", a)
            self.assertIn("tagline", a)
            self.assertIn("accent", a)
            self.assertIn("primary_cta", a)

    def test_unknown_avenue_falls_back(self):
        # None or unknown id both resolve to DEFAULT_AVENUE (leadgen).
        # The "default" avenue key in the registry exists for explicit
        # naming when callers want to opt out of an active campaign.
        self.assertEqual(get_avenue(None)["id"], "leadgen")
        self.assertEqual(get_avenue("does_not_exist")["id"], "leadgen")
        # Explicit "default" avenue id IS reachable directly:
        self.assertEqual(get_avenue("default")["id"], "default")

    def test_company_constants(self):
        self.assertTrue(COMPANY_URL.startswith("https://"))
        self.assertIn("empire-ai", COMPANY_URL)


class TestTemplates(unittest.TestCase):

    def _vars(self, **overrides):
        base = {
            "recipient_name": "Sarah",
            "niche": "roofing",
            "metro": "Dallas, TX",
            "source_detail": "23 verified reviews",
            "avenue_id": "leadgen",
            "tenant_id": "test-tenant",
        }
        base.update(overrides)
        return base

    def test_all_templates_render(self):
        # Outreach — lead_id not used, skip
        for tpl in list_outreach():
            for avenue in ("leadgen", "paypercall", "saas", "loans", "default"):
                html, text = render(tpl, self._vars(avenue_id=avenue))
                self.assertTrue(html.lstrip().startswith("<!DOCTYPE"), f"{tpl}/{avenue}: not HTML")
                self.assertGreater(len(html), 1000, f"{tpl}/{avenue}: too short")
                self.assertGreater(len(text), 100, f"{tpl}/{avenue}: text too short")
                self.assertIn("Unsubscribe", text, f"{tpl}/{avenue}: no unsub in text")
                self.assertIn("empire-ai.co.uk", text, f"{tpl}/{avenue}: no url in text")

        # Internal — each template uses different vars
        internal_vars = {
            "lead_delivered":  {"lead_id": "lead_abc123"},
            "payout_settled":  {"amount": "$1,234.56", "tx_id": "0xDEAD"},
        }
        for tpl, extra in internal_vars.items():
            html, text = render(tpl, {**self._vars(), **extra})
            self.assertTrue(html.lstrip().startswith("<!DOCTYPE"), f"{tpl}: not HTML")
            for k, v in extra.items():
                self.assertIn(v, text, f"{tpl}: missing {k}={v}")

    def test_subject_renders(self):
        for tpl in list_outreach():
            subj = render_subject(tpl, self._vars())
            self.assertGreater(len(subj), 5)
            self.assertNotIn("{}", subj, f"{tpl}: unfilled placeholder in subject")
            self.assertNotIn("None", subj, f"{tpl}: None in subject")

        self.assertIn("[Empire OS]", render_subject("lead_delivered", self._vars()))
        self.assertIn("[Empire OS]", render_subject("payout_settled", self._vars(amount="$500")))

    def test_paypercall_subject_prefix(self):
        subj = render_subject("outreach_first_touch", self._vars(avenue_id="paypercall"))
        self.assertTrue(subj.startswith("[PPC] "), f"missing PPC prefix: {subj}")

    def test_html_balanced(self):
        # Every template should produce parseable balanced HTML
        for tpl in list_all():
            html, _ = render(tpl, self._vars(
                lead_id="L1", amount="$1", tx_id="0xABC",
            ))
            p = _SafeHTMLParser()
            p.feed(html)
            self.assertFalse(p.stack, f"{tpl}: unclosed tags: {p.stack}")
            self.assertFalse(p.errors, f"{tpl}: HTML errors: {p.errors[:3]}")

    def test_xss_escapes_recipient_name(self):
        nasty = '<script>alert("xss")</script>Sarah'
        html, _ = render("outreach_first_touch", self._vars(recipient_name=nasty))
        self.assertNotIn("<script>alert", html, "recipient_name not escaped!")
        self.assertIn("&lt;script&gt;", html, "expected HTML entity escaping")

    def test_brand_color_present_in_html(self):
        html, _ = render("outreach_first_touch", self._vars(avenue_id="leadgen"))
        self.assertIn(NEON_GREEN.lower(), html.lower())

    def test_avenue_swap_changes_accent(self):
        html_leadgen, _ = render("outreach_first_touch", self._vars(avenue_id="leadgen"))
        html_saas, _ = render("outreach_first_touch", self._vars(avenue_id="saas"))
        # leadgen accent = neon green, saas accent = cyan
        self.assertIn("#39ff88", html_leadgen.lower())
        self.assertIn("#22e3ff", html_saas.lower())
        # saas should have cyan button bg, leadgen should have green button bg
        self.assertIn('background:#22e3ff', html_saas)
        self.assertIn('background:#39ff88', html_leadgen)


def run():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestBrand))
    suite.addTests(loader.loadTestsFromTestCase(TestTemplates))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run())