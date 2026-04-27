# Smart Helmet Violation Detection System
### PC-Side AI Processor | Works with any downloaded video

---

## Quick Start

**1. Install dependencies**
```
pip install -r requirements.txt
```

**2. Run**
```
python main.py
```
You will see an interactive menu. Choose option 1 and paste your video path.

---

## Command Line Usage

| Command | Description |
|---|---|
| `python main.py` | Interactive menu (recommended) |
| `python main.py --input video.mp4` | Process one file |
| `python main.py --input C:/Videos/` | Process entire folder |
| `python main.py --input video.mp4 --preview` | Show live detection window |
| `python main.py --input video.mp4 --conf 0.35` | Lower detection threshold |
| `python main.py --input C:/Videos/ --watch` | Auto-process new files |

---

## Supported Video Formats

mp4  avi  mov  mkv  webm  flv  wmv  m4v  3gp  ts  mts

> If a format won't open, convert it:
> `ffmpeg -i input.webm output.mp4`

---

## Violations Detected

| Violation | Detection Method |
|---|---|
| No Helmet | Person + motorcycle overlap + head region ratio |
| Red Light Running | Traffic light + vehicle motion across frames |
| Triple Riding | 3+ persons overlapping one motorcycle |
| Stop Sign Violated | Stop sign + moving vehicle in consecutive frames |
| Riding on Footpath | Motorcycle + 3+ pedestrians, no road vehicles |

---

## Output Files

| Location | Contents |
|---|---|
| `./evidence/` | 30-second AVI clip + JPG snapshot per violation |
| `./reports/` | PDF report per processed video |
| `./violations.db` | SQLite database of all violations |

---

## Email Reports to Authorities

Set these environment variables then choose option 5 in the menu:

**Windows:**
```
set GMAIL_USER=you@gmail.com
set GMAIL_PASSWORD=xxxx xxxx xxxx xxxx
set AUTHORITY_EMAIL=traffic@example.com
```

**Mac/Linux:**
```
export GMAIL_USER=you@gmail.com
export GMAIL_PASSWORD=xxxx xxxx xxxx xxxx
export AUTHORITY_EMAIL=traffic@example.com
```

Get a Gmail App Password at: https://myaccount.google.com/apppasswords

---

## Project Structure

```
helmet_cam/
├── main.py                        Entry point
├── requirements.txt
├── README.md
├── detection/
│   ├── rules_engine.py            Violation detection logic
│   └── processor.py               Video processing + YOLO + evidence saving
├── storage/
│   └── database.py                SQLite database
├── reporting/
│   ├── report_builder.py          PDF report generator
│   └── email_reporter.py          Email reports to authority
├── utils/
│   └── logger.py
├── evidence/                      Auto-created: clips + snapshots
└── reports/                       Auto-created: PDF reports
```
