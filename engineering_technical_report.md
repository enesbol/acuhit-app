# ACUHIT — Engineering Technical Report

**Team:** Dr. Mundo | **Date:** 2026-03-08
**Scale:** 352,522 episodes, 83,104 patients, 37.2M lab rows, 2.0M prescriptions

---

## 1. System Architecture

```
Raw CSVs → scripts/filter_to_parquet.py → data/clean/ (3 parquet tables)
  → pipeline/build_silver.py → pipeline/silver/ (6 files)
  → pipeline/build_gold.py → pipeline/gold/ (3 episode-level files)
  → scoring/nlp/extract_regex.py → NLP features
  → scoring/combine.py → 4 pillars → severity_score
  → scoring/calibrate.py → AUC, calibration bins
```

**E2E runner:** `uv run python run_e2e.py` with flags:

| Flag | What It Runs | Duration |
|------|-------------|----------|
| `pipeline` | Silver → Gold → Validation | ~15 min |
| `iter` | Regex + scoring + validation + calibration | ~4 min |
| `iterf` | Scoring + validation + calibration (skip regex) | ~40 sec |

Full rebuild: `uv run python run_e2e.py raw pipeline iter` (~19 min)

---

## 2. Data Layer

### Raw Data

| Table | Rows | Patients | Key |
|-------|------|----------|-----|
| anadata | 1,201,253 | 83,104 | HASTA_ID + SQ_EPISODE (3.4 rows/episode) |
| lab | 37,171,512 | 193,299 | HASTA_ID + REP_DATE (no episode key) |
| recete | 2,011,718 | 167,160 | HASTA_ID + RF_EPISODE (partial match) |

Three-table patient overlap: 54,342.

### Silver Layer (6 files)

| File | Rows | Purpose |
|------|------|---------|
| episode_core | 352,522 | Demographics, service, dates, source flags |
| episode_dx | ~534K | ICD-10 codes per episode |
| episode_text | 352,522 | YAKINMA, MUAYENE_NOTU, TEDAVI_NOTU |
| lab_clean | 37.2M | Parsed numerics, REFMIN/REFMAX, IS_ABNORMAL |
| recete_clean | ~1.9M | Drug names, routes |
| patient_icd_history | — | Longitudinal ICD history |

### Gold Layer (3 files)

| File | Rows | Disk | Load Time |
|------|------|------|-----------|
| episode_score_input | 352,522 | 7.4 MB | 1.2s |
| episode_lab_features | ~231K | <1 MB | <0.5s |
| episode_rx_features | ~300K | <1 MB | <0.5s |

Gold load time target: <2s. Achieved: 1.25s.

---

## 3. Join Strategies

### Lab → Episode

Labs have no episode key. Joined by patient + date proximity (±7 days). Coverage: 65.5% of episodes. Lab event match rate: 14.4% of 37.2M rows.

### Prescription → Episode

Hybrid: exact key first (`RF_EPISODE = SQ_EPISODE`, ~60%), date proximity fallback (±7 days). If both match, key wins.

### Drug Classification

Gold-layer drug features join to ATC-backed classification: WHO ATC 2024 + DrugBank synonyms + 900-entry Turkish brand bridge. Coverage: 95.4%. Output flags: `antibiotic_flag` (ATC J01), `oncology_flag` (ATC L01/L02).

---

## 4. DuckDB Configuration

Lab table is 37.2M rows — `pd.read_parquet()` causes OOM. All heavy operations use DuckDB:

```python
con.execute("PRAGMA threads=4")
con.execute("PRAGMA memory_limit='2GB'")
con.execute("SET preserve_insertion_order=false")
```

Pandas only for: gold-level tables (<50MB), EWMA computation, validation reports.

### Performance

| Operation | Time |
|-----------|------|
| Silver build (37M lab parse) | ~10 min |
| Gold build (joins + features) | ~3 min |
| NLP regex extraction (352K) | ~90 sec |
| Scoring (4 pillars + combine) | ~20 sec |
| Validation + calibration | ~15 sec |
| **Full E2E** | **~19 min** |
| **Incremental (iterf)** | **~40 sec** |

All outputs: zstd-compressed parquet. Gold table: 7.4 MB disk → 106 MB memory (14× ratio).

---

## 5. Scoring Pipeline

### Pillar Computation

