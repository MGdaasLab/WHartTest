#!/usr/bin/env bash

echo "Loading WHartTest Docker images..."
echo

count=0
shopt -s nullglob
for f in *-*.tar; do
    echo "[LOAD] $f"
    if docker load -i "$f" < /dev/null; then
        echo "✅ Loaded: $f"
        ((count++))
    else
        echo "❌ Failed: $f"
    fi
    echo
done
shopt -u nullglob

echo "Loaded $count image(s)."
echo "Run: docker compose up -d"