"""ACUHIT Clinical Severity Scoring — Demo Dashboard.

Pure read-only presentation. Pre-built 1% sample.

Usage:
    uv run streamlit run app.py --server.address 0.0.0.0
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="ACUHIT Severity Score", page_icon="🏥", layout="wide")

ROOT = Path(__file__).resolve().parent
SCORED_PATH = ROOT / "demo_sample.parquet"

N_EPISODES_FULL = 352_522
N_PATIENTS_FULL = 83_104
N_DECEASED_FULL = 192

EXAMPLE_PATIENTS = {
    "Deceased + Cancer (5 visits)": "ANON_246177",
    "Alive — Stable (4 visits)": "ANON_195978",
}


@st.cache_data(ttl=3600)
def load_data() -> pd.DataFrame:
    return pd.read_parquet(SCORED_PATH)


df = load_data()

# ── Page selector ────────────────────────────────────────────────
page = st.sidebar.radio("Page", ["Dashboard", "Key Results", "Scoring Flow", "NLP Examples", "Full Reports"], index=0)
st.sidebar.divider()
st.sidebar.caption("Dr. Mundo — ACUHIT")

@st.cache_data(ttl=3600)
def load_report(path: str) -> str:
    p = ROOT / path
    return p.read_text(encoding="utf-8") if p.exists() else "*Report not found.*"


if page == "Dashboard":
    # ── Header ───────────────────────────────────────────────────
    st.title("ACUHIT — Clinical Severity Score")
    st.caption("4-pillar scoring: dx(35) + lab(25) + tx(20) + nlp(20)")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Episodes", f"{N_EPISODES_FULL:,}")
    c2.metric("Patients", f"{N_PATIENTS_FULL:,}")
    c3.metric("Deceased", f"{N_DECEASED_FULL:,}")
    c4.metric("Mean Score", f"{df['severity_score'].mean():.1f}")
    c5.metric("AUC (test)", "0.940")

    # ── Score Distribution ───────────────────────────────────────
    st.subheader("Score Distribution")
    col_hist, col_stats = st.columns(2)

    with col_hist:
        counts = df["severity_score"].dropna().value_counts(bins=20).sort_index()
        labels = [f"{iv.left:.0f}-{iv.right:.0f}" for iv in counts.index]
        fig_hist = go.Figure(go.Bar(
            x=labels, y=counts.values,
            marker_color="#4A90D9",
            hovertemplate="Score %{x}<br>Episodes: %{y:,}<extra></extra>",
        ))
        fig_hist.update_layout(
            xaxis_title="Score", yaxis_title="Episodes",
            height=350, margin=dict(t=10, b=40),
        )
        st.plotly_chart(fig_hist, use_container_width=True)

    with col_stats:
        alive = df[df["has_ex_source"] == 0]
        dead = df[df["has_ex_source"] == 1]
        metrics = ["severity_score", "dx_burden", "lab_acuity", "tx_intensity"]
        st.dataframe(pd.DataFrame({
            "Metric": metrics,
            "Overall": [round(df[c].mean(), 1) for c in metrics],
            "Alive": [round(alive[c].mean(), 1) for c in metrics],
            "Deceased": [round(dead[c].mean(), 1) for c in metrics],
        }), hide_index=True, use_container_width=True)

        st.dataframe(pd.DataFrame({
            "Pillar": ["dx_burden", "lab_acuity", "tx_intensity", "nlp_severity"],
            "Max": [35, 25, 20, 20],
            "Mean": [round(df["dx_burden"].mean(), 1), round(df["lab_acuity"].mean(), 1),
                     round(df["tx_intensity"].mean(), 1), round(df["nlp_severity"].mean(), 1)],
        }), hide_index=True, use_container_width=True)

    # ── Score by Domain ──────────────────────────────────────────
    st.subheader("Score by Domain & Visit Type")
    col_dom, col_vt = st.columns(2)

    with col_dom:
        st.dataframe(
            df.groupby("source_domain")["severity_score"]
            .agg(["mean", "count"]).round(1)
            .sort_values("mean", ascending=False)
            .rename(columns={"mean": "Mean", "count": "N"}),
            use_container_width=True,
        )

    with col_vt:
        st.dataframe(
            df.groupby("visit_type")["severity_score"]
            .agg(["mean", "count"]).round(1)
            .sort_values("mean", ascending=False).head(15)
            .rename(columns={"mean": "Mean", "count": "N"}),
            use_container_width=True,
        )

    # ── Patient Trajectory ───────────────────────────────────────
    st.subheader("Patient Trajectory")

    example = st.radio("Patient", list(EXAMPLE_PATIENTS.keys()), horizontal=True)
    patient_id = EXAMPLE_PATIENTS[example]

    pdf = df[df["HASTA_ID"] == patient_id].sort_values("EPISODE_TARIH")
    pdf["_date"] = pd.to_datetime(pdf["EPISODE_TARIH"]).dt.date
    pdf = pdf.sort_values("severity_score", ascending=False).drop_duplicates("_date").sort_values("EPISODE_TARIH")

    if len(pdf) > 0:
            status = "DECEASED" if pdf["has_ex_source"].max() == 1 else "Alive"
            st.caption(f"**{patient_id}** | {len(pdf)} episodes | {status} | Sex: {pdf['CINSIYET'].iloc[0]}")

            hover = [
                f"<b>{r['EPISODE_TARIH']}</b><br>"
                f"Score: {r['severity_score']:.1f}<br>"
                f"dx: {r['dx_burden']:.1f}/35<br>"
                f"lab: {r['lab_acuity']:.1f}/25<br>"
                f"tx: {r['tx_intensity']:.1f}/20<br>"
                f"nlp: {r['nlp_severity']:.1f}/20<br>"
                f"Visit: {r['visit_type']}"
                for _, r in pdf.iterrows()
            ]

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=pdf["EPISODE_TARIH"], y=pdf["severity_score"],
                mode="lines+markers", name="Score",
                marker=dict(size=8, color="#E74C3C"),
                line=dict(width=2, color="#E74C3C"),
                hovertemplate="%{customdata}<extra></extra>",
                customdata=hover,
            ))
            fig.add_trace(go.Scatter(
                x=pdf["EPISODE_TARIH"], y=pdf["score_ewma"],
                mode="lines", name="EWMA",
                line=dict(width=2, color="#3498DB", dash="dot"),
                hovertemplate="EWMA: %{y:.1f}<extra></extra>",
            ))
            fig.update_layout(
                yaxis_title="Score", height=380,
                margin=dict(t=10, b=40), legend=dict(orientation="h", y=1.08),
            )
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(
                pdf[["EPISODE_TARIH", "severity_score", "dx_burden", "lab_acuity",
                     "tx_intensity", "nlp_severity", "visit_type", "source_domain"]].reset_index(drop=True),
                use_container_width=True,
            )

            # Show clinical text notes if available
            text_cols = [c for c in ["YAKINMA", "MUAYENE_NOTU", "TEDAVI_NOTU"] if c in pdf.columns]
            if text_cols and pdf[text_cols].notna().any().any():
                with st.expander("Clinical Notes", expanded=True):
                    for _, r in pdf.iterrows():
                        date_str = str(r["EPISODE_TARIH"])[:10]
                        st.markdown(f"**{date_str}** — Score: {r['severity_score']:.1f}")
                        for col, label in [("YAKINMA", "Complaint"), ("MUAYENE_NOTU", "Examination"), ("TEDAVI_NOTU", "Treatment")]:
                            if col in r and pd.notna(r[col]) and str(r[col]).strip():
                                st.caption(f"_{label}:_ {str(r[col]).strip()[:300]}")
                        st.markdown("---")

elif page == "Key Results":
    st.title("Key Results")

    # ── 1. Alive vs Deceased overlapping histogram ───────────────
    st.subheader("Score Separation: Alive vs Deceased")
    alive = df[df["has_ex_source"] == 0]["severity_score"].dropna()
    dead = df[df["has_ex_source"] == 1]["severity_score"].dropna()

    import numpy as np
    bins = np.arange(0, 105, 5)

    fig_sep = go.Figure()
    fig_sep.add_trace(go.Histogram(
        x=alive, xbins=dict(start=0, end=100, size=5),
        name=f"Alive (n={len(alive):,})",
        marker_color="rgba(74, 144, 217, 0.6)",
        hovertemplate="Score %{x}<br>Count: %{y}<extra>Alive</extra>",
    ))
    fig_sep.add_trace(go.Histogram(
        x=dead, xbins=dict(start=0, end=100, size=5),
        name=f"Deceased (n={len(dead):,})",
        marker_color="rgba(231, 76, 60, 0.7)",
        hovertemplate="Score %{x}<br>Count: %{y}<extra>Deceased</extra>",
    ))
    fig_sep.update_layout(
        barmode="overlay", height=380,
        xaxis_title="Severity Score", yaxis_title="Episodes",
        margin=dict(t=10, b=40),
        legend=dict(x=0.7, y=0.95),
    )
    st.plotly_chart(fig_sep, use_container_width=True)
    st.caption("The visual gap between distributions IS the AUC. Deceased episodes cluster at 40-80, alive at 10-35.")

    # ── 2. Cohort mean scores ────────────────────────────────────
    st.subheader("Cohort Ordering (Construct Validity)")
    cohort_data = df.groupby("source_domain")["severity_score"].mean().sort_values(ascending=True)
    colors = {"checkup": "#2ecc71", "cancer": "#f39c12", "ex": "#e74c3c"}

    fig_cohort = go.Figure(go.Bar(
        y=cohort_data.index,
        x=cohort_data.values,
        orientation="h",
        marker_color=[colors.get(d, "#95a5a6") for d in cohort_data.index],
        text=[f"{v:.1f}" for v in cohort_data.values],
        textposition="outside",
        hovertemplate="%{y}: %{x:.1f}<extra></extra>",
    ))
    fig_cohort.update_layout(
        xaxis_title="Mean Severity Score", height=250,
        margin=dict(t=10, b=40, l=100),
    )
    st.plotly_chart(fig_cohort, use_container_width=True)
    st.caption("Score orders cohorts correctly (ex > cancer > checkup) without ever being trained on outcomes.")

    # ── 3. Pillar contribution ───────────────────────────────────
    st.subheader("Pillar Contributions: Deceased vs Alive")
    pillars = ["dx_burden", "lab_acuity", "tx_intensity", "nlp_severity"]
    pillar_labels = ["dx_burden (35)", "lab_acuity (25)", "tx_intensity (20)", "nlp_severity (20)"]
    alive_df = df[df["has_ex_source"] == 0]
    dead_df = df[df["has_ex_source"] == 1]

    fig_pillar = go.Figure()
    fig_pillar.add_trace(go.Bar(
        name="Alive", y=pillar_labels,
        x=[alive_df[p].mean() for p in pillars],
        orientation="h", marker_color="rgba(74, 144, 217, 0.7)",
        text=[f"{alive_df[p].mean():.1f}" for p in pillars],
        textposition="outside",
    ))
    fig_pillar.add_trace(go.Bar(
        name="Deceased", y=pillar_labels,
        x=[dead_df[p].mean() for p in pillars],
        orientation="h", marker_color="rgba(231, 76, 60, 0.7)",
        text=[f"{dead_df[p].mean():.1f}" for p in pillars],
        textposition="outside",
    ))
    fig_pillar.update_layout(
        barmode="group", height=300,
        xaxis_title="Mean Pillar Score",
        margin=dict(t=10, b=40, l=140),
        legend=dict(orientation="h", y=1.1),
    )
    st.plotly_chart(fig_pillar, use_container_width=True)
    st.caption("dx_burden and lab_acuity drive the separation. tx_intensity and nlp_severity contribute minimally.")

    # ── 4. Deceased patient trajectory ───────────────────────────
    st.subheader("Trajectory: Deceased Cancer Patient")
    traj = df[df["HASTA_ID"] == "ANON_246177"].sort_values("EPISODE_TARIH")
    traj["date"] = pd.to_datetime(traj["EPISODE_TARIH"]).dt.date
    traj = traj.sort_values("severity_score", ascending=False).drop_duplicates("date").sort_values("EPISODE_TARIH")
    fig_traj = go.Figure()
    fig_traj.add_trace(go.Scatter(
        x=traj["EPISODE_TARIH"], y=traj["severity_score"],
        mode="lines+markers", name="Score",
        marker=dict(size=7, color="#E74C3C"),
        line=dict(width=2, color="#E74C3C"),
        hovertemplate="%{x}<br>Score: %{y:.1f}<extra></extra>",
    ))
    fig_traj.add_trace(go.Scatter(
        x=traj["EPISODE_TARIH"], y=traj["score_ewma"],
        mode="lines", name="EWMA trend",
        line=dict(width=2, color="#3498DB", dash="dot"),
    ))
    fig_traj.update_layout(
        yaxis_title="Severity Score", height=350,
        margin=dict(t=10, b=40), legend=dict(orientation="h", y=1.08),
    )
    st.plotly_chart(fig_traj, use_container_width=True)
    st.caption("ANON_246177 — 5 visits over 2 weeks. Score escalates 24→60 as cancer diagnosis + labs worsen. All 4 pillars present.")

    # ── 5. Summary metrics box ───────────────────────────────────
    st.subheader("Calibration Summary")
    st.dataframe(pd.DataFrame([
        {"Metric": "AUC (test, death_label_episode)", "Value": "0.940", "CI 95%": "[0.933 – 0.947]"},
        {"Metric": "AUC (train)", "Value": "0.916", "CI 95%": "[0.897 – 0.931]"},
        {"Metric": "Temporal split", "Value": "2022-12-31", "CI 95%": "train ≤ 2022, test > 2022"},
        {"Metric": "Deceased patients", "Value": "192", "CI 95%": "0.23% base rate"},
        {"Metric": "Bootstrap samples", "Value": "1,000", "CI 95%": "—"},
        {"Metric": "Score std", "Value": "11.9", "CI 95%": "Good discrimination"},
    ]), hide_index=True, use_container_width=True)

elif page == "Scoring Flow":
    st.title("Scoring Pipeline")

    # ── Scoring formula diagram (HTML) ──────────────────────────
    st.subheader("How a Score is Computed")

    cols = st.columns(4)
    for col, (name, pts, desc) in zip(cols, [
        ("dx_burden", 35, "ICD severity + history\nCharlson / Elixhauser"),
        ("lab_acuity", 25, "Abnormal / critical labs\n7-day window"),
        ("tx_intensity", 20, "Polypharmacy + oncology\n+ parenteral route"),
        ("nlp_severity", 20, "Symptom + chronic count\n+ negation"),
    ]):
        col.metric(name, f"max {pts} pts")
        col.caption(desc)

    st.markdown("---")
    c1, c2 = st.columns(2)
    c1.code("raw_score = dx + lab + tx + nlp", language=None)
    c2.code("possible_points = 35 + (25 if labs) + (20 if rx) + (20 if text)\n# Missing pillars excluded from denominator", language=None)
    st.markdown("---")
    st.code("severity_score = raw_score / possible_points × 100", language=None)

    # ── Cohort validation (HTML) ──────────────────────────────────
    st.subheader("Cohort Validation")

    c1, c2, c3 = st.columns(3)
    c1.metric("Deceased (191 pts)", "56.4")
    c2.metric("Cancer (198 pts)", "29.1")
    c3.metric("Check-up (197 pts)", "24.5")
    st.caption("Clinically expected ordering — emerged without training on mortality")

    # ── Two real patient examples ────────────────────────────────
    st.subheader("Worked Examples — Real Patients")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("#### Deceased Oncology Patient")
        st.markdown("**Visit:** Tibbi Onkoloji SGK Basvurusu")
        st.dataframe(pd.DataFrame([{
            "Pillar": "dx_burden",
            "Score": 31.5,
            "Max": 35,
            "Detail": "ICD severity_max=6 (metastatic), malignancy=1, 4 ICD chapters",
        }, {
            "Pillar": "lab_acuity",
            "Score": 25.0,
            "Max": 25,
            "Detail": "At cap — multiple critical labs (WBC, CRP, albumin)",
        }, {
            "Pillar": "tx_intensity",
            "Score": 0.0,
            "Max": 20,
            "Detail": "No prescriptions in 7-day window (excluded from denominator)",
        }, {
            "Pillar": "nlp_severity",
            "Score": 6.9,
            "Max": 20,
            "Detail": "Chronic mentions + some symptom burden",
        }]), hide_index=True, use_container_width=True)

        st.markdown(
            "**raw** = 31.5 + 25.0 + 0 + 6.9 = **63.4**\n\n"
            "**possible** = 35 + 25 + 0 + 20 = **80** (tx excluded — no rx data)\n\n"
            "**severity_score** = 63.4 / 80 × 100 = **79.3**"
        )

    with col_b:
        st.markdown("#### Routine Check-Up Patient")
        st.markdown("**Visit:** Kadin Hastaliklari ve Dogum SGK Basvurusu")
        st.dataframe(pd.DataFrame([{
            "Pillar": "dx_burden",
            "Score": 1.5,
            "Max": 35,
            "Detail": "Single low-severity ICD code, no malignancy, no history",
        }, {
            "Pillar": "lab_acuity",
            "Score": 0.0,
            "Max": 25,
            "Detail": "Labs present but all within normal range",
        }, {
            "Pillar": "tx_intensity",
            "Score": 1.8,
            "Max": 20,
            "Detail": "1-2 routine prescriptions, oral route",
        }, {
            "Pillar": "nlp_severity",
            "Score": 0.0,
            "Max": 20,
            "Detail": "No symptoms, no chronic mentions, routine visit",
        }]), hide_index=True, use_container_width=True)

        st.markdown(
            "**raw** = 1.5 + 0 + 1.8 + 0 = **3.3**\n\n"
            "**possible** = 35 + 25 + 20 + 20 = **100** (all pillars present)\n\n"
            "**severity_score** = 3.3 / 100 × 100 = **3.3**"
        )

elif page == "NLP Examples":
    # ── NLP Extraction Examples ──────────────────────────────────
    st.title("NLP Extraction Pipeline")
    st.caption("460-stem Turkish regex engine. Input → Normalized → Features.")

    st.dataframe(pd.DataFrame([
        {
            "Example": "1 — Multi-Symptom",
            "Raw (YAKINMA/MUAYENE)": "Öksürük, boğazda yanma, geniz akıntısı / Farinks hiperemik, kulaklar doğal",
            "symptom": 3, "negation": 0, "organs": 2, "chronic": 0, "routine": 0,
            "Why": "oksuruk (resp), bogazda yanma (ent), geniz akint (resp)",
        },
        {
            "Example": "2 — Negation-Heavy",
            "Raw (YAKINMA/MUAYENE)": "boğaz ağrısı / Farinks hiperemik, kript yok. Ral-ronküs yok",
            "symptom": 0, "negation": 2, "organs": 0, "chronic": 0, "routine": 0,
            "Why": "kript yok + ral-ronkus yok → all findings negated",
        },
        {
            "Example": "3 — Routine Check-Up",
            "Raw (YAKINMA/MUAYENE)": "CHECK UP YAKINMA YOK / EKG SR, EK SES YOK, EKO EF NORMAL",
            "symptom": 0, "negation": 0, "organs": 0, "chronic": 0, "routine": 1,
            "Why": "'check up' matches ROUTINE_RE",
        },
        {
            "Example": "4 — Mixed Signal",
            "Raw (YAKINMA/MUAYENE)": "ateş, burun akıntısı var / ht solunma eşit, ral yok, ronküs yok",
            "symptom": 2, "negation": 1, "organs": 2, "chronic": 1, "routine": 0,
            "Why": "ates (constitutional) + burun akint (resp). ronkus negated. 'ht' = chronic",
        },
    ]), hide_index=True, use_container_width=True, height=250)

    st.divider()

    st.subheader("Detailed Walkthrough")

    st.markdown("#### Example 1 — Multi-Symptom, Multi-Organ")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Raw**")
        st.code("YAKINMA: Öksürük, boğazda yanma, geniz akıntısı\nMUAYENE: Burunda deviasyon, seröz sekresyon.\nFarinks hiperemik. Kulaklar doğal", language=None)
    with col2:
        st.markdown("**Normalized**")
        st.code("oksuruk, bogazda yanma, geniz akintisi\n... farinks hiperemik ... kulaklar dogal", language=None)
    st.caption("3 symptoms: oksuruk (respiratory), bogazda yanma (ent), geniz akint (respiratory). 'dogal' only triggers on qualified patterns (e.g. 'batin normal'), not bare.")

    st.markdown("#### Example 2 — Negation-Heavy (Normal Exam)")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Raw**")
        st.code("YAKINMA: boğaz ağrısı\nMUAYENE: Farinks ve tonsiller hiperemik,\nkript yok. SS: HİHTSEK, Ral-ronküs yok", language=None)
    with col2:
        st.markdown("**Normalized**")
        st.code("bogaz agrisi ... kript yok ... ral-ronkus yok", language=None)
    st.caption("2 negations: kript yok + ral-ronkus yok. All findings negated → 0 organ systems affected.")

    st.markdown("#### Example 3 — Routine Check-Up")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Raw**")
        st.code("YAKINMA: CHECK UP YAKINMA YOK\nMUAYENE: EKG SR KALP RİTMİK EK SES YOK.\nEKO EF NORMAL. EFOR -", language=None)
    with col2:
        st.markdown("**Normalized**")
        st.code("check up yakinma yok\n... ek ses yok ... efor -", language=None)
    st.caption("'check up' matches ROUTINE_RE → is_routine=1. No symptom terms present to negate.")

    st.markdown("#### Example 4 — Mixed Signal (Symptoms + Negation + Chronic)")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Raw**")
        st.code("YAKINMA: ateş, burun akıntısı var\nMUAYENE: her iki ht solunma eşit katılıyor.\nral yok. ronküs yok sinüsler açık", language=None)
    with col2:
        st.markdown("**Normalized**")
        st.code("ates, burun akintisi var\n... ral yok. ronkus yok", language=None)
    st.caption("2 symptoms: ates (constitutional) + burun akint (respiratory). ronkus negated. 'ht' matches chronic pattern → chronic_mention=1.")

elif page == "Full Reports":
    st.title("ACUHIT — End-to-End Report")

    st.markdown("""
