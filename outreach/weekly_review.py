#!/usr/bin/env python3
"""
Weekly Review Script — Seen Safety Cold Outreach
Pulls all batches and contacts from the past 7 days out of Airtable
and prints a formatted summary for your Monday review.

Usage:
  python outreach/weekly_review.py
  python outreach/weekly_review.py --weeks 2    # look back 2 weeks
  python outreach/weekly_review.py --mark-reviewed  # flip batch status to Reviewed
"""

import os
import sys
import argparse
from datetime import date, timedelta
import requests

AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN", "")
AT_BASE        = "app0GlBSe5GZzwtdi"
AT_BATCHES     = "tblP9BzjJOJcKnLiT"
AT_CONTACTS    = "tblK6dCGng49LO7cl"

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

CONTACT_F = {
    "name":          "fldtLhRfRKw8qnvYa",
    "title":         "fldchBxq7gq85X2Za",
    "email":         "fldnYb3OjtIUUEwAq",
    "linkedin_url":  "fldvfl4uG9OBoqLJz",
    "ai_notes":      "fldVfqwrQZdedtgwH",
    "email_draft":   "fldJzXn8Car0QOAVN",
    "li_connect":    "fldhARUqZPbXWpORY",
    "li_followup":   "fld9Pabu7oI8kI1YK",
    "status":        "fld90kz4vOAbjPDhC",
    "outreach_date": "fldZOzJg0dFzrPcnH",
    "gmail_id":      "fldyl5QtoIzfh37hO",
}

STATUS_EMOJI = {
    "New":             "🔵",
    "Email Sent":      "📧",
    "LinkedIn Sent":   "💼",
    "Replied":         "💬",
    "Meeting Booked":  "📅",
    "Not Interested":  "⛔",
}


