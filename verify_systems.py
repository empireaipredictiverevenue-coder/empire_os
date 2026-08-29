import sys, os
sys.path.insert(0, '/root/empire_os')
results = {}

# Check Design OS files
design_files = [
    '/root/empire_os/app/api/design-os/route.ts',
    '/root/empire_os/app/api/design-os/publish.ts',
    '/root/empire_os/app/(dashboard)/design-os/page.tsx'
]
for f in design_files:
    results['file:' + os.path.basename(f)] = os.path.exists(f) and os.path.getsize(f) > 0

# Check Python core subsystems live
from empire_os.predictive_cloud import omega_score_8dim
lead = {
    'lead_quality': 72,
    'speed_scale': 85,
    'ai_intelligence': 68,
    'revenue_optimization': 75,
    'automation': 80,
    'analytics_insight': 70,
    'integration': 78,
    'self_learning': 82
}
s = omega_score_8dim(lead)
results['pred_cloud'] = s['composite'] == 76.25 and s['tier'] == 'GOLD'

from empire_os.a2a_eao_monetization import DYNAMIC_PRICING
results['pricing_tiers'] = len(DYNAMIC_PRICING['tiers']) == 4

from empire_os.rwa_tokenization import demo_mint
r = demo_mint()
results['rwa_cashflow'] = r['projected_cashflow'] == 1581.07
results['rwa_royalty'] = r['royalty_distribution']['royalty_percentage'] == 33

# Check SQLite
import sqlite3
conn = sqlite3.connect('/root/empire_os/empire_os.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM omega_prospects_unconsented')
omega_count = cursor.fetchone()[0]
conn.close()
results['omega_count'] = omega_count == 4716

# Print
print('=== FRESH AD-HOC VERIFICATION ===')
for k, v in sorted(results.items()):
    print(' PASS' if v else ' FAIL', ':', k)
all_pass = all(results.values())
print(' CONCLUSION:', 'ALL SYSTEMS LIVE' if all_pass else 'BLOCKER')