| Pillar | File | Max | Input |
|--------|------|-----|-------|
| dx_burden | pillar_dx.py | 35 | episode_dx + patient_icd_history + icd10_severity.csv |
| lab_acuity | pillar_lab.py | 25 | episode_lab_features |
| tx_intensity | pillar_tx.py | 20 | episode_rx_features + drug_classification_v2.csv |
| nlp_severity | pillar_nlp.py | 20 | nlp_features.parquet |

### Score Formula

```
raw_score = dx + lab + tx + nlp
possible_points = 35 + (25 if labs) + (20 if rx) + (20 if text)
severity_score = raw_score / possible_points × 100
```

Missing pillars excluded from denominator (not zero-filled). `data_confidence` tracks pillar availability.

### Trajectory

Per-patient EWMA (tau=30 days) + `score_delta` + `days_since_last` + `score_vs_ewma`.

---

## 6. NLP Engine

220 Turkish medical stems, 27 negation patterns, segment-based scoping:

```
Input: episode_text.parquet (352K, 4 text fields)
  → Turkish ASCII normalization
  → Zeyrek lemma cache (102 entries, offline-built)
  → Segment splitting (., ;, \n, ama, fakat, var, mevcut)
  → Per-segment: SYMPTOM_RE + NEGATION_RE + CHRONIC_RE
Output: nlp_features.parquet (352K rows, 16 columns)
```

| Metric | Value |
|--------|-------|
| Throughput | ~2,000 episodes/sec |
| Total time | ~90 sec |
| Recall | 78.4% |
| Runtime Zeyrek calls | 0 (cache only) |

Source priority: LLM batch → regex extraction → stratified sample.

---

## 7. Validation

### Pipeline Checks (validate.py)

Row count alignment, key integrity, source flag validation, lab count sanity, data_confidence range, dev sample size.

### Score Checks (validate_score.py)

| Check | Status |
|-------|--------|
| Null scores < 1% | **PASS** (0 nulls) |
| Score std > 10 | **PASS** (11.8) |
| Service ordering (Emergency > Screening) | **PASS** |
| Pillar correlations 0.1 < r < 0.9 | **PASS** |
| Polypharmacy direction | **PASS** |

### Calibration (calibrate.py)

| Outcome | Test AUC | 95% CI | Positives |
|---------|---------|--------|-----------|
| **death_label_episode** | **0.940** | 0.933–0.947 | 552 |
| death_label_patient (last visit) | 0.938 | 0.907–0.958 | 64 |
| revisit_30d_unplanned | 0.865 | 0.851–0.877 | 1,092 |

---

## 8. Reference Data Provenance

| Domain | Source | Coverage |
|--------|--------|----------|
| ICD-10 | Charlson (Quan 2005) + Elixhauser (Quan 2009) | 99.95% |
| Drugs | WHO ATC 2024 + DrugBank + 900-entry brand bridge | 95.4% |
| Labs | Hospital LIS REFMIN/REFMAX | 100% |
| Services | Manual taxonomy (133 → 5 tiers) | 100% |

All mapping CSVs include `_source` column tracing to authoritative reference.

---

## 9. Output Schema

### episode_scores.parquet

| Column | Type | Description |
|--------|------|-------------|
| HASTA_ID | str | Patient identifier |
| SQ_EPISODE | int | Episode identifier |
| severity_score | float | 0–100 composite severity |
| dx_burden / lab_acuity / tx_intensity / nlp_severity | float | Pillar scores |
| raw_score | float | Sum of pillars |
| possible_points | int | Denominator (35–100) |
| score_ewma | float | EWMA trend |
| score_delta | float | Change from previous |
| data_confidence | int | Pillars available (1–4) |
| dx/lab/tx/nlp_present | int | Pillar availability flags |
| + 20 component-level columns | — | Sub-scores for audit trail |

---

## 10. Reproducibility

- **Silver/Gold:** DuckDB — row order may vary, content deterministic
- **NLP:** Fully deterministic (same text → same features)
- **Scoring:** Deterministic given gold + NLP inputs
- **Calibration:** Deterministic (temporal split, not random)
- **Dev sample:** Non-deterministic (random 5K patients)
- **Dependencies:** python ≥3.10, duckdb, pandas, numpy, scikit-learn, pyarrow. Managed via `uv`.

