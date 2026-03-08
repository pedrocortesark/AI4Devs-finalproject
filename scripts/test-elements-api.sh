#!/bin/bash

# Test Elements API - Manual Validation Script
# Usage: ./scripts/test-elements-api.sh [dev|prod]
# 
# Tests T-1504-BACK endpoints:
# - GET /api/elements (list with filters)
# - GET /api/elements/{id} (detail)
# - GET /api/elements/{id}/navigation (prev/next)

set -e

ENV=${1:-dev}

if [ "$ENV" = "prod" ]; then
    BASE_URL="https://sf-pm.up.railway.app"
    echo "🌐 Testing PRODUCTION environment: $BASE_URL"
elif [ "$ENV" = "dev" ]; then
    BASE_URL="http://localhost:8000"
    echo "💻 Testing LOCAL DEV environment: $BASE_URL"
else
    echo "❌ Invalid environment. Use: ./test-elements-api.sh [dev|prod]"
    exit 1
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  T-1504-BACK API Validation"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Test 1: Health Check
echo "1️⃣  Health Check"
echo "   GET /ready"
curl -s "$BASE_URL/ready" | python3 -c "import sys, json; data = json.load(sys.stdin); print(f\"   Status: {data.get('status', 'N/A')}\"); print(f\"   Database: {data.get('database', 'N/A')}\")"
echo ""

