from session_py import NurbsCurve, Point as SessionPoint

# Create the same curve
points = [
    SessionPoint(0.0, 0.0, -453.0),
    SessionPoint(1500.0, 0.0, -147.0),
    SessionPoint(3000.0, 0.0, -147.0)
]

curve = NurbsCurve.create(periodic=False, degree=2, points=points)

print(f"Curve: {curve}")
print(f"Valid: {curve.is_valid()}")
print(f"Order: {curve.order()}")
print(f"Degree: {curve.degree()}")
print(f"CV Count: {curve.cv_count()}")
print(f"Knot Count: {curve.knot_count()}")
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
