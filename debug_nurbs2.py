from session_py import NurbsCurve, Point as SessionPoint
import numpy as np

# Create the curve manually with proper knot vector
curve = NurbsCurve()

# Set up parameters
dimension = 3
is_rational = False
order = 3  # degree 2
cv_count = 3

curve.m_dim = dimension
curve.m_is_rat = 0
curve.m_order = order
curve.m_cv_count = cv_count
curve.m_cv_stride = dimension

# Create proper knot vector for clamped curve: [0,0,0,1,1,1]
knot_count = order + cv_count  # Standard NURBS formula
curve.m_knot = np.array([0.0, 0.0, 0.0, 1.0, 1.0, 1.0], dtype=np.float64)

# Set control points
curve.m_cv = np.array([
    0.0, 0.0, -453.0,      # CV 0
    1500.0, 0.0, -147.0,   # CV 1
    3000.0, 0.0, -147.0    # CV 2
], dtype=np.float64)

print(f"Curve: {curve}")
print(f"Valid: {curve.is_valid()}")
print(f"Order: {curve.order()}")
print(f"Degree: {curve.degree()}")
print(f"CV Count: {curve.cv_count()}")
print(f"Knot Count: {len(curve.m_knot)}")
print(f"Knots: {curve.get_knots()}")
print(f"Domain: {curve.domain()}")
print(f"Is Clamped: {curve.is_clamped()}")

# Check control points
print("\nControl Points:")
for i in range(curve.cv_count()):
    cv = curve.get_cv(i)
    print(f"  CV[{i}]: {cv}")

# Try evaluating at domain endpoints
t0, t1 = curve.domain()
print(f"\nDomain evaluation:")
print(f"  point_at({t0}): {curve.point_at(t0)}")
print(f"  point_at({t1}): {curve.point_at(t1)}")
print(f"  point_at({(t0+t1)/2}): {curve.point_at((t0+t1)/2)}")

# Check divided points
print(f"\nDivided points:")
sampled_points, parameters = curve.divide_by_count(6)
for i, (p, t) in enumerate(zip(sampled_points, parameters)):
    print(f"  [{i}] t={t:.3f}: {p}")
