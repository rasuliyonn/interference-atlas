import json
import os
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ElementTree

from atlas.graph import plan_channels
from atlas.plan import demo_plan, plan_from_dict
from atlas.render import ascii_map, render_svg


class RenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = demo_plan()
        cls.result = plan_channels(cls.plan.environment, cls.plan.transmitters)

    def test_ascii_map_has_one_line_per_row_and_tower_markers(self):
        text = ascii_map(
            self.plan.environment,
            self.result["channels"],
            self.plan.transmitters,
            self.plan.width_m,
            self.plan.height_m,
            columns=40,
            rows=12,
        )
        rows = [line for line in text.splitlines() if line and not line.startswith("legend")]
        self.assertEqual(len(rows), 12)
        map_body = text.split("\n\n")[0]
        self.assertEqual(map_body.count("@"), len(self.plan.transmitters))
        self.assertIn("legend", text)

    def test_svg_is_well_formed_and_contains_every_cell(self):
        svg = render_svg(
            self.plan.environment,
            self.result["channels"],
            self.plan.transmitters,
            self.plan.width_m,
            self.plan.height_m,
            columns=20,
            rows=10,
            cell=10,
        )
        root = ElementTree.fromstring(svg.split("\n", 1)[1])
        self.assertTrue(root.tag.endswith("svg"))
        rectangles = [node for node in root.iter() if node.tag.endswith("rect")]
        self.assertEqual(len(rectangles), 20 * 10 + 4 + 1)
        circles = [node for node in root.iter() if node.tag.endswith("circle")]
        self.assertEqual(len(circles), len(self.plan.transmitters))

    def test_svg_reports_channel_count_and_colours(self):
        svg = render_svg(
            self.plan.environment,
            self.result["channels"],
            self.plan.transmitters,
            self.plan.width_m,
            self.plan.height_m,
            columns=12,
            rows=8,
            cell=8,
        )
        self.assertIn("%d channels" % self.result["channel_count"], svg)
        self.assertIn("#1f9d55", svg)
        self.assertIn("#4b5563", svg)


class CliTests(unittest.TestCase):
    def test_demo_command_writes_all_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            svg_path = os.path.join(directory, "coverage.svg")
            json_path = os.path.join(directory, "report.json")
            env = dict(os.environ)
            env["PYTHONPATH"] = os.getcwd()
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "atlas.cli",
                    "demo",
                    "--svg",
                    svg_path,
                    "--json-out",
                    json_path,
                    "--columns",
                    "16",
                    "--rows",
                    "8",
                ],
                cwd=os.getcwd(),
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("Channels:", completed.stdout)
            with open(json_path, encoding="utf-8") as handle:
                payload = json.load(handle)
            self.assertGreaterEqual(payload["channel_count"], payload["lower_bound"])
            self.assertTrue(os.path.getsize(svg_path) > 1000)


class PlanValidationTests(unittest.TestCase):
    def test_duplicate_names_are_rejected(self):
        payload = {
            "width_m": 1000,
            "height_m": 1000,
            "transmitters": [
                {"name": "A", "x": 10, "y": 10},
                {"name": "A", "x": 20, "y": 20},
            ],
        }
        with self.assertRaises(ValueError):
            plan_from_dict(payload)

    def test_out_of_area_site_is_rejected(self):
        payload = {
            "width_m": 100,
            "height_m": 100,
            "transmitters": [{"name": "A", "x": 500, "y": 10}],
        }
        with self.assertRaises(ValueError):
            plan_from_dict(payload)


if __name__ == "__main__":
    unittest.main()
