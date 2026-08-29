#!/usr/bin/env python3
"""
Create NYC General Contractor Lane

Based on actual empire_os.db analysis:
- Lanes table uses "id" as TEXT primary key (lane name)
- Need to create "general_contractor:NYC" lane with $15,000 price
- All NYC lanes are set to $199 except roof_repair:NYC at $29,351
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

def create_nyc_lane():
    """Create the NYC general contractor lane."""
    try:
        # Connect to database
        if not DB_PATH.exists():
            log.error(f"Database file not found: {DB_PATH}")
            return False
            
        cnx = sqlite3.connect(str(DB_PATH), timeout=30)
        cnx.row_factory = sqlite3.Row
        
        # Check if NYC lane already exists
        cursor = cnx.execute('SELECT id, sub_niche, metro, category, seat_price FROM lanes WHERE id = ? OR (sub_niche = ? AND metro = ?)', 
                           ('general_contractor:NYC', 'general_contractor', 'NYC'))
        existing_lane = cursor.fetchone()
        
        if existing_lane:
            log.info(f"NYC lane already exists: id={existing_lane['id']}, sub_niche={existing_lane['sub_niche']}, metro={existing_lane['metro']}, seat_price=${existing_lane['seat_price']:,}")
            return False
            
        # Create the NYC lane with correct configuration
        nyc_lane = {
            'id': 'general_contractor:NYC',
            'lane_number': 10001,
            'category': 'home_services',
            'category_label': 'Home Services',
            'sub_niche': 'general_contractor',
            'sub_label': 'General Contractor / Remodeling',
            'metro': 'NYC',
            'metro_label': 'New York City Metro (NY-NJ-CT)',
            'occupied_by': None,
            'firm_slug': None,
            'firm_tier': 'standard',
            'seat_price': 15000,
            'seat_expires_at': None,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }
        
        log.info(f"Creating NYC lane:")
        log.info(f"  ID: {nyc_lane['id']}")
        log.info(f"  Sub-niche: {nyc_lane['sub_niche']}")
        log.info(f"  Metro: {nyc_lane['metro']}")
        log.info(f"  Category: {nyc_lane['category']}")
        log.info(f"  Seat Price: ${nyc_lane['seat_price']:,}")
        
        # Insert the NYC lane
        insert_query = """
        INSERT INTO lanes (
            id, lane_number, category, category_label, sub_niche, sub_label, 
            metro, metro_label, occupied_by, firm_slug, firm_tier, 
            seat_price, seat_expires_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        cnx.execute(insert_query, (
            nyc_lane['id'],
            nyc_lane['lane_number'],
            nyc_lane['category'],
            nyc_lane['category_label'],
            nyc_lane['sub_niche'],
            nyc_lane['sub_label'],
            nyc_lane['metro'],
            nyc_lane['metro_label'],
            nyc_lane['occupied_by'],
            nyc_lane['firm_slug'],
            nyc_lane['firm_tier'],
            nyc_lane['seat_price'],
            nyc_lane['seat_expires_at'],
            nyc_lane['created_at'],
            nyc_lane['updated_at']
        ))
        
        cnx.commit()
        
        # Verification
        cursor = cnx.execute('SELECT * FROM lanes WHERE id = ?', (nyc_lane['id'],))
        verified_lane = cursor.fetchone()
        
        if verified_lane:
            log.info(f"✅ NYC lane successfully created!")
            log.info(f"  ID: {verified_lane['id']}")
            log.info(f"  Sub-niche: {verified_lane['sub_niche']}")
            log.info(f"  Metro: {verified_lane['metro']}")
            log.info(f"  Category: {verified_lane['category']}")
            log.info(f"  Seat Price: ${verified_lane['seat_price']:,}")
            log.info(f"  Occupied By: {verified_lane['occupied_by']}")
            log.info(f"  Status: AVAILABLE (ready for leads)")
            
            return True
        else:
            log.error("Failed to verify NYC lane creation")
            return False
            
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
    print("Creating NYC general contractor lane...")
    print("ID: general_contractor:NYC (primary key)")
    print("Price: $15,000 (correctly priced)")
    print("Metro: NYC (New York City)")
    print("Category: home_services (General Contractor)")
    
    if create_nyc_lane():
        print("\n✅ NYC lane successfully created!")
        print("📍 Lane: general_contractor:NYC")
        print("🏢 Category: Home Services")
        print("🏭 Sub-niche: General Contractor / Remodeling")
        print("🏙️ Metro: New York City (NYC)")
        print("💰 Seat Price: $15,000")
        print("📊 Status: AVAILABLE (ready for leads)")
        print("🚀 Ready for NYC lead generation!")
    else:
        print("\n❌ NYC lane creation failed!")
        print("ℹ️ NYC lane may already exist or there may be an error")
        sys.exit(1)

if __name__ == "__main__":
    main()