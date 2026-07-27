#!/usr/bin/env python3
"""
Fix the resolve_metro function in the satellite strike service.
The issue is in coordinate handling - it was incorrectly assuming coords were already in [lat, lon] format.
"""

import sys
sys.path.insert(0, "/root/empire_os")

# Read the satellite_strike_service.py file
with open("/root/empire_os/empire_os/satellite_strike_service.py", "r") as f:
    content = f.read()

# Let's find and fix the _resolve_metro_from_event function
# The problem is in lines 1242-1254 where coords are processed
fixed_code = '''def _resolve_metro_from_event(coords, area, event):
    """Find our metro code (NYC/HOU/DFW/...) from an NWS alert.

    Order:
      1. polygon centroid -> reverse-geocode via a lat/lon -> metro
         heuristic (cover the 11 supported metros with city bounding boxes).
      2. area string -> parse "Montgomery, MD" style tokens to a county,
         then look up in _COUNTY_TO_METRO.
      3. Fallback to the first token of area.
    """
    # 1. polygon centroid -> nearest supported metro by lat/lon bbox
    if coords and isinstance(coords, list) and coords:
        try:
            # coords are [lon, lat] from the NWS API
            # Handle both list of arrays [[lon1, lat1], [lon2, lat2]]
            flat = []
            for pt in coords[:50]:
                if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                    flat.append(float(pt[0]))  # longitude
                    flat.append(float(pt[1]))  # latitude
            if len(flat) >= 2:
                lon = sum(flat[0::2]) / max(1, len(flat[0::2]))
                lat = sum(flat[1::2]) / max(1, len(flat[1::2]))
                hit = _metro_from_latlon(lat, lon)
                if hit:
                    return hit
        except Exception:
            pass

    # 2. area string -> county lookup
    if area:
        for token in (t.strip() for t in area.split(";")):
            low = token.lower()
            for k, metro in _COUNTY_TO_METRO.items():
                if k in low or low.startswith(k.split(",")[0]):
                    return metro

    # 3. fallback
    return area.split(";")[0].strip() if area else "Unknown"
'''

# Let's just directly fix the issue by writing the whole file
with open("/root/empire_os/empire_os/satellite_strike_service.py", "r") as f:
    lines = f.readlines()

# Find the _resolve_metro_from_event function
start_idx = None
end_idx = None
for i, line in enumerate(lines):
    if 'def _resolve_metro_from_event(coords, area, event):' in line:
        start_idx = i
    elif start_idx is not None and line.strip() == '"""':
        end_idx = i
        break

if start_idx is not None and end_idx is not None:
    print(f"Found _resolve_metro_from_event function at lines {start_idx+1}-{end_idx+1}")
    
    # Let's see what the original looks like
    print("\nOriginal _resolve_metro_from_event function:")
    print("=" * 80)
    original = ''.join(lines[start_idx:end_idx+1])
    print(original)
    
    # Now let's fix it
    # We need to make sure the fix is in place
    fixed_lines = lines[:start_idx] + [fixed_code + '\n'] + lines[end_idx+1:]
    
    # Write back
    with open("/root/empire_os/empire_os/satellite_strike_service.py", "w") as f:
        f.writelines(fixed_lines)
    
    print("\nFixed _resolve_metro_from_event function written to satellite_strike_service.py")
else:
    print("Could not find _resolve_metro_from_event function")

# Test the fix now
from empire_os.satellite_strike_service import resolve_metro

# Test with the polygon from the failing unit test
poly = [[-95.40, 29.70], [-95.30, 29.70], [-95.30, 29.80], [-95.40, 29.80]]
result = resolve_metro(poly, "", "Tornado")
print("\n" + "=" * 80)
print("TESTING THE FIX")
print("=" * 80)
print(f"Polygon: {poly}")
print(f"resolve_metro(poly, '', 'Tornado') = {result}")
print(f"Expected: HOU")
print(f"Match: {result == 'HOU'}")

if result == 'HOU':
    print("\nSUCCESS: The fix is working correctly!")
else:
    print("\nFAILURE: The fix did not work.")
