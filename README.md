# Batch Product-Image Processor

Automatically clean up product photos in bulk. Point it at a folder of product
subfolders and it will, for every image: **remove the background**, place the
product on a **pure-white background**, **auto-crop** it with tidy white-space
padding, and save a **JPEG** — mirroring your folder structure into an output
folder. It also writes an **Excel report**, a **log file**, and can **resume**
if interrupted. Your original photos are never modified.

Runs entirely on your **CPU** — no GPU required.

---

## What it does to each image

1. **Removes the background** using [rembg](https://github.com/danielgatis/rembg)
   (the `u2net` model by default).
2. **Composites onto pure white** (`#FFFFFF`).
3. **Auto-crops to the product** and adds **8 % padding** on each side, so the
   result has clean, even white space and never looks cropped too tight.
4. **Keeps the product's native resolution** — the crop only removes background
   pixels; the product itself is never stretched, squashed, upscaled, or
   resized, so there is **no quality loss**.
5. **Saves as JPEG, quality 90**, keeping the original base filename (extension
   changed to `.jpg`).

---

## The folder rules it applies

Each **immediate subfolder** of your input folder is treated as one product.
The program counts the valid images in it and decides what to do:

| Images in folder | Action | Comment written to the Excel report |
|---|---|---|
| **0** | Not processed | `Empty – no valid image files` |
| **1 – 6** | Processed | *(blank)* |
| **7 – 8** | Processed | `N images – trim to 6 (remove extras/duplicates; keep front & back angles)` |
| **9 or more** | **Skipped** (no output folder created) | `Discard – N images (more than 8, review manually)` |

The program **never deletes or moves any photos** — for the 7–8 and 9+ cases it
simply **flags the folder in the report** so you can trim or discard those
folders yourself. All thresholds are configurable in `config.py`.

### Filename cleaning (`photoroom` / `copy`)

If an image's name contains `photoroom` or `copy` (any capitalisation), the
output copy has that word removed, along with any leftover separators
(`_`, `-`, space) at the start/end. The **original file is never renamed** —
only the JPEG written to the output folder.

| Original file | Output file |
|---|---|
| `Photoroom_IMG_5.png` | `IMG_5.jpg` |
| `IMG_2 copy.jpg` | `IMG_2.jpg` (or `IMG_2_1.jpg` if `IMG_2.jpg` also exists) |
| `IMG-copy-002.png` | `IMG-002.jpg` |

If two output names would collide, later ones get `_1`, `_2`, … so nothing is
overwritten. Untouched originals always keep their clean name.

---

## Requirements

- **Python 3.11 or newer**
- The packages in `requirements.txt` (`rembg`, `onnxruntime`, `Pillow`,
  `openpyxl`, `tqdm`, `numpy`)
- Internet **once**, the first time you run it, to download the background
  model (~176 MB for `u2net`). It is cached afterwards, so later runs are
  fully offline.

---

## Installation

```bash
# (recommended) create and activate a virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

# install dependencies
pip install -r requirements.txt
```

> **Folder pickers on Linux:** the graphical folder-picker uses `tkinter`, which
> ships with the official Python installers on Windows and macOS. On Linux you
> may need to install it once (`sudo apt install python3-tk`) — or just skip the
> dialogs by passing `--input` and `--output` on the command line.

---

## Running it

### Easiest — with folder pickers

```bash
python main.py
```

You'll be asked to pick the **input** folder (the parent containing your product
subfolders) and then the **output** folder. That's it.

### With explicit folders (no dialogs)

```bash
python main.py --input "Raw Images" --output "Edited Images"
```

### Useful options

```bash
# use 4 worker threads
python main.py --input "Raw Images" --output "Edited Images" --workers 4

# pick a different model or JPEG quality
python main.py --input RAW --output OUT --model u2netp --quality 92

# reprocess everything, ignoring saved progress
python main.py --input RAW --output OUT --force
```

| Option | Meaning | Default |
|---|---|---|
| `--input` | Parent folder of product subfolders | folder picker |
| `--output` | Output folder (created if missing) | folder picker |
| `--workers` | Parallel worker threads | 2–4 (based on CPU) |
| `--model` | rembg model name | `u2net` |
| `--quality` | Output JPEG quality (1–95) | `90` |
| `--force` | Ignore saved progress and redo everything | off |

---

## Output structure

The output folder mirrors the input exactly (folders with 9+ or 0 images are
listed in the report but produce no output folder):

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

`processing_report.xlsx` (in the output folder) has three columns:

