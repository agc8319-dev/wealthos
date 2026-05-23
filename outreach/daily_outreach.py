#!/usr/bin/env python3
"""
Cold Outreach Daily Script — Seen Safety
Finds 10 companies + 3 HSE/Ops contacts each via Apollo,
generates AI-personalized outreach via Claude,
saves everything to Airtable, creates Gmail drafts,
and logs a daily activity to Pipedrive.

Usage:
  python outreach/daily_outreach.py
  python outreach/daily_outreach.py --industry "Construction"
  python outreach/daily_outreach.py --dry-run
"""

import os
import sys
import json
import argparse
import time
from datetime import date
import requests

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic package not installed. Run: pip install -r outreach/requirements.txt")
    sys.exit(1)

# Gmail support — optional
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    import base64
    from email.mime.text import MIMEText
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False

# ── Environment variables ──────────────────────────────────────────────────────
AIRTABLE_TOKEN    = os.environ.get("AIRTABLE_TOKEN", "")
APOLLO_API_KEY    = os.environ.get("APOLLO_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
PIPEDRIVE_API_KEY = os.environ.get("PIPEDRIVE_API_KEY", "")
PIPEDRIVE_DOMAIN  = os.environ.get("PIPEDRIVE_DOMAIN", "")
GMAIL_TOKEN_FILE  = os.environ.get("GMAIL_TOKEN_FILE", "outreach/gmail_token.json")

# ── Airtable IDs ───────────────────────────────────────────────────────────────
AT_BASE      = "app0GlBSe5GZzwtdi"
AT_COMPANIES = "tblRQy6FOAZ257MIA"
AT_CONTACTS  = "tblK6dCGng49LO7cl"
AT_BATCHES   = "tblP9BzjJOJcKnLiT"

COMPANY_F = {
    "name":           "fldqpJKMBbLmhOELk",
    "industry":       "flde2rrwDSFBKtuln",
    "website":        "fldd5NkQRsiuRWySH",
    "linkedin_url":   "fldflQcW7wpfTHAfg",
    "employees":      "fldLxKSzRm0RKNwdz",
    "city":           "fldp1vBXpNXH2ALSs",
    "state":          "fldJ6P01Aec3PlviK",
    "apollo_id":      "fldW843iGlR6Szbls",
    "ai_research":    "fldhDzIvK6rZ8ykER",
    "batch_date":     "fldL2EpJzxhdRvAxE",
    "industry_focus": "fldODo8NcfcwHDssK",
}

CONTACT_F = {
    "name":          "fldtLhRfRKw8qnvYa",
    "first_name":    "fldOVnVVnayEKIurL",
    "last_name":     "fldjAQfdJxCD5PGXe",
    "title":         "fldchBxq7gq85X2Za",
    "email":         "fldnYb3OjtIUUEwAq",
    "linkedin_url":  "fldvfl4uG9OBoqLJz",
    "company_link":  "fldMmyO7YRGRqzP6C",
    "apollo_id":     "fldDhGpzcOcONPokn",
    "ai_notes":      "fldVfqwrQZdedtgwH",
    "email_draft":   "fldJzXn8Car0QOAVN",
    "li_connect":    "fldhARUqZPbXWpORY",
    "li_followup":   "fld9Pabu7oI8kI1YK",
    "gmail_id":      "fldyl5QtoIzfh37hO",
    "pd_activity":   "fldgmsl5vum21h6tZ",
    "status":        "fld90kz4vOAbjPDhC",
    "outreach_date": "fldZOzJg0dFzrPcnH",
    "department":    "fld7rpz6b9Q3KM9oa",
    "city":          "fldRsfTgKhFyAo0Ln",
    "state":         "fldrtDGkvFyYSdvMf",
}

BATCH_F = {
    "batch_date":     "fldAs5gXCZgYL9TaP",
    "industry":       "fldUdUZ4bdjLGmRSa",
    "companies":      "fldYnAbCbtKjuFjAJ",
    "contacts":       "fldEDpNvcesfJuyeC",
    "emails":         "fldI5WHmfErdEdMgJ",
    "pd_activity_id": "fld2mZalNVhI9Unrs",
    "review_status":  "fldefJ1Q4bqyN1ujy",
    "notes":          "fldmv2vzv9c07w11H",
}

# ── Industry rotation (cycles daily Mon-Fri) ──────────────────────────────────
INDUSTRIES = [
    "Manufacturing",
    "Logistics & Warehousing",
    "Construction",
    "Oil & Gas",
    "Chemical Manufacturing",
    "Food & Beverage Manufacturing",
    "Utilities",
    "Mining",
    "Automotive Manufacturing",
    "Aerospace & Defense",
    "Waste Management",
    "Transportation & Freight",
]

SENIORITY = ["director", "vp", "c_suite", "owner", "partner", "head"]

HSE_OPS_TITLE_KEYWORDS = [
    "Safety", "HSE", "EHS", "Health and Safety", "Environment Health",
    "Operations", "Warehouse", "Logistics", "Supply Chain",
]


def get_industry_for_date(d: date) -> str:
    return INDUSTRIES[d.timetuple().tm_yday % len(INDUSTRIES)]


# ── Apollo ────────────────────────────────────────────────────────────────────

def apollo_post(endpoint: str, payload: dict) -> dict:
    resp = requests.post(
        f"https://api.apollo.io/v1/{endpoint}",
        json=payload,
        headers={
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": APOLLO_API_KEY,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def search_apollo_companies(industry: str, limit: int = 10) -> list:
    data = apollo_post("mixed_companies/search", {
        "page": 1,
        "per_page": limit + 5,
        "q_organization_keyword_tags": [industry],
        "num_employees_ranges": ["11,200", "201,1000", "1001,10000"],
        "organization_locations": ["United States"],
    })

    companies = []
    for org in data.get("organizations", []):
        companies.append({
            "id":           org.get("id", ""),
            "name":         org.get("name", ""),
            "website":      org.get("website_url", ""),
            "linkedin_url": org.get("linkedin_url", ""),
            "employees":    str(org.get("estimated_num_employees", "")),
            "city":         org.get("city", ""),
            "state":        org.get("state", ""),
            "industry":     org.get("industry", industry),
            "description":  org.get("short_description", ""),
            "keywords":     org.get("keywords", []),
            "founded_year": str(org.get("founded_year", "")),
        })
    return companies[:limit]


def search_apollo_contacts(company: dict, limit: int = 3) -> list:
    data = apollo_post("mixed_people/search", {
        "page": 1,
        "per_page": 20,
        "q_organization_name": company["name"],
        "organization_ids": [company["id"]] if company.get("id") else [],
        "person_seniorities": SENIORITY,
        "person_titles": HSE_OPS_TITLE_KEYWORDS,
        "contact_email_status": ["verified", "likely to engage"],
    })

    director_plus, others = [], []
    director_keywords = {"director", "vp", "vice president", "chief", "president", "head of", "manager"}

    for person in data.get("people", []):
        title_lower = person.get("title", "").lower()
        contact = {
            "id":           person.get("id", ""),
            "first_name":   person.get("first_name", ""),
            "last_name":    person.get("last_name", ""),
            "name":         f"{person.get('first_name', '')} {person.get('last_name', '')}".strip(),
            "title":        person.get("title", ""),
            "email":        person.get("email", ""),
            "linkedin_url": person.get("linkedin_url", ""),
            "city":         person.get("city", ""),
            "state":        person.get("state", ""),
            "department":   (person.get("departments") or [""])[0],
        }
        if any(kw in title_lower for kw in director_keywords):
            director_plus.append(contact)
        else:
            others.append(contact)

    combined = (director_plus + others)[:limit]
    return combined


# ── Claude AI ─────────────────────────────────────────────────────────────────

_ai_client = None


def get_ai_client():
    global _ai_client
    if _ai_client is None:
        _ai_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _ai_client


def research_company(company: dict) -> str:
    prompt = f"""You are helping build a personalized cold outreach campaign for Seen Safety,
a safety management platform that helps HSE and operations teams streamline compliance,
incident reporting, and safety training.

Company:
- Name: {company['name']}
- Industry: {company['industry']}
- Location: {company.get('city', '')}, {company.get('state', '')}
- Employees: {company.get('employees', 'unknown')}
- Website: {company.get('website', '')}
- Description: {company.get('description', '')}
- Keywords: {', '.join(str(k) for k in company.get('keywords', [])[:10])}

Write 4 concise bullet points:
• Their likely HSE/safety challenges given industry and size
• Operational pain points in their space
• A specific angle for how Seen Safety solves their problem
• Any relevant industry context (regulations, trends)

Be specific and actionable. No fluff."""

    resp = get_ai_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


def generate_outreach(company: dict, contact: dict) -> dict:
    prompt = f"""Generate personalized cold outreach for Seen Safety (safety management software).

COMPANY:
- Name: {company['name']}
- Industry: {company['industry']}
- Location: {company.get('city', '')}, {company.get('state', '')}
- Size: {company.get('employees', 'unknown')} employees
- Research notes: {company.get('ai_research', '')}

CONTACT:
- Name: {contact['name']}
- Title: {contact['title']}
- Department: {contact.get('department', '')}

Generate exactly this JSON (no markdown, raw JSON only):
{{
  "ai_customization_notes": "2-3 sentences on why this person is a strong prospect and what specific angle to use",
  "email_subject": "subject line under 60 chars, no clickbait",
  "email_body": "email body only (no subject line), ~130 words, conversational, references their specific challenge, soft CTA for 15-min call. Sign off as Tony from Seen Safety.",
  "linkedin_connection": "connection note under 280 chars, personal and specific, zero pitch, no 'I wanted to reach out'",
  "linkedin_followup": "~90 word follow-up message after they accept. Reference their role/industry, expand value prop briefly, ask for a 15-min call."
}}"""

    resp = get_ai_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}],
    )

    text = resp.content[0].text.strip()
    for fence in ("```json", "```"):
        if fence in text:
            text = text.split(fence, 1)[1].rsplit("```", 1)[0].strip()
            break

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = {
            "ai_customization_notes": "Parse error — review raw output",
            "email_subject": f"Quick question for {contact.get('first_name', 'you')}",
            "email_body": text,
            "linkedin_connection": f"Hi {contact.get('first_name', '')}, noticed your work in {company['industry']} — would love to connect.",
            "linkedin_followup": f"Thanks for connecting! I help {company['industry']} teams with safety compliance. Happy to share some ideas specific to {company['name']}.",
        }

    email_body = data.get("email_body", "")
    email_subject = data.get("email_subject", "")

    return {
        "ai_notes":    data.get("ai_customization_notes", ""),
        "email_draft": f"Subject: {email_subject}\n\n{email_body}",
        "email_subject": email_subject,
        "li_connect":  data.get("linkedin_connection", ""),
        "li_followup": data.get("linkedin_followup", ""),
    }


