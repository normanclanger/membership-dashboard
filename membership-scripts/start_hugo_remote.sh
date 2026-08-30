#!/bin/bash

set -e

echo "=============================================="
echo " Hugo development - remote API"
echo "=============================================="

cd ~/membership-dashboard

source .venv/bin/activate
source ~/.membership-dashboard/supabase.env

export HUGO_API_MODE=REMOTE

echo "API_MODE: $API_MODE"
echo "API calls will use the remote API Gateway."
echo

cd ~/membership-dashboard/hugo

hugo server -D
