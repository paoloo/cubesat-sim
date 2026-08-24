import json
import tempfile
import unittest
from pathlib import Path

from cubesec_sim.audit import audit_campaign
from cubesec_sim.campaign import factorial, run_campaign
from cubesec_sim.config import SimulationConfig
from cubesec_sim.quality import evaluate_quality
from cubesec_sim.report import export_report


class CampaignTests(unittest.TestCase):
    def test_design_sizes_are_explicit(self):
        self.assertEqual(len(factorial("smoke")), 1)
        self.assertEqual(len(factorial("quick")), 16)
        self.assertEqual(len(factorial("controls")), 4)
        self.assertEqual(len(factorial("stress")), 10)
        self.assertEqual(len(factorial("full")), 768)

    def test_smoke_campaign_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "campaign"
            summary = run_campaign(
                SimulationConfig(), output, profile="smoke", save_iq="all"
            )
            self.assertEqual(summary["record_count"], 2)
            lines = [
                json.loads(x) for x in (output / "runs.jsonl").read_text().splitlines()
            ]
            self.assertEqual(lines[0]["iq_sha256"], lines[1]["iq_sha256"])
            self.assertTrue(list((output / "iq").glob("*.c64")))
            self.assertTrue(audit_campaign(output)["ok"])
            quality = evaluate_quality(output)
            self.assertTrue(quality["ok"])
            report = export_report(output)
            self.assertEqual(
                report["campaign_manifest_sha256"],
                json.loads((output / "campaign.json").read_text())["manifest_sha256"],
            )
            self.assertTrue((output / "report" / "policy_table.tex").is_file())
            self.assertTrue(audit_campaign(output)["ok"])
            with self.assertRaises(FileExistsError):
                run_campaign(SimulationConfig(), output, profile="smoke")


if __name__ == "__main__":
    unittest.main()