# ── Airtable ──────────────────────────────────────────────────────────────────

def _at_request(method: str, table_id: str, payload: dict = None, record_id: str = None) -> dict:
    url = f"https://api.airtable.com/v0/{AT_BASE}/{table_id}"
    if record_id:
        url += f"/{record_id}"
    resp = requests.request(
        method, url,
        json=payload,
        headers={"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def create_airtable_company(company: dict, batch_date: str, industry: str) -> str:
    fields = {
        COMPANY_F["name"]:           company["name"],
        COMPANY_F["industry"]:       company.get("industry", industry),
        COMPANY_F["employees"]:      company.get("employees", ""),
        COMPANY_F["city"]:           company.get("city", ""),
        COMPANY_F["state"]:          company.get("state", ""),
        COMPANY_F["apollo_id"]:      company.get("id", ""),
        COMPANY_F["ai_research"]:    company.get("ai_research", ""),
        COMPANY_F["batch_date"]:     batch_date,
        COMPANY_F["industry_focus"]: industry,
    }
    if company.get("website"):
        fields[COMPANY_F["website"]] = company["website"]
    if company.get("linkedin_url"):
        fields[COMPANY_F["linkedin_url"]] = company["linkedin_url"]

    result = _at_request("POST", AT_COMPANIES, {"fields": fields})
    return result["id"]


def create_airtable_contact(contact: dict, company_record_id: str, outreach_date: str, gmail_id: str = "") -> str:
    fields = {
        CONTACT_F["name"]:          contact["name"],
        CONTACT_F["first_name"]:    contact.get("first_name", ""),
        CONTACT_F["last_name"]:     contact.get("last_name", ""),
        CONTACT_F["title"]:         contact.get("title", ""),
        CONTACT_F["apollo_id"]:     contact.get("id", ""),
        CONTACT_F["ai_notes"]:      contact.get("ai_notes", ""),
        CONTACT_F["email_draft"]:   contact.get("email_draft", ""),
        CONTACT_F["li_connect"]:    contact.get("li_connect", ""),
        CONTACT_F["li_followup"]:   contact.get("li_followup", ""),
        CONTACT_F["status"]:        "New",
        CONTACT_F["outreach_date"]: outreach_date,
        CONTACT_F["department"]:    contact.get("department", ""),
        CONTACT_F["city"]:          contact.get("city", ""),
        CONTACT_F["state"]:         contact.get("state", ""),
    }
    if company_record_id:
        fields[CONTACT_F["company_link"]] = [company_record_id]
    if contact.get("email"):
        fields[CONTACT_F["email"]] = contact["email"]
    if contact.get("linkedin_url"):
        fields[CONTACT_F["linkedin_url"]] = contact["linkedin_url"]
    if gmail_id:
        fields[CONTACT_F["gmail_id"]] = gmail_id

    result = _at_request("POST", AT_CONTACTS, {"fields": fields})
    return result["id"]


def create_airtable_batch(batch_date: str, industry: str, n_companies: int,
                          n_contacts: int, n_emails: int, pd_id: str = "") -> str:
    fields = {
        BATCH_F["batch_date"]:    batch_date,
        BATCH_F["industry"]:      industry,
        BATCH_F["companies"]:     n_companies,
        BATCH_F["contacts"]:      n_contacts,
        BATCH_F["emails"]:        n_emails,
        BATCH_F["review_status"]: "Pending Review",
    }
    if pd_id:
        fields[BATCH_F["pd_activity_id"]] = str(pd_id)

    result = _at_request("POST", AT_BATCHES, {"fields": fields})
    return result["id"]


# ── Gmail ─────────────────────────────────────────────────────────────────────

def get_gmail_service():
    if not GMAIL_AVAILABLE or not os.path.exists(GMAIL_TOKEN_FILE):
        return None

    SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]
    creds = Credentials.from_authorized_user_file(GMAIL_TOKEN_FILE, SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(GMAIL_TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    if not creds or not creds.valid:
        return None

    return build("gmail", "v1", credentials=creds)


def create_gmail_draft(service, contact: dict) -> str:
    if not service or not contact.get("email"):
        return ""

    draft_text = contact.get("email_draft", "")
    lines = draft_text.split("\n\n", 1)
    if len(lines) == 2 and lines[0].startswith("Subject:"):
        subject = lines[0].replace("Subject:", "").strip()
        body = lines[1]
    else:
        subject = f"Quick question for {contact.get('first_name', 'you')}"
        body = draft_text

    msg = MIMEText(body)
    msg["to"] = contact["email"]
    msg["subject"] = subject

    encoded = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    draft = service.users().drafts().create(
        userId="me",
        body={"message": {"raw": encoded}},
    ).execute()
    return draft.get("id", "")


# ── Pipedrive ─────────────────────────────────────────────────────────────────

def create_pipedrive_activity(companies: list, contacts_pairs: list,
                              batch_date: date, industry: str) -> str:
    if not PIPEDRIVE_API_KEY or not PIPEDRIVE_DOMAIN:
        return ""

    lines = [
        f"Cold Outreach Batch — {batch_date.strftime('%B %d, %Y')}",
        f"Industry: {industry}",
        f"Companies: {len(companies)}  |  Contacts: {len(contacts_pairs)}",
        "",
        "=" * 60,
    ]

    for i, (company, contact) in enumerate(contacts_pairs, 1):
        lines += [
            "",
            f"{i}. {contact['name']}  |  {contact.get('title', '')}",
            f"   Company: {company['name']} ({company.get('industry', '')})",
            f"   Email: {contact.get('email', 'N/A')}",
            f"   LinkedIn: {contact.get('linkedin_url', 'N/A')}",
            "",
            f"   AI NOTES: {contact.get('ai_notes', '')}",
            "",
            f"   EMAIL DRAFT:",
            *[f"   {line}" for line in contact.get("email_draft", "").split("\n")],
            "",
            f"   LINKEDIN CONNECTION NOTE:",
            f"   {contact.get('li_connect', '')}",
            "",
            f"   LINKEDIN FOLLOW-UP (after accept):",
            f"   {contact.get('li_followup', '')}",
            "",
            "-" * 60,
        ]

    resp = requests.post(
        f"https://{PIPEDRIVE_DOMAIN}.pipedrive.com/api/v1/activities",
        json={
            "subject": f"Cold Outreach — {industry} — {batch_date.strftime('%m/%d/%Y')}",
            "type": "task",
            "due_date": batch_date.isoformat(),
            "done": 0,
            "note": "\n".join(lines),
        },
        params={"api_token": PIPEDRIVE_API_KEY},
        timeout=15,
    )

    if resp.ok:
        activity_id = str(resp.json().get("data", {}).get("id", ""))
        print(f"  Pipedrive activity created: {activity_id}")
        return activity_id

    print(f"  Pipedrive error {resp.status_code}: {resp.text[:200]}")
    return ""


# ── Validation ────────────────────────────────────────────────────────────────

def validate_env():
    missing = [k for k, v in {
        "AIRTABLE_TOKEN": AIRTABLE_TOKEN,
        "APOLLO_API_KEY": APOLLO_API_KEY,
        "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
    }.items() if not v]
    if missing:
        print(f"ERROR: Missing required environment variables: {', '.join(missing)}")
        print("Copy outreach/.env.example to .env and fill in the values.")
        sys.exit(1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Daily cold outreach — Seen Safety")
    parser.add_argument("--industry", help="Override industry (default: auto-rotate by date)")
    parser.add_argument("--companies", type=int, default=10, help="Companies to target (default: 10)")
    parser.add_argument("--contacts-per", type=int, default=3, help="Contacts per company (default: 3)")
    parser.add_argument("--dry-run", action="store_true", help="Generate content, print it, don't save anything")
    args = parser.parse_args()

    validate_env()

    today = date.today()
    industry = args.industry or get_industry_for_date(today)

    print(f"\n{'='*60}")
    print(f"  Seen Safety Cold Outreach — {today}")
    print(f"  Industry: {industry}")
    print(f"  Target: {args.companies} companies × {args.contacts_per} contacts")
    print(f"{'='*60}\n")

    # 1. Find companies via Apollo
    print("Searching Apollo for companies...")
    companies = search_apollo_companies(industry, args.companies)
    print(f"Found {len(companies)} companies\n")

    contacts_pairs = []

    for idx, company in enumerate(companies, 1):
        print(f"[{idx}/{len(companies)}] {company['name']}")

        contacts = search_apollo_contacts(company, args.contacts_per)
        print(f"  {len(contacts)} contacts found")

        if not contacts:
            continue

        # Research the company once
        print(f"  Researching with Claude...")
        company["ai_research"] = research_company(company)

        for contact in contacts:
            print(f"  → Generating outreach for {contact['name']} ({contact['title']})")
            outreach = generate_outreach(company, contact)
            contact.update(outreach)
            contacts_pairs.append((company, contact))

        time.sleep(0.5)  # gentle rate limiting

    print(f"\nGenerated outreach for {len(contacts_pairs)} contacts")

    if args.dry_run:
        print("\n--- DRY RUN — first contact preview ---")
        if contacts_pairs:
            co, ct = contacts_pairs[0]
            print(f"\nCompany: {co['name']}")
            print(f"Contact: {ct['name']} | {ct['title']}")
            print(f"\nAI Notes:\n{ct.get('ai_notes', '')}")
            print(f"\n{ct.get('email_draft', '')}")
            print(f"\nLinkedIn Connection:\n{ct.get('li_connect', '')}")
            print(f"\nLinkedIn Follow-up:\n{ct.get('li_followup', '')}")
        print("\n(Dry run complete — nothing saved)")
        return

    # 2. Gmail (optional)
    gmail_service = get_gmail_service()
    if gmail_service:
        print("\nGmail connected")
    else:
        print("\nGmail not configured — skipping draft creation")

    # 3. Save to Airtable
    print("\nSaving to Airtable...")
    company_record_ids = {}
    emails_drafted = 0

    for company, contact in contacts_pairs:
        # Create company record once per company
        if company["id"] not in company_record_ids:
            try:
                rid = create_airtable_company(company, today.isoformat(), industry)
                company_record_ids[company["id"]] = rid
                print(f"  Company saved: {company['name']}")
            except Exception as e:
                print(f"  Company FAILED {company['name']}: {e}")
                company_record_ids[company["id"]] = None

        # Gmail draft
        gmail_id = ""
        if gmail_service and contact.get("email"):
            try:
                gmail_id = create_gmail_draft(gmail_service, contact)
                if gmail_id:
                    emails_drafted += 1
            except Exception as e:
                print(f"  Gmail draft failed for {contact['name']}: {e}")

        # Contact record
        try:
            create_airtable_contact(
                contact,
                company_record_ids.get(company["id"]),
                today.isoformat(),
                gmail_id,
            )
            print(f"  Contact saved: {contact['name']} ({company['name']})")
        except Exception as e:
            print(f"  Contact FAILED {contact['name']}: {e}")

    # 4. Pipedrive activity
    print("\nCreating Pipedrive activity...")
    pd_id = create_pipedrive_activity(companies, contacts_pairs, today, industry)

    # 5. Daily batch summary record
    create_airtable_batch(
        today.isoformat(), industry,
        len(companies), len(contacts_pairs), emails_drafted, pd_id,
    )

    print(f"\n{'='*60}")
    print(f"  Done!")
    print(f"  Companies:       {len(companies)}")
    print(f"  Contacts:        {len(contacts_pairs)}")
    print(f"  Gmail drafts:    {emails_drafted}")
    print(f"  Pipedrive:       {pd_id or 'not configured'}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
