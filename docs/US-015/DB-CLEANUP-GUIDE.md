# Database Cleanup & Fresh Ingestion Guide

**Context:** US-015 Phase 0 — Before implementing the new Element model, we need a clean database state.

**Problem:** Current database has 1,356 obsolete test elements that don't match the new Element contract (missing `material_type` enum, workshops columns present, etc.).

**Solution:** Full database reset + fresh ingestion with 6 real Rhino pieces.

---

## 📋 Pre-Cleanup Checklist

Before running the cleanup script, verify:

- [ ] **Docker services running:** `docker compose ps` shows all containers healthy
- [ ] **Celery worker ready:** `docker compose logs agent-worker | grep "ready"` shows worker is listening
- [ ] **Rhino file prepared:** You have a `.3dm` file with 6 architectural pieces ready
- [ ] **UserStrings verified:** Each piece in the Rhino file has a UserString with key `"Codi"` (e.g., `"SF-C12-D-001"`)
- [ ] **Backup taken (optional):** If you want to preserve any test data, export it now

---

## 🧹 Step 1: Clean Database (Full Reset)

Run the cleanup script:

```bash
docker compose run --rm backend python infra/clean_database_full.py
```

**What this script does:**
1. Shows current state (blocks, events, storage files count)
2. Asks for explicit confirmation: `DELETE ALL`
3. Deletes all rows from `blocks` table (1,356 elements)
4. Deletes all rows from `events` table (processing logs)
5. Deletes all GLB files from Supabase Storage (`models/low-poly/*.glb`)
6. Shows deletion summary

**Expected output:**
```
📊 Current Database State:
   • Blocks (elements): 1356
   • Events (logs): XXXX
   • Storage GLB files: XXXX

⚠️  DATABASE FULL RESET - CONFIRMATION REQUIRED
Type 'DELETE ALL' to proceed: DELETE ALL

✅ DATABASE CLEANUP COMPLETE
   • Blocks deleted: 1356/1356
   • Events deleted: XXXX/XXXX
   • Storage files deleted: XXXX/XXXX
```

⚠️ **WARNING:** This operation is **IRREVERSIBLE**. All test data will be permanently deleted.

---

## 📥 Step 2: Fresh Ingestion (6 Rhino Pieces)

After cleanup, upload your Rhino file:

### 2.1 Start Frontend (if not running)

```bash
docker compose up -d frontend
open http://localhost:5173
```

### 2.2 Upload Rhino File

1. Navigate to **http://localhost:5173**
2. Click **"Upload 3DM File"** button
3. Select your `.3dm` file with 6 pieces
4. Wait for upload confirmation

### 2.3 Monitor Processing

**Backend logs (watch for file reception):**
```bash
docker compose logs -f backend | grep -E "(POST /api/upload|Rhino file|blocks created)"
```

**Celery worker logs (watch for geometry processing):**
```bash
docker compose logs -f agent-worker | grep -E "(Processing block|GLB generated|bbox calculated)"
```

**Expected flow:**
1. **Upload endpoint:** Backend receives `.3dm` file → Creates N block records (N = 6)
2. **Celery tasks:** Worker processes each block → Generates GLB → Calculates bbox → Updates `low_poly_url`
3. **Status updates:** Each block transitions: `uploaded` → `processing` → `validated`

### 2.4 Verify Ingestion

Check database state:

```bash
docker compose exec backend python -c "
from infra.supabase_client import get_supabase_client
supabase = get_supabase_client()

# Count blocks
result = supabase.table('blocks').select('id, iso_code, status, low_poly_url, bbox').execute()
blocks = result.data

print(f'📊 Total blocks: {len(blocks)}')
print(f'📊 Validated: {len([b for b in blocks if b[\"status\"] == \"validated\"])}')
print(f'📊 With geometry: {len([b for b in blocks if b.get(\"low_poly_url\")])}')
print(f'📊 With bbox: {len([b for b in blocks if b.get(\"bbox\")])}')

print('\n📝 Sample blocks:')
for block in blocks[:3]:
    print(f\"  - {block['iso_code']}: status={block['status']}, glb={bool(block.get('low_poly_url'))}, bbox={bool(block.get('bbox'))}\")
"
```

**Expected output:**
```
📊 Total blocks: 6
📊 Validated: 6
📊 With geometry: 6
📊 With bbox: 6

📝 Sample blocks:
  - SF-C12-D-001: status=validated, glb=True, bbox=True
  - SF-C12-D-002: status=validated, glb=True, bbox=True
  - SF-C12-D-003: status=validated, glb=True, bbox=True
```

