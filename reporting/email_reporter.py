"""
Email violation reports to traffic authorities via Gmail SMTP.

Setup:
  1. Get a Gmail App Password: https://myaccount.google.com/apppasswords
  2. Put your credentials directly in this file (lines marked CONFIGURE below)
  3. Reports are sent automatically when you choose option 5 in the menu
"""

import os, smtplib, glob
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from email.mime.base      import MIMEBase
from email                import encoders
from pathlib import Path
from storage.database import Database
from utils.logger import setup_logger

logger = setup_logger("email")

# ── CONFIGURE THESE ───────────────────────────────────────────────────────────
GMAIL_USER      = "om2018chougule@gmail.com"       # your Gmail address
GMAIL_PASSWORD  = "dxialjgksslhumyu"    # Gmail App Password (NOT your login password)
AUTHORITY_EMAIL = "chouguleom19@gmail.com"    # recipient address
# ─────────────────────────────────────────────────────────────────────────────


def send_report(report_path: str, violations: list) -> bool:
    """Send a single PDF report with a summary of violations."""
    rp = Path(report_path)
    if not rp.exists():
        logger.error(f"PDF not found: {report_path}")
        return False

    # Build summary counts
    summary: dict = {}
    for v in violations:
        vt = v.get("violation_type", "Unknown")
        summary[vt] = summary.get(vt, 0) + 1

    msg = MIMEMultipart()
    msg["From"]    = GMAIL_USER
    msg["To"]      = AUTHORITY_EMAIL
    msg["Subject"] = (f"Traffic Violation Report — "
                      f"{sum(summary.values())} violation(s) detected")

    body_lines = [
        "Dear Traffic Authority,",
        "",
        "The Smart Helmet Violation Detection System has recorded the following violations:",
        "",
    ]
    for vtype, count in summary.items():
        body_lines.append(f"  - {vtype}: {count} instance(s)")
    body_lines += [
        "",
        "The full PDF report with timestamps and evidence details is attached.",
        "Evidence video clips and snapshots are stored locally in the ./evidence/ folder.",
        "",
        "Regards,",
        "Smart Helmet IoT Detection System",
    ]
    msg.attach(MIMEText("\n".join(body_lines), "plain"))

    # Attach PDF
    with open(report_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition",
                        f"attachment; filename={rp.name}")
        msg.attach(part)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_USER, AUTHORITY_EMAIL, msg.as_string())
        logger.info(f"Report emailed to {AUTHORITY_EMAIL}")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("Authentication failed. Make sure you are using a Gmail APP PASSWORD,")
        logger.error("not your regular Gmail password.")
        logger.error("Get one at: https://myaccount.google.com/apppasswords")
        return False
    except Exception as e:
        logger.error(f"Email failed: {e}")
        return False


def send_all_unreported():
    """
    Find all PDF reports in ./reports/ that have not been emailed yet,
    match them to their violations in the DB, and send them.
    """
    db      = Database()
    pending = db.unreported()

    if not pending:
        print("  No pending violations to report.")
        return

    # Group violations by report_path.
    # Some violations may have report_path=None if they were saved before
    # the report was generated — group those by source_video instead,
    # then find the matching PDF in ./reports/.
    groups: dict = {}
    for v in pending:
        rp = v.get("report_path")
        if rp and Path(rp).exists():
            groups.setdefault(rp, []).append(v)
        else:
            # Fall back: find the newest PDF in ./reports/ that contains
            # the source video stem in its filename
            src  = Path(v.get("source_video", "")).stem[:40]
            pdfs = sorted(Path("./reports").glob(f"*{src[:20]}*.pdf")) if src else []
            if not pdfs:
                # Last resort: just grab the newest PDF overall
                pdfs = sorted(Path("./reports").glob("*.pdf"))
            if pdfs:
                fallback = str(pdfs[-1])
                groups.setdefault(fallback, []).append(v)
            else:
                print(f"  Warning: no PDF found for violation #{v['id']} ({v['violation_type']})")

    if not groups:
        print("  No PDF reports found in ./reports/ to send.")
        print("  Process a video first (option 1 or 2) to generate reports.")
        return

    print(f"  Found {len(groups)} report(s) to send:\n")
    for rpath, records in groups.items():
        print(f"  Sending: {Path(rpath).name}")
        print(f"  To     : {AUTHORITY_EMAIL}")
        print(f"  Items  : {len(records)} violation(s)")
        if send_report(rpath, records):
            print(f"  Status : Sent successfully\n")
            for r in records:
                db.mark_reported(r["id"], rpath)
        else:
            print(f"  Status : Failed — check credentials\n")


if __name__ == "__main__":
    send_all_unreported()