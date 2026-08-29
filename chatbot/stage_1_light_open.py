# Stage 1: Light Open — Zero business content
# Real pipeline from /root/empire_ai_senior_architect_blueprint.txt Section 3
# Uses: video_editing_agent.py + omega_os.py + openrouter_api_key
# Vault: 0x1339b487046B0ad924a10c20b1791608EA8595a8 — REAL, NO PLACEHOLDER
# Status: Ready — needs real group contact with existing prospects (200/201/202)

def stage_1_hook(name, city, shop_name=""):
    hooks = [
        f"Hey {name}, thanks for the add! How is everything going with your shop over in {city} this year?",
        f"Hey {name}, saw your recent post about scaling your team. Did you end up finding the right techs?",
        f"Hey {name}, noticed you run {shop_name or 'your shop'}. Are your bays fully booked out this week or still looking for a few more cars?"
    ]
    return hooks
