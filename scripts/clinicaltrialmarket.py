#!/usr/bin/env python3
"""
clinicaltrialmarket.py — Matches Clinical Trial Sponsors burning $50k+/day
with Site Management Organizations (SMOs), Trial Site Directors, and specialized CROs.

Methodology:
- Supply (Sites / CROs / SMOs): Trial site coordinators, clinical research directors,
  and site management organizations with pre-screened patient registries and immediate investigator capacity.
- Demand (Sponsor Execs): Pharma, Biotech & Medical Device sponsors under active 'Recruiting'
  or 'Not Yet Recruiting' status needing rapid patient recruitment velocity before patent exclusivity loss.
- Cross-Campaign Deduplication: Verifies against Warmbly PostgreSQL database of historical sends
  and tracks local dispatched leads in data/given.csv.
- Apollo Decision Maker Discovery: Integration (--apollo-key or APOLLO_API_KEY) to enrich
  Chief Medical Officers, VP of Clinical Operations, and Clinical Trial Managers with direct phone/email.
"""

import argparse
import csv
import datetime
import gzip
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(HERE, "data")
LEDGER = os.path.join(DATA_DIR, "given.csv")
TODAY = datetime.date.today()
STAMP = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")

sys.path.insert(0, os.path.join(HERE, "scripts"))
from name_parser import parse_contact_name, extract_sponsor_title, extract_site_title, clean_sponsor_name

TARGET_TITLES = [
    "Chief Medical Officer",
    "CMO",
    "VP of Clinical Operations",
    "Vice President of Clinical Operations",
    "Head of Clinical Operations",
    "Director of Clinical Operations",
    "Clinical Operations Director",
    "Clinical Trial Manager",
    "Director of Clinical Development",
    "Chief Executive Officer",
    "CEO",
    "President"
]


def free_path(folder, stem):
    """Never overwrite an existing export file."""
    p = os.path.join(folder, f"{stem}-{STAMP}.csv")
    n = 2
    while os.path.exists(p):
        p = os.path.join(folder, f"{stem}-{STAMP}-{n}.csv")
        n += 1
    return p


