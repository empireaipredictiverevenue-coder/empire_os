#!/usr/bin/env python3
"""edge-tts integration for Empire OS switchboard."""
import asyncio
import edge_tts
import tempfile
import os
from pathlib import Path

VOICES = {
    "en-US-AriaNeural": "Female, professional, clear",
    "en-US-DavisNeural": "Male, professional, confident",
    "en-US-GuyNeural": "Male, casual, friendly",
    "en-US-JennyNeural": "Female, warm, engaging",
}

async def generate_tts(text: str, voice: str = "en-US-AriaNeural", output_path: str = None) -> str:
    """Generate TTS audio file. Returns path to the audio file."""
    if voice not in VOICES:
        voice = "en-US-AriaNeural"
    
    if output_path is None:
        output_path = f"/tmp/tts_{os.getpid()}_{hash(text) & 0xffffffff}.mp3"
    
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)
    return output_path

def tts_sync(text: str, voice: str = "en-US-AriaNeural", output_path: str = None) -> str:
    """Synchronous wrapper for TTS generation."""
    return asyncio.run(generate_tts(text, voice, output_path))

# Pre-generated scripts for switchboard
SCRIPTS = {
    "awaiting_payment": """Hi, this is Empire AI. We noticed your account shows an awaiting payment status. Your monthly seat is ready to activate — just send the USDC amount shown in your dashboard to the BSC wallet address. Once confirmed, leads will start flowing immediately. No contracts, no cards. Call us back if you need help.""",
    "trial_welcome": """Welcome to Empire AI! You've been matched with exclusive leads in your niche. Your trial includes 5 free leads delivered to your CRM or inbox. After the trial, it's just the per-lead rate in USDC on BSC. No lock-in, cancel anytime. Check your email for the dashboard link.""",
    "payment_received": """Payment confirmed! Your seat is now active. Leads matching your niche will start delivering to your webhook or inbox within minutes. You'll pay per delivered lead at your tier rate. Thanks for joining Empire AI.""",
    "follow_up": """Hi, this is Empire AI following up on your lead inquiry. We have fresh prospects in your niche ready to deliver. If you're still interested, just fund your seat and we'll turn on the pipeline. No pressure — here when you're ready.""",
}

def get_script(key: str) -> str:
    """Get a pre-defined script by key."""
    return SCRIPTS.get(key, SCRIPTS["awaiting_payment"])

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
    else:
        text = "Hello, this is Empire AI. Your seat is ready to activate."
    out = tts_sync(text)
    print(f"Generated: {out}")
