"""
name_parser.py — Executive, Clinical Investigator & Site Coordinator Contact Parser for clinicaltrialskill.

Handles parsing and standardizing:
1. Clinical Operations Executives (VP Clinical Operations, Chief Medical Officer, Clinical Trial Manager)
2. Site Coordinators & Principal Investigators (CRC, Study Coordinator, Site Director, PI)
3. Salutation normalization ('Dr. Smith', 'Jeffrey', 'Sarah', 'there')
4. Sponsor and Hospital / SMO entity name cleaning
"""

import re

ENTITY_KW = re.compile(
    r'\b(inc\.?|llc|l\.l\.c\.?|corp\.?|corporation|therapeutics|pharmaceuticals?|'
    r'pharma|biosciences?|biotech|technologies|holdings?|ltd\.?|limited|'
    r'medical center|hospital|university|health|clinic|foundation)\b',
    re.I
)

SPONSOR_TITLE_PATTERNS = [
    (re.compile(r'\b(chief medical officer|cmo)\b', re.I), "Chief Medical Officer"),
    (re.compile(r'\b(vp\b.*clinical|vice president.*clinical)\b', re.I), "VP of Clinical Operations"),
    (re.compile(r'\b(head.*clinical operations|head.*clinical ops)\b', re.I), "Head of Clinical Operations"),
    (re.compile(r'\b(director.*clinical operations|clinical ops director)\b', re.I), "Director of Clinical Operations"),
    (re.compile(r'\b(clinical trial manager|ctm|study manager)\b', re.I), "Clinical Trial Manager"),
    (re.compile(r'\b(medical director)\b', re.I), "Medical Director"),
    (re.compile(r'\b(chief executive officer|ceo)\b', re.I), "Chief Executive Officer"),
    (re.compile(r'\b(regulatory.*affairs)\b', re.I), "Director of Regulatory Affairs"),
    (re.compile(r'\b(study chair|study director)\b', re.I), "Study Director"),
]

SITE_TITLE_PATTERNS = [
    (re.compile(r'\b(principal investigator|pi)\b', re.I), "Principal Investigator"),
    (re.compile(r'\b(clinical research coordinator|crc)\b', re.I), "Clinical Research Coordinator"),
    (re.compile(r'\b(study coordinator|site coordinator)\b', re.I), "Site Study Coordinator"),
    (re.compile(r'\b(site director|clinical trial director)\b', re.I), "Clinical Trial Site Director"),
    (re.compile(r'\b(sub-investigator|sub investigator)\b', re.I), "Sub-Investigator"),
    (re.compile(r'\b(patient recruitment manager|recruitment coordinator)\b', re.I), "Patient Recruitment Manager"),
]


def clean_word(w):
    return w.strip('.,;()/-\'\"')


def clean_sponsor_name(name):
    """Clean sponsor company name for natural email copy."""
    if not name:
        return ""
    # Strip suffixes like Inc., LLC, Co. but keep core branding (e.g., 'Mediar Therapeutics' -> 'Mediar Therapeutics')
    name = re.sub(r',\s*(Inc\.?|LLC|Corp\.?|Ltd\.?)\b', '', name, flags=re.I)
    name = re.sub(r'\s+(Inc\.?|LLC|Corp\.?|Ltd\.?)$', '', name, flags=re.I)
    return name.strip(' ,.-')


def extract_sponsor_title(text, role_hint=None):
    if text:
        for pat, label in SPONSOR_TITLE_PATTERNS:
            if pat.search(text):
                return label
    if role_hint:
        role_upper = role_hint.upper()
        if "STUDY_CHAIR" in role_upper:
            return "Study Chair / Chief Medical Officer"
        if "STUDY_DIRECTOR" in role_upper:
            return "Study Director / VP of Clinical Operations"
        if "CONTACT" in role_upper:
            return "VP / Director of Clinical Operations"
    return "VP of Clinical Operations / CMO"


def extract_site_title(text, role_hint=None):
    if text:
        for pat, label in SITE_TITLE_PATTERNS:
            if pat.search(text):
                return label
    if role_hint:
        role_upper = role_hint.upper()
        if "PRINCIPAL_INVESTIGATOR" in role_upper:
            return "Principal Investigator"
        if "SUB_INVESTIGATOR" in role_upper:
            return "Sub-Investigator"
        if "CONTACT" in role_upper:
            return "Clinical Research Site Coordinator"
    return "Clinical Trial Site Coordinator"


def parse_contact_name(full_name, default_greeting="there"):
    """
    Given 'Jeffrey Bornstein, MD' or 'Dr. Todd Astor' or 'Katherine Palu',
    extracts clean first_name, last_name, greeting (e.g. 'Dr. Bornstein' or 'Jeffrey').
    """
    if not full_name:
        return "", "", default_greeting

    cleaned = full_name.strip()

    # Detect degrees/credentials after name (MD, PhD, DO, PharmD, MS, RN, BSN, etc.)
    has_medical_degree = bool(re.search(r'\b(MD|M\.D\.|DO|D\.O\.|PhD|Ph\.D\.|PharmD)\b', cleaned, re.I))
    
    # Strip degree credentials from name part
    cleaned = re.sub(r'[,/]?\s*(MD|M\.D\.|DO|D\.O\.|PhD|Ph\.D\.|PharmD|BSN|RN|MS|MA|MPH|CCRC|CCRP)\b.*$', '', cleaned, flags=re.I).strip()

    # Strip prefixes like Mr., Ms., Mrs., Dr.
    honorific_match = re.match(r'^(Dr\.|Doctor|Mr\.|Ms\.|Mrs\.)\s+(.*)', cleaned, re.I)
    honorific = ""
    if honorific_match:
        honorific = honorific_match.group(1)
        if honorific.lower() in ['dr.', 'doctor']:
            has_medical_degree = True
        cleaned = honorific_match.group(2).strip()

    parts = cleaned.split()
    if not parts:
        return "", "", default_greeting

    first = clean_word(parts[0])
    last = clean_word(parts[-1]) if len(parts) > 1 else ""

    # Check for middle initials (e.g. 'John A. Smith' -> first: 'John')
    if len(parts) >= 2 and len(first) == 1 and parts[0].endswith('.'):
        first = clean_word(parts[1])

    # Build greeting
    if (has_medical_degree or honorific.lower() in ['dr.', 'doctor']) and last:
        greeting = f"Dr. {last}"
    elif first:
        greeting = first
    else:
        greeting = default_greeting

    return first, last, greeting
