# Mappings

Canonical mapping layer for ACUHIT scoring system. Every output CSV is 100% reproducible from committed scripts + reference data.

Protocol authority: `/root/projects/achk/AGENT.MD`

## Structure

```text
mappings/
├── build_mappings.py                          # orchestrator (service + ICD + drug v1 + lab + quality report)
├── service/
│   └── build_service_taxonomy.py              # standalone service builder
├── icd10/
│   ├── build_icd10_severity_v2.py             # ICD severity with Charlson/Elixhauser
│   ├── export_icd_reference_data.py           # extract reference CSVs from comorbidipy
│   └── prepare_icd_top200_review.py           # enrich top-200 codes for clinician review
├── drug/
│   └── build_drug_classification_v2.py        # ATC-based drug classification (WHO ATC + brand bridge)
├── lab_norm/
│   └── build_lab_unit_conversion_policy.py    # lab unit conversion rules
└── data/
    ├── service/service_taxonomy.csv
    ├── icd10/
    │   ├── icd10_severity_v2.csv
    │   ├── icd10_top200_review_queue.csv
    │   └── icd10_severity_v2_report.md
    ├── drug/
    │   ├── drug_classification_v2.csv         # main output (joined to gold)
    │   ├── drug_name_normalization.csv
    │   ├── drug_ingredient_dictionary.csv
    │   └── drug_classification_report.md
    ├── lab_norm/
    │   ├── lab_normalization.csv
    │   ├── lab_unit_conversion_policy.csv
    │   └── lab_unit_conversion_policy.md
    ├── shared/
    │   ├── mapping_quality_report.md
    │   ├── mapping_summary.json
    │   └── timestamp_inventory.csv
    └── reference_data/
        ├── drug/
        │   ├── WHO_ATC_DDD_2024.csv           # WHO ATC index (fabkury/atcd)
        │   ├── drugbank_vocabulary.csv          # DrugBank CC0 synonyms
        │   ├── brand_inn_bridge.csv             # 900 Turkish brand->INN mappings (TITCK-verified)
        │   └── README.md
        ├── icd10/
        │   ├── charlson_icd10_quan_prefixes.csv # Quan et al. 2005
        │   ├── charlson_icd10_quan_weights.csv
        │   ├── elixhauser_icd10_quan_prefixes.csv
        │   └── README.md
        └── lab/
            ├── clinical_importance_rules.csv
            └── README.md
```

## Rebuild Commands (Full Reproducibility)

All outputs can be recreated from scratch:

```bash
cd /root/projects/achk

# 1. Service taxonomy
uv run python mappings/service/build_service_taxonomy.py

# 2. ICD reference data (extract from comorbidipy)
uv run python mappings/icd10/export_icd_reference_data.py

# 3. ICD severity mapping
uv run python mappings/icd10/build_icd10_severity_v2.py

# 4. ICD top-200 review queue
uv run python mappings/icd10/prepare_icd_top200_review.py

# 5. Drug classification (requires reference_data/drug/*.csv)
uv run python mappings/drug/build_drug_classification_v2.py

# 6. Lab unit conversion policy
uv run python mappings/lab_norm/build_lab_unit_conversion_policy.py

# 7. Full orchestrator (service + ICD + drug v1 + lab + quality report)
uv run python mappings/build_mappings.py
```

## Output Samples

### Service Taxonomy (`data/service/service_taxonomy.csv`)

| raw_service_name | acuity_tier | acuity_score | department_category | is_emergency | _source |
|---|---|---|---|---|---|
| Check Up ve Saglikli Yasam | SCREENING | 1 | preventive | 0 | manual_rule::screening_keyword |
| Kardiyoloji | OUTPATIENT | 2 | specialty_outpatient | 0 | manual_rule::outpatient_keyword |
| Acil Servis | EMERGENCY | 5 | emergency | 1 | manual_rule::emergency_keyword |

### ICD-10 Severity (`data/icd10/icd10_severity_v2.csv`)

| icd_code | validity_status | severity_weight | charlson_category | is_malignancy | is_high_risk | _source |
|---|---|---|---|---|---|---|
| Z00.0 | valid_icd10 | 0 | | 0 | 0 | chapter_only |
| J06.9 | valid_icd10 | 3 | | 0 | 1 | chapter_only |
| C50.9 | valid_icd10 | 6 | malignancy | 1 | 1 | charlson_quan_2005 |

