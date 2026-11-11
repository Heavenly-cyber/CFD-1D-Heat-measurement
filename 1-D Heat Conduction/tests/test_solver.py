"""Numerical and end-to-end checks for the heat conduction assignment."""
import csv
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from openpyxl import load_workbook

from solver import ConvergenceError, solve_heat

PROJECT = Path(__file__).resolve().parents[1]


class NumericalTests(unittest.TestCase):
    def test_boundaries_and_sizes(self):
        result = solve_heat()
        self.assertEqual(len(result.x), 21)
        self.assertEqual(len(result.temperature), 21)
        self.assertEqual(len(result.analytical), 21)
        self.assertEqual(result.temperature[0], 300.0)
        self.assertEqual(result.temperature[-1], 1000.0)
        self.assertEqual(result.x[0], 0.0)
        self.assertEqual(result.x[-1], 1.0)
        self.assertTrue(np.isfinite(result.temperature).all())
        self.assertLessEqual(result.updates[-1], result.tolerance)
        self.assertLessEqual(result.unscaled_residual, 2 * result.tolerance)
        self.assertTrue(math.isfinite(result.pde_residual))
        self.assertLessEqual(np.max(np.abs(result.temperature-result.analytical)), 1e-6)

    def test_minimum_three_points(self):
        result = solve_heat(n=3)
        np.testing.assert_allclose(result.temperature, [300, 650, 1000], atol=1e-9, rtol=0)
        self.assertEqual(result.iterations, 2)

    def test_five_point_analytical_values(self):
        result = solve_heat(n=5, length=2.0)
        np.testing.assert_allclose(result.x, [0, 0.5, 1, 1.5, 2], atol=0, rtol=0)
        np.testing.assert_allclose(result.temperature, [300, 475, 650, 825, 1000], atol=1e-8, rtol=0)

    def test_invalid_inputs(self):
        for kwargs in ({"n": 2}, {"n": 3.5}, {"length": 0}, {"length": -1},
                       {"length": float("nan")}, {"tolerance": 0}, {"tolerance": float("inf")},
                       {"max_iterations": 0}, {"length": 1e-300}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                solve_heat(**kwargs)

    def test_nonconvergence_is_an_error(self):
        with self.assertRaises(ConvergenceError):
            solve_heat(max_iterations=1)


class IntegrationTests(unittest.TestCase):
    def test_cli_outputs_and_independent_audit(self):
        with tempfile.TemporaryDirectory(prefix="cfd-heat-test-") as tmp:
            out = Path(tmp) / "out"
            command = [sys.executable, str(PROJECT / "solver.py"), "--n", "5", "--length", "2",
                       "--output-dir", str(out)]
            completed = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            with (out / "temperature.csv").open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 5)
            self.assertEqual(float(rows[0]["numerical_temperature_K"]), 300.0)
            self.assertEqual(float(rows[-1]["numerical_temperature_K"]), 1000.0)
            book = load_workbook(out / "temperature.xlsx")
            self.assertEqual(len(book["Temperature data"]._charts), 1)
            book.close()
            audit = subprocess.run([sys.executable, str(PROJECT / "verify_outputs.py"), "--directory", str(out),
                                    "--n", "5", "--length", "2"], text=True, capture_output=True)
            self.assertEqual(audit.returncode, 0, audit.stdout + audit.stderr)
            repeat = subprocess.run(command, text=True, capture_output=True)
            self.assertNotEqual(repeat.returncode, 0)
            self.assertIn("already exists", repeat.stderr)

    def test_failing_cli_produces_no_result_directory(self):
        with tempfile.TemporaryDirectory(prefix="cfd-heat-fail-") as tmp:
            out = Path(tmp) / "out"
            completed = subprocess.run([sys.executable, str(PROJECT / "solver.py"), "--max-iterations", "1",
                                        "--output-dir", str(out)], text=True, capture_output=True)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("not converged", completed.stderr)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
