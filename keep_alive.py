"""
Keep Alive Script for Render Free Tier
This pings the app every 10 minutes to prevent sleep
"""

import os
import time
import threading
import requests
from app import app
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def keep_alive():
    """Ping the app every 10 minutes"""
    while True:
        try:
            # Get Render URL from environment
            render_url = os.environ.get('RENDER_EXTERNAL_URL')
            if render_url:
                response = requests.get(f"{render_url}/health", timeout=10)
                if response.status_code == 200:
                    logger.info(f"✅ Ping successful at {time.ctime()}")
                else:
                    logger.warning(f"⚠️ Ping failed: {response.status_code}")
            else:
                logger.info("🔄 Not on Render, no ping needed")
        except Exception as e:
            logger.error(f"❌ Ping error: {e}")
        
        # Wait 10 minutes (600 seconds)
        time.sleep(600)

def start_flask():
    """Start Flask app"""
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🚀 Starting Flask on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == '__main__':
    # Only run keep_alive on Render
    if os.environ.get('RENDER'):
        logger.info("🏃 Starting keep_alive thread for Render")
        # Start keep_alive in background thread
        keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
        keep_alive_thread.start()
    
    # Start Flask app
    start_flask()