### 2.5 Test 3D Canvas

1. Navigate to **http://localhost:5173**
2. Verify all 6 elements appear in the 3D canvas
3. Check that GLB models load correctly
4. Verify bbox positioning (elements should be spatially positioned)

---

## 🔍 Troubleshooting

### ❌ Problem: "No blocks created after upload"

**Check:**
```bash
docker compose logs backend --tail=50 | grep -E "(ERROR|Exception|Traceback)"
```

**Common causes:**
- Rhino file corrupted or empty
- Backend not connected to Supabase
- RLS policies blocking inserts

**Fix:**
```bash
# Restart services
docker compose restart backend agent-worker
```

---

### ❌ Problem: "Blocks created but status stuck at 'processing'"

**Check Celery worker:**
```bash
docker compose logs agent-worker --tail=100 | grep -E "(ERROR|FAILED|Traceback)"
```

**Common causes:**
- Celery worker not running
- rhino3dm parsing error (invalid geometry)
- trimesh crash (bbox calculation failed)

**Fix:**
```bash
# Restart Celery worker
docker compose restart agent-worker

# Check worker is ready
docker compose logs agent-worker | grep "ready"
```

---

### ❌ Problem: "Blocks validated but no GLB URL"

**Check:**
```bash
docker compose exec backend python -c "
from infra.supabase_client import get_supabase_client
supabase = get_supabase_client()

# List storage files
files = supabase.storage.from_('models').list('low-poly/')
print(f'Storage GLB files: {len(files)}')
for f in files[:5]:
    print(f\"  - {f['name']}\")
"
```

**Common causes:**
- Supabase Storage credentials invalid (`SUPABASE_KEY` wrong)
- RLS policy blocking file upload
- Worker generated GLB but failed to upload

**Fix:**
1. Verify `.env` has correct `SUPABASE_URL` and `SUPABASE_KEY`
2. Check Supabase dashboard: Storage → models → Policies
3. Re-run processing: `docker compose run --rm backend python infra/reprocess_parts_with_bbox.py`

---

## 🎯 Success Criteria

✅ Database cleanup successful when:
- `blocks` table shows 0 rows
- `events` table shows 0 rows
- Storage `models/low-poly/` folder is empty

✅ Fresh ingestion successful when:
- 6 blocks created (matching Rhino InstanceObjects count)
- All 6 blocks have `status = "validated"`
- All 6 blocks have `low_poly_url` (HTTPS URL)
- All 6 blocks have `bbox` (structure: `{"min": [x,y,z], "max": [x,y,z]}`)
- All 6 blocks have `iso_code` extracted from UserString "Codi"
- Frontend 3D canvas shows all 6 models rendered correctly

---

## 📚 Next Steps After Ingestion

Once you have 6 clean elements in the database:

1. **T-1501-DB:** Execute Element model migration
   - Add `material_type` column (TEXT or ENUM)
   - Drop `workshop_id` and `workshop_name` columns
   - Add check constraint: `material_type IN ('Stone', 'Ceramic')`
   - Verify 6 elements still load correctly

2. **T-1502-INFRA:** Implement storage path conventions
   - Refactor `generate_glb_storage_path()` with strict naming

3. **T-1503-AGENT:** Update Rhino parser
   - Extract `material_type` from UserString or default to "Stone"
   - Validate material_type is in enum before saving

4. **T-1504-BACK:** Update API with Element contract
   - Change `PartCanvasItem` → `Element` in schemas
   - Add MaterialType enum to Pydantic
   - Filter query: `WHERE low_poly_url IS NOT NULL AND bbox IS NOT NULL`

5. **T-1505-FRONT:** Update frontend with Zod validation
   - Rename interfaces to `Element` / `ElementDetail`
   - Add `MaterialTypeSchema` Zod validation

6. **T-1507-TEST:** E2E test with 6 elements
   - Upload → Process → Canvas render
   - Assert all 6 appear in canvas with correct material_type

---

## 📖 References

- [JSON-CONTRACTS.md](./JSON-CONTRACTS.md) — Element model specification
- [US-015/README.md](./README.md) — Full Epic roadmap
- [CLAUDE.md](../../CLAUDE.md) — Build commands and architecture
- [infra/clean_database_full.py](../../infra/clean_database_full.py) — Cleanup script source

---

**Author:** SF-PM DevTeam  
**Date:** 2026-03-06  
**Context:** US-015 Phase 0 — Prepare clean state for Element model migration
