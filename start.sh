#!/bin/bash
# start.sh - Main entrypoint untuk Railway

set -e

echo "============================================"
echo "🚀 Starting Nanobot AI Agent System"
echo "============================================"

# 1. Start LiteLLM Proxy (background)
echo "📡 Starting LiteLLM Proxy..."
python -m litellm.proxy.proxy_cli \
    --config litellm_config.yaml \
    --port ${LITELLM_PORT:-4000} \
    --host 0.0.0.0 \
    --num_workers 2 &
LITELLM_PID=$!
echo "   LiteLLM PID: $LITELLM_PID"

# Tunggu LiteLLM ready
echo "   Waiting for LiteLLM to be ready..."
for i in $(seq 1 30); do
    if curl -s http://localhost:${LITELLM_PORT:-4000}/health > /dev/null 2>&1; then
        echo "   ✅ LiteLLM is ready!"
        break
    fi
    sleep 2
done

# 2. Start Nanobot (background)
echo "🤖 Starting Nanobot..."
if [ -f "main.py" ]; then
    python main.py &
elif [ -f "app.py" ]; then
    python app.py &
else
    echo "   ⚠️ Nanobot main file not found, skipping..."
fi
NANOBOT_PID=$!
echo "   Nanobot PID: $NANOBOT_PID"

# Tunggu Nanobot ready
sleep 5

# 3. Start Telegram Bot (foreground - main process)
echo "💬 Starting Telegram Bot..."
python telegram_bot.py

# Cleanup
kill $LITELLM_PID $NANOBOT_PID 2>/dev/null || true
