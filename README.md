# SUMMIT TRACE

A six-stage progressive Capture The Flag (CTF) Play Box, following musni's trail from an exposed home terminal to his final transmission at the summit.

**Module:** IE3132 — Penetration Testing
**Assignment:** CTF Play Box Implementation

## Overview

Unlike a set of unrelated standalone challenges, SUMMIT TRACE connects all six stages into one continuous campaign. Completing each stage reveals the login credential or PIN needed to unlock the next.

| Stage | Title | Domain | Difficulty |
|---|---|---|---|
| 1 | Breach The Terminal | Web / Client-Side Security | Easy |
| 2 | The Hidden Admin Panel | Web Security (Broken Access Control) | Easy–Moderate |
| 3 | ShopNest Order Leak | Cryptography | Moderate |
| 4 | The Sealed Envelope | Steganography | Moderate |
| 5 | The Locked Radio | Reverse Engineering | Moderate–Hard |
| 6 | The Final Transmission | Digital Forensics + Networking | Hard (capstone) |

## Project Structure

```
ctf-challenges/
├── level_1/   # Breach The Terminal
├── level_2/   # The Hidden Admin Panel
├── level_3/   # ShopNest Order Leak
├── level_4/   # The Sealed Envelope
├── level_5/   # The Locked Radio
└── level_6/   # The Final Transmission
```

Each level folder contains its own `Dockerfile`, `docker-compose.yml`, `STAGE_SPEC.md`, and source files.

## Deployment

Each stage runs as an independent, isolated Docker container. To deploy any stage:

```bash
cd level_X
docker compose up -d --build
```

Each stage listens on its own host port (8081–8086). All six can run simultaneously without conflict.

To reset a stage to its original state:

```bash
docker compose restart
```

## Requirements

- Docker & Docker Compose
- A Kali Linux (or similar) machine with standard pentesting tools: `steghide`, `hashcat`, `binwalk`, `objdump`, `tshark`/Wireshark, `xxd`

## Notes

This repository contains the challenge environments only. Flags, credentials, and solution walkthroughs are intentionally not included in this README to avoid spoiling the challenges.
