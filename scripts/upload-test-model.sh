#!/bin/bash

# Upload test Rhino file using the real upload API flow
# This script tests the complete upload pipeline:
# 1. Generate presigned URL
# 2. Upload file to Supabase Storage
# 3. Confirm upload and trigger validation

set -e

BACKEND_URL="${1:-http://localhost:8000}"
TEST_FILE="tests/fixtures/test-model.3dm"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🚀 Uploading Rhino file to Sagrada Família Parts Manager"
echo "================================================"
echo ""

# Check file exists
if [ ! -f "$TEST_FILE" ]; then
    echo -e "${RED}❌ Error: Test file not found: $TEST_FILE${NC}"
    exit 1
fi

FILE_SIZE=$(stat -f%z "$TEST_FILE" 2>/dev/null || stat -c%s "$TEST_FILE" 2>/dev/null)
echo "📁 File: $TEST_FILE"
echo "📊 Size: $FILE_SIZE bytes"
echo ""

# Step 1: Generate presigned URL
echo "🔑 Step 1: Generating presigned upload URL..."
UPLOAD_RESPONSE=$(curl -s -X POST "$BACKEND_URL/api/upload/url" \
  -H "Content-Type: application/json" \
  -d "{\"filename\": \"test-model.3dm\", \"size\": $FILE_SIZE}")

# Check for errors
if echo "$UPLOAD_RESPONSE" | grep -q '"detail"'; then
    echo -e "${RED}❌ Error generating upload URL:${NC}"
    echo "$UPLOAD_RESPONSE" | jq
    exit 1
fi

FILE_ID=$(echo "$UPLOAD_RESPONSE" | jq -r '.file_id')
UPLOAD_URL=$(echo "$UPLOAD_RESPONSE" | jq -r '.upload_url')
FILE_KEY=$(echo "$UPLOAD_RESPONSE" | jq -r '.file_key')

echo -e "${GREEN}✅ Presigned URL generated${NC}"
echo "   File ID: $FILE_ID"
echo "   File Key: $FILE_KEY"
echo ""

# Step 2: Upload file to Supabase Storage
echo "📤 Step 2: Uploading file to Supabase Storage..."
UPLOAD_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "$UPLOAD_URL" \
  -H "Content-Type: model/vnd.3dm" \
  --data-binary "@$TEST_FILE")

if [ "$UPLOAD_STATUS" != "200" ]; then
    echo -e "${RED}❌ Upload failed with status: $UPLOAD_STATUS${NC}"
    exit 1
fi

echo -e "${GREEN}✅ File uploaded to Supabase Storage${NC}"
echo ""

# Step 3: Confirm upload
echo "✔️  Step 3: Confirming upload and triggering validation..."
CONFIRM_RESPONSE=$(curl -s -X POST "$BACKEND_URL/api/upload/confirm" \
  -H "Content-Type: application/json" \
  -d "{\"file_id\": \"$FILE_ID\", \"file_key\": \"$FILE_KEY\"}")

# Check for errors
if echo "$CONFIRM_RESPONSE" | grep -q '"success": *false'; then
    echo -e "${RED}❌ Error confirming upload:${NC}"
    echo "$CONFIRM_RESPONSE" | jq
    exit 1
fi

EVENT_ID=$(echo "$CONFIRM_RESPONSE" | jq -r '.event_id')
TASK_ID=$(echo "$CONFIRM_RESPONSE" | jq -r '.task_id')

echo -e "${GREEN}✅ Upload confirmed and validation enqueued${NC}"
echo "   Event ID: $EVENT_ID"
echo "   Celery Task ID: $TASK_ID"
echo ""

# Step 4: Monitor validation progress
echo "⏳ Step 4: Monitoring validation progress..."
echo "   (Checking status every 2 seconds for up to 60 seconds)"
echo ""

MAX_ATTEMPTS=30
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    ATTEMPT=$((ATTEMPT + 1))
    
    # Check event status
    EVENT_STATUS=$(curl -s "$BACKEND_URL/api/events/$EVENT_ID" | jq -r '.status')
    
    if [ "$EVENT_STATUS" == "completed" ]; then
        echo -e "${GREEN}✅ Validation completed successfully!${NC}"
        echo ""
        
        # Get full event details
        curl -s "$BACKEND_URL/api/events/$EVENT_ID" | jq '{
            event_id: .id,
            status: .status,
            file_name: .file_name,
            created_at: .created_at,
            completed_at: .completed_at
        }'
        echo ""
        
        # Check blocks created
        echo "📦 Blocks extracted from file:"
        curl -s "$BACKEND_URL/api/elements?limit=10" | jq '{
            total: .meta.total,
            with_geometry: .meta.filtered,
            blocks: .elements[:6] | map({
                iso_code: .iso_code,
                material: .material_type,
                status: .status,
                has_glb: (.low_poly_url != null),
                has_bbox: (.bbox != null)
            })
        }'
        
        exit 0
    elif [ "$EVENT_STATUS" == "failed" ]; then
        echo -e "${RED}❌ Validation failed${NC}"
        curl -s "$BACKEND_URL/api/events/$EVENT_ID" | jq
        exit 1
    elif [ "$EVENT_STATUS" == "processing" ]; then
        echo -n "."
        sleep 2
    else
        echo -e "${YELLOW}⏳ Status: $EVENT_STATUS${NC}"
        sleep 2
    fi
done

echo ""
echo -e "${YELLOW}⚠️  Validation still in progress after 60 seconds${NC}"
echo "   Event ID: $EVENT_ID"
echo "   Check status manually: curl $BACKEND_URL/api/events/$EVENT_ID"
echo ""
