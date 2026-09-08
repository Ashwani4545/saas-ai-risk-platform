# Remediation changelog

This documents the fixes made after an audit found the repo didn't hold up
under actual execution, despite looking complete on paper. Each entry
includes what was wrong, how it was confirmed, and what changed - useful
if you get asked about any of this in an interview.

## 1. `/predict` hung indefinitely without Kafka running
**Found by:** calling `kafka_producer.send_prediction_event()` directly and
timing it - it never returned within 15s. `KafkaProducer(...)` blocks on
its first broker connection before the surrounding `try/except` could catch
anything.
**Fix:** `messaging/kafka_service.py` now queues events to a background
worker thread. The request-handling code only ever does a non-blocking
`queue.put()` - confirmed at ~20 microseconds regardless of whether Kafka
is reachable. Also pinned `api_version=(2, 5, 0)` to skip the broker-version
auto-probe that caused the original blocking.

## 2. Auth was bypassable
**Found by:** reading `get_optional_user()` - it fell back to an
"anonymous" user built from the client-supplied `X-Tenant-ID` header when
no token/API key was present. Every "protected" endpoint was effectively
public, and the Streamlit UI even shipped a "Header Only" auth mode that
exploited this.
**Fix:** `auth/security.py` - `get_current_user()` now raises 401 if
neither a valid JWT nor API key is provided. No anonymous fallback exists
anymore.

## 3. "Multi-tenant" wasn't enforced
**Found by:** tracing how `tenant_id` was used - it was a request header,
used only for metrics labels. Nothing scoped feature or vector-store reads
by tenant.
**Fix:** `feature_store/feature_service.py` and `vector_store/faiss_store.py`
now require `tenant_id` on every read, sourced from the authenticated
principal (never a header). Each tenant gets its own FAISS index. Verified
live: the same `customer_id` queried under two different tenants' API keys
returns different data.

## 4. No persistence
**Found by:** users/API keys lived in Python dicts in `auth/security.py` -
wiped on every restart.
**Fix:** `core/db.py` - SQLite-backed users, API keys, tenants, and a
prediction audit log. SQLite (not Postgres) so the project still runs with
zero external infra.

## 5. Feast was decorative
**Found by:** `feature_store/feast_repo/feature_repo.py` defined Feast
entities, but nothing in the running app ever called into Feast -
`feature_service.py` read a parquet file directly with pandas.
**Fix:** removed the Feast folder and dependency. The feature store is
honestly a small pandas-backed service now, with a comment noting Feast as
a real next step rather than a claim.

## 6. Model was trained on labels derived from noise
**Found by:** `data/generate_features.py` generated `risk_label` from a
formula over `np.random.randn(...)`, unrelated to any of the named
features. No train/test split, no metrics ever printed.
**Fix:** `data/generate_features.py` now derives risk from a documented,
weighted combination of the actual features (recency, disputes, credit
score, etc). `models/risk_model.py` holds out a test split and writes
AUC/precision/recall/F1 to `models/trained/metrics.json`. Current numbers:
AUC ~0.67-0.68 for both models - a believable number for synthetic data,
not a suspicious 0.99.

## 7. CI never actually tested anything
**Found by:** `.github/workflows/` contained unmodified GitHub default
templates (`python-package.yml`, `python-publish.yml`) that ran bare
`pytest` with no Kafka service - which would have hung/timed out given
issue #1.
**Fix:** replaced with `.github/workflows/ci.yml`, which runs the real test
suite (now fast and hang-free) plus a frontend build check.

## 8. Hardcoded secrets
**Found by:** a static JWT secret string and demo credentials baked into
source as defaults.
**Fix:** `core/config.py` requires `JWT_SECRET_KEY` in production and
generates a per-process random one (with a warning) in dev. Added
`.env.example`. Demo credentials only seed when `SEED_DEMO_DATA=true`
against an empty DB.

## 9. Frontend
Added a React (Vite) dashboard in `frontend/` - login, prediction with a
live risk gauge, feature lookup, similarity search, A/B stats, and recent
prediction history, all wired to the real API with tenant-scoped auth.
Verified end-to-end: built, served, and confirmed the backend accepts
requests from its origin (CORS preflight checked directly).