## 1. What Is ACUHIT?

A **4-pillar clinical severity score (0–100)** built from Turkish hospital data — 352,522 episodes, 83,104 patients, 192 deceased.
The score was **never trained on mortality**, yet achieves **AUC = 0.940** on death prediction (test set).

---

## 2. Data Pipeline

| Layer | Source | Scale |
|-------|--------|-------|
| **Raw** | 3 hospital tables (anadata, lab, recete) | 1.2M + 37.2M + 2.0M rows |
| **Silver** | Parsed, cleaned, normalized | 6 parquet files |
| **Gold** | Episode-level features (joins by patient + date) | 352K episodes, 7.4 MB |
| **Scored** | 4 pillar scores → composite | 352K rows |

**Engine:** DuckDB (threads=4, memory=2GB). No pandas on raw tables. Gold loads in 1.2s.

---

## 3. Four Scoring Pillars

| Pillar | Max | Source | Coverage | Standalone AUC |
|--------|-----|--------|----------|----------------|
| **dx_burden** | 35 | ICD-10 → Charlson (Quan 2005) + Elixhauser (Quan 2009) | 100% | 0.867 |
| **lab_acuity** | 25 | Hospital REFMIN/REFMAX, ±7d window | 65.5% | 0.855 |
| **tx_intensity** | 20 | WHO ATC 2024 + DrugBank + 900-entry brand bridge | 47.7% | 0.532 |
| **nlp_severity** | 20 | 220 Turkish stems, 27 negation patterns | 100% | 0.440 |

