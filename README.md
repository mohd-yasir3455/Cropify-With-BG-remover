# Cropify — Batch Product-Image Processor

Got a folder full of messy product photos? Point Cropify at it and walk away.

For every image, it strips out the background, drops the product onto a clean
white backdrop, trims the empty space around it (leaving a bit of breathing
room so nothing feels cramped), and saves the result as a JPEG. Your output
folder ends up looking exactly like your input folder — same structure, just
cleaner pictures.

Along the way it also builds an Excel report and a log file, and if something
interrupts the run, it can pick up right where it left off. And don't worry
about your originals — Cropify never touches them.

No GPU needed. It runs happily on a regular laptop CPU.

---

## What happens to each photo

Here's the journey every image takes:

1. The background gets removed with [rembg](https://github.com/danielgatis/rembg)
   (using the `u2net` model unless you tell it otherwise).
2. The product is placed on pure white (`#FFFFFF`).
3. Cropify tightens the frame down to the product, then adds **7% padding** on
   every side — enough white space to look intentional, never so tight it looks
   accidentally chopped.
4. The product keeps its original resolution. Cropify only shaves off background
   pixels; it never stretches, squashes, upscales, or resizes the product
   itself. **No quality loss.**
5. It saves as a **JPEG at quality 90**, keeping the original filename (just
   swapping the extension to `.jpg`).

---

## How it decides what to do with each folder

Cropify treats every folder directly inside your input folder as a single
product. It counts the real images in there and acts accordingly:

| Images in the folder | What Cropify does | Note it leaves in the report |
|---|---|---|
| **0** | Skips it | `Empty – no valid image files` |
| **1 – 6** | Processes it | *(nothing — all good)* |
| **7 – 8** | Processes it, but flags it | `N images – trim to 6 (remove extras/duplicates; keep front & back angles)` |
| **9 or more** | Skips it entirely | `Discard – N images (more than 8, review manually)` |

The important thing: Cropify **never deletes or moves your photos**. For the
crowded folders (7–8 or 9+), it just makes a note in the report so you can go
sort them out yourself when you're ready. Every one of these thresholds lives in
`config.py` if you want to change them.

### Cleaning up filenames (`photoroom` / `copy`)

If a filename has `photoroom` or `copy` in it (capitalized however), Cropify
quietly drops that word from the output copy — along with any leftover dashes,
underscores, or spaces hanging around the edges. Your original file keeps its
name; only the new JPEG gets the tidy version.

| Original file | Becomes |
|---|---|
| `Photoroom_IMG_5.png` | `IMG_5.jpg` |
| `IMG_2 copy.jpg` | `IMG_2.jpg` (or `IMG_2_1.jpg` if `IMG_2.jpg` already exists) |
| `IMG-copy-002.png` | `IMG-002.jpg` |

If two cleaned-up names would clash, the later ones get `_1`, `_2`, and so on —
so nothing ever gets overwritten by accident.

---

## What you'll need

- **Python 3.11 or newer**
- The packages listed in `requirements.txt`: `rembg`, `onnxruntime`, `Pillow`,
  `pillow-heif`, `openpyxl`, `tqdm`, and `numpy`
- An internet connection **for the very first run only** — it needs to download
  the background-removal model (about 176 MB for `u2net`). After that it's
  cached, and every later run works completely offline.
- HEIC and HEIF input files are supported when those dependencies are installed.

---

## Getting set up

```bash
# (recommended) spin up a virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

# install everything
pip install -r requirements.txt
```

> **A note for Linux folks:** the graphical folder-picker relies on `tkinter`,
> which comes bundled with the official Python installers on Windows and macOS.
> On Linux you might need to add it once with `sudo apt install python3-tk` — or
> just skip the pop-up dialogs entirely by passing `--input` and `--output` on
> the command line.

---

## Running it

### The easy way — with folder pickers

```bash
python main.py
```

It'll pop up and ask you to pick your **input** folder (the one holding all your
product subfolders), then your **output** folder. Done.

### The explicit way — no pop-ups

```bash
python main.py --input "Raw Images" --output "Edited Images"
```

### Handy extras

```bash
# use 4 worker threads
python main.py --input "Raw Images" --output "Edited Images" --workers 4

# switch models or nudge the JPEG quality
python main.py --input RAW --output OUT --model u2netp --quality 92

# start over from scratch, ignoring any saved progress
python main.py --input RAW --output OUT --force
```

