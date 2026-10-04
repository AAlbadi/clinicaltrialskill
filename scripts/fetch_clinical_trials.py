#!/usr/bin/env python3
"""
fetch_clinical_trials.py — Scrapes & synchronizes active interventional clinical trials
from the official ClinicalTrials.gov Public API v2.

Extracts:
1. DEMAND: Sponsor Central Contacts, Medical Directors, Chief Medical Officers, and VP of Clinical Operations
   who are burning $50k+/day and desperately need patient enrollment velocity.
2. SUPPLY: Trial Site Management Organizations (SMOs), Principal Investigators, and Site Coordinators
   with active trial beds and pre-screened patient registries.
"""

import argparse
import csv
import gzip
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(HERE, "data")
API_ENDPOINT = "https://clinicaltrials.gov/api/v2/studies"


def clean_str(s):
    if not s:
        return ""
    return re.sub(r'\s+', ' ', str(s)).strip()


def fetch_trials(max_pages=10, page_size=100, query_term="Interventional", status="RECRUITING,NOT_YET_RECRUITING", location="United States"):
    """Fetch interventional studies with active recruiting status from ClinicalTrials.gov."""
    params = {
        "query.term": query_term,
        "filter.overallStatus": status,
        "pageSize": str(page_size),
    }
    if location:
        params["query.locn"] = location

    sponsors_list = []
    sites_list = []

    next_page_token = None
    page = 0

    headers = {
        "User-Agent": "ClinicalTrialSkill/1.0 (Biotech Life Sciences Matching Pipeline; contact@warmbly.com)",
        "Accept": "application/json"
    }

    print(f"[*] Starting ClinicalTrials.gov API fetch (target: up to {max_pages} pages, {page_size} per page)...")

    while page < max_pages:
        page += 1
        query_dict = dict(params)
        if next_page_token:
            query_dict["pageToken"] = next_page_token

        url = f"{API_ENDPOINT}?{urllib.parse.urlencode(query_dict)}"
        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"[!] Error fetching page {page}: {e}")
            break

        studies = data.get("studies", [])
        if not studies:
            print(f"[*] No more studies returned on page {page}.")
            break

        print(f"    Page {page}: received {len(studies)} study records.")

        for s in studies:
            ps = s.get("protocolSection", {})
            id_mod = ps.get("identificationModule", {})
            nct_id = id_mod.get("nctId", "")
            brief_title = clean_str(id_mod.get("briefTitle", ""))
            official_title = clean_str(id_mod.get("officialTitle", "")) or brief_title

            spon_mod = ps.get("sponsorCollaboratorsModule", {})
            lead_sponsor = clean_str(spon_mod.get("leadSponsor", {}).get("name", ""))
            sponsor_class = spon_mod.get("leadSponsor", {}).get("class", "INDUSTRY")

            status_mod = ps.get("statusModule", {})
            overall_status = status_mod.get("overallStatus", "")
            start_date = status_mod.get("startDateStruct", {}).get("date", "")

            design_mod = ps.get("designModule", {})
            phases = ", ".join(design_mod.get("phases", [])) or "N/A"
            study_type = design_mod.get("studyType", "INTERVENTIONAL")

            cond_mod = ps.get("conditionsModule", {})
            conditions = "; ".join(cond_mod.get("conditions", [])[:4])

            clm = ps.get("contactsLocationsModule", {})

            # 1. DEMAND: Sponsor Central Contacts & Overall Officials
            central_contacts = clm.get("centralContacts", [])
            overall_officials = clm.get("overallOfficials", [])

            for cc in central_contacts:
                email = clean_str(cc.get("email", "")).lower()
                name = clean_str(cc.get("name", ""))
                phone = clean_str(cc.get("phone", ""))
                role = clean_str(cc.get("role", "CONTACT"))
                if email and "@" in email and "." in email:
                    sponsors_list.append({
                        "nct_id": nct_id,
                        "sponsor_name": lead_sponsor,
                        "sponsor_class": sponsor_class,
                        "contact_name": name,
                        "contact_role": role,
                        "email": email,
                        "phone": phone,
                        "trial_title": brief_title,
                        "official_title": official_title,
                        "phases": phases,
                        "conditions": conditions,
                        "status": overall_status,
                        "start_date": start_date,
                        "study_type": study_type
                    })

            # Check overall officials if they have emails (often researchers or CMOs)
            for oo in overall_officials:
                # Some API records include contact fields inside officials
                email = clean_str(oo.get("email", "")).lower()
                if email and "@" in email:
                    sponsors_list.append({
                        "nct_id": nct_id,
                        "sponsor_name": lead_sponsor,
                        "sponsor_class": sponsor_class,
                        "contact_name": clean_str(oo.get("name", "")),
                        "contact_role": clean_str(oo.get("role", "STUDY_DIRECTOR")),
                        "email": email,
                        "phone": clean_str(oo.get("phone", "")),
                        "trial_title": brief_title,
                        "official_title": official_title,
                        "phases": phases,
                        "conditions": conditions,
                        "status": overall_status,
                        "start_date": start_date,
                        "study_type": study_type
                    })

            # 2. SUPPLY: Trial Site Management Organizations & Site Coordinators
            locations = clm.get("locations", [])
            for loc in locations:
                facility = clean_str(loc.get("facility", ""))
                city = clean_str(loc.get("city", ""))
                state = clean_str(loc.get("state", ""))
                country = clean_str(loc.get("country", ""))
                zip_code = clean_str(loc.get("zip", ""))
                loc_status = loc.get("status", overall_status)

                loc_contacts = loc.get("contacts", [])
                for lc in loc_contacts:
                    email = clean_str(lc.get("email", "")).lower()
                    name = clean_str(lc.get("name", ""))
                    phone = clean_str(lc.get("phone", ""))
                    role = clean_str(lc.get("role", "SITE_COORDINATOR"))
                    if email and "@" in email and "." in email:
                        sites_list.append({
                            "nct_id": nct_id,
                            "facility_name": facility,
                            "city": city,
                            "state": state,
                            "country": country,
                            "zip": zip_code,
                            "contact_name": name,
                            "contact_role": role,
                            "email": email,
                            "phone": phone,
                            "sponsor_name": lead_sponsor,
                            "trial_title": brief_title,
                            "phases": phases,
                            "conditions": conditions,
                            "status": loc_status
                        })

        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            print("[*] Reached end of available results.")
            break

        time.sleep(0.4)

    print(f"\n[✓] Ingestion complete:")
    print(f"    - Demand (Sponsor Execs): {len(sponsors_list)} records")
    print(f"    - Supply (Trial Sites / CROs / SMOs): {len(sites_list)} records")

    return sponsors_list, sites_list