The existing Streamlit app (`streamlit_app/app.py`) was also fixed - it had
a "Header Only" auth mode built around the bug in #2, which is now removed,
plus a display bug in the batch-prediction table.

## Verified, not just claimed
- 47/47 tests pass in ~7 seconds (previously: hung indefinitely on the
  second API test)
- Live smoke test against a running server: unauthenticated request → 401,
  authenticated predict → 200 with a real score, cross-tenant isolation
  confirmed with matching customer IDs returning different data
- Frontend: `npm run build` succeeds, served build makes real API calls
  and gets real predictions back, CORS preflight returns correct headers
  for the frontend's origin

## Still worth doing before calling this production-ready
- Replace the synthetic feature generator with a real public credit-risk
  dataset if you want defensible real-world metrics
- Move the in-memory rate limiter to Redis for multi-instance deployment
- Add refresh tokens / token revocation (current JWTs can't be revoked
  before they expire)
- Add integration tests that actually spin up Kafka via docker-compose in
  CI, rather than relying on the non-blocking fallback path

## 10. GenAI / RAG / vector-DB addition: policy-grounded risk explanations

Added after a specific request to evaluate whether GenAI/RAG components
would genuinely help this project - not added by default, and scoped to a
use case the domain actually has: explaining *why* a risk decision was
made, grounded in underwriting policy. This is close to a real regulatory
requirement in US lending (adverse action notices under ECOA) - see
`rag/knowledge_base/regulatory_notes.md`.

**`rag/retriever.py`** - retrieval over a small markdown knowledge base of
underwriting policy (`rag/knowledge_base/`), using TF-IDF (scikit-learn,
already a dependency) over paragraph-level chunks. Deliberately not a
dense embedding model: this sandbox's network can't reach model hosts
like Hugging Face, and a handful of short policy docs don't need one. The
`retrieve(query, k)` interface is the same one a real embedding-based
retriever would expose (sentence-transformers + pgvector/Chroma, or the
FAISS store already in this repo), so swapping it in later is contained,
not a rewrite. Verified live: dispute-related queries surface
`dispute_policy.md`, account-age queries surface
`account_history_policy.md`, etc.

**`rag/llm_client.py`** - thin async wrapper around the Anthropic Messages
API. Off by default (`LLM_PROVIDER=none` unless `ANTHROPIC_API_KEY` is
set). `generate()` never raises - a missing key, timeout, or API failure
returns `None` rather than breaking the request, the same non-blocking
design principle as the Kafka fix in section 1.

**`rag/explain.py`** - combines the model's prediction + actual feature
values + retrieved policy chunks into either an LLM-generated explanation
(if configured) or a deterministic template citing the same retrieved
chunks (if not). Both paths are real code, not a mocked demo path -
confirmed by running the full test suite and a live server with no API
key set, which exercises the fallback path.

**New endpoints:**
- `POST /explain` - `{customer_id}` → risk score + natural-language
  explanation + the policy excerpts it's grounded in. Tenant-scoped, auth
  required, same as `/predict`.
- `POST /policy/ask` - `{question}` → general RAG Q&A over the policy
  knowledge base, not tied to a specific customer.

**Frontend:** new "Explain" tab in the React dashboard - shows the risk
score, the explanation, whether it was LLM-generated or template
fallback, and the retrieved policy excerpts it's grounded in, plus a
free-text "ask the policy assistant" box.

