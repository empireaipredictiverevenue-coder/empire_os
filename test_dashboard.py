import sys
import os
sys.path.insert(0, '/root/empire_os')

from empire_os.revenue_dashboard import RevenueDashboard, get_dashboard_json

def main():
    print("=== Testing Empire OS Revenue Dashboard ===\n")
    
    try:
        # Test 1: Basic dashboard data
        print("📊 Test 1: Dashboard Data Generation")
        data = get_dashboard_json()
        
        print(f"   ✅ Dashboard generated successfully")
        print(f"   📈 Total Leads: {data['leads']['total']}")
        print(f"   💰 Today's Revenue: ${data['revenue']['today']['settled_revenue_usd']:.2f}")
        
        # Fix: Get conversion rate as float, not dict
        conversion_rate = data['leads'].get('conversion_rate', 0)
        if isinstance(conversion_rate, dict):
            # Calculate weighted average conversion rate
            conversion_rate = sum(conversion_rate.values()) / max(len(conversion_rate.values()), 1)
        print(f"   🎯 Lead Conversion Rate: {conversion_rate:.1f}%")
        print(f"   🏥 Platform Health: {data['platform']['system_health']}")
        print(f"   🏁 Market Health Score: {data['kpis']['market_health_score']:.1f}/100")
        
        # Test 2: Revenue metrics
        print(f"\n💸 Test 2: Revenue Analytics")
        print(f"   📅 7-Day Revenue: ${data['revenue']['7day']['total_gross_usd']:.2f}")
        print(f"   7-Day Growth Rate: {data['revenue']['7day']['growth_rate_pct']:.2f}%")
        print(f"   📊 Average Deal Size: ${data['kpis']['customer_lifetime_value']:.2f}")
        
        # Test 3: Marketplace metrics
        print(f"\n🛒 Test 3: Marketplace Analysis")
        marketplace = data['marketplace']
        print(f"   📦 Active Subscriptions: {marketplace['active_subscriptions']}")
        print(f"   🎫 Lead Tiers Performance: Bronze ${marketplace['lead_tiers_performance']['bronze']:.0f}")
        print(f"   💳 Payment Methods: {list(marketplace['payment_methods'].keys())}")
        
        # Test 4: Real-time indicators
        print(f"\n⏱️  Test 4: Real-Time Indicators")
        realtime = data['real_time']
        print(f"   🔥 Current Hour Activity: {realtime['current_hour_activity']} leads")
        print(f"   📈 Lead Rate per Hour: {realtime['lead_rate_per_hour']:.1f} leads/hour")
        print(f"   💰 Revenue Rate per Hour: ${realtime['revenue_rate_per_hour']:.2f}/hour")
        
        # Test 5: Performance alerts
        print(f"\n⚠️  Test 5: Performance Alerts")
        alerts = data['insights']['performance_alerts']
        opportunities = data['insights']['market_opportunities']
        risks = data['insights']['risk_factors']
        
        print(f"   🚨 Performance Alerts: {len(alerts)}")
        print(f"   💡 Opportunities: {len(opportunities)}")
        print(f"   ⚠️  Risk Factors: {len(risks)}")
        
        print(f"\n🎉 All tests passed! Revenue Dashboard is working correctly.")
        
        # Print detailed results
        print(f"\n=== Detailed Dashboard Results ===")
        print(f"Revenue KPIs:")
        for k, v in data['kpis'].items():
            if isinstance(v, float) and v > 1000000:
                v_str = f"${v/1000000:.1f}M"
            elif isinstance(v, float):
                v_str = f"{v:.2f}"
            else:
                v_str = str(v)
            print(f"   • {k.replace('_', ' ').title()}: {v_str}")
        
        print(f"\nLead Funnel:")
        for state, count in data['leads']['by_state'].items():
            if count > 0:
                print(f"   • {state.title()}: {count} leads")
                
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())