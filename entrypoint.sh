
#!/bin/sh

if [ -z "$LITELLM_MASTER_KEY" ]; then
  echo "ERROR: Missing LITELLM_MASTER_KEY"
  exit 1
fi

if [ -z "$LITELLM_PROXY_URL" ]; then
  echo "ERROR: Missing LITELLM_PROXY_URL"
  exit 1
fi

sed -i "s|${LITELLM_MASTER_KEY}|$LITELLM_MASTER_KEY|g" /app/config.json
sed -i "s|${LITELLM_PROXY_URL}|$LITELLM_PROXY_URL|g" /app/config.json

node dist/server.js