### Drug Classification V2 (`data/drug/drug_classification_v2.csv`)

| drug_name | atc_code | drug_classification | antibiotic_flag | oncology_flag | _source |
|---|---|---|---|---|---|
| AUGMENTIN BID 1000 MG.14 FILM TB. | J01CR02 | antibiotic | 1 | 0 | manual_clinician_review |
| ARVELES 25 MG.20 FILM TABLET | M01AE17 | nsaid_analgesic | 0 | 0 | manual_clinician_review |
| XELODA 500 MG 120 FILM TB | L01BC06 | oncology | 0 | 1 | who_atc_exact |

### Lab Normalization (`data/lab_norm/lab_normalization.csv`)

| sub_code | primary_unit | empirical_mean | avg_refmin | avg_refmax | clinical_importance | _source |
|---|---|---|---|---|---|---|
| Lokosit | x10^3/uL | 8.33 | 3.87 | 10.59 | high | empirical+refrange+rule_table |
| Hematokrit | % | 39.29 | 37.47 | 46.25 | high | empirical+refrange+rule_table |

## Reference Data (Not Script-Generated)

Files under `data/reference_data/` are **curated reference datasets**, not generated outputs:

- **WHO ATC index**: Downloaded from fabkury/atcd (WHO ATC/DDD 2024-07-31)
- **DrugBank vocabulary**: Downloaded from DrugBank Open Data 5.1.15 (CC0)
- **Brand-INN bridge**: 900 Turkish brand-to-INN mappings, each verified against TITCK (Turkish Medicines and Medical Devices Agency). This is equivalent to a dictionary file — curated, not LLM-generated.
- **Charlson/Elixhauser prefixes**: Extracted from `comorbidipy` package (Quan et al. 2005)
- **Lab importance rules**: Clinical judgment rules for lab test prioritization

Each reference_data subdirectory has a README.md documenting provenance, download date, and license.

## Clinical Defense

How each mapping contributes to the ACUHIT severity score, what authority backs it, and what it does NOT do.

| Mapping | Scoring Pillar | Max Points | Source Authority | What It Provides | What It Does NOT Do |
|---|---|---|---|---|---|
| **ICD-10 severity** | dx_burden | 35 | Quan et al. 2005 (Charlson/Elixhauser, >10K citations) | severity_weight, comorbidity flags, chronic/malignancy flags | Does not validate physician coding accuracy; chapter-level weights for non-Charlson codes |
| **Drug classification** | tx_intensity | 20 | WHO ATC hierarchy + TITCK brand-to-INN bridge | 5 binary clinical flags (antibiotic, oncology, opioid, anticoagulant, immunosuppressant) | Does not score individual drugs, dosage, or interactions; UNRESOLVED drugs contribute zero |
| **Lab normalization** | lab_acuity | 25 | Hospital LIS reference ranges (sex/age-stratified at instrument level) | Abnormal/critical counts from hospital's own REFMIN/REFMAX | Does not interpret individual values; all abnormals weighted equally regardless of test type |
| **Service taxonomy** | *(not a scoring input)* | 0 | Turkish hospital department naming conventions | Tier labels for calibration validation and service escalation outcomes | Not a model feature; acuity_score is ordinal only, not interval-scale |

### Scoring formula (combine.py)

```
severity_score = (dx_burden + lab_acuity + tx_intensity + nlp_severity) / possible_points * 100
```

- `possible_points` excludes missing pillars (e.g., no labs -> lab_acuity excluded from denominator)
- Service department does NOT contribute points — it validates that scores are clinically coherent (EMERGENCY > SCREENING)

### Per-mapping details

See each subfolder's README.md for full clinical defense:
- `service/README.md` — why tier labels are validation-only, not a feature
- `icd10/README.md` — Charlson/Elixhauser defensibility, chapter-level limitations
- `drug/README.md` — ATC flag derivation, coverage honesty, UNRESOLVED handling
- `lab_norm/README.md` — hospital LIS dependency, abnormal counting approach, unit conversion purpose

## AGENT.MD Compliance

- All mappings built from real `pipeline/silver/*.parquet` data
- Reference datasets under `data/reference_data/` with README lineage
- True mapped coverage reported separately from unresolved/fallback rates
- Every output row has `_source` lineage column
- Every output is reproducible via committed script
