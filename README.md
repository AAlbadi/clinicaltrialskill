# ClinicalTrials.gov Protocol Postings & Life Sciences CROs (`clinicaltrialskill`)

Connects biotech and pharmaceutical sponsors burning **$50,000+/day** in venture cash with clinical trial sites, site management organizations (SMOs), and specialized CROs for rapid patient recruitment.

## Installation & Setup

```bash
cd .agents/skills/clinicaltrialskill
pip install -r requirements.txt # Standard Python 3 standard library, zero external pip dependencies required!
```

## Running the Skill

### 1. Ingest Data
```bash
python3 scripts/fetch_clinical_trials.py --pages 10
```

### 2. Export Demand & Supply Lists
```bash
python3 scripts/clinicaltrialmarket.py --side both --limit 100
```
