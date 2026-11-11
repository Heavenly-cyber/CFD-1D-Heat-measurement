#!/usr/bin/env python3
"""One-dimensional steady conduction solved by in-place Gauss-Seidel."""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import json
import math
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from openpyxl import Workbook
from openpyxl.chart import Reference, ScatterChart, Series
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.table import Table, TableStyleInfo

LEFT_K = 300.0
RIGHT_K = 1000.0
OUTPUT_NAMES = (
    "temperature.dat", "temperature.csv", "temperature.xlsx",
    "temperature_comparison.png", "convergence_history.png",
    "verification_report.json",
)
HEADERS = ("position_m", "index", "numerical_temperature_K", "analytical_temperature_K")


class ConvergenceError(RuntimeError):
    """The iteration did not converge in the permitted number of sweeps."""


@dataclass
class Solution:
    x: np.ndarray
    temperature: np.ndarray
    analytical: np.ndarray
    iterations: int
    tolerance: float
    max_iterations: int
    updates: list[float]
    unscaled_residual: float
    pde_residual: float


def solve_heat(n: int = 21, length: float = 1.0, tolerance: float = 1e-10,
               max_iterations: int = 50000) -> Solution:
    """Solve with fixed endpoint values and return diagnostics for every sweep."""
    if not isinstance(n, int) or isinstance(n, bool) or n < 3:
        raise ValueError("n must be an integer >= 3, including the boundary points")
    if not isinstance(max_iterations, int) or isinstance(max_iterations, bool) or max_iterations < 1:
        raise ValueError("max_iterations must be a positive integer")
    if not math.isfinite(length) or length <= 0:
        raise ValueError("length must be finite and positive")
    if not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("tolerance must be finite and positive")
    dx = length / (n - 1)
    dx_squared = dx * dx
    if not math.isfinite(dx_squared) or dx_squared == 0:
        raise ValueError("grid spacing squared must be finite and nonzero")

    x = np.linspace(0.0, length, n, dtype=float)
    temperature = np.full(n, LEFT_K, dtype=float)
    temperature[-1] = RIGHT_K
    updates: list[float] = []
    residual = math.inf
    for iteration in range(1, max_iterations + 1):
        largest = 0.0
        for i in range(1, n - 1):
            previous = temperature[i]
            # Left neighbour is already updated during this sweep.
            temperature[i] = (temperature[i - 1] + temperature[i + 1]) / 2.0
            largest = max(largest, abs(float(temperature[i] - previous)))
        # The loop does not modify either boundary, and explicitly restore
        # them to make the boundary-condition invariant visible.
        temperature[0], temperature[-1] = LEFT_K, RIGHT_K
        residual = float(np.max(np.abs(temperature[:-2] - 2.0 * temperature[1:-1] + temperature[2:])))
        if not np.all(np.isfinite(temperature)) or not math.isfinite(residual) or not math.isfinite(largest):
            raise ConvergenceError("non-finite numerical value detected during iteration")
        updates.append(largest)
        if largest <= tolerance and residual <= 2.0 * tolerance:
            analytical = LEFT_K + (RIGHT_K - LEFT_K) * (x / length)
            pde_residual = residual / dx_squared
            if not np.all(np.isfinite(analytical)) or not math.isfinite(pde_residual):
                raise ConvergenceError("non-finite analytical value or scaled residual")
            return Solution(x, temperature, analytical, iteration, tolerance,
                            max_iterations, updates, residual, pde_residual)
    raise ConvergenceError(
        f"not converged after {max_iterations} sweeps: max update "
        f"{updates[-1]:.6g} K, unscaled residual {residual:.6g} K, "
        f"tolerance {tolerance:.6g} K; increase --max-iterations or adjust --tolerance"
    )


def _rows(solution: Solution):
    for i, (position, numerical, analytical) in enumerate(
            zip(solution.x, solution.temperature, solution.analytical)):
        yield (float(position), i, float(numerical), float(analytical))