| Option | What it's for | Default |
|---|---|---|
| `--input` | The parent folder of your product subfolders | folder picker |
| `--output` | Where the results go (created if it doesn't exist) | folder picker |
| `--workers` | How many threads run in parallel | 2–4 (based on your CPU) |
| `--model` | Which rembg model to use | `u2net` |
| `--quality` | Output JPEG quality (1–95) | `90` |
| `--force` | Ignore saved progress and redo everything | off |

---

## The extra helper scripts

These are little companion tools for the `Raw Images`, `Edited Images`, and
`MANUAL` folder workflows.

### 1. Build `MANUAL` from `Raw Images`

Reach for this when you want cropped copies in `MANUAL` for any raw folders that
didn't make it into `Edited Images`.

```bash
python3 crop_only.py --input "Raw Images" --edited "Edited Images" --manual "MANUAL"
```

Here's the logic:

- `Raw Images` stays completely untouched
- It compares each raw folder against `Edited Images`
- Anything missing from `Edited Images` gets cropped JPEGs made in `MANUAL`
- If `Edited Images` is empty, every raw folder heads to `MANUAL`

Want to rebuild and overwrite what's already in `MANUAL`? Add `--force`:

```bash
python3 crop_only.py --input "Raw Images" --edited "Edited Images" --manual "MANUAL" --force
```

### 2. Make an Excel sheet for `MANUAL`

When you want the same style of report for your `MANUAL` folder:

```bash
python3 manual_report.py --manual "MANUAL"
```

This creates or updates `MANUAL/processing_report.xlsx`.

### 3. Make an Excel sheet for `Raw Images`

When you want a report of your current raw folders and how many images each one
holds:

```bash
python3 raw_report.py --raw "Raw Images"
```

This creates or updates `Raw Images/processing_report.xlsx`.

### 4. Shuffle similar extras into `REVIEW`

Got a folder with 7 or 8 images and only want to keep 6? This finds the most
similar extras and tucks them into a `REVIEW` subfolder — it moves them, never
deletes them.

For your edited images:

```bash
python3 review_similar.py --input "Edited Images"
```

Extras land in `Edited Images/REVIEW/<folder-name>`.

For your raw images:

```bash
python3 review_similar.py --input "Raw Images"
```

Extras land in `Raw Images/REVIEW/<folder-name>`.

In short, it only looks at folders with 7 or 8 images, keeps the 6 most distinct
ones, moves the closest duplicates into `REVIEW`, and never permanently deletes
anything.

### 5. Rebuild edited output as JPEG-only

The main script already writes JPEGs. But if you've got older PNG files lying
around inside `Edited Images` from earlier runs, convert them to `.jpg` before
moving on to the review and report steps. The command that did the job in the
workspace was simply:

```bash
python3 main.py --input "Raw Images" --output "Edited Images"
```

---

## What your output folder looks like

The output mirrors your input exactly. (Folders with 0 or 9+ images show up in
the report but don't get an output folder created.)

```
Raw Images/                    Edited Images/
├── #DTV-0001/                 ├── #DTV-0001/
│   ├── IMG_1.jpg        →     │   ├── IMG_1.jpg
│   ├── IMG_2 copy.jpg   →     │   ├── IMG_2_1.jpg
│   └── Photoroom_5.png  →     │   └── 5.jpg
├── #DTV-0002/ (8 imgs)  →     ├── #DTV-0002/   (processed + flagged)
├── #DTV-0003/ (10 imgs) →     │  (skipped — not created)
└── #DTV-EMPTY/ (0 imgs) →     │  (empty  — not created)
                               ├── processing_report.xlsx
                               ├── processing.log
                               └── processing_state.json
```

---

## The Excel report

`processing_report.xlsx` lands in your output folder with three simple columns:

| Folder Name | No. of Pics | Any Comment |
|---|---|---|

A couple of things worth knowing:

- **No. of Pics** counts only real images — hidden, system, and unsupported
  files are ignored.
- The report **updates itself in place** on every run. Old rows stay put (along
  with any notes you've added yourself), a folder that shows up again just
  updates its own row instead of duplicating, and a folder that failed before
  but succeeds later gets its row quietly corrected.

---

## If a run gets interrupted

Cropify saves its progress to `processing_state.json` as it works. So if you hit
`Ctrl+C`, shut the laptop, lose power — whatever — just **run the same command
again**. It skips everything that already finished and carries on from there.

- If a few images in a folder failed, that folder gets marked *partial*. Running
  again **retries only the images that failed** and updates the report.
- Want to ignore the saved state and start completely fresh? Use `--force`.

---

## Logging

`processing.log` (also in the output folder) keeps a full, timestamped record of
everything — which folders and images were handled, how long each took, whatever
got skipped, and the complete error details (tracebacks included) for anything
that failed. Meanwhile your console stays calm and readable: just a progress bar
and the occasional warning or error. The messy details go to the file where you
can dig into them if you need to.

And here's a promise: **one bad image can never stop the whole batch.** Any
failure gets logged, Cropify moves on, and the folder's report row tells you how
many made it through versus how many didn't.

---

## Tweaking things

Every setting you might want to change lives in **`config.py`** — edit a value,
re-run, and you're done. The ones you'll reach for most:

| Setting | What it does | Default |
|---|---|---|
| `REMBG_MODEL` | Which background-removal model to use | `"u2net"` |
| `PADDING_RATIO` | How much white space around the product (0.07 = 7%) | `0.07` |
| `JPEG_QUALITY` | Output JPEG quality (1–95) | `90` |
| `SUPPORTED_EXTENSIONS` | Which file types count as images | 9 formats, including HEIC/HEIF |
| `REVIEW_MIN` / `REVIEW_MAX` | The range that gets the "trim to 6" flag | `7` / `8` |
| `SKIP_MIN` | Folder size that gets skipped as "discard" | `9` |
| `TARGET_KEEP` | How many images you'd ideally keep | `6` |
| `RENAME_STRIP_TOKENS` | Words stripped from output filenames | `("photoroom", "copy")` |
| `ALPHA_MATTING` | Refine fuzzy edges (slower) | `False` |
| `MAX_INPUT_DIMENSION` | Optional cap on input size to save memory | `None` |
| `DEFAULT_WORKERS` | How many threads run at once | 2–4 |
| `EXCEL_SAVE_EVERY` | Save the report every N folders | `1` |

---

## Getting the best out of a laptop CPU

- **The first run is the slow one** — it's downloading that ~176 MB model and
  warming up. Every run after reuses the cached copy.
- **Threads:** somewhere between `--workers 2` and `4` usually hits the sweet
  spot on a laptop. All the threads share a single model session (so memory
  stays reasonable); they mostly help by overlapping image loading, cropping,
  JPEG encoding, and disk work with the actual background removal. Piling on more
  threads mainly just eats more RAM.
- **Faster vs. prettier:** `u2netp` is quicker with a slight quality trade-off;
  `isnet-general-use` looks better but is noticeably slower on a CPU.
- **Really big photos:** if you start hitting memory limits, set
  `MAX_INPUT_DIMENSION` in `config.py` (say, `4000`). That caps the working size
  to keep memory in check — though your output would then be limited to that
  size too. Leave it `None` to keep full resolution.

---

## When something goes wrong

| What you're seeing | How to fix it |
|---|---|
| `No module named tkinter` / no dialog shows up | Install `python3-tk` (on Linux), or just pass `--input`/`--output`. |
| The download fails on the first run | Check your internet — the model comes from GitHub releases. Once it's cached, you're offline-friendly. |
| A few edges look a bit rough | Set `ALPHA_MATTING = True` in `config.py` (it's slower, but cleaner). |
| Running low on memory | Drop `--workers`, or set `MAX_INPUT_DIMENSION`. |
| You want a folder redone from scratch | Run it again with `--force`. |

---

## How the project is laid out

```
main.py             # the entry point: folder pickers, orchestration, progress bar, parallelism, resume
crop_only.py        # builds MANUAL from Raw Images when folders are missing in Edited Images
manual_report.py    # creates processing_report.xlsx for MANUAL
raw_report.py       # creates processing_report.xlsx for Raw Images
review_similar.py   # moves similar extras from 7–8 image folders into REVIEW
config.py           # every tunable setting (edit these; no logic in here)
image_processor.py  # background removal, white matte, crop + padding, JPEG save
excel_report.py     # appends/updates the Excel report (never overwrites)
state.py            # resume-safe progress (processing_state.json)
logger.py           # logging setup (detailed file log + clean console)
utils.py            # folder scanning + output-filename cleaning/dedup
requirements.txt    # dependencies
README.md           # you're reading it
```

*(`config.py` and `state.py` are kept separate from the core modules on purpose
— it keeps the settings and the resume logic clean and easy to adjust.)*