**Formula:** `severity_score = raw_score / possible_points × 100`
Missing pillars excluded from denominator (not zero-filled).

---

## 4. Reference Data Provenance

| Domain | Authority | Method |
|--------|-----------|--------|
| **ICD-10** | Quan et al. 2005/2009 (>10K citations) | comorbidipy prefix lists → severity weights |
| **Drugs** | WHO ATC/DDD 2024 + DrugBank 5.1.15 (CC0) + TITCK | Exact ATC match → classification from hierarchy |
| **Labs** | Hospital LIS instrument ranges | REFMIN/REFMAX per test, sex-aware |
| **Services** | Manual taxonomy (133 → 5 tiers) | Validation-only, not a scoring input |

All mapping CSVs include `_source` column. No regex classification, no LLM-generated mappings.

---

## 5. Validation Results

| Metric | Test Set | 95% CI |
|--------|---------|--------|
| **Death AUC (episode)** | **0.940** | 0.933–0.947 |
| Death AUC (patient-last) | 0.938 | 0.907–0.958 |
| Revisit 30d AUC | 0.865 | 0.851–0.877 |

**Temporal split:** train ≤ 2022-12-31, test > 2022-12-31. 1,000 bootstrap resamples.

**Cohort ordering** (no supervision): Deceased 56.4 > Cancer 29.1 > Check-up 24.5

