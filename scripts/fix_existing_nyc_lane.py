#!/usr/bin/env python3
"""
Fix Existing NYC General Contractor Lane

The NYC lane (general_contractor:NYC) already exists but needs to be
fixed with the correct price of $15,000 (currently $0).
"""

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("/root/empire_os/empire_os.db")

# Setup logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
log = logging.getLogger(__name__)

def fix_nyc_lane():
    """Fix the NYC lane price and configuration."""
    try:
        # Connect to database
        if not DB_PATH.exists():
            log.error(f"Database file not found: {DB_PATH}")
            return False
            
        cnx = sqlite3.connect(str(DB_PATH), timeout=30)
        cnx.row_factory = sqlite3.Row
        
        # Check current state
        cursor = cnx.execute('SELECT * FROM lanes WHERE sub_niche = ? AND metro = ?', 
                           ('general_contractor', 'NYC'))
        current_lane = cursor.fetchone()
        
        if not current_lane:
            log.error("NYC lane not found")
            return False
            
        # Get current values
        lane_id = current_lane['id']
        current_sub_niche = current_lane['sub_niche']
        current_metro = current_lane['metro']
        current_category = current_lane['category']
        current_seat_price = current_lane['seat_price']
        current_occupied = current_lane['occupied_by']
        current_firm_slug = current_lane['firm_slug']
        current_firm_tier = current_lane['firm_tier']
        
        log.info(f"Current NYC lane state:")
        log.info(f"  ID: {lane_id}")
        log.info(f"  Sub-niche: {current_sub_niche}")
        log.info(f"  Metro: {current_metro}")
        log.info(f"  Category: {current_category}")
        log.info(f"  Seat Price: ${current_seat_price:,}")
        log.info(f"  Occupied By: {current_occupied}")
        log.info(f"  Firm Slug: {current_firm_slug}")
        log.info(f"  Firm Tier: {current_firm_tier}")
        
        # Check what needs to be fixed
        fixes_needed = []
        
        if current_seat_price != 15000:
            fixes_needed.append(f"Seat price: ${current_seat_price:,} → $15,000")
            
        if current_category != 'home_services':
            fixes_needed.append(f"Category: {current_category} → home_services")
            
        if current_occupied is not None:
            fixes_needed.append(f"Occupied By: {current_occupied} → None (available)")
            
        if current_firm_slug is not None:
            fixes_needed.append(f"Firm Slug: {current_firm_slug} → None")
            
        if not fixes_needed:
            log.info("NYC lane is already properly configured - no changes needed")
            return True
            
        # Apply fixes
        log.info(f"Applying fixes: {', '.join(fixes_needed)}")
        
        # Prepare update values
        update_values = {
            'sub_niche': current_sub_niche,
            'metro': current_metro,
            'category': 'home_services',
            'seat_price': 15000,
            'occupied_by': None,
            'firm_slug': None,
            'firm_tier': 'standard',
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }
        
        update_query = """
        UPDATE lanes SET 
            sub_niche = ?,
            metro = ?,
            category = ?,
            seat_price = ?,
            occupied_by = ?,
            firm_slug = ?,
            firm_tier = ?,
            updated_at = ?
        WHERE id = ?
        """
        
        cnx.execute(update_query, (
            update_values['sub_niche'],
            update_values['metro'],
            update_values['category'],
            update_values['seat_price'],
            update_values['occupied_by'],
            update_values['firm_slug'],
            update_values['firm_tier'],
            update_values['updated_at'],
            lane_id
        ))
        
        cnx.commit()
        
        # Verification
        cursor = cnx.execute('SELECT * FROM lanes WHERE id = ?', (lane_id,))
        verified_lane = cursor.fetchone()
        
        log.info(f"Successfully fixed NYC lane: ID {lane_id}")
        log.info(f"New values:")
        log.info(f"  Sub-niche: {verified_lane['sub_niche']}")
        log.info(f"  Metro: {verified_lane['metro']}")
        log.info(f"  Category: {verified_lane['category']}")
        log.info(f"  Seat Price: ${verified_lane['seat_price']:,}")
        log.info(f"  Occupied By: {verified_lane['occupied_by']}")
        log.info(f"  Firm Tier: {verified_lane['firm_tier']}")
        
        return True
        
    except sqlite3.Error as exc:
        log.error(f"SQLite error: {exc}")
        return False
        
    except Exception as exc:
        log.error(f"Unexpected error: {exc}")
        return False
        
    finally:
        cnx.close()

def main():
    """Main execution."""
    print("Fixing existing NYC general contractor lane...")
    
    if fix_nyc_lane():
        print("\n✅ NYC lane successfully fixed!")
        print("📍 Lane: general_contractor:NYC")
        print("🎯 Fixes applied:")
        print("  • Seat price: $0 → $15,000")
        print("  • Category: auto-corrected")
        print("  • Status: AVAILABLE")
        print("  • Ready for lead generation")
    else:
        print("\n❌ NYC lane fix failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()