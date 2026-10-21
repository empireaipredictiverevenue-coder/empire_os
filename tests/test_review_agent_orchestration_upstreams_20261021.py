"""Synthetic fail-closed tests. Never starts an external agent runtime."""
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/review_agent_orchestration_upstreams_20261021.py"
spec = importlib.util.spec_from_file_location("agent_upstream_review", SCRIPT)
mod = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class StaticUpstreamReviewTests(unittest.TestCase):
    def test_all_sources_have_full_pins_and_unique_names(self):
        self.assertEqual(len(mod.SOURCES), 5)
        self.assertEqual(len({source.slug for source in mod.SOURCES}), 5)
        for source in mod.SOURCES:
            self.assertEqual(len(source.pinned_head), 40)
            self.assertIn(source.licence, ("MIT", "Apache-2.0"))

    def test_unknown_ai_template_identity_is_not_assumed(self):
        templates = [s for s in mod.SOURCES if "template" in s.slug]
        self.assertEqual(len(templates), 2)
        self.assertTrue(all(not s.identity_confirmed for s in templates))

    def test_missing_upstream_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            result = mod.source_inventory(Path(temp), mod.SOURCES[0])
            self.assertFalse(result["clone_present"])
            self.assertFalse(result["ready_to_install"])
            self.assertFalse(result["pin_verified"])
            self.assertIn("clone_missing", result["issues"])

    def test_fake_git_directory_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / mod.SOURCES[0].slug
            (folder / ".git").mkdir(parents=True)
            result = mod.source_inventory(Path(temp), mod.SOURCES[0])
            self.assertFalse(result["pin_verified"])
            self.assertFalse(result["ready_to_install"])

    def test_different_commit_is_rejected_even_with_readme(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "paperclip"
            folder.mkdir()
            subprocess.run(["git", "init", "-q", str(folder)], check=True)
            (folder / "README.md").write_text("org chart budgets heartbeats approval")
            subprocess.run(["git", "-C", str(folder), "-c", "user.email=test@example.invalid",
                "-c", "user.name=Offline Test", "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(folder), "-c", "user.email=test@example.invalid",
                "-c", "user.name=Offline Test", "commit", "-qm", "local test"], check=True)
            result = mod.source_inventory(Path(temp), mod.SOURCES[0])
            self.assertFalse(result["pin_verified"])
            self.assertIn("upstream_pin_mismatch", result["issues"])

    def test_no_empire_or_upstream_root_can_grant_release(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = mod.audit(root / "empire", root / "sources")
            self.assertEqual(result["mode"], "OBSERVE")
            self.assertEqual(result["execution_authority"], "none")
            for flag in ("release_allowed", "external_software_installed",
                         "production_services_changed", "third_party_code_executed",
                         "production_queue_or_db_modified"):
                self.assertFalse(result[flag])
            self.assertFalse(result["all_source_pins_verified"])
            self.assertFalse(result["all_expected_local_controls_present"])

    def test_source_is_a_readonly_review_not_dispatcher(self):
        source = SCRIPT.read_text()
        self.assertNotIn("import requests", source)
        self.assertNotIn("import docker", source)
        self.assertNotIn("DepartmentWorkQueue(", source)
        self.assertNotIn("systemctl", source)
        self.assertNotIn("subprocess.Popen", source)


if __name__ == "__main__":
    unittest.main()
