---
name: clinicaltrialskill
description: ClinicalTrials.gov Protocol Postings & Life Sciences CROs. Connects clinical trial sponsors (biotech & pharma) burning $50,000+/day in venture cash with trial site management organizations (SMOs), clinical research coordinators, and specialized CROs for rapid patient recruitment. Includes verified direct emails for Chief Medical Officers, VPs of Clinical Operations, and Site Trial Coordinators.
---

# ClinicalTrials.gov Protocol Postings & Life Sciences CROs

**A pharmaceutical or biotech sponsor receives FDA Investigational New Drug (IND) clearance and posts an official study status: "Recruiting" or "Not Yet Recruiting". The sponsor is burning $50,000+/day in venture cash, and every month a trial is delayed due to slow patient enrollment costs up to $1,000,000+ in patent exclusivity loss. Specialized site coordinators and clinical research organizations (CROs) have the pre-screened patient registries and trial beds the sponsor needs to hit their FDA milestone.**

---

## The Operational Reality & Ground Truth

### 1. The High-Urgency Signal
* **The Bleed ($50k+/Day & $1M+/Month Patent Loss)**: Running a Phase 1–3 clinical trial carries burn rates exceeding **$50,000 to $100,000 per day**. If patient enrollment stalls, the drug's 20-year patent clock continues ticking, resulting in **$1M to $10M+** in lost peak annual revenues.
* **The Failure Rate (80% of Trials Delayed)**: Over **80% of clinical trials** fail to meet initial recruitment timelines; 50% of trial sites enroll one or zero patients.
* **The Regulatory Trigger**: Under federal regulation (FDAAA 801 / 42 CFR Part 11), sponsors must register interventional trials on ClinicalTrials.gov within 21 days of first patient enrollment, publishing their study phase, target conditions, and public contacts.

### 2. Both Emails Inside the Public Record (Zero Guesswork)
Federal disclosure mandates that every trial record publish direct points of contact:
1. **Demand Field (Sponsor Leadership)**:
   * **Central Contact Email** & **Overall Study Official Email**.
   * Typically the **Chief Medical Officer (CMO)**, **VP of Clinical Operations**, or **Clinical Trial Director**.
2. **Supply Field (Site Coordinators & CRO / SMO Facilities)**:
   * **Facility / Investigator Locations** lists every trial site, clinical department, hospital, or dedicated research site.
   * Direct **Site Coordinator Email**, **Principal Investigator (PI)**, and site intake contact.

---

## Mandatory Core Rule: Cross-Campaign Historical Deduplication

**Never email the same recipient twice across any campaign.**

Before launching ANY campaign, all extracted leads MUST be cross-referenced against historical sends in the Warmbly database:

```sql
SELECT DISTINCT LOWER(c.email) 
FROM campaign_contact_progress ccp 
JOIN contacts c ON c.id = ccp.contact_id 
WHERE ccp.sent_at IS NOT NULL;
```

Any lead whose email address was already emailed in ANY past campaign MUST be filtered out completely before loading or sending. The `scripts/clinicaltrialmarket.py` engine automatically enforces this rule by querying the Warmbly PostgreSQL database and screening against the local `data/given.csv` ledger.

---

## The Liquid Clearinghouse Architecture

Instead of locking 1 biotech sponsor to 1 local clinic, demand and supply are organized into **Indication & Therapeutic Area Clearinghouse Pools**:

```
           [DEMAND POOL]                                   [SUPPLY POOL]
 (Biotech Sponsors Under Active $50k/Day Burn)       (Trial Sites / SMOs / CROs with Patient Registries)
  ├── Mediar Therapeutics (Fibrosis / Rare)          ├── Arizona Clinical Trials (Multi-specialty Site)
  ├── Tarapeutics Science (Oncology / Immunotherapy) ├── Florida Research Institute (Metabolic / Neuro)
  ├── AbbVie / Mid-cap Biotechs (Oncology)           ├── UCSF / Academic Health Sites (Specialty Beds)
  └── Boston Biotech Series B (Neurology / CNS)       └── Global CROs / SMO Site Networks
                      \                                   /
                       \                                 /
                        ▼                               ▼
                       [DYNAMIC MATCHING ON FIRST REPLY]
```

### Why the Liquid Clearinghouse Wins:
1. **Instant Match on First Reply**: Ping all sponsors and matching trial sites simultaneously. Whichever site confirms patient intake capacity first receives the referral introduction.
2. **Category Pitch Protection**: You pitch network-level trial recruitment capability (*"We work with clinical research site networks and patient registries specializing in [Therapeutic Indication]..."*).
3. **Double-Sided Monetization**:
   * **Sponsor Side**: Paid site placement or recruiting acceleration retainer.
   * **Site / CRO Side**: Per-enrolled-patient referral fee (**$1,500 – $4,500 per patient**) or trial placement referral agreement (**$5,000 – $10,000 flat fee** upon trial contract execution).

---

## Cold Outreach Copy & Multi-Touch Sequence

### Email 1: Demand Outreach (To Sponsor VP of Clinical Operations / CMO)
```text
Subject: Patient recruitment bandwidth for {{trial_title}} ({{nct_id}})

Hey {{firstName}},

Saw {{company}} recently posted the {{phase}} study for {{condition}} on ClinicalTrials.gov ({{nct_id}}).

Given the burn rate once sites go active, keeping enrollment on schedule across your target patient cohort is always a battle.

We work with dedicated clinical research sites and pre-screened patient registries with immediate investigator capacity in {{condition}}.

Would it be helpful to see if our site network has intake bandwidth for your protocol?

Best,
Abdulaziz
```

### Email 2: Supply Outreach (To Clinical Trial Site Coordinator / SMO Director)
```text
Subject: Protocol referral intake: {{condition}} study

Hi {{firstName}},

Checking your site's protocol capacity at {{facility_name}}.

We have an active sponsor running a {{phase}} study for {{condition}} looking to expand trial site locations and boost patient recruitment velocity.

Does your site currently have open investigator bandwidth and an active patient pool for {{condition}} studies?

If you have open capacity, let me know and I'll route the protocol details over.

Best,
Abdulaziz
```

---

## Command Reference

### 1. Ingest ClinicalTrials.gov Data
```bash
# Fetch latest interventional studies with active recruiting status
python3 scripts/fetch_clinical_trials.py --pages 10 --query "Interventional" --location "United States"
```

### 2. Export Filtered Demand & Supply CSVs
```bash
# Export both Demand (Sponsors) and Supply (Sites) respecting Warmbly DB deduplication
python3 scripts/clinicaltrialmarket.py --side both --limit 100

# Export Demand only with optional Apollo enrichment
python3 scripts/clinicaltrialmarket.py --side demand --limit 50 --apollo-key "$APOLLO_API_KEY"

# Export Supply only
python3 scripts/clinicaltrialmarket.py --side supply --limit 100
```
