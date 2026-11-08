# Stage Specification

| Field | Description |
|---|---|
| **Stage ID & Title** | WEB-03 — "ShopNest Order Leak" |
| **Domain** | Cryptography (Base64 encoding + weak MD5 hashing) / Web Security (broken access control via `robots.txt` disclosure) — dual-domain stage. |
| **Difficulty** | Moderate — justification: chains three distinct techniques (recon via `robots.txt` with decoys to filter out, Base64 decoding, and offline hash cracking with a real wordlist via hashcat), each requiring a different tool/skill, matching the module's "combine multiple concepts" Stage 5 (Moderate–Hard) description, brought slightly earlier in the sequence as a deliberate difficulty ramp. |
| **Scenario** | ShopNest, an online store, accidentally left an internal order-export endpoint exposed. The player must find it among decoys, extract a leaked user record containing a hashed password, and crack that password to fully compromise the account. |
| **Learning Objective** | Combine reconnaissance (filtering real endpoints from decoys via `robots.txt`), data-encoding recognition (Base64 vs encryption), and password auditing (dictionary attacks against weak hashing with hashcat) into a single realistic attack chain. |
| **Challenge Environment** | Single Docker container, pure Python stdlib HTTP server (no external frameworks), in-memory session state, white/orange e-commerce-style dashboard UI. |
| **Player Task** | 1) Log in with any `@gmail.com` email and 10+ character password. 2) Find the real leaked endpoint via `/robots.txt` (ignoring two decoys) and submit its path for Task 1 (50 marks). 3) Decode the Base64 token it returns, extract the MD5 password hash, download the now-unlocked wordlist, crack the hash with hashcat, and submit the recovered password for Task 2 (50 marks). |
| **Flag Location / Logic** | Flag (`CTF{b4se64_th3n_h4shc4t_ftw}`) is revealed only once both tasks are solved; final score is locked and the session cannot be reused afterward. |
| **Required Tools** | Browser DevTools/`curl` for recon; `base64 -d` (or any decoder) for decoding; `hashcat` (mode 0 = MD5, mode `-a 0` dictionary attack) for cracking. |
| **Dependencies** | Task 2 is server-side gated behind Task 1 — the wordlist endpoint returns HTTP 403 until Task 1 is marked complete, not just hidden in the UI, so the dependency is enforced, not just cosmetic. |
| **Expected Solution Path** | 1) Check `/robots.txt` → 3 candidate paths → 2) Visit each; two return plausible-but-irrelevant content (decoys), one (`/orders-export`) returns a token → 3) Submit that path for Task 1 → 4) Decode the Base64 token → JSON reveals `passwordHash` (MD5) → 5) Download `/password-wordlist` (now unlocked) → 6) `hashcat -m 0 -a 0 hash.txt wordlist.txt` → 7) `hashcat -m 0 hash.txt --show` to view the cracked password → 8) Submit it for Task 2. |
| **Validation** | Both task answers are checked server-side (`/task1/submit`, `/task2/submit`); flag and final score only render once both are true, following the platform's flag-validation pattern used in earlier stages. |
| **Hints** | Two separate one-time hints (20 marks each): Hint 1 points at `robots.txt` and the need to test each candidate; Hint 2 gives full step-by-step decode + hashcat command syntax, since this is the "hard" task per the assignment's request. |
| **Reset / Recovery** | All state is in-memory only — `docker compose restart web03-shopnest` fully resets everything (sessions, task progress, wordlist re-seeded identically since it's deterministically generated with a fixed random seed). |

## Scoring Model (explicit design decision — flag for report)
- Start: 0, earn 50 marks per task solved (100 max).
- Time decay: **−5 marks per full minute elapsed**, over a **20-minute (1200s)** budget.
- Each hint: **−20 marks flat**, one-time.
- **All-or-nothing timeout rule:** if the 20-minute timer expires before **both** tasks are solved, the final score is forced to **0** regardless of partial progress (e.g. Task 1 already solved). This is a deliberately harsh design choice per the challenge brief, intended to create urgency; worth explicitly noting in the report's difficulty/scoring justification, since it diverges from the softer linear decay used in earlier stages.
- Once both tasks are solved (or time runs out), the session is permanently locked — no further interaction possible.

## Estimated Resources
- CPU: negligible (<0.2 core, lightweight stdlib HTTP server)
- RAM: ~30–40 MB (bare Python process)
- Storage: <60 MB image size (python:3.12-slim base)
- Network: single HTTP port (8000 internal / 8083 host mapped)