**Tests (`tests/test_rag.py`):** retrieval returns the expected policy doc
for realistic queries, both new endpoints require auth, and the fallback
path is asserted explicitly (CI never sets `ANTHROPIC_API_KEY`, so this
confirms the feature doesn't silently no-op without a key). 56/56 tests
pass including these.

**To actually see LLM-generated (not template) output:** set
`ANTHROPIC_API_KEY` in `.env`. Without it, the feature still works and is
still gradeable/testable - that was an intentional design choice, not a
missing feature.

## 11. Second domain: Product Authenticity Scanner & Fraud Detection

Added as a genuine second application of this platform's shared
infrastructure (auth, tenant isolation, persistence, model pipeline
pattern, RAG explanation), not a separate bolted-on project. The overlap
was checked for real reuse before writing any code - see the compatibility
breakdown earlier in this conversation for the reasoning.

**Problem it solves:** verify product authenticity via QR code and flag
likely counterfeits using scan-pattern fraud signals - duplicate scans and
"impossible travel" (the same item scanned from two distant locations
faster than physically possible).

**`product_auth/qr_service.py`** - generates a unique, non-guessable serial
(UUID-based, not sequential - so counterfeiters can't enumerate valid
serials) and a QR code as SVG. SVG, not PNG, for the same dependency-free
reason as the RAG retriever choice: no Pillow/native imaging dependency
needed.

**`product_auth/scan_service.py`** - `haversine_km()` (great-circle
distance) and `compute_scan_features()`, which turns a product's scan
history into named features: scan_count, unique_locations,
max_travel_speed_kmh, min_seconds_between_scans, scans_last_hour. Verified
directly: two scans ~1150km apart seconds apart in test time produce a
max_travel_speed_kmh in the millions - correctly flagged as impossible.

**`product_auth/fraud_model.py`** - deliberately mirrors
`models/risk_model.py`'s interface (load-from-disk, `.predict()` ->
`{risk_score, risk_class}`, held-out AUC/precision/recall written to a
metrics.json) - the same platform pattern applied to a second domain.

**`product_auth/data_generator.py`** - synthetic legit vs. suspicious scan
patterns. First version scored a suspicious AUC of 1.0 - caught this the
same way the credit-risk model's noise-trained labels were caught earlier
in this project: an unbelievable metric is a signal to look harder, not a
result to ship. Added realistic overlap (legit products occasionally get
one slow, distant "travel" scan; some fraud cases are deliberately mild)
plus 6% label noise, since real fraud labeling is never perfectly clean.
Final AUC: ~0.92 on held-out data - strong and still believable.

**RAG reuse:** `rag/explain.py` gained `explain_fraud_risk()`, and two new
policy documents (`duplicate_scan_policy.md`,
`product_authenticity_policy.md`) were added to the *same* knowledge base
used by the credit-risk explainer. Verified the shared TF-IDF index still
retrieves cleanly per-domain (dispute queries → dispute policy, scan
queries → scan policy, no cross-contamination in the top results) - though
one honest limitation: on a generic/low-signal query, a low-ranked
irrelevant chunk from the other domain can occasionally surface (seen live
in testing: a low-risk product scan pulled in a `credit_score_policy.md`
chunk at rank 3, lowest score). Not wrong, just a known limitation of
sharing one small TF-IDF index across domains - splitting into
per-domain indices is the fix if this matters more than the simplicity of
one shared knowledge base.

**New endpoints:**
- `POST /products/register` - `{product_name}` → generates serial + QR
- `POST /scan` - `{serial, latitude, longitude}` → records the scan, runs
  the fraud model, returns a risk score with a RAG-grounded explanation.
  An unregistered or wrong-tenant serial is immediately flagged unverified
  (risk 1.0) without needing a model call - per
  `product_authenticity_policy.md`.
- `GET /products/{serial}/history` - tenant-scoped scan history

**Tenant isolation, enforced the same way as the credit-risk domain:**
scans and product lookups are always scoped to `(serial, tenant_id)` from
the authenticated principal. Verified live: scanning another tenant's real
serial with a valid API key for a *different* tenant returns `verified:
false`, and `GET .../history` for a product you don't own returns 404.

**Frontend:** two new tabs - "Register Product" (shows the generated QR +
serial) and "Scan" (location presets for three cities to make the
impossible-travel demo easy to trigger, the same risk gauge component
reused from the credit-risk Predict tab, and scan history).

**Tests (`tests/test_product_auth.py`):** haversine correctness, QR
uniqueness, feature computation on known impossible-travel data, and the
same auth/tenant-isolation assertions as the rest of the suite, applied to
the new endpoints. 71/71 tests pass across the whole project including
these.

**Verified live**, not just unit-tested: registered a real product,
scanned it from Delhi (risk 0.14, low, grounded in general authenticity
policy), then scanned the same serial from Mumbai seconds later in test
time (risk jumped to 0.69, high, grounded specifically in
`duplicate_scan_policy.md`'s impossible-travel clause) - confirming the
whole pipeline (scan → feature computation → model → RAG explanation)
reacts correctly to a real fraud pattern, not just to hardcoded test
inputs.
