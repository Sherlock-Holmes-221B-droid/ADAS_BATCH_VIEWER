[README.md](https://github.com/user-attachments/files/30177537/README.md)

# MF4 Analyser by AMAL NAMBIAR

A fast, user‑friendly desktop tool for converting **.mf4 (ASAM MDF v4)** data to CSV, selecting channels interactively, and exploring signals visually with rich  operations (resample/export, math ops, statistics, legend/grid, etc.). Built for engineering workflows that need repeatable exports and quick visual analysis.

**Author:** _Created by Amal Nambiar for Mahindra and Mahindra_


**Department:** ADAS Simulations Group  

## Table of Contents

- [Key Features](#key-features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Launching](#launching)
- [UI Tour](#ui-tour)
  - [Source & Output](#source--output)
  - [Channel Browser](#channel-browser)
  - [Channel Editor](#channel-editor)
  - [Options](#options)
  - [Run Export & Batch Mode](#run-export--batch-mode)
  - [Plot Explorer](#plot-explorer)
- [Units & CSV Conventions](#units--csv-conventions)
- [Default Channels & Frequency Config](#default-channels--frequency-config)
- [Troubleshooting](#troubleshooting)
- [Privacy](#privacy)
- [Changelog (R6 highlights)](#changelog-r6-highlights)

> **Note**
> This software is created using open source libraries available in python.

---

## Key Features

- **Channel Browser** that loads channels from an MF4 file, with **grouped view** (by prefix) and search. Add to the list with double‑click or **Add Selected**. Disambiguate multiple occurrences via a dialog. 
- **Channel Editor** accepts channel names separated by comma or newline; supports `name@group/index` to pin specific occurrences. Duplicate/blank entries are ignored. 
- **Export to CSV** with options to **include units** as a second header row or appended to column names; always includes a time index. 
- **Batch mode**: choose a folder; exports each MF4 (recursively) next to the source with `*_selected_channels.csv`. The first file prompts for ambiguous channels and caches selections for the rest. 
- **Plot Explorer** (interactive): overlay/subplots/hybrid layouts; overlay subset and **Hold** stacking; dark mode toggle; hover crosshair & nearest‑curve annotation; right‑click menu with statistics, operations, colors, line styles, legend/grid, find & clip, export (selected/subplot/figure), and more. 
- **Export‑dt**: Set a uniform export **time step dt**; the tool resamples all visible curves to a common time vector and writes CSV (selected/subplot/figure). Optionally **auto‑sets dt from a `frequency = …`** entry in the default channels file.

---

## Requirements

> Just pin the software in the taskbar and receive all the updates immediately.

---

## Installation


> <mark>\\MNMRVFSNAS04\ActiveSafetySimulations$\Amal\Software\MDF Analyzer</mark>  Open the software from this path and pin it to the taskbar.
No special OS setup is required. On Windows, the app sets **DPI awareness** to improve rendering.


On start, the app attempts to maximize the main window.

---

## UI Tour

### Start of GUI
The initial GUI is loaded in light/system mode. Users can toggle between the light mode or dark mode. Users can load a .MF4 file and export to csv. In order to add more signals in the list, users can add by just loading the channels and later clicking on 'Add selected' button. 
<div style="display:flex; gap:20px;">
    <img src="file:////MNMRVFSNAS04/ActiveSafetySimulations$/Amal/Software/MDF Analyzer/Images/GUI_Start.jpg" alt="Light Mode" style="width:45%;">
    <img src="file:////MNMRVFSNAS04/ActiveSafetySimulations$/Amal/Software/MDF Analyzer/Images/GUI_Start_d.jpg" alt="Dark Mode" style="width:45%;">
</div>

### Source & Output
- **MF4 file:** Select a single `.mf4` **file** or enable **Batch mode** to choose a **folder** (recursively scans subfolders).
<div align="center">
<img src="file:////MNMRVFSNAS04/ActiveSafetySimulations$/Amal/Software/MDF Analyzer/Images/BatchMode.jpg" alt="Dark Mode" style="width:80%;">
</div>
> If batchmode is checked, the folder and subfolder containing .MF4 files are exported to csv with selected channels with same name as MF4 file name.
- **Output CSV:** Path for single‑file export. Disabled in Batch mode (each MF4 writes next to itself).


### Channel Browser
- **Use display names:** Toggles display vs. raw names when loading via `asammdf`.
- **Load channels:** Reads all channels with occurrence info. Signals are grouped by prefix (before first underscore). Double‑click or **Add Selected** to include in the editor. If a channel has multiple occurrences, a **Select occurrence** dialog appears (`name@group/index`).
- **Search:** Filters the grouped tree in real time.

### Channel Editor
- Accepts a list via comma or newline; `name@group/index` pins an occurrence. The editor ignores `key=value` tokens (e.g., `frequency=1000`) if pasted from a config.

### Options
- **time_from_zero:** Start time index at 0 s when reading channels. The export csv will export all the time history data from time as zero as well as plot the signals with time starting from zero.
- **Include units:**
  - **Append to column names:** `Speed [km/h]`
  - **Second header row:** A separate row under the header with units (time unit is **s**).

### Run Export & Batch Mode
- **Run Export:** Converts the selected channels to a CSV (time index + columns). Units per selected mode.
- **Batch mode:** Scans a folder recursively for `.mf4`. Output for each file is `<base>_selected_channels.csv` in the same folder. The **first file** prompts for ambiguous channels; the choice is **cached** and reused for the rest. A summary dialog appears at completion.

### Plot Explorer

Open with **Open Plot Explorer**. The window is split into:

- **Left:** Search + tree of signals; buttons for **Plot Selected**, **Start from zero**, manage **overlay subset**, and **Hold**.
- **Right (toolbar row):** Layout toggles
  - **Single axes (overlay)**
  - **Live preview** (limits to the first **20** signals for responsiveness)
  - **Hybrid (overlay subset + subplots)**
  - **Plot dark mode**

**Layouts**
- **Overlay:** All selected signals on one axes.
- **Subplots:** One axes per signal (shared X).
- **Hybrid:** Top overlay of “subset” signals + subplots for others. Use **Add to overlay subset** on the left to manage the subset.

**Hover** shows a crosshair and nearest‑curve annotation (label, time, value). Categorical labels are handled safely.

#### Right‑click (context menu) on a curve

- **Statistic:** **Min**, **Max**, **Average** (adds an annotation & marker).
- **Colors:** Quick palette + color picker.
- **Operations:**
  - **Reflect**, **Absolute**, **Integrate**, **Differentiate**, **Inverse (1/x)**, **Scale**.
  - **Add** ▶ **Add constant…**, **Add with another curve…** (resamples other curve onto current X).
  - **Subtract** ▶ **Subtract constant…**, **Subtract with another curve…** (resamples other curve onto current X).
  - **Set mean…**: shift the signal so its mean equals the requested target (numeric only).
  - **Reset to original** (restores the curve’s original x/y).
- **Find:** **Given X → find Y**, **Given Y → find X** (numeric uses interpolation/nearest; categorical does case‑insensitive matching).
- **Clip…:** Keep only points in X and/or Y ranges (Y range applies to numeric only).
- **Line style:** Solid / Dash / Dot / DashDot.
- **Grid / Legend:** Toggle per‑axes; legend rebuilds based on **visible** curves.
- **Delete selected signal:** Remove the curve from axes and state (also clears any stat annotations for it).
- **Export (dt)**
  - **Time step dt = … (change…)** opens a prompt;
  - **Selected → CSV** (resampled to common t);
  - **All (This Subplot) → CSV**;
  - **All (Entire Figure) → CSV**.

> **Tip:** Use **Hold** to keep previously plotted signals while adding more; Live preview caps to 20 latest to stay responsive.

---

## Units & CSV Conventions

- **Single‑file export**: time is the index; channels are columns. If **Include units** is enabled:
  - **Append to column names**: `Speed [km/h]`
  - **Second header row**: writes a second row with units (time unit fixed to **s**).
- **Plot Explorer (dt) exports**: time is a regular column (first), then one column per curve with resampled values (numeric linear interpolation; non‑numeric nearest‑by‑time).

---

## Default Channels & Frequency Config

Place a defaults file **next to the script/exe**:

- **`default_channels.json`** or **`default_channels.txt`** (or `default_channels` without extension).
- The list can be a simple array or newline/comma separated text. Lines starting with `#` are ignored.
- You may also add a line like `frequency = 100` to set the default **export frequency** (Hz) → Plot Explorer initializes **dt = 1/100 = 0.01 s** automatically. (JSON can use keys `export_frequency_hz`, `frequency`, or `freq_hz`.)

**Examples**

`default_channels.txt`
```txt
# Channel list (commas or newlines)
VEHICLE_SPEED
YAW_RATE
STEERING_ABSOLUTE_ANGLE

# Optional export frequency (Hz):
frequency = 100
```

`default_channels.json`
```json
{
  "channels": [
    "VEHICLE_SPEED",
    "YAW_RATE",
    "STEERING_ABSOLUTE_ANGLE"
  ],
  "export_frequency_hz": 100
}
```

---

## Troubleshooting

- **“Missing channels”**: If a name isn’t in the file, it will be reported. Use the **Channel Browser** to confirm the exact display/physical name or choose **Use display names** before loading.
- **Ambiguous channels** (multiple occurrences): You’ll be prompted to select `(group, index)`; selections in Batch mode are cached after the first file. Use `name@group/index` to pin in the editor.
- **No units in output**: Ensure **Include units** is checked; choose “Append to column names” or “Second header row”. Some signals may not have a defined unit in MDF; they’ll appear blank.
- **Legend shows hidden curves**: Use the built‑in legend toggles from the context menu—the app **rebuilds** legend based on visibility; external toolbar toggles may be out‑of‑sync.
- **Large selections slow in Live preview**: The explorer caps plotted signals to **20** in Live preview mode to keep navigation smooth. Use non‑preview plotting for complete sets.
- **Categorical signals**: Export uses nearest‑by‑time for dt resampling; values are preserved as strings. Hover annotations and find/clip are robust to bytes/str content.

---

## Privacy

All reads/writes are **local** to your machine: the app opens your MF4 files and writes CSV where you choose. No network calls or telemetry are performed by the application logic.

---

## Changelog (R6 highlights)

- **Right‑click → Operations grouped**: **Add** (constant/curve), **Subtract** (constant/curve).
- **Right‑click → Set mean…**: shift signal to a target mean.
- **Right‑click → Delete selected signal**.
- **Plot dark‑mode theming** improvements and robust hover for categorical signals.
- **Export dt** can be **auto‑initialized** from `frequency = …` in defaults.

---