def deduplicate_records(records, key_func):
    seen = set()
    deduped = []
    for r in records:
        k = key_func(r)
        if k not in seen:
            seen.add(k)
            deduped.append(r)
    return deduped


def save_to_gz(records, filepath):
    if not records:
        print(f"[!] Warning: No records to save to {filepath}")
        return
    keys = list(records[0].keys())
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with gzip.open(filepath, "wt", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(records)
    print(f"[✓] Saved {len(records)} records to {filepath}")


def main():
    parser = argparse.ArgumentParser(description="Fetch public clinical trials data from ClinicalTrials.gov")
    parser.add_argument("--pages", type=int, default=10, help="Number of pages to scrape (100 studies/page)")
    parser.add_argument("--query", type=str, default="Interventional", help="Search query term")
    parser.add_argument("--location", type=str, default="United States", help="Geographic location query")
    args = parser.parse_args()

    sponsors, sites = fetch_trials(
        max_pages=args.pages,
        page_size=100,
        query_term=args.query,
        location=args.location
    )

    # Deduplicate demand by (email, nct_id)
    sponsors_deduped = deduplicate_records(sponsors, lambda r: (r["email"], r["nct_id"]))
    # Deduplicate supply by (email, facility_name)
    sites_deduped = deduplicate_records(sites, lambda r: (r["email"], r["facility_name"]))

    demand_path = os.path.join(DATA_DIR, "demand.csv.gz")
    supply_path = os.path.join(DATA_DIR, "supply.csv.gz")

    save_to_gz(sponsors_deduped, demand_path)
    save_to_gz(sites_deduped, supply_path)


if __name__ == "__main__":
    main()
