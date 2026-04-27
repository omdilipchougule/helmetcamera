"""
PDF report generator using fpdf2.
All text uses ASCII-safe characters only to avoid font encoding errors.
"""

from pathlib import Path
from datetime import datetime
from fpdf import FPDF
from utils.logger import setup_logger

logger = setup_logger("reports")
REPORTS_DIR = Path("./reports")
REPORTS_DIR.mkdir(exist_ok=True)


def _safe(text: str) -> str:
    """Replace any non-latin-1 characters so fpdf never crashes."""
    replacements = {
        "—": "-",   # em dash
        "–": "-",   # en dash
        "‒": "-",   # figure dash
        "‘": "'",   # left single quote
        "’": "'",   # right single quote
        "“": '"',   # left double quote
        "”": '"',   # right double quote
        "•": "*",   # bullet
        "…": "...", # ellipsis
        " ": " ",   # non-breaking space
    }
    for orig, repl in replacements.items():
        text = text.replace(orig, repl)
    # Final safety net: drop anything still outside latin-1
    return text.encode("latin-1", errors="replace").decode("latin-1")


class _PDF(FPDF):
    def header(self):
        self.set_fill_color(15, 40, 80)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 12, "TRAFFIC VIOLATION REPORT",
                  align="C", fill=True, new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 8)
        self.cell(0, 6,
                  f"Generated: {datetime.now().strftime('%d %B %Y  %I:%M %p')}",
                  align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(3)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(140, 140, 140)
        self.cell(0, 10,
                  f"Smart Helmet Violation Detection System  |  Page {self.page_no()}",
                  align="C")


class ReportBuilder:
    def generate_report(self, violations: list, stem: str) -> str:
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Sanitise the filename stem too (long filenames from YouTube etc.)
        safe_stem = stem[:60].encode("ascii", errors="ignore").decode("ascii")
        path = REPORTS_DIR / f"report_{safe_stem}_{ts}.pdf"

        pdf = _PDF()
        pdf.set_auto_page_break(auto=True, margin=14)
        pdf.add_page()

        # ── Summary section ──────────────────────────────────────────────────
        pdf.set_fill_color(235, 235, 235)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 8, "SUMMARY", fill=True, new_x="LMARGIN", new_y="NEXT")

        counts: dict = {}
        for v in violations:
            counts[v.violation_type] = counts.get(v.violation_type, 0) + 1

        pdf.set_font("Helvetica", "", 10)
        pdf.cell(55, 7, "Source file:")
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 7, _safe(safe_stem), new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", "", 10)
        pdf.cell(55, 7, "Total violations:")
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(180, 0, 0)
        pdf.cell(0, 7, str(len(violations)), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 10)

        for vt, cnt in counts.items():
            pdf.cell(10)
            pdf.cell(0, 6, _safe(f"  {vt}: {cnt} instance(s)"),
                     new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        # ── Detailed records ─────────────────────────────────────────────────
        pdf.set_fill_color(235, 235, 235)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 8, "DETAILED RECORDS", fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        for i, v in enumerate(violations, 1):
            pdf.set_fill_color(200, 40, 40)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 8, _safe(f"  #{i}  {v.violation_type.upper()}"),
                     fill=True, new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)

            rows = [
                ("Detected at",   v.detected_at),
                ("Video time",    f"{v.timestamp_sec:.1f}s"),
                ("Confidence",    f"{v.confidence*100:.1f}%"),
                ("Evidence clip", v.evidence_clip or "N/A"),
                ("Snapshot",      v.snapshot_path or "N/A"),
                ("Notes",         v.notes or "none"),
            ]
            for label, val in rows:
                val_str = _safe(str(val))
                if len(val_str) > 65:
                    val_str = "..." + val_str[-62:]
                pdf.set_font("Helvetica", "B", 9)
                pdf.cell(42, 6, f"  {label}:")
                pdf.set_font("Helvetica", "", 9)
                pdf.cell(0, 6, val_str, new_x="LMARGIN", new_y="NEXT")

            if v.snapshot_path and Path(v.snapshot_path).exists():
                try:
                    pdf.image(v.snapshot_path, x=pdf.get_x() + 10, w=75)
                    pdf.ln(2)
                except Exception:
                    pass
            pdf.ln(4)

        pdf.output(str(path))
        logger.info(f"Report: {path}")
        return str(path)
