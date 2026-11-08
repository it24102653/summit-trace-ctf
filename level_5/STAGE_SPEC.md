# Stage Specification

| Field | Description |
|---|---|
| **Stage ID & Title** | WEB-05 — "Basecamp Systems" |
| **Domain** | Linux / System Security (Task 1) and Reverse Engineering (Task 2) — dual-domain stage. |
| **Difficulty** | Moderate — Task 1 requires genuine permission-auditing skill (not just reading a description); Task 2 requires actual binary analysis since the check isn't a plain string comparison. |
| **Scenario** | musni has reached basecamp. Its support server (with real, audit-worthy file permissions) and a locked radio access panel (a real compiled binary) must both be investigated before continuing the ascent. |
| **Learning Objective** | Task 1: recognise insecure Unix file permissions (world-writable files, especially ones triggered by root-owned cron jobs) using `ls -la` and `cat`. Task 2: understand that not all crackmes are solvable with `strings` alone — some require dumping raw bytes (`objdump -s`) and manually reversing simple logic (here, a single-byte XOR). |
| **Challenge Environment** | Single Docker container, pure Python stdlib HTTP server. Two real downloadable artifacts: a `.tar.gz` bundle with genuinely different Unix permissions (built via real `chmod`), and a real compiled unstripped ELF binary (`radio_lock`, built via `gcc -O0`). |
| **Player Task** | 1) Enter the 7-digit PIN from Level 4 to unlock this level. 2) Task 1: download and extract the audit tarball, use `ls -la` to spot the world-writable file among normal ones, `cat` it to find the hidden code. 3) Task 2: download `radio_lock`, recognise the input isn't checked via plain `strcmp`, dump `.rodata` with `objdump -s -j .rodata`, and manually XOR-decode the bytes with the key (0x5A, given in Hint 2) to recover the 8-character access code. |
| **Flag Location / Logic** | Flag (`CTF{perm5_l34k_th3n_x0r_cr4ck}`) is revealed only once both tasks are solved. Submitting it via the chain's Submit Flag box reveals Level 6's login (`musni_final` / `SummitCode2026`). |
| **Required Tools** | `tar`, `ls -la`, `cat` for Task 1; `strings`, `objdump -s -j .rodata` (or `xxd`/`gdb`), and basic Python/mental XOR arithmetic for Task 2. |
| **Dependencies** | None enforced server-side — both tasks are independently solvable once the PIN gate is passed. |
| **Expected Solution Path** | Task 1: `tar -xzf basecamp_audit.tar.gz && cd basecamp_audit && ls -la` → spot `-rwxrwxrwx service_status.sh` → `cat service_status.sh` → find the code in a comment line. Task 2: `chmod +x radio_lock && strings radio_lock` (no answer visible) → `objdump -s -j .rodata radio_lock` → find the 8 encoded bytes → XOR each with `0x5A` → recover `TRAILEND`. |
| **Validation** | Both task answers checked server-side (`/task1/submit`, `/task2/submit`); Task 2's comparison is case-insensitive to avoid unnecessary friction from capitalization. Flag only renders once both are correct. |
| **Hints** | Four one-time hints, matching Level 4's cost structure: Task 1 hints −8 each (max −16), Task 2 hints −12 each (max −24). None of the hints print the actual code or the encoded bytes directly — Hint 2 for Task 2 does reveal the XOR key (0x5A) since that's a reasonable "final push" for a Moderate-tier binary challenge, consistent with how Level 4's hints revealed technique/tooling without handing over the final answer. |
| **Reset / Recovery** | All state is in-memory only — `docker compose restart web05-basecamp` fully resets everything. |

## Scoring Model (same pattern as Level 4 — deduction-only, no time limit)
- Starts at **100**.
- Each wrong submission (either task): **−7 marks**, unlimited retries.
- Hints cost marks individually per use, one-time each: Task 1 hints −8 each (max −16 total), Task 2 hints −12 each (max −24 total).
- Correct task completion does **not** add marks — a perfect run with no mistakes and no hints preserves the full starting 100.
- Once both tasks are solved, the score is locked and shown with the flag; the flag must then be submitted via the chain's Submit Flag box to reveal Level 6's credentials.

## Estimated Resources
- CPU: negligible (<0.2 core)
- RAM: ~30–40 MB
- Storage: ~17 KB combined assets (841 B tarball + 16 KB binary) + <60 MB base image
- Network: single HTTP port (8000 internal / 8085 host mapped)

## Required Level 4 Patch (to complete the chain)
Level 4's `handle_submit_flag` message currently ends the campaign. To connect it to Level 5, replace its message text with:

```python
message = (
    "🎉 Congratulations! Chapter 4 complete.\n\n"
    "musni has reached basecamp - a 7-digit PIN is needed for what's next:\n\n"
    f"PIN: {CHAIN_PIN_FOR_LEVEL5}\n\n"
    "Head to Level 5 and enter it to continue."
)
```
Where `CHAIN_PIN_FOR_LEVEL5 = "5923187"` (matching this stage's `CHAIN_PIN` constant).
