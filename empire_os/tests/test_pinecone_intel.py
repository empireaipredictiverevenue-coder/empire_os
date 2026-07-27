#!/usr/bin/env python3
"""
test_pinecone_intel.py — unit tests for the business-layer functions.

Mocks the PineconeClient and verifies the right MCP arguments are built
for each operation, and that result shaping is correct.
"""
from __future__ import annotations

import json
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, "/root/empire_os")

from empire_os import pinecone_intel
from empire_os.pinecone_config import PinconeConfig


def _client():
    c = MagicMock()
    c.config = PinconeConfig(
        api_key="pcsk_x", index="empire-leads", cloud="aws", region="us-east-1",
        embed_model="llama-text-embed-v2", dimension=1024,
    )
    return c


def _wrap(payload: dict) -> dict:
    """MCP wraps tool results in content[0].text."""
    return {"content": [{"type": "text", "text": json.dumps(payload)}]}


class TestUpsertLead(unittest.TestCase):

    def test_builds_upsert_records_with_text(self):
        client = _client()
        client.call.return_value = _wrap({"result": {"upsertedCount": 1}})
        result = pinecone_intel.upsert_lead(42, {
            "niche": "roofing", "sub_niche": "residential", "metro": "Austin",
            "omega_tier": "T1", "omega_score": 87, "predicted_revenue": 1200,
        }, client=client, namespace="leads")
        self.assertTrue(result)
        method, params = client.call.call_args.args
        self.assertEqual(method, "tools/call")
        # The outer "name" is the MCP tool name, the inner "arguments.name" is the index.
        self.assertEqual(params["name"], "upsert-records")
        args = params["arguments"]
        self.assertEqual(args["name"], "empire-leads")  # index name (MCP field)
        self.assertEqual(args["namespace"], "leads")
        self.assertEqual(args["records"][0]["_id"], "lead_42")
        self.assertIn("roofing", args["records"][0]["text"])
        self.assertEqual(args["records"][0]["omega_score"], 87)


class TestFindSimilar(unittest.TestCase):

    def test_uses_search_records_with_topK(self):
        client = _client()
        client.call.return_value = _wrap({"result": {"hits": [
            {"_id": "buyer_b1", "score": 0.91, "metadata": {
                "buyer_id": "b1", "niche": "roofing", "metro": "Austin",
                "payout_per_lead": 25,
            }},
        ]}})
        results = pinecone_intel.find_similar_buyers(
            {"niche": "roofing", "metro": "Austin"}, client=client, top_k=5,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["buyer_id"], "b1")
        method, params = client.call.call_args.args
        args = params["arguments"]
        # Critical: camelCase MCP arg name, not top_k
        self.assertIn("topK", args["query"])
        self.assertEqual(args["query"]["topK"], 5)
        # Text starts with the lead's niche+metro (extra fields are allowed)
        self.assertTrue(args["query"]["inputs"]["text"].startswith("roofing | Austin"))
        self.assertTrue(args["includeMetadata"])

    def test_no_snake_case_in_args(self):
        """Regression: old code passed top_k, include_metadata, index=."""
        client = _client()
        client.call.return_value = _wrap({"result": {"hits": []}})
        pinecone_intel.find_similar_leads({"niche": "x"}, client=client)
        method, params = client.call.call_args.args
        args = params["arguments"]
        self.assertNotIn("top_k", args)
        self.assertNotIn("include_metadata", args)
        self.assertNotIn("index", args)
        self.assertEqual(args["name"], "empire-leads")  # MCP wants "name"


class TestSemanticMatch(unittest.TestCase):

    def test_ranks_by_combined_score(self):
        client = _client()
        client.call.return_value = _wrap({"result": {"hits": [
            {"_id": "bA", "score": 0.5, "metadata": {
                "buyer_id": "A", "niche": "plumbing", "metro": "Dallas",
                "payout_per_lead": 10,
            }},
            {"_id": "bB", "score": 0.5, "metadata": {
                "buyer_id": "B", "niche": "roofing", "metro": "Austin",
                "payout_per_lead": 30,
            }},
        ]}})
        best = pinecone_intel.semantic_buyer_match(
            {"niche": "roofing", "metro": "Austin"}, client=client,
        )
        # B matches both niche + metro + has higher payout
        self.assertEqual(best["buyer_id"], "B")

    def test_returns_none_when_no_candidates(self):
        client = _client()
        client.call.return_value = _wrap({"result": {"hits": []}})
        self.assertIsNone(pinecone_intel.semantic_buyer_match(
            {"niche": "x"}, client=client))


class TestBootstrap(unittest.TestCase):

    def test_no_op_when_index_exists(self):
        client = _client()
        client.call.return_value = _wrap({"dimension": 1024})
        # Should not call create-index-for-model at all
        self.assertTrue(pinecone_intel.bootstrap_index(client=client))
        methods = [c.args[1]["name"] for c in client.call.call_args_list]
        self.assertNotIn("create-index-for-model", methods)

    def test_creates_when_missing(self):
        from empire_os.pinecone_client import PineconeNotFoundError

        client = _client()
        # First call: describe raises NotFound. Second: create returns ok.
        client.call.side_effect = [
            PineconeNotFoundError("not found", tool="describe-index-stats"),
            _wrap({"name": "empire-leads"}),
        ]
        self.assertTrue(pinecone_intel.bootstrap_index(client=client))
        methods = [c.args[1]["name"] for c in client.call.call_args_list]
        self.assertIn("create-index-for-model", methods)
        # And the create call must use the right shape
        create_call = [c for c in client.call.call_args_list
                       if c.args[1].get("name") == "create-index-for-model"][0]
        body = create_call.args[1]["arguments"]
        self.assertEqual(body["embed"]["model"], "llama-text-embed-v2")
        self.assertIn("fieldMap", body["embed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
