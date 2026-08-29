"""
Daily voice outreach cron - generates MP3s for leads with real phones.
"""
import sqlite3, os, time, sys
sys.path.insert(0, "/root/empire_os/empire_os")
from gtts import gTTS

DB = "/root/empire_os/empire_os.db"
VOICE_DIR = "/root/empire_os/voice_outreach"
os.makedirs(VOICE_DIR, exist_ok=True)
BATCH = 20  # per day

SCRIPT = "Hello, this is Empire AI. You have 4 free lead evaluation credits waiting. Each credit evaluates one lead against 14 quality signals. Normal price is ten dollars per credit. Visit factory-ai.co.uk slash v1 slash evaluate slash signup to redeem."

def main():
    db = sqlite3.connect(DB, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=30000")
    c = db.cursor()
    
    # Get leads with real phones, not placeholder
    c.execute("""
        SELECT prospect_id, business_name, phone, niche
        FROM si_buyer_outreach 
        WHERE phone IS NOT NULL AND phone != ''
        AND phone NOT LIKE '%****%'
        ORDER BY rowid ASC
        LIMIT ?
    """, (BATCH,))
    
    leads = c.fetchall()
    db.close()
    
    if not leads:
        print("No leads with real phones")
        return
    
    print(f"Generating voice for {len(leads)} leads...")
    
    for i, lead in enumerate(leads):
        name = lead["business_name"] or "there"
        phone = lead["phone"]
        text = f"Hi {name}. {SCRIPT}"
        
        filename = f"{VOICE_DIR}/eval_{lead['prospect_id']}_{i}.mp3"
        try:
            start = time.time()
            tts = gTTS(text=text, lang="en", slow=False)
            tts.save(filename)
            elapsed = time.time() - start
            print(f"  {i+1}. {name[:30]} ({phone}) -> {filename} [{elapsed:.1f}s]")
        except Exception as e:
            print(f"  {i+1}. {name} FAILED: {e}")
        
        time.sleep(0.5)  # rate limit
    
    print("DONE")

if __name__ == "__main__":
    main()