"""
Smart Helmet Violation Detection System
========================================
PC-side processor — works with any downloaded video. No camera needed.

Run without arguments for the interactive menu:
    python main.py

Or pass a path directly:
    python main.py --input "C:/Videos/traffic.mp4"
    python main.py --input "C:/Videos/"          # whole folder
    python main.py --input "C:/Videos/" --watch  # auto-mode: process new files
    python main.py --input video.mp4 --preview   # live detection window
    python main.py --input video.mp4 --conf 0.35 # lower = more detections

Supported formats: mp4  avi  mov  mkv  webm  flv  wmv  m4v  3gp  ts  mts
"""

import argparse, sys, time
from pathlib import Path
from detection.processor   import VideoProcessor
from reporting.report_builder import ReportBuilder
from storage.database      import Database

EXTS = {".mp4",".avi",".mov",".mkv",".webm",".flv",".wmv",".m4v",".3gp",".ts",".mts",".mpeg",".mpg"}

BANNER = """
+----------------------------------------------------------+
|   Smart Helmet Violation Detection System  v1.0          |
|   PC Mode — works with any downloaded traffic video      |
+----------------------------------------------------------+
"""


# ── helpers ───────────────────────────────────────────────────────────────────

def find_videos(folder: Path):
    found = []
    for ext in EXTS:
        found.extend(folder.rglob(f"*{ext}"))
        found.extend(folder.rglob(f"*{ext.upper()}"))
    return sorted(set(found))


def process(path: Path, proc: VideoProcessor, db: Database, rb: ReportBuilder, preview=False):
    print(f"\n  Processing : {path.name}")
    print(f"  Full path  : {path.resolve()}")
    viols = proc.process_video(str(path), show_preview=preview)
    if viols:
        print(f"\n  {len(viols)} violation(s) found:")
        for v in viols:
            print(f"    [{v.violation_type}]  at {v.timestamp_sec:.1f}s  (confidence {v.confidence:.0%})")
            db.save(v)
        rp = rb.generate_report(viols, path.stem)
        print(f"\n  PDF report : {rp}")
        print(f"  Evidence   : ./evidence/")
    else:
        print("  No violations detected.")
    return viols


def show_summary(db: Database):
    s = db.summary()
    total = sum(s.values()) if s else 0
    print(f"\n  {'─'*50}")
    print(f"  DATABASE SUMMARY  ({total} total violations recorded)")
    print(f"  {'─'*50}")
    if s:
        for vtype, count in s.items():
            bar = "#" * min(count, 35)
            print(f"  {vtype:<26} {bar} {count}")
    else:
        print("  No violations recorded yet.")
    print(f"  {'─'*50}\n")


def watch(folder: Path, proc, db, rb, preview=False):
    print(f"\n  Watching: {folder.resolve()}")
    print("  Drop any video file here to auto-process it.")
    print("  Press Ctrl+C to stop.\n")
    seen = set()
    while True:
        for vf in find_videos(folder):
            if vf not in seen:
                seen.add(vf)
                process(vf, proc, db, rb, preview)
        time.sleep(3)


# ── interactive menu ──────────────────────────────────────────────────────────

def menu(proc, db, rb):
    print(BANNER)
    while True:
        print("  What would you like to do?")
        print("    [1]  Process a single video file")
        print("    [2]  Process all videos in a folder")
        print("    [3]  Watch a folder (auto-process new files)")
        print("    [4]  View database summary")
        print("    [5]  Email pending reports to authority")
        print("    [6]  Exit")
        choice = input("\n  Enter choice (1-6): ").strip()

        if choice == "1":
            raw = input("  Paste video path: ").strip().strip('"\'"')
            p   = Path(raw)
            if not p.exists():
                print(f"  Not found: {p}"); continue
            preview = input("  Show live preview window? (y/N): ").strip().lower() == "y"
            process(p, proc, db, rb, preview)

        elif choice == "2":
            raw = input("  Paste folder path: ").strip().strip('"\'"')
            fp  = Path(raw)
            if not fp.is_dir():
                print(f"  Not a folder: {fp}"); continue
            vids = find_videos(fp)
            if not vids:
                print("  No supported video files found."); continue
            print(f"\n  Found {len(vids)} video(s):")
            for v in vids: print(f"    {v.name}")
            preview = input("\n  Show live preview? (y/N): ").strip().lower() == "y"
            for vf in vids: process(vf, proc, db, rb, preview)

        elif choice == "3":
            raw = input("  Paste folder path to watch: ").strip().strip('"\'"')
            fp  = Path(raw); fp.mkdir(parents=True, exist_ok=True)
            preview = input("  Show live preview? (y/N): ").strip().lower() == "y"
            try:    watch(fp, proc, db, rb, preview)
            except KeyboardInterrupt: print("\n  Watch stopped.")

        elif choice == "4":
            show_summary(db)

        elif choice == "5":
            try:
                from reporting.email_reporter import send_all_unreported
                send_all_unreported()
            except Exception as e:
                print(f"  Error: {e}")
                print("  Set GMAIL_USER / GMAIL_PASSWORD / AUTHORITY_EMAIL env vars first.")

        elif choice == "6":
            print("\n  Goodbye!\n"); sys.exit(0)

        else:
            print("  Please enter a number from 1 to 6.")


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Helmet Cam Violation Detector",
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=__doc__)
    parser.add_argument("--input",   help="Video file or folder path")
    parser.add_argument("--watch",   action="store_true")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--conf",    type=float, default=0.4)
    args = parser.parse_args()

    db   = Database()
    proc = VideoProcessor(confidence=args.conf)
    rb   = ReportBuilder()

    if not args.input:
        menu(proc, db, rb)
        return

    p = Path(args.input)

    if args.watch:
        if not p.is_dir(): print(f"--watch needs a folder, got: {p}"); sys.exit(1)
        try:    watch(p, proc, db, rb, args.preview)
        except KeyboardInterrupt: print("\nStopped.")

    elif p.is_dir():
        vids = find_videos(p)
        if not vids: print(f"No videos found in {p}"); sys.exit(1)
        for vf in vids: process(vf, proc, db, rb, args.preview)
        show_summary(db)

    elif p.is_file():
        process(p, proc, db, rb, args.preview)
        show_summary(db)

    else:
        print(f"Path not found: {p}"); sys.exit(1)

    print("Done. Check ./evidence/ and ./reports/\n")


if __name__ == "__main__":
    main()
