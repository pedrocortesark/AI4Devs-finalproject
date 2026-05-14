# US-018 Deployment Checklist

**User Story:** LangGraph Agent Implementation (The Librarian)  
**Sprint:** Sprint 10  
**Date:** 2026-05-14  
**Status:** ✅ READY FOR PRODUCTION

---

## Pre-Deployment Validation ✅

### Code Quality
- ✅ All 27 critical tests PASS (Rate Limiter + Prometheus)
- ✅ Zero regression (419+ baseline tests maintained)
- ✅ Branch merged to `main` (commit: c08b59a)
- ✅ Feature branch cleaned up (local + remote deleted)

### Build Artifacts
- ✅ Frontend built: `src/frontend/dist/index.html` exists
- ✅ Backend Dockerfile updated (includes new dependencies)
- ✅ Docker Compose validated locally

---

## Railway Backend Deployment 🚂

### New Environment Variables (Required)

Add to Railway backend service:

```bash
# T-1810: OpenAI Rate Limiting
OPENAI_RATE_LIMIT_PER_MIN=5           # Start conservative (Free Tier: 3-5 RPM)
OPENAI_MAX_CONCURRENT=3                # Max simultaneous OpenAI requests
OPENAI_RATE_LIMIT_BUCKET_SIZE=5        # Burst allowance
OPENAI_RATE_LIMITER_TIMEOUT=30.0       # Seconds before fallback

# Existing (verify present)
OPENAI_API_KEY=sk-...                  # Your OpenAI API key
REDIS_PASSWORD=...                     # Redis authentication
SUPABASE_URL=https://....supabase.co   # Supabase project URL
SUPABASE_KEY=...                       # Service role key
SUPABASE_DATABASE_URL=postgresql://... # Direct DB connection
```

### Deployment Steps

1. **Push to GitHub** (already done ✅):
   ```bash
   git push origin main
   ```

2. **Railway Auto-Deploy**:
   - Railway detects new commit on `main`
   - Builds Docker image from `src/backend/Dockerfile`
   - Auto-deploys if build succeeds
   - Estimated time: 5-10 minutes

3. **Add Environment Variables**:
   - Navigate to Railway dashboard → backend service → Variables
   - Add 4 new OPENAI_* variables (see above)
   - Railway will restart service automatically

4. **Verify Deployment**:
   ```bash
   # Health check
   curl https://sf-pm-backend.railway.app/health
   
   # New endpoints
   curl https://sf-pm-backend.railway.app/api/metrics/langgraph
   curl https://sf-pm-backend.railway.app/metrics  # Prometheus format
   ```

### Expected Response - Health Check
```json
{
  "status": "healthy",
  "timestamp": "2026-05-14T...",
  "version": "1.0.0",
  "environment": "production"
}
```

### Expected Response - Metrics Endpoint
```json
{
  "total_blocks_processed": 42,
  "classification_distribution": {
    "llm_gpt4": 38,
    "fallback_regex": 4
  },
  "circuit_breaker_trips_24h": 2,
  "processing_time_seconds": {
    "p50": 8.5,
    "p95": 15.2,
    "p99": 22.1
  },
  "llm_confidence_avg_24h": 0.87,
  "window": "24h"
}
```

---

## Vercel Frontend Deployment 🔺

### Environment Variables (Verify Present)

No new variables required for US-018. Verify existing:

```bash
VITE_SUPABASE_URL=https://....supabase.co
VITE_SUPABASE_ANON_KEY=...
VITE_API_URL=https://sf-pm-backend.railway.app
```

### Deployment Steps

1. **Vercel Auto-Deploy** (already configured ✅):
   - Vercel detects new commit on `main`
   - Builds from `src/frontend/`
   - Auto-deploys if build succeeds
   - Estimated time: 3-5 minutes

2. **Verify Deployment**:
   ```bash
   # Frontend loads
   curl -I https://sf-pm.vercel.app
   
   # Progress indicator visible (check browser DevTools)
   # Look for WebSocket connection to Supabase Realtime
   ```

---

## Prometheus + Grafana Setup (Optional, Post-Deployment)

### Prometheus Configuration

1. **Add scrape target** (prometheus.yml):
   ```yaml
   scrape_configs:
     - job_name: 'sf-pm-backend'
       scrape_interval: 15s
       static_configs:
         - targets: ['sf-pm-backend.railway.app:443']
       scheme: https
       metrics_path: '/metrics'
   ```