def write_outputs(solution: Solution, output_dir: Path, overwrite: bool = False) -> dict:
    """Write portable data, a real Excel chart, plots, and a JSON report."""
    output_dir = Path(output_dir)
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"output path is not a directory: {output_dir}")
    for name in OUTPUT_NAMES:
        destination = output_dir / name
        if destination.is_symlink() or (destination.exists() and not overwrite):
            raise FileExistsError(f"output already exists or is a symlink: {destination}; choose a new directory or use --overwrite")
        if destination.exists() and not destination.is_file():
            raise FileExistsError(f"output path is not a regular file: {destination}")
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = list(_rows(solution))
    with (output_dir / "temperature.dat").open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("# Steady 1-D heat conduction: position_m index numerical_temperature_K analytical_temperature_K\n")
        stream.write("# Uniform grid; endpoint temperatures 300 K and 1000 K; index starts at zero.\n")
        for x, i, numerical, analytical in rows:
            stream.write(f"{x:.17g} {i:d} {numerical:.17g} {analytical:.17g}\n")
    with (output_dir / "temperature.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(HEADERS)
        for x, i, numerical, analytical in rows:
            writer.writerow((f"{x:.17g}", i, f"{numerical:.17g}", f"{analytical:.17g}"))

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Temperature data"
    sheet.append(HEADERS)
    for row in rows:
        sheet.append(row)
    sheet.freeze_panes = "C2"
    for col, width in {"A": 18, "B": 12, "C": 29, "D": 29}.items():
        sheet.column_dimensions[col].width = width
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="17365D")
        cell.alignment = Alignment(wrap_text=True)
    for row in sheet.iter_rows(min_row=2, max_row=len(rows) + 1):
        for cell in (row[0], row[2], row[3]):
            cell.number_format = "0.000000000"
    table = Table(displayName="TemperatureData", ref=f"A1:D{len(rows) + 1}")
    table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    sheet.add_table(table)
    chart = ScatterChart()
    chart.title = "Steady-state temperature versus position"
    chart.x_axis.title = "Position, x (m)"
    chart.y_axis.title = "Temperature, T (K)"
    chart.width, chart.height = 19, 11
    xvalues = Reference(sheet, min_col=1, min_row=2, max_row=len(rows) + 1)
    for col in (3, 4):
        values = Reference(sheet, min_col=col, min_row=1, max_row=len(rows) + 1)
        chart.series.append(Series(values, xvalues, title_from_data=True))
    sheet.add_chart(chart, "F2")
    workbook.save(output_dir / "temperature.xlsx")

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(8.2, 5.2), layout="constrained")
    ax.plot(solution.x, solution.analytical, color="#1D4E89", linewidth=2.4, label="Analytical solution")
    ax.plot(solution.x, solution.temperature, linestyle="none", marker="o", markersize=4.0,
            markerfacecolor="white", markeredgecolor="#C73E1D", label="Gauss-Seidel solution")
    ax.set(title="Steady 1-D heat conduction", xlabel="Position x (m)", ylabel="Temperature T (K)")
    ax.legend(frameon=True)
    fig.savefig(output_dir / "temperature_comparison.png", dpi=200)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.2, 5.2), layout="constrained")
    ax.semilogy(range(1, solution.iterations + 1),
                np.maximum(solution.updates, np.finfo(float).tiny), color="#1D4E89", linewidth=1.7,
                label="Maximum temperature update")
    ax.axhline(solution.tolerance, color="#C73E1D", linestyle="--", label="Update tolerance")
    ax.set(title="Gauss-Seidel convergence history", xlabel="Iteration (sweep)", ylabel="Maximum update (K)")
    ax.legend(frameon=True)
    fig.savefig(output_dir / "convergence_history.png", dpi=200)
    plt.close(fig)

    report = {
        "problem": "steady 1-D conduction, d2T/dx2=0",
        "grid_size": len(rows), "length_m": float(solution.x[-1]),
        "dx_m": float(solution.x[-1] / (len(rows) - 1)),
        "iterations": solution.iterations, "max_iterations": solution.max_iterations,
        "convergence_tolerance_K": solution.tolerance, "converged": True,
        "max_update_K": solution.updates[-1],
        "max_unscaled_residual_K": solution.unscaled_residual,
        "max_pde_residual_K_per_m2": solution.pde_residual,
        "max_error_K": float(np.max(np.abs(solution.temperature - solution.analytical))),
        "left_boundary_K": float(solution.temperature[0]),
        "right_boundary_K": float(solution.temperature[-1]),
    }
    with (output_dir / "verification_report.json").open("w", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=21, help="number of points, including endpoints (default: 21)")
    parser.add_argument("--length", type=float, default=1.0, help="rod length in metres (default: 1)")
    parser.add_argument("--tolerance", type=float, default=1e-10, help="sweep update tolerance in K (default: 1e-10)")
    parser.add_argument("--max-iterations", type=int, default=50000)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--overwrite", action="store_true", help="replace existing regular output files")
    args = parser.parse_args(argv)
    try:
        solution = solve_heat(args.n, args.length, args.tolerance, args.max_iterations)
        report = write_outputs(solution, args.output_dir, args.overwrite)
    except (ValueError, ConvergenceError, OSError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"PASS: converged in {report['iterations']} iterations; "
          f"maximum analytical error {report['max_error_K']:.3e} K; "
          f"PDE residual {report['max_pde_residual_K_per_m2']:.3e} K/m^2")
    print(f"Output directory: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
