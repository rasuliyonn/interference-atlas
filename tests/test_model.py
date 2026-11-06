import math
import unittest

from atlas.model import (
    Environment,
    Transmitter,
    bearing_deg,
    coverage_grid,
    distance_m,
    evaluate_link,
    free_space_loss_db,
    noise_floor_dbm,
    summarize_coverage,
)


def tower(name, x, y, power=30.0, gain=10.0):
    return Transmitter(name=name, x=x, y=y, power_dbm=power, gain_dbi=gain)


class PropagationTests(unittest.TestCase):
    def test_free_space_loss_reference_point(self):
        # 1 km at 900 MHz is the classic 91.5 dB reference.
        self.assertAlmostEqual(free_space_loss_db(1000, 900), 91.52, places=2)

    def test_free_space_loss_is_monotonic(self):
        losses = [free_space_loss_db(d, 2400) for d in (10, 100, 1000, 10000)]
        self.assertEqual(losses, sorted(losses))
        self.assertGreater(losses[-1], losses[0] + 50)

    def test_noise_floor_uses_bandwidth_and_figure(self):
        # -174 dBm/Hz + 53.01 dB (200 kHz) + 7 dB NF
        self.assertAlmostEqual(noise_floor_dbm(200_000, 7.0), -113.99, places=2)

    def test_received_power_falls_with_distance(self):
        env = Environment(model="free-space")
        site = tower("A", 0, 0)
        near = env.rx_power_dbm(site, 100, 0)
        far = env.rx_power_dbm(site, 5000, 0)
        self.assertGreater(near, far)
        self.assertAlmostEqual(near - far, 20 * math.log10(50), places=6)

    def test_unknown_model_is_rejected(self):
        with self.assertRaises(ValueError):
            Environment(model="ray-tracing").path_loss_db(100)

    def test_distance_and_bearing(self):
        a, b = tower("A", 0, 0), tower("B", 100, 100)
        self.assertAlmostEqual(distance_m(a, b), math.hypot(100, 100))
        self.assertAlmostEqual(bearing_deg(a, b), 45.0, places=6)
        self.assertAlmostEqual(bearing_deg(b, a), 225.0, places=6)


class SinrTests(unittest.TestCase):
    def setUp(self):
        self.env = Environment(model="free-space", frequency_mhz=900)
        self.alpha = tower("Alpha", 0, 0, power=36)
        self.beta = tower("Beta", 600, 0, power=36)

    def test_single_transmitter_is_noise_limited(self):
        link = evaluate_link(self.env, {"Alpha": 0}, 50, 0, [self.alpha])
        self.assertEqual(link.serving, "Alpha")
        self.assertEqual(link.quality, "great")
        self.assertAlmostEqual(link.sinr_db, link.signal_dbm - link.noise_dbm, places=6)
        self.assertEqual(link.interferers, ())

    def test_co_channel_interference_reduces_sinr(self):
        shared = evaluate_link(self.env, {"Alpha": 0, "Beta": 0}, 300, 0, [self.alpha, self.beta])
        separated = evaluate_link(self.env, {"Alpha": 0, "Beta": 3}, 300, 0, [self.alpha, self.beta])
        self.assertLess(shared.sinr_db, separated.sinr_db)
        self.assertTrue(shared.interferers)
        self.assertEqual(shared.serving, "Alpha")

    def test_adjacent_channel_isolation_is_applied(self):
        adjacent = evaluate_link(self.env, {"Alpha": 0, "Beta": 1}, 300, 0, [self.alpha, self.beta])
        self.assertAlmostEqual(
            adjacent.interferers[0][1],
            self.env.rx_power_dbm(self.beta, 300, 0) - self.env.adjacency_isolation_db,
            places=6,
        )

    def test_far_away_site_does_not_dominate(self):
        distant = tower("Far", 50_000, 0)
        link = evaluate_link(self.env, {"Alpha": 0, "Far": 0}, 10, 0, [self.alpha, distant])
        self.assertEqual(link.serving, "Alpha")

    def test_empty_transmitter_list_is_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_link(self.env, {}, 0, 0, [])


class CoverageTests(unittest.TestCase):
    def test_grid_shape_and_summary(self):
        env = Environment(model="log-distance")
        sites = [tower("A", 0, 0), tower("B", 1000, 0)]
        cells = coverage_grid(env, {"A": 0, "B": 1}, sites, 2000, 1000, columns=10, rows=5)
        self.assertEqual(len(cells), 50)
        summary = summarize_coverage(cells)
        total = summary["great"] + summary["good"] + summary["fair"] + summary["outage"]
        self.assertAlmostEqual(total, 100.0, places=6)
        self.assertEqual(summary["cell_count"], 50)
        self.assertLessEqual(summary["p10_sinr_db"], summary["mean_sinr_db"])

    def test_grid_rejects_empty_resolution(self):
        env = Environment()
        with self.assertRaises(ValueError):
            coverage_grid(env, {"A": 0}, [tower("A", 0, 0)], 100, 100, columns=0, rows=4)


if __name__ == "__main__":
    unittest.main()
