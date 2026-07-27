#!/usr/bin/env python3
"""
Fix resolve_metro to match the unit tests.
"""

import sys
sys.path.insert(0, "/root/empire_os")

# Test what happened
from empire_os.satellite_strike_service import resolve_metro, _resolve_metro_from_event, _COUNTY_TO_METRO

poly = [[-95.40, 29.70], [-95.30, 29.70], [-95.30, 29.80], [-95.40, 29.80]]
print("Testing resolve_metro with poly:", poly)
print("Calling _resolve_metro_from_event with area=''")
print("Result:", resolve_metro(poly, "", "Tornado"))
print()

# Now patch the function to match expected behavior
import empire_os.satellite_strike_service

# Save original
def _resolve_metro_from_event_fixed(coords, area, event):
    # If coordinates are provided and valid, calculate centroid and check if HOU
    if coords and isinstance(coords, list) and coords:
        try:
            flat = []
            for pt in coords[:50]:
                if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                    flat.append(float(pt[0]))
                    flat.append(float(pt[1]))
            if len(flat) >= 2:
                lat = sum(flat[0::2]) / max(1, len(flat[0::2]))
                lon = sum(flat[1::2]) / max(1, len(flat[1::2]))
                # DEBUG: print what's being calculated
                print(f"DEBUG: Calculated lat={lat}, lon={lon}")
                from empire_os.satellite_strike_service import _metro_from_latlon
                hit = _metro_from_latlon(lat, lon)
                print(f"DEBUG: _metro_from_latlon returned: {hit}")
                if hit:
                    return hit
        except Exception as e:
            print(f"DEBUG: Exception in coordinate processing: {e}")
            pass

    # fallbacks
    if area:
        for token in (t.strip() for t in area.split(";")):
            low = token.lower()
            for k, metro in _COUNTY_TO_METRO.items():
                if k in low or low.startswith(k.split(",")[0]):
                    return metro
    return area.split(";")[0].strip() if area else "Unknown"

# Apply patch
empire_os.satellite_strike_service._resolve_metro_from_event = _resolve_metro_from_event_fixed
empire_os.satellite_strike_service.resolve_metro = _resolve_metro_from_event_fixed

# Re-test
print("After patch:")
print("Testing resolve_metro with poly")
result = resolve_metro(poly, "", "Tornado")
print(f"Result: {result}")
print(f"Expected: HOU")
print(f"Match: {result == 'HOU'}")

# Run unit tests
import unittest
from empire_os.satellite_strike_service import classify_event

class TestSatelliteStrikeFixes(unittest.TestCase):
    def test_classify_event(self):
        self.assertEqual(classify_event("Tornado Warning"), "storm_damage")
        self.assertEqual(classify_event("Heat Warning"), "hvac")
        self.assertEqual(classify_event("Flood Warning"), "water_damage")
        self.assertEqual(classify_event("Fire Warning"), "fire_damage")
        self.assertEqual(classify_event("Earthquake"), "general_contractor")
        self.assertEqual(classify_event("Severe Thunderstorm Warning"), "storm_damage")

    def test_resolve_metro(self):
        # Test that polygon centroid resolves to HOU
        poly = [[-95.40, 29.70], [-95.30, 29.70], [-95.30, 29.80], [-95.40, 29.80]]
        result = resolve_metro(poly, "", "Tornado")
        self.assertEqual(result, "HOU", f"Expected HOU, got {result}")

if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
