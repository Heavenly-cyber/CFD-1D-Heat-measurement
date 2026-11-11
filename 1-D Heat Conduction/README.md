# One-dimensional steady heat conduction

This undergraduate CFD assignment solves d²T/dx² = 0 along a rod with fixed
endpoint temperatures of 300 K and 1000 K. The documented default has length
L = 1 m and N = 21 uniformly spaced points, including both boundaries. The
expected temperature varies linearly from one endpoint to the other; at
x = 0.5 m it is 650 K. The [methodology](METHODOLOGY.md) derives the
second-order, three-point central difference, the tridiagonal A u = b system,
and the in-place Gauss-Seidel iteration.

## Installation

From the repository root on Linux, use Python 3.11 or later and `uv` to install
the pinned packages into a virtual environment. The builder tested these
versions with Python 3.12:

```bash
uv venv --python python3 .venv
uv pip install --python .venv/bin/python -r '1-D Heat Conduction/requirements.txt'
```

On Pop!_OS, if creating the environment fails because `venv` is missing,
install the operating-system package `python3-venv` and retry. The builder
uses its own isolated temporary environment for its validation, bootstrapping
`uv` privately if needed; the commands above make a separate reusable
environment in your repository once `uv` is available on your PATH.

## Run the solver

From the repository root:

```bash
.venv/bin/python '1-D Heat Conduction/solver.py' --output-dir /tmp/cfd-heat-example
.venv/bin/python '1-D Heat Conduction/solver.py' --n 41 --length 2.0 --tolerance 1e-10 --max-iterations 50000 --output-dir /tmp/cfd-heat-custom
```

Use `--help` to see all options. The boundary temperatures are fixed at
300 K and 1000 K. The tolerance is the maximum per-sweep update in K, with
an additional unscaled-residual check. Reusing an output folder requires the
explicit `--overwrite` option; use it only when those output files may be
replaced. A too-small iteration limit or invalid input produces a nonzero exit
and does not present an unconverged solution as a valid result.

## Included results and validation

The committed `results/` folder contains the default 21-point calculation:

- `temperature.dat`: a descriptive header followed by position in metres,
  zero-based index, numerical temperature and analytical temperature in K.
- `temperature.csv`: the same columns with an Excel-friendly header.
- `temperature.xlsx`: a labelled data table and an embedded XY scatter chart.
- `temperature_comparison.png`: numerical and analytical temperature curves.
- `convergence_history.png`: maximum update by iteration on a log scale.
- `verification_report.json`: convergence, settings, residuals, endpoint
  temperatures and maximum absolute analytical error.

The builder runs the unit tests, an end-to-end CLI smoke test, and a separate
artifact checker. It accepts the default results only if the numerical error
is at most 1e-6 K. The JSON report contains the measured values for this run;
the finite-difference residual has units K/m² and is reported separately
from the error in K. See `METHODOLOGY.md` for why the numerical result should
be a line and why iteration tolerance is not itself an error bound.

Run the tests and independently recheck the included results:

```bash
cd '1-D Heat Conduction'
../.venv/bin/python -m unittest discover -s tests -v
../.venv/bin/python verify_outputs.py --directory results --n 21 --length 1.0
```

## Open and check the data in Excel

Open `results/temperature.xlsx` directly in Excel or LibreOffice Calc. The
worksheet contains numeric values, column labels, and an embedded chart. To
use the CSV, open or import `results/temperature.csv` as comma-separated
data; the first row supplies the column names. Check that the first and last
numerical temperatures are 300 K and 1000 K, the midpoint is close to 650 K,
and the numerical and analytical columns agree. You can also compute the
absolute difference between the last two columns. The `.dat` file is a
whitespace-delimited text version for scientific tools.
