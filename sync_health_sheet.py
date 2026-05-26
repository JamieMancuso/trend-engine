"""
sync_health_sheet.py — Export "Health Tracking 2026" Google Sheet → health_manual.csv
---------------------------------------------------------------------------------------
Run this from a Cowork session (not as a scheduled task — it needs the Drive MCP).
Alternatively, download the sheet manually as CSV and save as health_manual.csv.

Usage:
    Ask Claude in Cowork to run this, or run it in a context where gspread
    / google-auth is configured. The simplest path: download from Google Sheets
    as CSV and drop the file in the trend-engine folder as health_manual.csv.

Since this script can't directly call the Cowork Drive MCP from the command line,
it provides two fallback methods below.
"""

import csv
import os
import sys

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV  = os.path.join(SCRIPT_DIR, "health_manual.csv")

# ── Method 1: gspread (if google credentials are configured) ─────────────────
def try_gspread():
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        return False

    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path or not os.path.exists(creds_path):
        print("GOOGLE_APPLICATION_CREDENTIALS not set — skipping gspread method.")
        return False

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds  = Credentials.from_service_account_file(creds_path, scopes=scope)
    client = gspread.authorize(creds)
    sheet  = client.open("Health Tracking 2026").sheet1
    rows   = sheet.get_all_records()

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        if not rows:
            print("Sheet is empty.")
            return True
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"Exported {len(rows)} rows → {OUTPUT_CSV}")
    return True


# ── Method 2: manual CSV drop reminder ───────────────────────────────────────
def manual_instructions():
    print("""
No automated sync method available in this environment.

To sync your Google Sheet manually:
  1. Open Health Tracking 2026 in Google Sheets
  2. File → Download → Comma Separated Values (.csv)
  3. Rename the downloaded file to: health_manual.csv
  4. Move it to: """ + SCRIPT_DIR + """
  5. Commit and push to git so Streamlit Cloud picks it up

The Health dashboard page will load it automatically on next refresh.
""")


if __name__ == "__main__":
    if not try_gspread():
        manual_instructions()
