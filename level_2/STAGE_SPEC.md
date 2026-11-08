# Stage Specification

| Field | Description |
|---|---|
| **Stage ID & Title** | WEB-02 — "The Hidden Admin Panel" |
| **Domain** | Web Security (Broken Access Control) — with an OSINT/Reconnaissance overlap via the `robots.txt` disclosure technique. |
| **Difficulty** | Easy–Moderate — note: while flagged as an Easy-tier stage in initial planning, this stage chains three steps (recon → access-control bypass → privileged action), which is slightly more involved than a single-step Easy challenge. Recommend classifying as the "bridge" stage between Easy and Moderate tiers in the difficulty progression, or documenting the extra step count as the Moderate-leaning justification. |
| **Scenario** | "DailyByte Blog" has a normal reader login (open to anyone) and a separate, unlinked administrator panel. The player must discover the hidden panel and use leaked-in-source-code administrator credentials to log in and remove the admin account. |
| **Learning Objective** | Understand broken access control via "security through obscurity" — a hidden admin path is not a real control if it's discoverable through `robots.txt`, and separate credential scopes must both be genuinely protected, not just hidden. |
| **Challenge Environment** | Single Docker container running a Python stdlib HTTP server (no external frameworks) serving the blog, normal login, hidden admin login, and admin dashboard, all with in-memory session state. |
| **Player Task** | 1) Log in as a normal user (any username, password ≥8 characters). 2) Discover `/administrator-panel` via `/robots.txt`. 3) Log in there with the real admin credentials (`musni` / `password123`) — normal user credentials do NOT work here. 4) From the admin dashboard, delete the admin account "musni" to complete the task. |
| **Flag Location / Logic** | Flag (`CTF{r0b0ts_txt_l3aks_th3_p4nel}`) and final score are revealed only after the "Delete Admin Account" action succeeds; the session is then permanently locked from further admin actions. |
| **Required Tools** | A web browser; optionally `curl`/Burp Suite for direct request crafting. No advanced tooling required — the core skill is thinking to check `robots.txt`. |
| **Dependencies** | None — standalone stage, though thematically it reinforces the Web Security domain introduced in WEB-01. |
| **Expected Solution Path** | 1) Register/login as any normal user → 2) Notice the blog has a login and dashboard but no visible admin link → 3) Check `/robots.txt` (either directly or via the in-game hint) → 4) Find `Disallow: /administrator-panel` → 5) Visit that path directly → 6) Realize normal creds fail there → 7) Recognize the admin username `musni` was previewed on the dashboard's "Danger Zone" once logged in — but for the intended flow, the credentials `musni`/`password123` are the target the player must already know or find via the challenge's account-recon framing → 8) Log in and delete the admin account. |
| **Validation** | Flag displayed on successful completion; submitted to the CTF platform's flag-validation service. Final score is computed server-side (not trusted from the client) based on elapsed time and hint usage. |
| **Hints** | Single hint available via the 💡 icon: explicitly names `robots.txt` as the technique to check. Costs a flat **25 marks** (displayed to the player as "~1 minute lost"). |
| **Reset / Recovery** | All session and blog-post state is held in memory only — `docker compose restart web02-blog` fully resets everything (all sessions cleared, blog posts reset to the original four, admin account restored). |

## Scoring Model
- Start: **100 marks**, timer starts the moment the player completes normal login.
- Decay: **−1 mark per 4 seconds elapsed** (display budget shown as a 400-second countdown; score can still decay past 0 floor, clamped at 0).
- Hint: **−25 marks flat**, one-time, computed server-side the moment the hint endpoint is called (not client-trusted).
- Final score is locked and displayed only once the admin account is deleted; no further actions are possible after that point in the same session.

## Estimated Resources
- CPU: negligible (<0.2 core, lightweight single-threaded-per-request Python HTTP server)
- RAM: ~30–40 MB (bare Python process, no framework overhead)
- Storage: <60 MB image size (python:3.12-slim base)
- Network: single HTTP port (8000 internal / 8082 host mapped)

## Security Note
Session cookies are marked `HttpOnly` to reduce trivial XSS-based session theft, though this challenge does not otherwise defend against session fixation or CSRF — those are out of scope for this Easy–Moderate stage and could be called out explicitly in the report's Risks/Limitations section as intentionally simplified for teaching purposes, not production-grade practice.
