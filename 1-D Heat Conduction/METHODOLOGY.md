# Methodology: steady one-dimensional heat conduction

## Physical model

For a rod of length L = 1.0 m, the default boundary temperatures are 300 K
at x = 0 and 1000 K at x = L. The model assumes steady conditions,
one-dimensional conduction, constant thermal conductivity, and no internal
heat generation. These assumptions give d²T/dx² = 0. The steady-state
temperature therefore has the exact solution

    T_exact(x) = 300 + 700 x/L  K.

The conductivity value itself is unnecessary for finding this temperature
distribution; it would be needed to calculate heat flux. L is selectable at
the command line; boundary temperatures remain fixed at 300 K and 1000 K.

## Grid and derivation

Choose N equally spaced grid points including both endpoints. Let
dx = L/(N-1) and x_i = i dx for i = 0, ..., N-1. Taylor expansions at x_i are

    T_(i+1) = T_i + dx T'_i + (dx²/2) T''_i + (dx³/6) T'''_i + O(dx⁴),
    T_(i-1) = T_i - dx T'_i + (dx²/2) T''_i - (dx³/6) T'''_i + O(dx⁴).

Adding them gives the second-order central approximation

    T''_i = (T_(i+1) - 2 T_i + T_(i-1))/dx² + O(dx²).

At each interior grid point, setting the discrete equation to zero and
rearranging gives T_i = (T_(i-1) + T_(i+1))/2. This is a one-dimensional
three-point stencil, not a two-dimensional stencil. For this particular
problem, the exact linear solution also satisfies the discrete equations
exactly in exact arithmetic, so the observed discrepancy is due to iterative
convergence and floating-point roundoff rather than truncation of the line.

## Matrix form and iteration

Collect the N-2 interior unknowns in u. Multiplying each equation by -dx²
produces A u = b, where A is tridiagonal with 2 on its diagonal and -1 on
each adjacent diagonal. The fixed boundary temperatures enter b: 300 in the
first row and 1000 in the last row. When N = 3, there is only one equation,
so its right-hand side contains their sum, 1300.

Gauss-Seidel solves these equations iteratively. For each sweep from left to
right, the newest left-neighbour value and the current right-neighbour value
are averaged, updating the solution in place. The endpoints are never
updated. This matrix is symmetric positive definite for N >= 3, and standard
Gauss-Seidel converges for it. The method avoids forming or inverting a
matrix and makes the stencil easy to inspect.

Start the interior at 300 K, hold the last point at 1000 K, and perform
sweeps until BOTH the largest absolute temperature update is <= tolerance
and the largest absolute unscaled stencil residual is <= 2*tolerance. The
unscaled residual is max |T_(i-1) - 2T_i + T_(i+1)| in K. Independently,
the report also records the finite-difference PDE residual, this quantity
divided by dx², in K/m². The tolerance is an iteration stopping test, not a
universal bound on the true temperature error. If the iteration limit is
reached, the program exits with an error rather than claiming convergence.
For verification, compare every numerical value with the analytical solution
and check boundary values, finiteness, and the residual separately.
