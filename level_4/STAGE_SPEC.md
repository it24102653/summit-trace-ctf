# Stage Specification

| Field | Description |
|---|---|
| **Stage ID & Title** | WEB-04 — "The Sealed Envelope" |
| **Domain** | Steganography (primary) — with a Cryptography (Hex/Base-16 encoding) overlap in Task 1. |
| **Difficulty** | Moderate — two chained techniques (hex decoding, and steganographic extraction requiring an external tool), each gated by its own recon step. |
| **Scenario** | A personal letter arrives in a kraft-paper envelope, along with a photo. Hidden within the server and the photo itself are two separate secrets that must be uncovered using different techniques. |
| **Learning Objective** | Recognise Hex/Base-16 encoding and decode it correctly; understand that steganography hides data inside innocuous-looking files (here, a JPEG) and use `steghide` to extract it once the correct passphrase is known. |
| **Challenge Environment** | Single Docker container, pure Python stdlib HTTP server, serving a static envelope/letter UI and the challenge image (with data already embedded via `steghide` at build time — the running container itself does not need steghide installed, only the player's own machine does). |
| **Player Task** | 1) Open the envelope to read the letter and download the photo. 2) Task 1: find the correct leaked path via `robots.txt` (ignoring two decoys) and hex-decode its content to get a 12-character key. 3) Task 2: use that same key as the `steghide` passphrase to extract a hidden text file from the downloaded photo, then submit its contents. |
| **Flag Location / Logic** | Flag (`CTF{h3x_th3n_st3gh1d3_s34l3d}`) is revealed only once both tasks are solved; the same key found in Task 1 is deliberately reused as the Task 2 steghide passphrase, tying the two techniques together narratively and technically. |
| **Required Tools** | Browser DevTools/`curl` for recon; `xxd -r -p` (or any hex decoder) for Task 1; `steghide extract -sf <file>` for Task 2 (pre-installed on Kali, or `apt install steghide`). |
| **Dependencies** | None enforced server-side (unlike Stage 3's hard-gated wordlist) — Task 2 is solvable independently of Task 1's completion status, though the passphrase needed for Task 2 can only be discovered via Task 1. |
| **Expected Solution Path** | 1) Open envelope → download photo → 2) Check `/robots.txt` → 3 candidate paths → 2 decoys return irrelevant content, 1 real path returns a hex string → 3) `echo "<hex>" \| xxd -r -p` → 12-character key → 4) `steghide extract -sf envelope_photo.jpg` with that key as the passphrase → 5) `cat` the extracted file → 6) submit the recovered message in Task 2. |
| **Validation** | Both task answers checked server-side (`/task1/submit`, `/task2/submit`); flag only renders once both are correct. Task 2's answer comparison is whitespace/case-normalized to avoid unnecessary friction from copy-paste formatting differences. |
| **Hints** | Four separate one-time hints: Task 1 Hint 1 (points to `robots.txt`, −8 marks), Task 1 Hint 2 (explains hex/Base-16 with a generic non-spoiling example, −8 marks), Task 2 Hint 1 (confirms the photo contains hidden data, −12 marks), Task 2 Hint 2 (explains the `steghide extract` command syntax generically, −12 marks). None of the hints ever print the actual real hex value, key, or secret message directly — they teach the technique, not the answer. |
| **Reset / Recovery** | All session state is in-memory only — `docker compose restart web04-envelope` fully resets everything. |

## Scoring Model (deduction-only, no time limit)
- Starts at **100** — unlike Stages 2–3, this stage has **no countdown timer**.
- Each wrong submission (either task): **−7 marks**, unlimited retries.
- Hints cost marks individually per use: Task 1 hints −8 each (max −16 total), Task 2 hints −12 each (max −24 total).
- Correct task completion does **not** add marks — completing both tasks with no mistakes and no hints preserves the full starting 100.
- Once both tasks are solved, the score is locked and displayed with the flag; the session cannot be replayed.

## Estimated Resources
- CPU: negligible (<0.2 core)
- RAM: ~30–40 MB
- Storage: ~450 KB image asset + <60 MB base image (python:3.12-slim)
- Network: single HTTP port (8000 internal / 8084 host mapped)

## Note on Asset Handling
The challenge photo is served under the generic filename `envelope_photo.jpg` (not the real uploaded filename) to keep the challenge's public-facing artifacts free of personally identifying filenames, even though the image content itself is used with the owner's permission as part of the narrative.