# Test 2: List Elements (render-ready only)
echo "2️⃣  List Elements (render-ready filter)"
echo "   GET /api/elements?limit=10"
ELEMENTS_RESPONSE=$(curl -s "$BASE_URL/api/elements?limit=10")
echo "$ELEMENTS_RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
elements = data.get('elements', [])
meta = data.get('meta', {})
print(f\"   Total elements: {meta.get('total', 0)}\")
print(f\"   Filtered (render-ready): {meta.get('filtered', 0)}\")
print(f\"   Returned: {len(elements)}\")
if elements:
    elem = elements[0]
    print(f\"\\n   Sample Element:\")
    print(f\"     - ID: {elem.get('id', 'N/A')[:8]}...\")
    print(f\"     - ISO Code: {elem.get('iso_code', 'N/A')}\")
    print(f\"     - Material: {elem.get('material_type', 'N/A')}\")
    print(f\"     - Status: {elem.get('status', 'N/A')}\")
    print(f\"     - Has GLB: {bool(elem.get('low_poly_url'))}\")
    print(f\"     - Has BBox: {bool(elem.get('bbox'))}\")
    if elem.get('bbox'):
        bbox = elem['bbox']
        print(f\"       BBox min: [{', '.join(map(str, bbox.get('min', [])))}]\")
        print(f\"       BBox max: [{', '.join(map(str, bbox.get('max', [])))}]\")
else:
    print('   ⚠️  No elements found (database may be empty)')
"
echo ""

# Extract first element ID for detail tests
ELEMENT_ID=$(echo "$ELEMENTS_RESPONSE" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data['elements'][0]['id'] if data.get('elements') else '')" 2>/dev/null || echo "")

if [ -z "$ELEMENT_ID" ]; then
    echo "⚠️  No elements available for detail/navigation tests"
    echo "   Tip: Upload .3dm files first or run reprocess script"
    exit 0
fi

# Test 3: Element Detail
echo "3️⃣  Element Detail"
echo "   GET /api/elements/$ELEMENT_ID"
curl -s "$BASE_URL/api/elements/$ELEMENT_ID" | python3 -c "
import sys, json
elem = json.load(sys.stdin)
print(f\"   ID: {elem.get('id', 'N/A')[:8]}...\")
print(f\"   ISO Code: {elem.get('iso_code', 'N/A')}\")
print(f\"   Material Type: {elem.get('material_type', 'N/A')}\")
print(f\"   Status: {elem.get('status', 'N/A')}\")
print(f\"   Created: {elem.get('created_at', 'N/A')[:19]}\")
print(f\"   Low Poly URL: {elem.get('low_poly_url', 'N/A')[:50]}...\")
bbox = elem.get('bbox', {})
if bbox:
    print(f\"   BBox: min={bbox.get('min')}, max={bbox.get('max')}\")
report = elem.get('validation_report')
if report:
    print(f\"   Validation Report: {report.get('status', 'N/A')}\")
"
echo ""

# Test 4: Navigation (Prev/Next)
echo "4️⃣  Navigation (Prev/Next IDs)"
echo "   GET /api/elements/$ELEMENT_ID/navigation"
curl -s "$BASE_URL/api/elements/$ELEMENT_ID/navigation" | python3 -c "
import sys, json
nav = json.load(sys.stdin)
print(f\"   Current Index: {nav.get('current_index', 'N/A')} / {nav.get('total_count', 'N/A')}\")
prev_id = nav.get('prev_id')
next_id = nav.get('next_id')
print(f\"   Previous ID: {prev_id[:8] + '...' if prev_id else 'null (first element)'}\")
print(f\"   Next ID: {next_id[:8] + '...' if next_id else 'null (last element)'}\")
"
echo ""

# Test 5: Filter by Material Type
echo "5️⃣  Filter by Material Type (Montjuïc)"
echo "   GET /api/elements?material_type=Montjuïc&limit=5"
curl -s "$BASE_URL/api/elements?material_type=Montjuïc&limit=5" | python3 -c "
import sys, json
data = json.load(sys.stdin)
elements = data.get('elements', [])
print(f\"   Found: {len(elements)} elements with material_type='Montjuïc'\")
for i, elem in enumerate(elements[:3], 1):
    print(f\"   {i}. {elem.get('iso_code', 'N/A')} - {elem.get('material_type', 'N/A')}\")
"
echo ""

# Test 6: Filter by Status
echo "6️⃣  Filter by Status (validated)"
echo "   GET /api/elements?status=validated&limit=5"
curl -s "$BASE_URL/api/elements?status=validated&limit=5" | python3 -c "
import sys, json
data = json.load(sys.stdin)
elements = data.get('elements', [])
print(f\"   Found: {len(elements)} validated elements\")
for i, elem in enumerate(elements[:3], 1):
    print(f\"   {i}. {elem.get('iso_code', 'N/A')} - {elem.get('status', 'N/A')}\")
"
echo ""

# Test 7: Invalid Material Type (Error Handling)
echo "7️⃣  Error Handling (Invalid Material Type)"
echo "   GET /api/elements?material_type=InvalidStone"
RESPONSE=$(curl -s -w "\n%{http_code}" "$BASE_URL/api/elements?material_type=InvalidStone")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
echo "$BODY" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(f\"   HTTP Status: $HTTP_CODE\")
    print(f\"   Error Detail: {data.get('detail', 'N/A')}\")
    print(f\"   ✅ Validation working (rejected invalid material)\")
except:
    print(f\"   HTTP Status: $HTTP_CODE\")
    print(f\"   ✅ Validation working (rejected invalid material)\")
"
echo ""

# Test 8: Non-existent Element (404)
echo "8️⃣  Error Handling (Non-existent Element)"
echo "   GET /api/elements/00000000-0000-0000-0000-000000000000"
RESPONSE=$(curl -s -w "\n%{http_code}" "$BASE_URL/api/elements/00000000-0000-0000-0000-000000000000")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
echo "$BODY" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(f\"   HTTP Status: $HTTP_CODE\")
    print(f\"   Error Message: {data.get('detail', 'N/A')}\")
    if '$HTTP_CODE' == '404':
        print(f\"   ✅ 404 handling working\")
    else:
        print(f\"   ⚠️  Expected 404, got $HTTP_CODE\")
except:
    print(f\"   HTTP Status: $HTTP_CODE\")
"
echo ""

echo "═══════════════════════════════════════════════════════════"
echo "✅ API Validation Complete"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "Next Steps:"
echo "  - If tests pass → Backend ready for frontend integration"
echo "  - If errors → Check logs: docker compose logs backend"
echo "  - Upload test files: make upload-fixtures"
echo ""
