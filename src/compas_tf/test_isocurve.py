from session_py.nurbssurface import NurbsSurface
from session_py.point import Point

# Create a simple surface
srf = NurbsSurface(3, False, 4, 4, 5, 5)
srf.make_clamped_uniform_knot_vector(0, 1.0)
srf.make_clamped_uniform_knot_vector(1, 1.0)

# Set control points
for i in range(5):
    for j in range(5):
        x = float(i)
        y = float(j)
        z = 0.5 * (i - 2) * (j - 2) / 4.0
        srf.set_cv(i, j, Point(x, y, z))

# Get domains
u_min, u_max = srf.domain(0)
v_min, v_max = srf.domain(1)

print(f"Surface domain: u=[{u_min}, {u_max}], v=[{v_min}, {v_max}]\n")

# Test iso-curve extraction at u=1.0
test_u = 1.0
print(f"Testing iso-curve at u={test_u} (direction=0, v varies)")
print("="*60)

iso_curve = srf.iso_curve(0, test_u)
if iso_curve:
    t_min, t_max = iso_curve.domain()
    print(f"Iso-curve domain: [{t_min}, {t_max}]\n")
    
    # Compare 5 points
    for i in range(5):
        v_param = v_min + (v_max - v_min) * i / 4
        
        # Method 1: Direct surface evaluation
        pt_surface = srf.point_at(test_u, v_param)
        
        # Method 2: Iso-curve evaluation at corresponding t
        # If curve domain matches surface v domain, t should equal v_param
        t_param = t_min + (t_max - t_min) * i / 4
        pt_curve = iso_curve.point_at(t_param)
        
        print(f"v={v_param:.2f}, t={t_param:.2f}:")
        print(f"  Surface: ({pt_surface.x:.4f}, {pt_surface.y:.4f}, {pt_surface.z:.4f})")
        print(f"  Curve:   ({pt_curve.x:.4f}, {pt_curve.y:.4f}, {pt_curve.z:.4f})")
        
        # Check if they match
        diff = ((pt_surface.x - pt_curve.x)**2 + 
                (pt_surface.y - pt_curve.y)**2 + 
                (pt_surface.z - pt_curve.z)**2)**0.5
        
        match = "✓ MATCH" if diff < 0.001 else f"✗ DIFF: {diff:.6f}"
        print(f"  {match}\n")

print("\n" + "="*60)
print("Testing iso-curve at v=1.0 (direction=1, u varies)")
print("="*60)

test_v = 1.0
iso_curve = srf.iso_curve(1, test_v)
if iso_curve:
    t_min, t_max = iso_curve.domain()
    print(f"Iso-curve domain: [{t_min}, {t_max}]\n")
    
    for i in range(5):
        u_param = u_min + (u_max - u_min) * i / 4
        
        pt_surface = srf.point_at(u_param, test_v)
        
        t_param = t_min + (t_max - t_min) * i / 4
        pt_curve = iso_curve.point_at(t_param)
        
        print(f"u={u_param:.2f}, t={t_param:.2f}:")
        print(f"  Surface: ({pt_surface.x:.4f}, {pt_surface.y:.4f}, {pt_surface.z:.4f})")
        print(f"  Curve:   ({pt_curve.x:.4f}, {pt_curve.y:.4f}, {pt_curve.z:.4f})")
        
        diff = ((pt_surface.x - pt_curve.x)**2 + 
                (pt_surface.y - pt_curve.y)**2 + 
                (pt_surface.z - pt_curve.z)**2)**0.5
        
        match = "✓ MATCH" if diff < 0.001 else f"✗ DIFF: {diff:.6f}"
        print(f"  {match}\n")