def at_get(table_id: str, params: dict = None) -> list:
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    url = f"https://api.airtable.com/v0/{AT_BASE}/{table_id}"
    records = []
    offset = None

    while True:
        p = dict(params or {})
        if offset:
            p["offset"] = offset
        resp = requests.get(url, headers=headers, params=p, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break

    return records


def at_patch(table_id: str, record_id: str, fields: dict) -> dict:
    resp = requests.patch(
        f"https://api.airtable.com/v0/{AT_BASE}/{table_id}/{record_id}",
        json={"fields": fields},
        headers={
            "Authorization": f"Bearer {AIRTABLE_TOKEN}",
            "Content-Type": "application/json",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def main():
    parser = argparse.ArgumentParser(description="Weekly outreach review — Seen Safety")
    parser.add_argument("--weeks", type=int, default=1, help="How many weeks back to review (default: 1)")
    parser.add_argument("--mark-reviewed", action="store_true", help="Mark pending batches as Reviewed")
    parser.add_argument("--show-drafts", action="store_true", help="Print full email drafts in output")
    args = parser.parse_args()

    if not AIRTABLE_TOKEN:
        print("ERROR: AIRTABLE_TOKEN not set.")
        sys.exit(1)

    cutoff = date.today() - timedelta(weeks=args.weeks)
    cutoff_str = cutoff.isoformat()

    print(f"\n{'='*65}")
    print(f"  Seen Safety — Weekly Outreach Review")
    print(f"  Period: {cutoff_str} → {date.today().isoformat()}")
    print(f"{'='*65}\n")

    # ── Fetch batches ──────────────────────────────────────────────────────────
    batch_records = at_get(AT_BATCHES, {
        "filterByFormula": f"IS_AFTER({{{BATCH_F['batch_date']}}}, '{cutoff_str}')",
        "sort[0][field]": BATCH_F["batch_date"],
        "sort[0][direction]": "desc",
    })

    if not batch_records:
        print("No batches found in this period.")
        return

    total_companies = 0
    total_contacts  = 0
    total_emails    = 0

    print(f"{'Date':<14} {'Industry':<30} {'Companies':>9} {'Contacts':>9} {'Emails':>7} {'Status'}")
    print("-" * 85)

    for r in batch_records:
        f = r["fields"]
        d          = f.get(BATCH_F["batch_date"], "")[:10]
        industry   = f.get(BATCH_F["industry"], "")
        companies  = f.get(BATCH_F["companies"], 0)
        contacts   = f.get(BATCH_F["contacts"], 0)
        emails     = f.get(BATCH_F["emails"], 0)
        status     = f.get(BATCH_F["review_status"], "")

        total_companies += companies
        total_contacts  += contacts
        total_emails    += emails

        print(f"{d:<14} {industry:<30} {companies:>9} {contacts:>9} {emails:>7}  {status}")

        if args.mark_reviewed and status == "Pending Review":
            at_patch(AT_BATCHES, r["id"], {BATCH_F["review_status"]: "Reviewed"})

    print("-" * 85)
    print(f"{'TOTAL':<14} {'':<30} {total_companies:>9} {total_contacts:>9} {total_emails:>7}\n")

    # ── Fetch contacts ─────────────────────────────────────────────────────────
    contact_records = at_get(AT_CONTACTS, {
        "filterByFormula": f"IS_AFTER({{{CONTACT_F['outreach_date']}}}, '{cutoff_str}')",
        "sort[0][field]": CONTACT_F["outreach_date"],
        "sort[0][direction]": "desc",
    })

    # Status breakdown
    status_counts = {}
    for r in contact_records:
        s = r["fields"].get(CONTACT_F["status"], "New")
        status_counts[s] = status_counts.get(s, 0) + 1

    print("Status Breakdown:")
    for status, count in sorted(status_counts.items()):
        emoji = STATUS_EMOJI.get(status, "•")
        bar   = "█" * count
        print(f"  {emoji} {status:<20} {count:>3}  {bar}")

    print()

    # Contacts needing action (no email sent yet, not disqualified)
    actionable = [
        r for r in contact_records
        if r["fields"].get(CONTACT_F["status"], "New") == "New"
        and r["fields"].get(CONTACT_F["email"])
    ]

    if actionable:
        print(f"Action Required — {len(actionable)} contacts with email addresses not yet contacted:\n")
        for r in actionable[:20]:
            f = r["fields"]
            name  = f.get(CONTACT_F["name"], "")
            title = f.get(CONTACT_F["title"], "")
            email = f.get(CONTACT_F["email"], "")
            d     = f.get(CONTACT_F["outreach_date"], "")[:10]
            print(f"  {d}  {name:<28} {title[:35]:<36} {email}")

    # Replies / meetings
    hot = [
        r for r in contact_records
        if r["fields"].get(CONTACT_F["status"], "") in ("Replied", "Meeting Booked")
    ]
    if hot:
        print(f"\nHot Contacts — {len(hot)} replied or booked:\n")
        for r in hot:
            f = r["fields"]
            emoji = STATUS_EMOJI.get(f.get(CONTACT_F["status"], ""), "•")
            print(f"  {emoji} {f.get(CONTACT_F['name'], '')} | {f.get(CONTACT_F['title'], '')}")

    if args.show_drafts and contact_records:
        print(f"\n{'='*65}")
        print("Full Draft Preview (first 3 contacts):")
        print(f"{'='*65}")
        for r in contact_records[:3]:
            f = r["fields"]
            print(f"\n--- {f.get(CONTACT_F['name'], '')} | {f.get(CONTACT_F['title'], '')} ---")
            print(f"\nAI NOTES:\n{f.get(CONTACT_F['ai_notes'], '')}")
            print(f"\nEMAIL DRAFT:\n{f.get(CONTACT_F['email_draft'], '')}")
            print(f"\nLINKEDIN CONNECTION:\n{f.get(CONTACT_F['li_connect'], '')}")
            print(f"\nLINKEDIN FOLLOW-UP:\n{f.get(CONTACT_F['li_followup'], '')}")

    if args.mark_reviewed:
        print(f"\nBatches marked as Reviewed in Airtable.")

    print(f"\n{'='*65}\n")


if __name__ == "__main__":
    main()