| Folder Name | No. of Pics | Any Comment |
|---|---|---|

- `No. of Pics` counts **valid images only** (hidden/system/unsupported files
  are ignored).
- The report is **appended to / updated in place** on every run. Existing rows
  (and any notes you add) are kept; a folder that appears again updates its own
  row instead of creating a duplicate. A folder that previously failed and later
  succeeds has its row corrected automatically.

---

## Resuming an interrupted run

Progress is saved to `processing_state.json` as it goes. If the run is stopped
(you press `Ctrl+C`, close the laptop, lose power, …), just **run the same
command again** — it skips folders and images that already finished and picks up
where it left off.

- If some images in a folder **failed**, that folder is marked *partial*; a
  rerun **retries only the failed images** (the successful ones are skipped) and
  updates the report.
- Use `--force` to ignore the saved state and reprocess everything from scratch.

---

## Logging

`processing.log` (in the output folder) records everything with timestamps:
which folders and images were processed, how long each took, anything skipped,
and full error details (including tracebacks) for any image that failed. The
console stays clean — it shows the progress bar and only warnings/errors — while
the file keeps the detail for troubleshooting.

**One image can never stop the batch.** Any failure is logged and processing
continues; the folder's report row notes how many succeeded vs. failed.

---

## Configuration

Every tunable value lives in **`config.py`** — change a value, re-run, done. The
most useful ones:

| Setting | What it controls | Default |
|---|---|---|
| `REMBG_MODEL` | Background-removal model | `"u2net"` |
| `PADDING_RATIO` | White space around the object (0.08 = 8 %) | `0.08` |
| `JPEG_QUALITY` | Output JPEG quality (1–95) | `90` |
| `SUPPORTED_EXTENSIONS` | Which file types are treated as images | 7 formats |
| `REVIEW_MIN` / `REVIEW_MAX` | Range that gets the "trim to 6" flag | `7` / `8` |
| `SKIP_MIN` | Folder size that gets skipped as "discard" | `9` |
| `TARGET_KEEP` | How many images you want to keep | `6` |
| `RENAME_STRIP_TOKENS` | Words stripped from output filenames | `("photoroom", "copy")` |
| `ALPHA_MATTING` | Refine edges (slower; for fuzzy outlines) | `False` |
| `MAX_INPUT_DIMENSION` | Optional cap on input size to save memory | `None` |
| `DEFAULT_WORKERS` | Parallel threads | 2–4 |
| `EXCEL_SAVE_EVERY` | Save the report every N folders | `1` |

---

## Performance tips (CPU laptops)

- **First run is slower** — it downloads the model (~176 MB) and warms up. Later
  runs reuse the cached model.
- **Threads:** `--workers 2` to `4` is usually best on a laptop. A single model
  session is shared across threads (so memory stays low); the threads mainly
  overlap image loading, cropping, JPEG encoding and disk I/O with inference.
  More threads mostly just use more RAM.
- **Faster vs. nicer:** `u2netp` is quicker with slightly lower quality;
  `isnet-general-use` is higher quality but noticeably slower on CPU.
- **Very large photos:** if you hit memory limits, set `MAX_INPUT_DIMENSION` in
  `config.py` (e.g. `4000`). This caps the working size to bound memory (the
  output would then be limited to that size); leaving it `None` keeps full
  resolution.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `No module named tkinter` / no dialog appears | Install `python3-tk` (Linux), or pass `--input`/`--output`. |
| Download fails on first run | Check your internet connection; the model comes from GitHub releases. Once cached it works offline. |
| A few edges look rough | Set `ALPHA_MATTING = True` in `config.py` (slower). |
| Running low on memory | Lower `--workers`, or set `MAX_INPUT_DIMENSION`. |
| Want the same folder redone | Run with `--force`. |

---

## Project structure

```
main.py             # entry point: folder pickers, orchestration, progress bar, parallelism, resume
config.py           # all tunable settings (edit these; no logic here)
image_processor.py  # background removal, white matte, crop + padding, JPEG save
excel_report.py     # append/update the Excel report (never overwrites)
state.py            # resume-safe progress (processing_state.json)
logger.py           # logging setup (detailed file log + clean console)
utils.py            # folder scanning + output-filename cleaning/dedup
requirements.txt    # dependencies
README.md           # this file
```

*(`config.py` and `state.py` are split out from the core modules to keep
settings and resume-logic cleanly separated and easy to adjust.)*
# Cropify-With-BG-remover
