# Library Contents Claim Agent
### AI-Powered Library Inventory, Valuation & Insurance Claim Reporting

An AI-assisted prototype for documenting library contents through camera capture, identifying books and non-book objects, researching market prices, estimating dimensions where calibration is available, and generating structured insurance claim reports.

> **Project status:** Prototype for an insurance contents assessment workflow. Automated tests cover selected components; live model performance, measurement accuracy, and assessment pass criteria require real-world validation.

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Technology Stack](#technology-stack)
- [Prerequisites](#prerequisites)
- [Installation and Setup](#installation-and-setup)
- [Running the Application](#running-the-application)
- [Performing a Library Sweep](#performing-a-library-sweep)
- [Claim Outputs](#claim-outputs)
- [Project Structure](#project-structure)
- [Running Tests](#running-tests)
- [Demo Video and Assessment Reports](#demo-video-and-assessment-reports)
- [Limitations and Validation](#limitations-and-validation)
- [Security](#security)
- [Future Improvements](#future-improvements)

---

## Overview

Manual library inventory for insurance claims can be time-consuming. Books must be counted and identified, replacement values must be researched, non-book contents must be recorded, and measurements must be documented.

The Library Contents Claim Agent explores how computer vision, language models, web-grounded price research, and structured data processing can support this workflow.

The application captures evidence frames during a camera sweep, sends images to a Gemini vision model for structured extraction, maintains an inventory for review, and produces a machine-readable claim packet alongside a human-readable HTML report.

The project prioritizes traceability: uncertain identifications and unsupported prices should be reviewed rather than presented as verified facts.

### Project objectives

1. Identify visible book spines and record candidate titles and authors.
2. Inventory non-book objects visible in the library.
3. Associate detections with captured evidence frames.
4. Estimate spine dimensions when a known-size reference is properly calibrated.
5. Research replacement and used-market prices using Google Search grounding through Gemini.
6. Incorporate room geometry or explicitly supplied room measurements.
7. Generate a structured claim packet and readable report for review.

---

## Key Features

### 1. Camera-based library inventory

- Captures periodic image frames during a sweep.
- Sends captured frames for vision-based extraction.
- Records detected books and non-book objects.
- Associates inventory entries with frame evidence.
- Uses conservative duplicate-handling logic across nearby frames.

Repeated views, missed books, and incorrect detections remain possible and require review.

### 2. Book identification

The vision pipeline extracts information such as:

- Candidate book title and author.
- Visible spine text and supporting evidence.
- Confidence or review indicators.
- Associated frame references.
- Identification fields that remain blank when evidence is insufficient.

The application also supports importing existing book photographs for analysis.

### 3. Market-price research

The application uses Gemini with Google Search grounding to investigate replacement prices and used-market listings.

The pricing workflow attempts to verify cited offers against accessible source-page information, including title overlap, currency, and price evidence. If a price cannot be verified, the application can leave it blank and flag the record for review.

Prices must still be checked for the correct edition, format, seller, condition, stock, and local market before being used in an insurance claim.

### 4. Spine-dimension estimation

Metric spine measurements require a known-size reference, such as a ruler, visible in the same plane as the books.

When the reference and its actual height are supplied, image geometry can support approximate height and thickness estimates.

These estimates are not equivalent to tape-measured ground truth. Perspective, camera angle, occlusion, and detection errors can affect the results.

### 5. Room geometry and measurements

The project includes a native iOS RoomPlan companion workflow for sending room geometry to the backend. A JSON import/export path is also available.

The browser-based fallback accepts tape-measured room dimensions as user inputs. The ordinary browser camera does not independently establish accurate metric room dimensions.

Room measurements and shelf-covered wall area should be reviewed and validated separately.

### 6. Voice interaction and corrections

The browser interface uses supported speech-recognition capabilities for voice input and speech synthesis for spoken feedback. Text input is available as a fallback.

Supported correction examples include:

- `title B001-001 is [correct title]`
- `that is a first edition`
- `skip this shelf, those are not mine`
- `that portrait is a print`

These commands help record corrections and review decisions. The companion application is not yet a fully unified Gemini Live, full-duplex voice-and-vision agent.

### 7. Structured claim reporting

The application can generate:

- A structured `claim_packet.json`.
- A readable HTML report.
- Saved evidence frames.
- Review-queue information.
- Per-stage timing and available token-usage information.
- Optional cost estimates when model token rates are configured.

The generated files provide an auditable basis for checking inventory records, source evidence, and unresolved fields.

---

## System Architecture

The workflow is organized into the following stages:

1. **Capture:** Browser camera frames or imported photographs provide visual evidence.
2. **Vision extraction:** Gemini analyzes frames and returns structured book and non-book detections.
3. **Inventory management:** Records are associated with frames, duplicate handling is applied, and review information is retained.
4. **Identification and pricing:** Candidate titles are researched, and replacement or used prices are checked against available source evidence.
5. **Measurement:** Calibrated image geometry or supplied room geometry contributes measurements where available.
6. **Claim generation:** Inventory, pricing evidence, measurements, and review flags are assembled into a JSON packet and HTML report.
7. **Human review:** Uncertain titles, prices, duplicates, and measurements are checked before the output is used for a claim.

The repository's companion service runs separately from the original Insurance Claim Live Agent Team reference application.

---

## Technology Stack

| Component | Technology |
|---|---|
| Backend API | Python, FastAPI |
| Application server | Uvicorn |
| Vision and extraction | Google Gemini API |
| Price research | Gemini Google Search grounding |
| Browser interaction | HTML, JavaScript, browser camera APIs |
| Voice input/output | Browser speech recognition and speech synthesis, where supported |
| Structured output | JSON |
| Human-readable output | HTML |
| Room geometry | Native iOS RoomPlan companion and JSON import/export |
| Automated tests | pytest |

---

## Prerequisites

Before starting, install:

- Python 3.12
- Git
- A modern browser with camera permissions
- A Google AI Studio API key with access to the configured Gemini model

Create an API key through [Google AI Studio](https://aistudio.google.com/apikey).

For phone-based browser camera access, use a secure HTTPS context. The local address `127.0.0.1` works on the same computer; it does not automatically make the service available as a secure page on a phone.

---

## Installation and Setup

### 1. Clone the repository

Replace `YOUR_USERNAME` with the GitHub account that owns the repository.

```bash
git clone https://github.com/YOUR_USERNAME/library-contents-claim-agent.git
cd library-contents-claim-agent
```

Alternatively, download the repository as a ZIP and extract it.

### 2. Create a virtual environment

**Windows PowerShell**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, consult the Python documentation or use Command Prompt:

```bat
.venv\Scripts\activate.bat
```

**macOS/Linux**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy the example configuration:

**Windows PowerShell**

```powershell
Copy-Item .env.example .env
```

**macOS/Linux**

```bash
cp .env.example .env
```

Open `.env` and configure the API key and model settings:

```dotenv
GOOGLE_API_KEY=your_google_ai_studio_api_key
LIBRARY_VISION_MODEL=gemini-2.5-flash
LIBRARY_PRICE_MODEL=gemini-2.5-flash
```

Optional cost-estimation settings are available in `.env.example`. Populate them only with appropriate current token rates.

**Never commit your real `.env` file or API credentials to GitHub.**

---

## Running the Application

From the repository root, with the virtual environment activated:

```bash
python -m uvicorn app:app --reload --host 0.0.0.0 --port 4178
```

Open the companion application in your browser:

**http://127.0.0.1:4178**

The application uses port `4178` so it can run alongside the original reference application on port `4177`, if that application is installed and running.

The companion service does not replace or automatically merge into the reference application's Gemini Live WebSocket and agent graph.

### Health check

With the server running, visit:

**http://127.0.0.1:4178/health**

Check the response for API configuration and service status. A missing or invalid API key can prevent live model analysis.

### Windows helper script

The repository also includes a PowerShell helper:

```powershell
.\run_local.ps1
```

It creates `.env` from `.env.example` when needed, installs requirements, and starts the server. Add your private API key to `.env` before starting a model-backed workflow.

---

## Performing a Library Sweep

1. Open the application and configure the local country and currency, along with the comparison market.
2. Start a sweep and grant camera permission.
3. Move slowly across shelves and visible library contents. Keep book spines readable and allow the camera to capture evidence frames.
4. If estimating metric spine dimensions, place a ruler or known-height reference beside the books in the same plane and enter its real measurement.
5. Enter tape-measured room dimensions when using the browser measurement fallback.
6. Review detected titles, authors, confidence indicators, non-book items, and evidence references.
7. Correct uncertain records and inspect the cited price sources.
8. Finish the sweep and generate the claim packet.
9. Download or inspect the JSON packet and HTML report. Review missing values and unresolved flags before using the results.

Do not assume that every book has been detected or that every displayed estimate is accurate. Compare the generated inventory with the physical scene.

### Analyze existing photographs

The application also provides an upload workflow for existing book photographs:

1. Locate **Upload book pictures** in the application.
2. Select supported JPG, PNG, or WebP photographs.
3. Choose **Analyze selected photos**.
4. Review the resulting records and correct uncertain detections.
5. Complete the required measurement inputs and generate a packet if needed.

Photograph uploads can produce overlapping or duplicate detections. Image uploads alone do not establish metric measurements or independently verify market prices.

---

## Claim Outputs

The main output locations are:

| Output | Purpose |
|---|---|
| `outputs/frames/` | Captured image evidence |
| `outputs/<sweep>_claim_packet.json` | Structured inventory and claim data |
| `outputs/<sweep>_report.html` | Human-readable report |
| Review queue | Records needing additional verification |
| Timing and usage metadata | Available stage-timing and model-usage information |

The exact files available depend on which workflows have been run. Frame links may use application routes and therefore work only while the corresponding server is available.

### Report from the supplied inventory workbook

A report generator is included for the supplied workbook.

```bash
python generate_claim_report.py sample_data/Library_Books_Inventory.xlsx outputs/Library_Contents_Claim_Report.html
```

This command uses the bundled sample workbook and writes an HTML report to the specified destination. To use another workbook, provide its path as the first argument.

The report generator standardizes unverified titles and prices rather than presenting unverified values as confirmed facts. It does not invent missing room measurements.

---

## Project Structure

```text
library-contents-claim-agent/
├── app.py
├── src/
│   └── packet.py
├── tests/
├── sample_data/
│   └── Library_Books_Inventory.xlsx
├── outputs/
│   ├── frames/
│   └── generated claim outputs
├── validation/
├── generate_claim_report.py
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── .gitignore
├── ARCHITECTURE.md
├── FAILURE_LOG_TEMPLATE.md
├── REQUIREMENTS_VERIFICATION_GUIDE.md
├── FINAL_SUBMISSION_CHECKLIST.md
└── README.md
```

Generated output files may appear only after running the application or report generator. Additional native iOS RoomPlan files may be present in the repository.

---

## Running Tests

Install the development dependencies:

```bash
pip install -r requirements-dev.txt
```

Run the automated test suite:

```bash
pytest -q
```

The included tests cover selected behaviors such as claim-packet generation, duplicate handling, voice-command processing, price verification, and room-measurement logic.

Passing automated tests does not establish end-to-end accuracy for a real library scene, prove that every external retailer can be checked, or validate the native iOS workflow on a physical device.

For the assessment, run the separate ground-truth evaluation workflow documented in `REQUIREMENTS_VERIFICATION_GUIDE.md` and record the actual results.

---

## Demo Video and Assessment Reports

The GitHub repository contains the project's source code and assessment artifacts.

### Demo video

**[Watch the project demonstration](https://drive.google.com/file/d/117cZUwgU9FXj90sDehuz_V36_mscSjdf/view?usp=sharing)**

The demonstration should show the actual application, the capture workflow, the inventory as it is populated, and the resulting claim packet. Use the real recorded workflow and clearly disclose any limitations or manual steps.

### Assessment reports

- [Final Library Contents Claim Report (HTML)](outputs/Library_Contents_Claim_Report5.html)
- [Standardized HTML report](outputs/Library_Contents_Claim_Report_standardized.html)
- [Architecture note](ARCHITECTURE.md)
- [Failure log template](FAILURE_LOG_TEMPLATE.md)
- [Requirements verification guide](REQUIREMENTS_VERIFICATION_GUIDE.md)

Add the demo video and final report files to the repository at the paths shown above, or update the links if you use different filenames. If you have a PDF version of the report, you can also include it in `submission/`.

For a private assessment repository, share access with the reviewers. Do not make a repository public if the assessment instructions require a private repository.

---

## Limitations and Validation

This project is a prototype, and its output should be treated as a draft for human review rather than a verified insurance valuation.

Current limitations include:

- Book detections can be missed or repeated across frames.
- Spine measurements depend on suitable scale calibration and can be affected by perspective.
- Browser-based room measurements are supplied by the user rather than inferred reliably from ordinary camera frames.
- RoomPlan is a separate native iOS workflow and has not been validated here on a supported physical device.
- Search-grounded prices can refer to a different edition, condition, format, or seller. Blocked or inaccessible pages may prevent verification.
- The companion browser speech workflow is not the same as a fully integrated real-time Gemini Live voice conversation.
- Accuracy against the assessment's required ground-truth scene and pass bars has not been established by the included automated tests.

A reliable evaluation should include a hand-counted library, manually checked titles, tape-measured spines and room dimensions, and independently verified local-market prices. Record misses and errors rather than reporting accuracy only on successful detections.

---

## Security

- Store API keys in `.env`, not in source files.
- Keep `.env` excluded through `.gitignore`.
- Commit `.env.example` with placeholders only.
- Avoid uploading personal, private, or sensitive camera footage without permission.
- Inspect generated reports and evidence frames before publishing them.
- Check repository history if a credential was accidentally committed; removing it from the latest version alone may not remove it from earlier commits.

---

## Future Improvements

- Integrate the companion workflow with a unified real-time voice-and-vision session.
- Improve cross-frame tracking and shelf-level duplicate detection.
- Validate dimension estimates against hand-measured ground truth.
- Expand market-specific pricing verification and edition matching.
- Improve room geometry integration and derive room surface areas from validated geometry.
- Add repeatable end-to-end evaluation and publish measured results.
- Improve the review interface for unresolved titles, prices, and measurements.

---

## Acknowledgements

This project was developed with reference to the [Insurance Claim Live Agent Team](https://github.com/Shubhamsaboo/awesome-llm-apps/tree/main/voice_ai_agents/insurance_claim_live_agent_team) example, adapting the contents of a home library into a structured inventory and claim-reporting workflow.

**Disclaimer:** This is an experimental assessment prototype. Its output is not a substitute for an independent inventory, verified market valuation, or professional insurance-adjustment decision.