def read_gz(filename):
    p = os.path.join(DATA_DIR, filename)
    if not os.path.exists(p):
        sys.exit(f"[!] Error: Missing required dataset file {p}. Run fetch_clinical_trials.py first.")
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def get_warmbly_historical_sent():
    """Query Warmbly PostgreSQL database to fetch all emails sent in past campaigns."""
    try:
        cmd = [
            "docker", "exec", "-i", "warmbly-postgres-1",
            "psql", "-U", "warmbly", "-d", "warmbly", "-t", "-A", "-c",
            "SELECT DISTINCT LOWER(c.email) FROM campaign_contact_progress ccp JOIN contacts c ON c.id = ccp.contact_id WHERE ccp.sent_at IS NOT NULL;"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        if res.returncode == 0:
            emails = set(line.strip().lower() for line in res.stdout.splitlines() if line.strip())
            return emails
    except Exception:
        pass
    return set()


def load_ledger():
    if not os.path.exists(LEDGER):
        return set(), set()
    seen_emails, seen_nct = set(), set()
    with open(LEDGER, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            e = (r.get("email") or "").strip().lower()
            if e:
                seen_emails.add(e)
            nct = (r.get("nct_id") or "").strip().upper()
            if nct:
                seen_nct.add(nct)
    return seen_emails, seen_nct


def record_given(rows):
    os.makedirs(DATA_DIR, exist_ok=True)
    file_exists = os.path.exists(LEDGER)
    with open(LEDGER, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["nct_id", "email", "name", "role", "organization", "type", "date_given"])
        for r in rows:
            writer.writerow([
                r.get("nct_id", ""),
                r.get("email", ""),
                r.get("contact_name", "") or r.get("firstName", ""),
                r.get("role", "") or r.get("title", ""),
                r.get("organization", "") or r.get("company", ""),
                r.get("pool_type", ""),
                TODAY.isoformat()
            ])


def enrich_via_apollo(company_name, apollo_key):
    """Optionally query Apollo API to discover senior Clinical Ops decision makers."""
    if not apollo_key or not company_name:
        return None
    url = "https://api.apollo.io/api/v1/mixed_people/api_search"
    payload = {
        "api_key": apollo_key,
        "q_organization_name": company_name,
        "person_titles": TARGET_TITLES,
        "page": 1,
        "per_page": 3
    }
    headers = {"Content-Type": "application/json", "Cache-Control": "no-cache"}
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            people = data.get("people", [])
            for p in people:
                em = p.get("email")
                fn = p.get("first_name")
                ln = p.get("last_name")
                title = p.get("title")
                if em and "@" in em:
                    return {
                        "firstName": fn,
                        "lastName": ln,
                        "email": em.strip().lower(),
                        "title": title,
                        "linkedin_url": p.get("linkedin_url", "")
                    }
    except Exception:
        pass
    return None


def export_demand(args, warmbly_sent, seen_emails, seen_nct):
    """Export Demand: Biotech / Pharma Clinical Operations & CMO Contacts."""
    records = read_gz("demand.csv.gz")
    out_rows = []
    given_rows = []

    print(f"[*] Processing {len(records)} raw demand records from ClinicalTrials.gov...")

    for r in records:
        email = (r.get("email") or "").strip().lower()
        nct_id = (r.get("nct_id") or "").strip().upper()
        sponsor_name = clean_sponsor_name(r.get("sponsor_name", ""))

        if not email or "@" not in email:
            continue
        if email in warmbly_sent:
            continue
        if email in seen_emails:
            continue

        raw_name = r.get("contact_name", "")
        first, last, greeting = parse_contact_name(raw_name)
        title = extract_sponsor_title(raw_name, r.get("contact_role"))

        # Apollo lookup if requested and email is generic/call center
        is_generic_email = any(x in email for x in ["info@", "contact@", "clinicaltrials@", "trials@", "callcenter@", "medinfo@"])
        if args.apollo_key and is_generic_email:
            apollo_match = enrich_via_apollo(sponsor_name, args.apollo_key)
            if apollo_match:
                email = apollo_match["email"]
                first = apollo_match["firstName"] or first
                last = apollo_match["lastName"] or last
                greeting = first
                title = apollo_match["title"] or title

        apollo_url = f"https://app.apollo.io/#/people?qOrganizationName={urllib.parse.quote(sponsor_name)}&personTitles[]={urllib.parse.quote('Clinical Operations')}&personTitles[]={urllib.parse.quote('Chief Medical Officer')}"

        row = {
            "email": email,
            "firstName": first or "Trial Sponsor",
            "lastName": last,
            "greeting": greeting,
            "title": title,
            "company": sponsor_name,
            "nct_id": nct_id,
            "trial_title": r.get("trial_title", ""),
            "phase": r.get("phases", "Interventional"),
            "condition": r.get("conditions", "").split(";")[0].strip(),
            "status": r.get("status", "RECRUITING"),
            "phone": r.get("phone", ""),
            "apollo_reveal_url": apollo_url,
            "pool_type": "Demand - Sponsor Exec"
        }

        out_rows.append(row)
        given_rows.append({
            "nct_id": nct_id,
            "email": email,
            "contact_name": f"{first} {last}".strip(),
            "role": title,
            "organization": sponsor_name,
            "pool_type": "demand"
        })

        if args.limit and len(out_rows) >= args.limit:
            break

    out_file = free_path(HERE, "clinical_trials_demand_sponsors")
    if out_rows:
        keys = list(out_rows[0].keys())
        with open(out_file, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(out_rows)
        print(f"[✓] Demand Export: Generated {len(out_rows)} ready-to-send sponsor leads -> {out_file}")
        if not args.dry_run:
            record_given(given_rows)
    else:
        print("[!] No new demand leads met filtering criteria.")
    return out_file


def export_supply(args, warmbly_sent, seen_emails, seen_nct):
    """Export Supply: Site Coordinators, SMOs & Clinical Research Facilities."""
    records = read_gz("supply.csv.gz")
    out_rows = []
    given_rows = []

    print(f"[*] Processing {len(records)} raw supply records from ClinicalTrials.gov...")

    for r in records:
        email = (r.get("email") or "").strip().lower()
        facility = (r.get("facility_name") or "").strip()
        nct_id = (r.get("nct_id") or "").strip().upper()

        if not email or "@" not in email:
            continue
        if email in warmbly_sent:
            continue
        if email in seen_emails:
            continue

        raw_name = r.get("contact_name", "")
        first, last, greeting = parse_contact_name(raw_name)
        title = extract_site_title(raw_name, r.get("contact_role"))

        row = {
            "email": email,
            "firstName": first or "Site Coordinator",
            "lastName": last,
            "greeting": greeting,
            "title": title,
            "facility_name": facility,
            "city": r.get("city", ""),
            "state": r.get("state", ""),
            "country": r.get("country", ""),
            "nct_id": nct_id,
            "sponsor_name": r.get("sponsor_name", ""),
            "trial_title": r.get("trial_title", ""),
            "phase": r.get("phases", "Interventional"),
            "condition": r.get("conditions", "").split(";")[0].strip(),
            "phone": r.get("phone", ""),
            "pool_type": "Supply - Trial Site / SMO / CRO"
        }

        out_rows.append(row)
        given_rows.append({
            "nct_id": nct_id,
            "email": email,
            "contact_name": f"{first} {last}".strip(),
            "role": title,
            "organization": facility,
            "pool_type": "supply"
        })

        if args.limit and len(out_rows) >= args.limit:
            break

    out_file = free_path(HERE, "clinical_trials_supply_sites")
    if out_rows:
        keys = list(out_rows[0].keys())
        with open(out_file, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(out_rows)
        print(f"[✓] Supply Export: Generated {len(out_rows)} ready-to-send site/CRO leads -> {out_file}")
        if not args.dry_run:
            record_given(given_rows)
    else:
        print("[!] No new supply leads met filtering criteria.")
    return out_file


def main():
    parser = argparse.ArgumentParser(description="Clinical Trials Demand & Supply Clearinghouse Engine")
    parser.add_argument("--side", choices=["demand", "supply", "both"], default="both", help="Which side of clearinghouse to export")
    parser.add_argument("--limit", type=int, default=100, help="Max leads to export per side")
    parser.add_argument("--apollo-key", type=str, default=os.environ.get("APOLLO_API_KEY"), help="Optional Apollo API key")
    parser.add_argument("--dry-run", action="store_true", help="Do not record dispatched leads to given.csv")
    args = parser.parse_args()

    warmbly_sent = get_warmbly_historical_sent()
    seen_emails, seen_nct = load_ledger()

    print(f"[*] Ledger & Database Gate loaded:")
    print(f"    - Historical Warmbly Sent emails: {len(warmbly_sent)}")
    print(f"    - Local ledger dispatched emails: {len(seen_emails)}")

    if args.side in ["demand", "both"]:
        export_demand(args, warmbly_sent, seen_emails, seen_nct)
    if args.side in ["supply", "both"]:
        export_supply(args, warmbly_sent, seen_emails, seen_nct)


if __name__ == "__main__":
    main()
