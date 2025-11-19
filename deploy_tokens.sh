#!/bin/bash
# Deploy fresh tokens to production Ubuntu server
# Run this on your Windows machine or WSL to copy the token file to the server

set -e  # Exit on error

# Configuration
SERVER="ubuntu@YOUR_SERVER_IP"
REMOTE_PATH="/home/ubuntu/webhook_magic/Xero-Payroll"

echo "======================================================================"
echo "DEPLOYING FRESH XERO TOKENS TO PRODUCTION"
echo "======================================================================"
echo ""

# Check if token file exists locally
if [ ! -f "xero_tokens.json" ]; then
    echo "ERROR: xero_tokens.json not found in current directory"
    echo "Run 'python quick_authorize.py' first to get fresh tokens"
    exit 1
fi

echo "Token file found: xero_tokens.json"
echo "Server: $SERVER"
echo "Remote path: $REMOTE_PATH"
echo ""

# Copy file to server
echo "Copying token file to server..."
scp xero_tokens.json "$SERVER:$REMOTE_PATH/"

if [ $? -eq 0 ]; then
    echo "✓ File copied successfully"
    echo ""
    
    # Set permissions
    echo "Setting file permissions to 666..."
    ssh "$SERVER" "chmod 666 $REMOTE_PATH/xero_tokens.json"
    
    echo "✓ Permissions set"
    echo ""
    echo "======================================================================"
    echo "✓ DEPLOYMENT COMPLETE!"
    echo "======================================================================"
    echo ""
    echo "The fresh token is now on the production server."
    echo "Next webhook call should work without token errors!"
    echo ""
else
    echo "✗ Failed to copy file to server"
    exit 1
fi
