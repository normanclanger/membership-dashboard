#!/bin/bash

set -e

echo "=============================================="
echo " Local disaster-recovery development"
echo "=============================================="

cd ~/membership-dashboard

source .venv/bin/activate
source ~/.membership-dashboard/supabase.env

export HUGO_API_MODE=LOCAL
export API_MODE=LOCAL

echo "API_MODE: $API_MODE"
echo "HUGO_API_MODE: $HUGO_API_MODE"
echo
echo "Starting Flask DR proxy..."
echo

python flask-dr/proxy.py &
FLASK_PID=$!

cleanup() {
    echo
    echo "Stopping Flask DR proxy..."
    kill "$FLASK_PID" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

sleep 2

echo
echo "Starting Hugo..."
echo

cd ~/membership-dashboard/hugo

hugo server -D

