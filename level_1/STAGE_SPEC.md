# Stage Specification

| Field | Description |
|---|---|
| **Stage ID & Title** | WEB-01 — "Breach The Terminal" |
| **Domain** | Web / Client-Side Security |
| **Difficulty** | Easy — justification: authentication logic runs entirely client-side and is discoverable via browser DevTools with no server-side exploitation, no injection, and only a single encoding layer (Base64) to reverse. Matches Stage 1–2 "introduce the scenario and basic concepts" tier. |
| **Scenario** | An old ShadowNet admin login panel was left exposed on the network. The login check happens entirely in the browser, and the developer hid the real password using Base64 rather than proper encryption. |
| **Learning Objective** | Introduce client-side security analysis: using browser DevTools (Inspect/View Source) to read front-end JavaScript, recognising Base64 as encoding (not encryption), and decoding it to recover a credential. |
| **Challenge Environment** | Single Docker container running nginx serving a static HTML/CSS/JS login page. No backend/API — authentication check and scoring happen fully client-side in `script.js`. |
| **Player Task** | Inspect the page source, locate the Base64-encoded password string in `script.js`, decode it, and log in as `admin` to reveal the flag. |
| **Flag Location / Logic** | The real password is Base64-encoded (`TDN0TTNJbiQyMDI2`) and stored as a JS variable, decoded via `atob()` only at the moment of form submission — so the plaintext password never appears anywhere in the static source, only the encoded form does. Once the correct password is entered, the flag `CTF{b4s3_64_1sn7_3ncrypt10n}` is displayed alongside the player's final score. |
| **Required Tools** | Browser DevTools (Inspect Element / View Page Source / Console), any Base64 decoder (e.g. `echo ... \| base64 -d` in a Kali terminal, or an online decoder such as CyberChef). |
| **Dependencies** | None — standalone entry-level stage. |
| **Expected Solution Path** | 1) Open DevTools → View Source or Sources tab → open `script.js` → 2) locate the `ENC_PASS` variable → 3) recognise it as Base64 (padding/character set) → 4) decode it via terminal (`echo "TDN0TTNJbiQyMDI2" \| base64 -d`) or an online tool → 5) enter `admin` / decoded password into the login form → 6) read the flag and final score from the success message. |
| **Validation** | Correct credentials trigger a client-side success message containing the flag and the computed score; flag is then submitted to the CTF platform's flag-validation service for exact-match scoring/logging. |
| **Hints** | Hint icon reveals a confirmation prompt before showing the actual hint text, since viewing it costs marks. Hint points toward `script.js` and describes the string as "encoded, not encrypted" without naming the variable or the decoded value. |
| **Reset / Recovery** | Fully stateless static site — no player input is persisted server-side. Recovery = container restart (`docker compose restart web01-terminal`); nothing to corrupt since there is no backend state. Score/attempt state resets automatically on page reload since it lives only in browser memory for this stage. |

## Scoring Model
- Start: **100 marks**
- Each failed login attempt: **−5 marks**
- Using the hint (one-time deduction, regardless of how many times viewed): **−20 marks**
- Final score is displayed to the player immediately on successful login, alongside the flag.
- This client-side score is indicative/formative for the player's own feedback. The platform's authoritative scoring (for the leaderboard/grading) should be computed server-side at the control layer based on submission timestamps, hint-reveal API calls, and flag-submission attempts — not trusted purely from client-reported values, since a player could in principle tamper with client-side JavaScript. See note below.

## Note on Security Controls (Platform-Level)
This individual stage container does not implement attempt-limiting or logging itself — it's a stateless static site by design. However, the assignment's Security Controls requirement (isolation, reset mechanism, privilege restrictions, **logging**) is addressed at the **CTF platform / control-layer**, not per-challenge-container. The architecture write-up should document that:
- The control layer receives and logs every flag-submission attempt across all 6 stages (timestamp, player ID, stage ID, success/failure), independent of each challenge container's own internal logic.
- Rate-limiting/lockout for abusive brute-forcing (if desired) is enforced centrally at the platform, not duplicated inside every individual container.
- This keeps each challenge container simple, stateless, and easy to reset, while centralising the security-sensitive logging/audit responsibility in one place — consistent with least-privilege and separation-of-concerns principles.

## Estimated Resources
- CPU: negligible (<0.1 core, static file serving via nginx)
- RAM: ~10–20 MB (nginx:alpine base)
- Storage: <15 MB image size
- Network: single HTTP port (80 internal / 8081 host mapped)
