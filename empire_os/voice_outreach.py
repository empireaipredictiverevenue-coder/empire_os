"""
Empire Voice Outreach — AI voice calls to leads with collected phone numbers.
Uses gTTS (Google TTS) for now, can swap to bark/xtts later.
"""
import sqlite3
import os
from gtts import gTTS
import subprocess
from datetime import datetime

DB = "/root/empire_os/empire_os.db"
VOICE_DIR = "/root/empire_os/voice_outreach"
os.makedirs(VOICE_DIR, exist_ok=True)

SCRIPTS = {
    "evaluation": "Hello, this is Empire AI. You have 4 free lead evaluation credits waiting. Each credit evaluates one lead against 14 quality signals. Normal price is ten dollars per credit. Visit factory-ai.co.uk slash v1 slash evaluate slash signup to redeem. Press 1 to connect with our team.",
    "cortex": "Hello, this is Empire AI. Our Cortex Intelligence platform predicts which businesses need your services before they search. It monitors 16 real-time data sources. First 10 companies get free evaluation worth two hundred dollars. Sign up at empire-ai.co.uk slash v1 slash cortex slash signup.",
    "lead_grader": "Hello, this is Empire AI. Our Lead Grader scores incoming leads on quality so you only chase deals that close. Forty-nine dollars per month, each grade costs about ten dollars. Free plan gives three grades per day. Get your API key at factory-ai.co.uk slash v1 slash lead-grader slash signup.",
}

def get_leads_with_phones(product="evaluation", limit=50):
    """Get leads with phone numbers for voice outreach."""
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Get leads with phones, prioritize by niche
    c.execute("""
        SELECT prospect_id, business_name, phone, niche, metro, email
        FROM si_buyer_outreach 
        WHERE phone IS NOT NULL AND phone != ''
        AND (email IS NULL OR email = '' OR email NOT LIKE '%@example%')
        ORDER BY rowid ASC
        LIMIT ?
    """, (limit,))
    
    leads = [dict(row) for row in c.fetchall()]
    conn.close()
    return leads

def generate_voice(text, filename):
    """Generate MP3 using gTTS."""
    try:
        tts = gTTS(text=text, lang="en", slow=False)
        tts.save(filename)
        return True
    except Exception as e:
        print(f"gTTS error: {e}")
        return False

def play_voice(filename):
    """Play voice file (requires audio output)."""
    try:
        subprocess.run(["mpg123", "-q", filename], check=False, timeout=30)
        return True
    except Exception:
        return False

def run_voice_campaign(product="evaluation", limit=10):
    """Run voice outreach campaign."""
    leads = get_leads_with_phones(product, limit)
    print(f"Voice campaign: {product} -> {len(leads)} leads with phones")
    
    script = SCRIPTS.get(product, SCRIPTS["evaluation"])
    
    for i, lead in enumerate(leads):
        phone = lead["phone"]
        name = lead["business_name"] or "there"
        personalized = f"Hi {name}. {script}"
        
        filename = f"{VOICE_DIR}/{product}_{lead['prospect_id']}_{i}.mp3"
        if generate_voice(personalized, filename):
            print(f"  Generated: {filename} for {name} ({phone})")
        else:
            print(f"  FAILED: {name}")

if __name__ == "__main__":
    import sys
    product = sys.argv[1] if len(sys.argv) > 1 else "evaluation"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    run_voice_campaign(product, limit)