2. **Verify scraping**:
   ```bash
   # Check Prometheus targets page
   # Status should be "UP" with last scrape < 30s ago
   ```

### Grafana Dashboard Import

1. **Import JSON**:
   - File: `infra/grafana-dashboard-langgraph.json`
   - Grafana UI → Dashboards → Import → Upload JSON
   - Select Prometheus datasource

2. **Verify Panels** (8 total):
   - Classification Distribution (pie chart)
   - Circuit Breaker Trips (timeseries)
   - Processing Time Histogram (histogram)
   - LLM Confidence (gauge)
   - Total Processed (stat)
   - p50/p95/p99 (3 stats)

---

## Post-Deployment Validation 🧪

### 1. Backend Health Checks

```bash
# Health endpoint
curl https://sf-pm-backend.railway.app/health | jq

# Ready endpoint (checks DB + Redis)
curl https://sf-pm-backend.railway.app/ready | jq

# Metrics endpoint
curl https://sf-pm-backend.railway.app/api/metrics/langgraph | jq

# Prometheus endpoint (text format)
curl https://sf-pm-backend.railway.app/metrics | head -20
```

**Expected:** All return 200 OK

### 2. Frontend Functionality

- [ ] Upload page loads (https://sf-pm.vercel.app)
- [ ] File upload works (drag & drop .3dm file)
- [ ] Progress indicator appears during upload
- [ ] 8 steps visible in progress UI:
  1. Upload Iniciado
  2. Extracción Geometría
  3. Validación Nomenclatura
  4. Validación Geometría
  5. Clasificación LLM
  6. Enriquecimiento Metadatos
  7. Generación Reporte
  8. Validación Completa

### 3. LangGraph Workflow E2E

Upload a test .3dm file and verify:

- [ ] File uploaded to Supabase Storage
- [ ] Celery task enqueued (check Railway logs: "Task validation_workflow[...]")
- [ ] LangGraph StateGraph executed (8 nodes logged)
- [ ] Rate limiter active (logs: "Token acquired", "Concurrent slot acquired")
- [ ] Classification completed (LLM or fallback regex)
- [ ] Audit trail created (20-24 events in `events` table)
- [ ] Validation report generated (JSON in `blocks.validation_report`)
- [ ] Block status updated to "validated" or "rejected"
- [ ] Frontend progress indicator updates in real-time

### 4. Rate Limiting Validation

Upload 10 files simultaneously and check Railway logs:

```bash
# Expected logs (search "rate_limiter"):
[INFO] Token acquired from bucket (tokens_remaining=4)
[INFO] Concurrent slot acquired (active_requests=1/3)
[INFO] OpenAI request completed successfully
[INFO] Concurrent slot released (active_requests=0/3)

# If rate limit exceeded:
[WARNING] Rate limiter timeout after 30.0s, using fallback
[INFO] Classification fallback: regex pattern matched
```

**Expected:** No HTTP 429 errors, all files processed (some may use fallback)

### 5. Observability Metrics

After processing 10+ files, check metrics:

```bash
curl https://sf-pm-backend.railway.app/api/metrics/langgraph | jq
```

**Expected values:**
- `total_blocks_processed` > 10
- `classification_distribution.llm_gpt4` > 0 (if rate limit not exceeded)
- `classification_distribution.fallback_regex` >= 0
- `circuit_breaker_trips_24h` >= 0
- `processing_time_seconds.p50` < 15s
- `llm_confidence_avg_24h` > 0.6 (if LLM used)

---

## Monitoring & Alerts 📊

### Redis Keys to Monitor

```bash
# Rate limiter state (using redis-cli)
GET rate_limiter:openai:tokens          # Available tokens (0-5)
GET rate_limiter:openai:concurrent      # Active requests (0-3)
GET rate_limiter:openai:last_refill     # Timestamp

# Metrics cache (60s TTL)
GET metrics:langgraph:latest            # JSON response
TTL metrics:langgraph:latest            # Remaining seconds
```

### Railway Logs to Watch

```bash
# Rate limiter events
grep "rate_limiter" railway.log

# Circuit breaker activations
grep "circuit_breaker" railway.log

# LLM classification errors
grep "LLMClassificationError" railway.log

# OpenAI API errors (should be zero)
grep "HTTP 429" railway.log
```

### Recommended Alerts

1. **Rate Limit Saturation**:
   - Condition: `rate_limiter:openai:tokens == 0` for >60s
   - Action: Increase `OPENAI_RATE_LIMIT_PER_MIN` (requires higher OpenAI tier)

2. **Concurrent Limit Reached**:
   - Condition: `rate_limiter:openai:concurrent >= 3` for >60s
   - Action: Increase `OPENAI_MAX_CONCURRENT` or optimize batch processing

3. **Circuit Breaker High Trip Rate**:
   - Condition: `circuit_breaker_trips_24h > 50`
   - Action: Investigate OpenAI API availability or adjust CB thresholds

4. **Low LLM Confidence**:
   - Condition: `llm_confidence_avg_24h < 0.5`
   - Action: Review classification prompts or fallback regex patterns

---

## Rollback Plan 🔄

If issues occur post-deployment:

### Option 1: Revert Merge Commit

```bash
# Create revert commit
git revert c08b59a -m 1

# Push to main
git push origin main

# Railway/Vercel auto-redeploy previous version (~5 min)
```

### Option 2: Disable New Features via Env Vars

```bash
# Railway dashboard → backend service → Variables
# Set rate limiter to "disabled" mode by removing Redis:
REDIS_URL=  # (empty value triggers graceful degradation)

# Or increase limits to effectively disable:
OPENAI_RATE_LIMIT_PER_MIN=10000
OPENAI_MAX_CONCURRENT=100
```

**Impact:** LangGraph continues working, rate limiting disabled (revert to pre-US-018 behavior)

---

## Success Criteria ✅

- [ ] Backend deploys successfully on Railway
- [ ] Frontend deploys successfully on Vercel
- [ ] All 5 new endpoints return 200 OK:
  - GET /health
  - GET /ready
  - GET /api/metrics/langgraph
  - GET /metrics (Prometheus)
  - POST /api/parts (with LangGraph validation)
- [ ] Rate limiting active (logs confirm token acquisition)
- [ ] Zero HTTP 429 errors during batch upload (10+ files)
- [ ] Progress indicator updates in real-time (frontend)
- [ ] Audit trail created (20-24 events per validation)
- [ ] Metrics endpoint returns valid data
- [ ] Prometheus endpoint scraping works (if configured)

---

## Known Issues & Mitigations ⚠️

### Issue 1: E2E Tests (2/6 SKIPPED)

**Description:** EC-E2E-03 (ChatOpenAI mock timing) and INT-E2E-05 (ThreadPoolExecutor mock propagation) skipped due to tech debt.

**Impact:** Low — Core functionality (4/6 tests) validated. Known issues documented in T-1806-TechnicalSpec.md.

**Mitigation:** Manual E2E validation during deployment (upload 5-10 .3dm files).

### Issue 2: Redis Caching Metrics (60s TTL)

**Description:** First request to `/api/metrics/langgraph` may be slow (~500ms DB query), subsequent requests fast (<5ms Redis cache hit).

**Impact:** Low — Only affects monitoring dashboards, not user-facing features.

**Mitigation:** Pre-warm cache on deployment with initial curl request.

### Issue 3: OpenAI Free Tier Rate Limit (3-5 RPM)

**Description:** Batch uploads >5 files may trigger fallback regex classification.

**Impact:** Medium — Classification quality degrades for large batches (80% LLM → 40% LLM + 60% regex).

**Mitigation:** Communicate to users: "Large batches (>20 files) may take 20-30 min. Please wait patiently."

---

## Timeline ⏱️

| Phase | Duration | Status |
|-------|----------|--------|
| Code merge to main | Complete | ✅ Done |
| Railway backend deploy | 5-10 min | ⏳ Pending |
| Vercel frontend deploy | 3-5 min | ⏳ Pending |
| Environment variables setup | 5 min | ⏳ Pending |
| Post-deployment validation | 15-20 min | ⏳ Pending |
| Prometheus + Grafana (optional) | 30 min | 🔵 Optional |
| **Total** | **30-40 min** | **In Progress** |

---

## Contacts & Support 📞

- **Backend Issues:** Check Railway logs → Project → backend service → Deploy logs
- **Frontend Issues:** Check Vercel logs → Project → Deployments → View Function logs
- **Database Issues:** Supabase Dashboard → Database → Logs
- **Redis Issues:** Railway logs → redis service → Runtime logs

---

**Document Version:** 1.0  
**Last Updated:** 2026-05-14  
**Status:** ✅ READY FOR PRODUCTION DEPLOYMENT
