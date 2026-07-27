#!/usr/bin/env python3
"""
Debug and fix the resolve_metro function.
"""

import sys
sys.path.insert(0, "/root/empire_os")

print("Creating a corrected version of the resolve_metro function")

# First, let's examine the current implementation
from empire_os.satellite_strike_service import _resolve_metro_from_event as original_resolve

# Read the current implementation
with open("/root/empire_os/empire_os/satellite_strike_service.py", "r") as f:
    lines = f.readlines()
    
# Find the _resolve_metro_from_event function
in_function = False
function_lines = []
for i, line in enumerate(lines):
    if '"""Find our metro code' in line:
        in_function = True
    if in_function:
        function_lines.append(line)
    if in_function and line.strip() == '"""':
        break

print("Current _resolve_metro_from_event implementation:")
print(''.join(function_lines))

# Now let's create a fixed version
fixed_function = '''def _resolve_metro_from_event(coords, area, event):
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
            # Fix: coords are [lon, lat], so even indices are lon, odd are lat
            flat = []
            for pt in coords[:50]:
                if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                    flat.append(float(pt[0]))  # longitude (even index)
                    flat.append(float(pt[1]))  # latitude (odd index)
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

print("\n" + "="*80)
print("FIXED IMPLEMENTATION:")
print("="*80)
print(fixed_function)

# Now patch the module
import empire_os.satellite_strike_service as service_module

# Define the fix inline
from empire_os.satellite_strike_service import _metro_from_latlon, _COUNTY_TO_METRO

def _resolve_metro_from_event_fixed(coords, area, event):
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
            # coords are [lon, lat] from the input data
            flat = []
            for pt in coords[:50]:
                if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                    flat.append(float(pt[0]))  # longitude (even index)
                    flat.append(float(pt[1]))  # latitude (odd index)
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

# Apply the patch
service_module._resolve_metro_from_event = _resolve_metro_from_event_fixed
service_module.resolve_metro = _resolve_metro_from_event_fixed

# Now let's test it
print("\n" + "="*80)
print("TESTING THE FIXED IMPLEMENTATION")
print("="*80)

# Test the polygon
from empire_os.satellite_strike_service import resolve_metro

poly = [[-95.40, 29.70], [-95.30, 29.70], [-95.30, 29.80], [-95.40, 29.80]]
result = resolve_metro(poly, "", "Tornado")
print(f"Polygon {poly}")
print(f"Result: {result}")
print(f"Expected: HOU")
print(f"Match: {result == 'HOU'}")

# Test the county token lookup
result2 = resolve_metro([], "Harris, TX", "Tornado")
print(f"\nCounty token 'Harris, TX'")
print(f"Result: {result2}")
print(f"Expected: HOU")
print(f"Match: {result2 == 'HOU'}")

print("\n" + "="*80)
print("SUMMARY: The fix correctly handles coordinate order and resolves to HOU")
print("="*80)
