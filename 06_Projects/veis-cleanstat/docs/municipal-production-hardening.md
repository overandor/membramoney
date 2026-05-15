# Municipal Production Hardening Plan

This document translates pilot-grade architecture feedback into a concrete implementation plan for a city-ready deployment.

## Current Maturity Position

**Status:** pilot-ready architecture with strong production direction.

The platform has foundational strengths already:

- separated API/service/task/middleware boundaries
- Postgres + Redis + Celery operational baseline
- revocable refresh-token model
- organization-aware data model
- audit and rate-limit concepts in place
- infrastructure-as-code + AWS path

## Hardening Gaps and Required Actions

### 1) JWT secret lifecycle

**Risk:** service restarts can invalidate active sessions and create multi-instance inconsistency if a runtime-generated default secret is used.

**Action:**

- Require `JWT_SECRET` in non-development environments.
- Permit generated fallback only for local development.
- Add startup validation that fails fast with a clear error.

**Done when:** app boot in `production` or `staging` fails if `JWT_SECRET` is missing.

---

### 2) Production config validation

**Risk:** `assert`-based checks are not reliable runtime safeguards.

**Action:**

- Replace `assert` checks with explicit validation functions.
- Raise `RuntimeError` or `ValueError` with actionable messages.
- Validate all critical settings (database, redis, secrets, cookie/domain config, CORS allowlist).

**Done when:** startup emits deterministic validation errors and exits non-zero for invalid config.

---

### 3) Refresh-token source-of-truth contract

**Risk:** ambiguous state between Redis and DB can create revocation drift.

**Action:**

- Define source-of-truth model:
  - Redis: active session lookups + revocation checks (fast path)
  - DB: durable session inventory + audit trail (system of record)
- Document write-order and reconciliation behavior.
- Add consistency job/endpoint for drift detection.

**Done when:** token issuance, rotation, and revocation flows have explicit state transitions and tests.

---

### 4) Audit API consistency

**Risk:** usage patterns (e.g., `AuditLog.create(...)`) may not match model implementation.

**Action:**

- Standardize the audit write interface (class method, repository, or service helper).
- Ensure all call sites use the same API.
- Add unit tests for audit event persistence and schema expectations.

**Done when:** one canonical audit write API exists and all auth/verification flows use it.

---

### 5) Auth router runtime reliability

**Risk:** incomplete imports and ad-hoc time handling can create production regressions.

**Action:**

- Consolidate datetime handling with timezone-aware UTC utilities.
- Add strict linting/CI for import/runtime errors.
- Add integration tests for login, refresh, logout, and revoked-token behavior.

**Done when:** auth router passes static checks and integration tests in CI.

---

### 6) Identity architecture for municipal users

**Risk:** wallet-only auth is not enough for internal city staff workflows.

**Action:**

- Add enterprise SSO path (OIDC/SAML) for city employees.
- Keep wallet auth as optional high-assurance step for contractor attestations or signed actions.
- Map identity provider groups to role + organization boundaries.

**Done when:** staff can authenticate via SSO while retaining optional wallet-based attestation for specific events.

---

### 7) Tenant isolation enforcement

**Risk:** manual query helpers can be bypassed accidentally.

**Action:**

- Enforce org scoping in repository/service layers.
- Add policy tests that intentionally attempt cross-tenant data access.
- Evaluate Postgres RLS for high-risk tables.

**Done when:** automated tests prove cross-tenant reads/writes are denied.

---

### 8) Unified rate-limit policy

**Risk:** divergent app and edge rate-limit behavior causes unpredictable failures.

**Action:**

- Publish one policy matrix (path, actor type, burst, sustained rate, trusted client IP headers).
- Keep app and NGINX/ALB policies aligned from a single source.
- Add observability tags for limit-trigger diagnostics.

**Done when:** rate-limit behavior is consistent and debuggable across layers.

---

### 9) Cookie/session hardening

**Risk:** secure flags alone are incomplete without domain/path/CSRF model.

**Action:**

- Define cookie domain/path strategy for all environments.
- Implement CSRF defense for cookie-based refresh flows.
- Define token rotation cadence and session invalidation policy.

**Done when:** documented and tested cookie model supports intended frontend deployment topology.

---

### 10) Web3 verification boundaries

**Risk:** implicit provider behavior (`web3.auto`) reduces deterministic operations.

**Action:**

- Use explicit provider configuration where chain access is required.
- Isolate signature verification so it does not require live chain connectivity unless necessary.
- Add chain/network configuration controls and test fixtures.

**Done when:** signature verification works in offline/unit-test contexts and production network selection is explicit.

---

### 11) Observation provenance metadata

**Risk:** insufficient evidence metadata weakens municipal auditability.

**Action:**

Add first-class fields for:

- device capture timestamp + server receive timestamp
- client clock offset
- source type + uploader device identifier
- geo accuracy metrics
- original media hash + derivative hash chain
- EXIF retention/sanitization status
- model/version identifiers used during processing

**Done when:** each observation can be reconstructed with full provenance for dispute handling.

---

### 12) Verification policy governance

**Risk:** analysis output without policy framework is hard to operationalize.

**Action:**

- Define policy engine inputs/outputs and threshold tiers.
- Add escalation routing (auto-approve, human review, fraud queue).
- Persist decision rationale and model confidence snapshots.

**Done when:** verification outcomes are reproducible, explainable, and auditable.

## Readiness Milestones

### Milestone A — Security Baseline (2-4 weeks)

- secrets externalization (AWS Secrets Manager/SSM)
- startup config validator
- dependency scanning + SBOM
- key rotation and backup/restore drill

### Milestone B — Operational Reliability (2-4 weeks)

- SLOs, SLIs, alert routing
- Celery retry + poison message + dead-letter pattern
- migration rollback strategy
- incident response runbook

### Milestone C — Governance & Productization (3-6 weeks)

- retention/deletion policies and legal posture
- operator review dashboard
- exception workflows + audit/report exports
- contractor vs city org boundary policy

## Recommended Next Build Order (Highest Leverage)

1. Secure configuration + secrets hardening
2. Auth/session and tenant-isolation invariants with tests
3. Operator dashboard + review queues + reporting exports
4. Governance brief (security, retention, explainability)

This sequence best supports pilot conversion into a contract-ready municipal software asset.
