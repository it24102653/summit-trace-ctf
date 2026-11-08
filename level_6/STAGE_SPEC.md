# Stage Specification

| Field | Description |
|---|---|
| **Stage ID & Title** | WEB-06 — "The Final Transmission" |
| **Domain** | Digital Forensics (Task 1) and Networking (Task 2) — dual-domain capstone stage. |
| **Difficulty** | Hard — matches the module's Stage 6 "integrating, capstone-style challenge" description. Combines two previously-unused domains in a genuine dependency chain (Task 2's artifact only exists because Task 1 recovered it), rather than two unrelated puzzles bolted together. |
| **Scenario** | musni's basecamp radio log recorded his last transmission before his final push to the summit, but the recording is hidden inside an ordinary-looking photo. The player must recover it, then analyse the recovered network traffic to reconstruct his final message. |
| **Learning Objective** | Task 1: recognise that a valid file (a real, openable JPEG) can still carry a second hidden file appended after its own data — using `file`/`binwalk` to detect it and manual byte carving (`tail -c +N`) or extraction to recover it, then hashing the result to prove correct extraction. Task 2: read real packet-capture traffic, filter out decoy/noise packets, and reconstruct a message that was deliberately split across multiple DNS query labels — a real-world data-exfiltration technique. |
| **Challenge Environment** | Single Docker container, pure Python stdlib HTTP server. One real downloadable artifact: a genuine JPEG (renders correctly, 800×500, generated originally — not a real person's photo, avoiding any privacy concerns for this final public-facing asset) with a real ZIP archive (containing a real pcap file, built with `scapy`) appended after the JPEG's own end-of-file marker. |
| **Player Task** | 1) Log in with the credentials from Level 5. 2) Task 1: download `basecamp_photo.jpg`, discover the appended ZIP via `file`/`binwalk`, carve/extract it, and submit the MD5 hash of the recovered `.pcap` file. 3) Task 2: open that pcap in Wireshark/`tshark`, filter to the DNS queries sharing an unusual shared suffix (ignoring decoy queries to unrelated domains), read them in order, and concatenate the first label of each to reconstruct the final code. |
| **Flag Location / Logic** | Flag (`CTF{c4rv3_th3n_sn1ff_th3_summit}`) is revealed only once both tasks are solved. This is the **final stage** — submitting the flag via the chain's Submit Flag box shows a full campaign-completion message instead of new credentials, closing the "musni's hiking trip" narrative that has run across all six levels. |
| **Required Tools** | `file`, `binwalk` (or manual `tail -c +N` carving), `unzip`, `md5sum` for Task 1; Wireshark or `tshark -Y "dns.qry.name contains ..."` for Task 2. |
| **Dependencies** | Task 2 genuinely depends on Task 1's output (the pcap only exists once extracted) but is not server-side gated — the player already has the file once they've solved Task 1, so an artificial lock isn't necessary. |
| **Expected Solution Path** | 1) `file basecamp_photo.jpg` confirms JPEG → 2) `binwalk basecamp_photo.jpg` reveals a Zip archive at a byte offset → 3) `tail -c +<offset+1> basecamp_photo.jpg > carved.zip && unzip carved.zip` → 4) `md5sum final_transmission.pcap` → submit for Task 1 → 5) `tshark -r final_transmission.pcap -Y "dns.qry.name contains \"telemetry\""` → 6) read the 4 matching queries in order, concatenate first labels → submit for Task 2. |
| **Validation** | Both task answers checked server-side. Task 1 is case-insensitive (hashes are conventionally lowercase but shouldn't trip up a correct answer typed in uppercase). Task 2 strips dashes/spaces and is case-insensitive, since players may reasonably format the reconstructed code differently. |
| **Hints** | Four one-time hints: Task 1 hints −10 each (max −20), Task 2 hints −15 each (max −30) — the highest hint costs in the whole campaign, appropriate for the final Hard-tier stage. None reveal the actual MD5 hash or final code directly — they teach the carving/filtering technique only. |
| **Reset / Recovery** | All state is in-memory only — `docker compose restart web06-final` fully resets everything. |

## Scoring Model (same deduction-only pattern as Levels 4–6, no time limit)
- Starts at **100**.
- Each wrong submission (either task): **−10 marks**, unlimited retries.
- Hints cost marks individually per use, one-time each: Task 1 −10 each (max −20 total), Task 2 −15 each (max −30 total).
- Correct task completion does not add marks — a perfect run with no mistakes and no hints preserves the full starting 100.
- Once both tasks are solved, the score is locked and shown with the flag; submitting the flag via the chain's Submit Flag box closes out the entire six-level campaign.

## Estimated Resources
- CPU: negligible (<0.2 core)
- RAM: ~30–40 MB
- Storage: ~18 KB combined asset (JPEG + appended ZIP/pcap) + <60 MB base image
- Network: single HTTP port (8000 internal / 8086 host mapped)

## Note on Asset Construction (for the report's methodology section)
The `basecamp_photo.jpg` asset was built by: (1) generating an original illustrative image with PIL (not a real photograph, to avoid any privacy/copyright concerns on this public-facing artifact), (2) crafting a genuine multi-packet pcap with `scapy`, containing real DNS query packets — some carrying fragments of the hidden code as subdomain labels, others decoy traffic — (3) zipping the pcap, and (4) concatenating the zip's bytes directly after the JPEG's own data, a well-known real-world file-carving scenario (the JPEG remains fully valid and viewable; the appended data is simply ignored by image viewers but detectable by tools like `binwalk` that scan for embedded file signatures).
