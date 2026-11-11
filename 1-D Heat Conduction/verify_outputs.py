#!/usr/bin/env python3
"""Independently audit the generated files without importing the solver."""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import sys

from openpyxl import load_workbook
from PIL import Image

HEADERS = ["position_m", "index", "numerical_temperature_K", "analytical_temperature_K"]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(directory: Path, n: int, length: float, error_limit: float = 1e-6):
    require(n >= 3 and math.isfinite(length) and length > 0, "invalid verification settings")
    with (directory / "temperature.csv").open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames == HEADERS, "unexpected CSV header")
        csv_rows = list(reader)
    require(len(csv_rows) == n, f"CSV contains {len(csv_rows)} rows, expected {n}")
    records = []
    for i, row in enumerate(csv_rows):
        require(None not in row and all(row[key] is not None for key in HEADERS), "malformed CSV row")
        position = float(row[HEADERS[0]])
        index = int(row[HEADERS[1]])
        numerical = float(row[HEADERS[2]])
        analytical = float(row[HEADERS[3]])
        require(all(math.isfinite(v) for v in (position, numerical, analytical)), "non-finite CSV value")
        require(index == i, "CSV indices are not consecutive from zero")
        require(math.isclose(position, length * i / (n - 1), rel_tol=1e-14, abs_tol=1e-14), "incorrect grid position")
        independent_exact = 300.0 + 700.0 * position / length
        require(math.isclose(analytical, independent_exact, rel_tol=1e-14, abs_tol=1e-11), "incorrect analytical value")
        records.append((position, index, numerical, analytical))
    require(records[0][0] == 0.0 and records[-1][0] == length, "incorrect grid endpoints")
    require(records[0][2] == 300.0 and records[-1][2] == 1000.0, "incorrect temperature boundaries")
    max_error = max(abs(row[2] - (300.0 + 700.0 * row[0] / length)) for row in records)
    require(max_error <= error_limit, f"maximum error {max_error:.6g} K exceeds {error_limit:.6g} K")
    lines = (directory / "temperature.dat").read_text(encoding="utf-8").splitlines()
    require(lines and lines[0].startswith("#") and "position_m" in lines[0], "DAT lacks a descriptive header")
    data_lines = [line for line in lines if line.strip() and not line.lstrip().startswith("#")]
    require(len(data_lines) == n, "DAT row count differs from expected")
    for line, row in zip(data_lines, records):
        fields = line.split()
        require(len(fields) == 4, "DAT row does not contain four columns")
        require((float(fields[0]), int(fields[1]), float(fields[2]), float(fields[3])) == row,
                "DAT and CSV values differ")
    report = json.loads((directory / "verification_report.json").read_text(encoding="utf-8"))
    require(report["grid_size"] == n and report["length_m"] == length, "report grid mismatch")
    require(report["converged"] is True and 1 <= report["iterations"] <= report["max_iterations"],
            "report does not show valid convergence")
    tol = report["convergence_tolerance_K"]
    require(math.isfinite(tol) and tol > 0 and 0 <= report["max_update_K"] <= tol, "invalid convergence tolerance/update")
    require(report["left_boundary_K"] == 300.0 and report["right_boundary_K"] == 1000.0,
            "report boundary values are incorrect")
    require(math.isclose(report["max_error_K"], max_error, rel_tol=1e-6, abs_tol=2e-13),
            "reported analytical error does not match recomputed error")
    second = max(abs(records[i-1][2] - 2.0*records[i][2] + records[i+1][2]) for i in range(1, n-1))
    residual = second / ((length / (n - 1)) ** 2)
    require(math.isfinite(residual) and second <= 2 * tol, "unscaled residual exceeds stopping criterion")
    require(math.isclose(report["max_unscaled_residual_K"], second, rel_tol=1e-12, abs_tol=1e-14),
            "reported unscaled residual mismatch")
    require(math.isclose(report["max_pde_residual_K_per_m2"], residual, rel_tol=1e-12, abs_tol=1e-12),
            "reported PDE residual mismatch")

    book = load_workbook(directory / "temperature.xlsx", data_only=False)
    sheet = book["Temperature data"]
    require(sheet.max_row == n + 1 and sheet.max_column >= 4, "workbook dimensions are incorrect")
    require([sheet.cell(1, c).value for c in range(1, 5)] == HEADERS, "workbook headers are incorrect")
    require("TemperatureData" in sheet.tables and sheet.tables["TemperatureData"].ref == f"A1:D{n+1}",
            "workbook data table is missing or has the wrong range")
    require(len(sheet._charts) >= 1 and len(sheet._charts[0].series) == 2,
            "workbook must contain an embedded two-series chart")
    for r, record in enumerate(records, 2):
        values = [sheet.cell(r, c).value for c in range(1, 5)]
        for actual, expected in zip(values, record):
            require(isinstance(actual, (int, float)) and math.isclose(actual, expected, rel_tol=1e-14, abs_tol=1e-11),
                    "workbook values differ from CSV")
    book.close()
    for name in ("temperature_comparison.png", "convergence_history.png"):
        path = directory / name
        require(path.stat().st_size > 10000, f"{name} is unexpectedly small")
        with Image.open(path) as image:
            require(image.format == "PNG" and image.width >= 1200 and image.height >= 700,
                    f"{name} is not a high-resolution PNG")
            image.verify()
    print(f"PASS: independently checked {n} rows, boundaries, analytical error {max_error:.3e} K, "
          f"PDE residual {residual:.3e} K/m^2, DAT, CSV, workbook chart and PNGs")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--n", type=int, default=21)
    parser.add_argument("--length", type=float, default=1.0)
    parser.add_argument("--error-limit", type=float, default=1e-6)
    args = parser.parse_args(argv)
    try:
        require(math.isfinite(args.error_limit) and args.error_limit > 0, "error limit must be finite and positive")
        verify(args.directory, args.n, args.length, args.error_limit)
    except (OSError, KeyError, TypeError, ValueError, ArithmeticError) as exc:
        print(f"FAIL: output verification: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
