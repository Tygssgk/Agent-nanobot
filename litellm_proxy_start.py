#!/usr/bin/env python3
"""
LiteLLM Proxy Starter untuk Railway
Menjalankan LiteLLM proxy server dengan config load balancing
"""

import subprocess
import sys
import os

def start_litellm_proxy():
    port = os.environ.get("LITELLM_PORT", "4000")
    config_path = os.environ.get("LITELLM_CONFIG", "litellm_config.yaml")
    
    cmd = [
        sys.executable, "-m", "litellm.proxy.proxy_cli",
        "--config", config_path,
        "--port", port,
        "--host", "0.0.0.0",
        "--num_workers", "2",
        "--detailed_debug" if os.environ.get("DEBUG") == "true" else "--no-debug"
    ]
    
    print(f"🚀 Starting LiteLLM Proxy on port {port}...")
    print(f"📋 Config: {config_path}")
    print(f"🔑 API Keys configured:")
    print(f"   Flash Keys: {sum(1 for k in ['GOOGLE_API_KEY_FLASH_1', 'GOOGLE_API_KEY_FLASH_2', 'GOOGLE_API_KEY_FLASH_3'] if os.environ.get(k))}/3")
    print(f"   Pro Keys: {sum(1 for k in ['GOOGLE_API_KEY_PRO_1', 'GOOGLE_API_KEY_PRO_2'] if os.environ.get(k))}/2")
    
    subprocess.run(cmd)

if __name__ == "__main__":
    start_litellm_proxy()
