# Mappings

Canonical mapping layer for ACUHIT scoring system. Every output CSV is 100% reproducible from committed scripts + reference data.

## Structure

```text
mappings/
├── service/       # Service taxonomy (133 departments → 5 tiers)
├── icd10/         # ICD-10 severity (Charlson/Elixhauser)
├── drug/          # Drug classification (WHO ATC + brand bridge)
├── lab_norm/      # Lab normalization (unit conversion)
└── reference_data/
    ├── drug/      # WHO ATC 2024, DrugBank, 900-entry brand bridge
    ├── icd10/     # Charlson/Elixhauser prefix lists (Quan 2005)
    └── lab/       # Clinical importance rules
```

## Output Samples

### Service Taxonomy

| raw_service_name | acuity_tier | acuity_score | department_category | is_emergency | _source |
|---|---|---|---|---|---|
| Check Up ve Saglikli Yasam | SCREENING | 1 | preventive | 0 | manual_rule::screening_keyword |
| Kardiyoloji | OUTPATIENT | 2 | specialty_outpatient | 0 | manual_rule::outpatient_keyword |
| Acil Servis | EMERGENCY | 5 | emergency | 1 | manual_rule::emergency_keyword |

### ICD-10 Severity

| icd_code | severity_weight | charlson_category | is_malignancy | is_high_risk | _source |
|---|---|---|---|---|---|
| Z00.0 | 0 | | 0 | 0 | chapter_only |
| J06.9 | 3 | | 0 | 1 | chapter_only |
| C50.9 | 6 | malignancy | 1 | 1 | charlson_quan_2005 |

### Drug Classification

| drug_name | atc_code | drug_classification | antibiotic_flag | oncology_flag | _source |
|---|---|---|---|---|---|
| AUGMENTIN BID 1000 MG.14 FILM TB. | J01CR02 | antibiotic | 1 | 0 | manual_clinician_review |
| ARVELES 25 MG.20 FILM TABLET | M01AE17 | nsaid_analgesic | 0 | 0 | manual_clinician_review |
| XELODA 500 MG 120 FILM TB | L01BC06 | oncology | 0 | 1 | who_atc_exact |

### Lab Normalization

| sub_code | primary_unit | empirical_mean | avg_refmin | avg_refmax | clinical_importance | _source |
|---|---|---|---|---|---|---|
| Lokosit | x10^3/uL | 8.33 | 3.87 | 10.59 | high | empirical+refrange+rule_table |
| Hematokrit | % | 39.29 | 37.47 | 46.25 | high | empirical+refrange+rule_table |

## Reference Data

- **WHO ATC index**: [fabkury/atcd](https://github.com/fabkury/atcd) (WHO ATC/DDD 2024-07-31)
- **DrugBank vocabulary**: [DrugBank Open Data 5.1.15](https://go.drugbank.com/releases/latest#open-data) (CC0)
- **Brand-INN bridge**: 900 Turkish brand-to-INN mappings, verified against [TITCK](https://www.titck.gov.tr/)
- **Charlson/Elixhauser prefixes**: [Quan et al. 2005](https://doi.org/10.1097/01.mlr.0000182534.19832.83) via comorbidipy
- **Lab importance rules**: Clinical judgment rules for lab test prioritization

## Clinical Defense

| Mapping | Pillar | Max | Source Authority | Provides | Does NOT Do |
|---|---|---|---|---|---|
| **ICD-10 severity** | dx_burden | 35 | Quan et al. 2005 (>10K citations) | severity_weight, comorbidity flags | Does not validate physician coding accuracy |
| **Drug classification** | tx_intensity | 20 | WHO ATC + TITCK bridge | 5 binary clinical flags | Does not score dosage or interactions |
| **Lab normalization** | lab_acuity | 25 | Hospital LIS REFMIN/REFMAX | Abnormal/critical counts | Does not interpret individual values |
| **Service taxonomy** | *(validation only)* | 0 | Hospital department naming | Tier labels for coherence checks | Not a scoring input |