**Calibration:** Top decile death rate = 5.9% vs 0.07% base (85× enrichment).

---

## 6. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Missing pillar → exclude from denominator | Avoids penalizing patients without labs/rx |
| Expert weights over data-optimal | Data-derived gives negative NLP weight (clinically absurd) |
| Lab at 25% despite data saying 47% | 34.5% of episodes lack labs — higher weight makes those unreliable |
| NLP kept at 20% despite AUC=0.440 | Inverted signal (terse oncology follow-ups). Kept for calibration |
| Strict `<` for history features | No current/future data leakage |
| Drug coverage 95.4% (honest) | ATC-backed only. 4.6% = UNRESOLVED, not catch-all |

---

## 7. Strengths & Limitations

**Strengths:**
- Construct validity without supervision (cohort ordering emerged naturally)
- Authoritative references only (Charlson, WHO ATC, DrugBank, hospital LIS)
- Reproducible end-to-end: `uv run python run_e2e.py raw pipeline iter` (~19 min)

**Limitations:**
- ~40 uncited coefficients (all marked `CALIBRATION_PENDING`)
- 192 deceased → wide confidence intervals
- NLP has inverted signal (deceased score lower)
- No external validation dataset
- Lab join is symmetric (±7d) — may include future labs
""")


# ── Footer ───────────────────────────────────────────────────────
st.divider()
st.caption(f"ACUHIT — Dr. Mundo | AUC=0.940 | {N_EPISODES_FULL:,} episodes, {N_PATIENTS_FULL:,} patients (1% sample displayed)")
