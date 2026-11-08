#!/usr/bin/env python3
"""
WEB-04 : "The Sealed Envelope"
Domain      : Steganography (primary) / Cryptography - Hex/Base16 encoding (secondary)
Difficulty  : Moderate

Pure Python standard-library implementation (no Flask, no pip installs).

Flow:
  1. Landing page shows a closed kraft-paper envelope. Clicking "Open"
     reveals a personal letter, an embedded photo, and a download link
     for that photo.
  2. Task 1 (robots.txt recon + hex decoding): robots.txt discloses three
     candidate paths. Two are decoys with irrelevant content; the real
     one returns a Hex (Base-16) encoded string. Decoding it reveals a
     12-character key.
  3. Task 2 (steganography): the SAME key from Task 1 is the steghide
     passphrase embedded in the downloaded photo. The player extracts a
     hidden text file from the image using that passphrase and submits
     the secret message it contains.
  4. No time limit on this stage - purely deduction-based scoring: start
     at 100, lose marks for wrong answers and hint usage. Once both
     tasks are solved, the final score is locked and shown; no way back.
"""

import http.server
import socketserver
import uuid
import base64
import re
import urllib.parse
import html
import json
from http import cookies

import sys
sys.path.insert(0, "/app")
from image_data import IMAGE_B64

HOST = "0.0.0.0"
PORT = 8000

REAL_KEY = "assassin1234"
KEY_HEX = REAL_KEY.encode().hex()  # 617373617373696e31323334

SECRET_MESSAGE = ("The Grand Crest Hotel, Room 214. The details are set, "
                   "and the security package is stored in the lockbox "
                   "under the floorboards")

WRONG_PENALTY = 7
HINT1_COST = 8    # task 1, each of its 2 hints
HINT2_COST = 12   # task 2, each of its 2 hints

CORRECT_PATH = "/secret-key-a1"
DECOY_1 = "/notes-b2"
DECOY_2 = "/config-c3"

FLAG = "CTF{h3x_th3n_st3gh1d3_s34l3d}"

# Entry PIN required to open the envelope - revealed by Level 3's flag
# submission.
CHAIN_PIN = "7734"

# 7-digit PIN revealed to the player upon submitting THIS level's flag,
# needed to unlock Level 5.
NEXT_LEVEL_PIN = "5923187"

SESSIONS = {}

LETTER_TEXT = """Hey sharaf,

I am out hiking in the mountains right now.
My phone signal is very weak here. I will text you back as soon as I get back to a place with good service.

Talk to you soon!

Best,
musni"""


def new_session():
    sid = uuid.uuid4().hex
    SESSIONS[sid] = {
        "pin_verified": False,
        "opened": False,
        "task1_done": False,
        "task2_done": False,
        "wrong1": 0,
        "wrong2": 0,
        "hint1a_used": False,
        "hint1b_used": False,
        "hint2a_used": False,
        "hint2b_used": False,
        "completed": False,
        "flag_finalized": False,
    }
    return sid


def get_or_create_session(handler):
    if "Cookie" in handler.headers:
        c = cookies.SimpleCookie()
        c.load(handler.headers["Cookie"])
        if "session_id" in c and c["session_id"].value in SESSIONS:
            return c["session_id"].value, SESSIONS[c["session_id"].value], None
    sid = new_session()
    return sid, SESSIONS[sid], f"session_id={sid}; Path=/; HttpOnly"


def get_session(handler):
    if "Cookie" in handler.headers:
        c = cookies.SimpleCookie()
        c.load(handler.headers["Cookie"])
        if "session_id" in c and c["session_id"].value in SESSIONS:
            return c["session_id"].value, SESSIONS[c["session_id"].value]
    return None, None


def current_score(sess):
    score = 100
    score -= sess["wrong1"] * WRONG_PENALTY
    score -= sess["wrong2"] * WRONG_PENALTY
    if sess["hint1a_used"]:
        score -= HINT1_COST
    if sess["hint1b_used"]:
        score -= HINT1_COST
    if sess["hint2a_used"]:
        score -= HINT2_COST
    if sess["hint2b_used"]:
        score -= HINT2_COST
    return max(0, score)


def normalize(text):
    return re.sub(r"\s+", " ", text.strip().lower())


def status_bar(sess, extra_buttons=""):
    if not sess or not sess.get("opened"):
        return ""
    score = current_score(sess)
    flag_done = sess.get("flag_finalized")
    return f"""
    <div class="navbar">
      <div class="nav-left">
        <button class="icon-btn flag-btn" onclick="openFlagModal()" {'disabled' if flag_done else ''}>
          {'🎉 Chapter Complete' if flag_done else '🚩 Submit Flag'}
        </button>
      </div>
      <span class="brand">✉️ The Sealed Envelope</span>
      <div class="actions">
        <span class="badge">Score: {score}</span>
        {extra_buttons}
      </div>
    </div>
    <div id="flagModal" class="modal" style="display:none;">
      <div class="modal-box">
        <h3>🚩 Submit Flag to Continue</h3>
        <p>Once you've found this level's flag, paste it below to confirm
           the chapter is complete and unlock the next one.</p>
        <input type="text" id="flagInputBox" placeholder="CTF{{...}}" style="width:100%;padding:9px;border:1px solid var(--line);border-radius:4px;margin:8px 0;font-family:'Public Sans',sans-serif;background:#fbf6ea;color:var(--ink);">
        <button onclick="submitFlag()">Submit Flag</button>
        <p id="flagModalMsg" class="error"></p>
        <div id="nextLevelBox" style="display:none;background:rgba(92,122,77,0.1);border:1px solid var(--green);border-radius:4px;padding:12px 14px;margin-top:10px;white-space:pre-line;font-size:0.9rem;color:var(--ink);font-family:'IBM Plex Mono',monospace;"></div>
        <button onclick="document.getElementById('flagModal').style.display='none'" style="background:var(--ink-soft);margin-top:8px;">Close</button>
      </div>
    </div>
    <script>
      function openFlagModal() {{ document.getElementById('flagModal').style.display='flex'; }}
      function submitFlag() {{
        const val = document.getElementById('flagInputBox').value.trim();
        const body = new URLSearchParams();
        body.append('flag_guess', val);
        fetch('/submit-flag', {{ method: 'POST', headers: {{'Content-Type':'application/x-www-form-urlencoded'}}, body: body }})
          .then(r => r.json()).then(data => {{
            if (data.correct) {{
              document.getElementById('flagModalMsg').textContent = '';
              const box = document.getElementById('nextLevelBox');
              box.textContent = data.message;
              box.style.display = 'block';
              document.querySelectorAll('.flag-btn').forEach(b => {{ b.disabled = true; b.textContent = '🎉 Chapter Complete'; }});
            }} else {{
              document.getElementById('flagModalMsg').textContent = 'Incorrect flag. Keep working on the tasks.';
            }}
          }});
      }}
    </script>
    """


def page_shell(title, body):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{html.escape(title)}</title>
<style>{BASE_CSS}</style>
</head>
<body>
<div class="trail-tape"></div>
{body}
</body>
</html>"""


BASE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,600;1,9..144,500&family=Public+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;600&display=swap');

:root {
  --paper: #faf6ec;
  --paper-card: #fffdf8;
  --line: #d8c9a8;
  --brown: #8a5a34;
  --brown-dark: #6b4324;
  --green: #5c7a4d;
  --green-dark: #47603c;
  --ink: #3a2f22;
  --ink-soft: #6b5c46;
  --red: #b5432f;
}

* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: 'Public Sans', Arial, sans-serif;
  background: var(--paper);
  color: var(--ink);
}
.trail-tape {
  height: 8px;
  width: 100%;
  background: repeating-linear-gradient(
    45deg,
    var(--brown) 0px, var(--brown) 16px,
    var(--green) 16px, var(--green) 32px
  );
}
h1, h2, h3 { font-family: 'Fraunces', serif; font-weight: 600; }
.navbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 28px;
  background: var(--paper-card);
  border-bottom: 1px solid var(--line);
}
.navbar .nav-left { display: flex; align-items: center; }
.navbar .flag-btn {
  background: transparent !important;
  border: 1px solid var(--brown) !important;
  color: var(--brown-dark) !important;
  font-weight: 600;
}
.navbar .flag-btn:hover { background: var(--brown) !important; color: #fff8ec !important; }
.navbar .flag-btn:disabled { opacity: 0.6; cursor: default; }
.navbar .brand { font-family: 'Fraunces', serif; font-style: italic; font-weight: 500; font-size: 1.1rem; color: var(--brown-dark); }
.navbar .actions { display: flex; gap: 10px; align-items: center; }
.navbar .icon-btn {
  background: transparent;
  border: 1px solid var(--brown);
  color: var(--brown-dark);
  padding: 6px 14px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
  text-decoration: none;
  font-family: 'Public Sans', sans-serif;
  font-weight: 600;
}
.navbar .icon-btn:hover { background: var(--brown); color: #fff8ec; }
.badge {
  font-family: 'IBM Plex Mono', monospace;
  background: rgba(92,122,77,0.08);
  color: var(--green-dark);
  border: 1px solid var(--green);
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 0.82rem;
}
.landing {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 90vh;
  padding: 20px;
}
.envelope {
  width: 340px;
  height: 220px;
  background: linear-gradient(135deg, var(--brown), var(--brown-dark));
  position: relative;
  border-radius: 4px;
  box-shadow: 0 14px 34px rgba(90,74,53,0.25);
  margin-bottom: 30px;
}
.envelope::before {
  content: "";
  position: absolute;
  top: 0; left: 0;
  width: 0; height: 0;
  border-left: 170px solid transparent;
  border-right: 170px solid transparent;
  border-top: 110px solid var(--brown-dark);
}
.spec-caption {
  max-width: 520px;
  text-align: center;
  font-size: 0.85rem;
  color: var(--ink-soft);
  margin-bottom: 24px;
  line-height: 1.5;
  font-style: italic;
}
.btn-open {
  background: var(--brown);
  color: #fff8ec;
  border: none;
  padding: 12px 32px;
  border-radius: 4px;
  font-size: 1rem;
  cursor: pointer;
  font-family: 'Public Sans', sans-serif;
  font-weight: 600;
}
.btn-open:hover { background: var(--brown-dark); }
.wrap { max-width: 760px; margin: 0 auto; padding: 30px 20px; }
.letter-card {
  background: var(--paper-card);
  border: 1px solid var(--line);
  border-left: 6px solid var(--brown);
  border-radius: 4px;
  padding: 30px 34px;
  box-shadow: 0 8px 24px rgba(90,74,53,0.08);
  white-space: pre-line;
  font-size: 1.05rem;
  line-height: 1.7;
}
.image-card {
  margin-top: 26px;
  text-align: center;
}
.image-card img {
  max-width: 100%;
  border-radius: 4px;
  box-shadow: 0 8px 24px rgba(90,74,53,0.18);
}
.download-btn {
  display: inline-block;
  margin-top: 14px;
  background: var(--brown);
  color: #fff8ec;
  padding: 10px 22px;
  border-radius: 4px;
  text-decoration: none;
  font-family: 'Public Sans', sans-serif;
  font-weight: 600;
  font-size: 0.9rem;
}
.download-btn:hover { background: var(--brown-dark); }
.card {
  background: var(--paper-card);
  border: 1px solid var(--line);
  border-radius: 4px;
  box-shadow: 0 8px 24px rgba(90,74,53,0.08);
  padding: 24px;
  margin-bottom: 20px;
  border-left: 5px solid var(--brown);
  font-family: 'Public Sans', sans-serif;
}
.card.done { border-left-color: var(--green); }
.task-title { display:flex; justify-content:space-between; align-items:center; flex-wrap: wrap; gap: 8px; }
.hint-icon-btn {
  background: rgba(138,90,52,0.08);
  border: 1px solid var(--brown);
  color: var(--brown-dark);
  padding: 5px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.78rem;
}
.hint-icon-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.hint-text-box {
  background: rgba(138,90,52,0.08);
  border: 1px dashed var(--brown);
  padding: 12px 14px;
  border-radius: 4px;
  font-size: 0.85rem;
  margin-top: 10px;
  white-space: pre-wrap;
  color: var(--ink-soft);
}
label { font-size: 0.8rem; color: var(--ink-soft); display:block; margin-top: 12px; font-family: 'Public Sans', sans-serif; font-weight: 600; }
input[type=text], textarea {
  width: 100%;
  padding: 9px 10px;
  border: 1px solid var(--line);
  border-radius: 4px;
  margin-top: 4px;
  font-size: 0.95rem;
  font-family: 'Public Sans', sans-serif;
  background: #fbf6ea;
  color: var(--ink);
}
button, .btn {
  margin-top: 14px;
  background: var(--brown);
  color: #fff8ec;
  border: none;
  padding: 10px;
  border-radius: 4px;
  cursor: pointer;
  width: 100%;
  font-size: 0.9rem;
  font-family: 'Public Sans', sans-serif;
  font-weight: 600;
}
button:hover { background: var(--brown-dark); }
.error { color: var(--red); font-size: 0.85rem; margin-top: 8px; font-family: 'Public Sans', sans-serif; }
.success-text { color: var(--green-dark); font-size: 0.85rem; margin-top: 8px; font-weight: 600; font-family: 'Public Sans', sans-serif; }
.modal {
  position: fixed; inset: 0; background: rgba(58,47,34,0.45);
  display: flex; align-items: center; justify-content: center;
}
.modal-box {
  background: var(--paper-card); border: 1px solid var(--line); padding: 26px 30px; border-radius: 4px;
  max-width: 460px; width: 90%; font-family: 'Public Sans', sans-serif;
}
code { background: rgba(92,122,77,0.1); padding: 1px 5px; border-radius: 3px; color: var(--green-dark); font-family: 'IBM Plex Mono', monospace; }
"""


class Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass

    def send_html(self, body_str, status=200, set_cookie=None):
        encoded = body_str.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
        self.end_headers()
        self.wfile.write(encoded)

    def send_text(self, text, status=200, content_type="text/plain"):
        encoded = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def redirect(self, location, set_cookie=None):
        self.send_response(302)
        self.send_header("Location", location)
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
        self.end_headers()

    def read_form(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8") if length else ""
        return {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}

    # ---------------- routing ----------------
    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        query = urllib.parse.urlsplit(self.path).query

        if path == "/robots.txt":
            self.send_text(
                "User-agent: *\n"
                f"Disallow: {CORRECT_PATH}\n"
                f"Disallow: {DECOY_1}\n"
                f"Disallow: {DECOY_2}\n"
            )
            return
        if path == "/":
            self.render_landing()
            return
        if path == "/open":
            sid, sess, set_cookie = get_or_create_session(self)
            if not sess.get("pin_verified"):
                self.redirect("/", set_cookie=set_cookie)
                return
            sess["opened"] = True
            self.redirect("/letter", set_cookie=set_cookie)
            return
        if path == "/letter":
            self.render_letter()
            return
        if path == "/assets/envelope_photo.jpg":
            self.serve_image(download="download" in query)
            return
        if path == "/tasks":
            self.render_tasks()
            return
        if path == CORRECT_PATH:
            self.send_text(KEY_HEX)
            return
        if path == DECOY_1:
            self.send_text(
                "Reminder: the printer on the 3rd floor is out of toner again.\n"
                "Also don't forget the team lunch on Friday."
            )
            return
        if path == DECOY_2:
            self.send_text(
                json.dumps({"status": "deprecated", "message": "This config endpoint is no longer in use."}, indent=2),
                content_type="application/json"
            )
            return
        if path == "/hint1a":
            self.handle_hint("hint1a_used", HINT1_COST,
                "Check /robots.txt - it lists a few disallowed paths. Not "
                "all of them are decoys; visit each one and see what it "
                "actually returns.")
            return
        if path == "/hint1b":
            self.handle_hint("hint1b_used", HINT1_COST,
                "The value you found is Hexadecimal (Base-16) encoding, not "
                "real encryption. You can decode any hex string the same way, "
                "for example:\n  echo \"48656c6c6f\" | xxd -r -p\n"
                "...which outputs \"Hello\". Try the same command on the "
                "value you found from the leaked path.")
            return
        if path == "/hint2a":
            self.handle_hint("hint2a_used", HINT2_COST,
                "That photo isn't just a photo - there's a hidden text file "
                "embedded inside it using steganography. Nothing looks "
                "different to the eye, but the file itself is larger than "
                "a plain photo would need to be.")
            return
        if path == "/hint2b":
            self.handle_hint("hint2b_used", HINT2_COST,
                "Steghide can extract hidden files from a JPEG if you know "
                "the passphrase. General syntax:\n"
                "  steghide extract -sf your_downloaded_image.jpg\n"
                "It will then prompt you for a passphrase - use the exact "
                "same key you already decoded in Task 1. Once extracted, "
                "read the resulting file with:\n  cat <extracted_filename>")
            return
        if path == "/completed":
            self.render_completed()
            return

        self.send_text("404 Not Found", status=404)

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path

        if path == "/verify-pin":
            self.handle_verify_pin()
            return
        if path == "/task1/submit":
            self.handle_task1_submit()
            return
        if path == "/task2/submit":
            self.handle_task2_submit()
            return
        if path == "/submit-flag":
            self.handle_submit_flag()
            return

        self.send_text("404 Not Found", status=404)

    # ---------------- landing / letter ----------------
    def render_landing(self, error=None):
        sid, sess = get_session(self)

        if not sess or not sess.get("pin_verified"):
            error_html = f'<p class="error">{html.escape(error)}</p>' if error else ""
            body = f"""
            <div class="landing">
              <h1 style="color:var(--brown-dark);">A Sealed Envelope Awaits</h1>
              <p class="spec-caption">
                📖 Chapter 4 — Journey's End: This envelope is locked with a
                4-digit PIN. You'll need the one revealed at the end of
                Chapter 3 to open it.
              </p>
              <div class="envelope"></div>
              <form method="POST" action="/verify-pin" style="max-width:260px;margin-top:10px;">
                <label style="font-family:'Segoe UI',Arial,sans-serif;font-size:0.85rem;color:var(--brown-dark);">Enter 4-digit PIN</label>
                <input type="text" name="pin" maxlength="4" pattern="[0-9]{{4}}"
                       style="width:100%;padding:10px;border:1px solid var(--brown);border-radius:4px;margin-top:6px;text-align:center;font-size:1.2rem;letter-spacing:4px;font-family:'IBM Plex Mono',monospace;background:#fbf6ea;color:var(--ink);" required>
                <button type="submit" class="btn-open" style="width:100%;margin-top:12px;">Unlock Envelope</button>
              </form>
              {error_html}
            </div>
            """
            self.send_html(page_shell("A Sealed Envelope", body))
            return

        body = """
        <div class="landing">
          <h1 style="color:var(--brown-dark);">A Sealed Envelope Has Arrived</h1>
          <p class="spec-caption">
            Manufacturing note: outer stock is an eco-friendly, natural brown
            kraft paper (120gsm), bonded via cold-set lamination to a premium
            100gsm white interior lining for a clean contrast when opened.
          </p>
          <div class="envelope"></div>
          <a href="/open"><button class="btn-open">Open Envelope</button></a>
        </div>
        """
        self.send_html(page_shell("A Sealed Envelope", body))

    def handle_verify_pin(self):
        sid, sess, set_cookie = get_or_create_session(self)
        form = self.read_form()
        pin = form.get("pin", "").strip()

        if pin == CHAIN_PIN:
            sess["pin_verified"] = True
            self.redirect("/", set_cookie=set_cookie)
            return

        error_html = '<p class="error">Incorrect PIN. This must come from completing Chapter 3.</p>'
        body = f"""
        <div class="landing">
          <h1 style="color:var(--brown-dark);">A Sealed Envelope Awaits</h1>
          <p class="spec-caption">
            📖 Chapter 4 — Journey's End: This envelope is locked with a
            4-digit PIN. You'll need the one revealed at the end of
            Chapter 3 to open it.
          </p>
          <div class="envelope"></div>
          <form method="POST" action="/verify-pin" style="max-width:260px;margin-top:10px;">
            <label style="font-family:'Segoe UI',Arial,sans-serif;font-size:0.85rem;color:var(--brown-dark);">Enter 4-digit PIN</label>
            <input type="text" name="pin" maxlength="4" pattern="[0-9]{{4}}"
                   style="width:100%;padding:10px;border:1px solid var(--brown);border-radius:4px;margin-top:6px;text-align:center;font-size:1.2rem;letter-spacing:4px;font-family:'IBM Plex Mono',monospace;background:#fbf6ea;color:var(--ink);" required>
            <button type="submit" class="btn-open" style="width:100%;margin-top:12px;">Unlock Envelope</button>
          </form>
          {error_html}
        </div>
        """
        self.send_html(page_shell("A Sealed Envelope", body), set_cookie=set_cookie)

    def render_letter(self):
        sid, sess = get_session(self)
        if not sess or not sess.get("opened"):
            self.redirect("/")
            return
        if sess.get("completed"):
            self.redirect("/completed")
            return

        buttons = '<button class="icon-btn" onclick="showReadme()">📄 README</button><a class="icon-btn" href="/tasks">📋 Tasks</a>'
        bar = status_bar(sess, buttons)

        body = f"""
        {bar}
        <div class="wrap">
          <div class="letter-card">{html.escape(LETTER_TEXT)}</div>
          <div class="image-card">
            <img src="/assets/envelope_photo.jpg" alt="Envelope photo">
            <br>
            <a class="download-btn" href="/assets/envelope_photo.jpg?download=1" download="envelope_photo.jpg">⬇ Download Image</a>
          </div>
        </div>

        <div id="readmeModal" class="modal" style="display:none;">
          <div class="modal-box">
            <h3>📄 README — WEB-04: The Sealed Envelope</h3>
            <p><strong>Domain:</strong> Steganography / Cryptography (Hex encoding)</p>
            <p><strong>Task 1:</strong> Find a hidden file path and decode what it reveals.</p>
            <p><strong>Task 2:</strong> Download the photo and extract a hidden message from it.</p>
            <p><strong>Scoring:</strong> Start at 100. Each wrong answer: -7 marks.
               Hints cost marks individually and can only be used once each.</p>
            <p><strong>Flag format:</strong> CTF{{...}}</p>
            <button onclick="document.getElementById('readmeModal').style.display='none'">Close</button>
          </div>
        </div>
        <script>
          function showReadme() {{ document.getElementById('readmeModal').style.display='flex'; }}
        </script>
        """
        self.send_html(page_shell("The Letter", body))

    def serve_image(self, download=False):
        sid, sess = get_session(self)
        if not sess or not sess.get("opened"):
            self.redirect("/")
            return
        data = base64.b64decode(IMAGE_B64)
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        if download:
            self.send_header("Content-Disposition", 'attachment; filename="envelope_photo.jpg"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ---------------- tasks ----------------
    def render_tasks(self, t1_error=None, t2_error=None):
        sid, sess = get_session(self)
        if not sess or not sess.get("opened"):
            self.redirect("/")
            return
        if sess.get("completed"):
            self.redirect("/completed")
            return

        t1_done = sess["task1_done"]
        t2_done = sess["task2_done"]

        task1_card = f"""
        <div class="card {'done' if t1_done else ''}">
          <div class="task-title">
            <h3>Task 1: Find the Hidden Key</h3>
            <div>
              <button class="hint-icon-btn" id="hint1aBtn" onclick="getHint('1a')" {'disabled' if sess['hint1a_used'] else ''}>💡 Hint 1 (-{HINT1_COST})</button>
              <button class="hint-icon-btn" id="hint1bBtn" onclick="getHint('1b')" {'disabled' if sess['hint1b_used'] else ''}>💡 Hint 2 (-{HINT1_COST})</button>
            </div>
          </div>
          <p>Somewhere on this server a file path leaks a secret key. Find it
             and decode what it reveals. The key is exactly 12 characters.</p>
          {"<p class='success-text'>✅ Solved!</p>" if t1_done else f'''
          <form method="POST" action="/task1/submit">
            <label>Secret key (12 characters)</label>
            <input type="text" name="answer" maxlength="12" placeholder="Enter the 12-character key" required>
            <button type="submit">Submit</button>
          </form>
          {'<p class="error">' + html.escape(t1_error) + '</p>' if t1_error else ''}
          '''}
          <div id="hint1aBox" class="hint-text-box" style="display:none;"></div>
          <div id="hint1bBox" class="hint-text-box" style="display:none;"></div>
        </div>
        """

        task2_card = f"""
        <div class="card {'done' if t2_done else ''}">
          <div class="task-title">
            <h3>Task 2: What Was Hidden in the Image?</h3>
            <div>
              <button class="hint-icon-btn" id="hint2aBtn" onclick="getHint('2a')" {'disabled' if sess['hint2a_used'] else ''}>💡 Hint 1 (-{HINT2_COST})</button>
              <button class="hint-icon-btn" id="hint2bBtn" onclick="getHint('2b')" {'disabled' if sess['hint2b_used'] else ''}>💡 Hint 2 (-{HINT2_COST})</button>
            </div>
          </div>
          <p>Download the photo from the letter and find the message hidden
             inside it. What does the secret message say?</p>
          {"<p class='success-text'>✅ Solved!</p>" if t2_done else f'''
          <form method="POST" action="/task2/submit">
            <label>Secret message</label>
            <textarea name="answer" rows="3" placeholder="Paste the extracted message here" required></textarea>
            <button type="submit">Submit</button>
          </form>
          {'<p class="error">' + html.escape(t2_error) + '</p>' if t2_error else ''}
          '''}
          <div id="hint2aBox" class="hint-text-box" style="display:none;"></div>
          <div id="hint2bBox" class="hint-text-box" style="display:none;"></div>
        </div>
        """

        if t1_done and t2_done:
            sess["completed"] = True
            self.redirect("/completed")
            return

        buttons = '<a class="icon-btn" href="/letter">✉️ Letter</a>'
        bar = status_bar(sess, buttons)

        body = f"""
        {bar}
        <div class="wrap">
          <h2 style="color:var(--brown-dark);">📋 Task Panel</h2>
          {task1_card}
          {task2_card}
        </div>
        <script>
          function getHint(id) {{
            fetch('/hint' + id).then(r => r.json()).then(data => {{
              if (data.error) return;
              document.querySelector('.badge').textContent = 'Score: ' + data.score;
              const box = document.getElementById('hint' + id + 'Box');
              box.textContent = data.hint;
              box.style.display = 'block';
              document.getElementById('hint' + id + 'Btn').disabled = true;
            }});
          }}
        </script>
        """
        self.send_html(page_shell("Task Panel", body))

    def handle_task1_submit(self):
        sid, sess = get_session(self)
        if not sess or not sess.get("opened"):
            self.redirect("/")
            return
        if sess.get("completed"):
            self.redirect("/completed")
            return

        form = self.read_form()
        guess = form.get("answer", "").strip()

        if guess == REAL_KEY:
            sess["task1_done"] = True
            self.render_tasks()
        else:
            sess["wrong1"] += 1
            self.render_tasks(t1_error="Incorrect key. Keep investigating the leaked paths.")

    def handle_task2_submit(self):
        sid, sess = get_session(self)
        if not sess or not sess.get("opened"):
            self.redirect("/")
            return
        if sess.get("completed"):
            self.redirect("/completed")
            return

        form = self.read_form()
        guess = form.get("answer", "")

        if normalize(guess) == normalize(SECRET_MESSAGE):
            sess["task2_done"] = True
            self.render_tasks()
        else:
            sess["wrong2"] += 1
            self.render_tasks(t2_error="That doesn't match the hidden message. Make sure you extracted it correctly.")

    def handle_hint(self, flag_name, cost, hint_text):
        sid, sess = get_session(self)
        if not sess:
            self.send_text(json.dumps({"error": "no session"}), content_type="application/json")
            return
        sess[flag_name] = True
        self.send_text(json.dumps({"hint": hint_text, "score": current_score(sess)}), content_type="application/json")

    # ---------------- completion ----------------
    def handle_submit_flag(self):
        sid, sess = get_session(self)
        if not sess:
            self.send_text(json.dumps({"correct": False}), content_type="application/json")
            return

        form = self.read_form()
        guess = form.get("flag_guess", "").strip()

        if guess == FLAG:
            sess["flag_finalized"] = True
            message = (
                "🎉 Congratulations! Chapter 4 complete.\n\n"
                "musni is almost there. The next checkpoint is locked "
                "behind a 7-digit access code:\n\n"
                f"PIN: {NEXT_LEVEL_PIN}\n\n"
                "Head to Level 5 and enter it to continue."
            )
            self.send_text(json.dumps({"correct": True, "message": message}), content_type="application/json")
        else:
            self.send_text(json.dumps({"correct": False}), content_type="application/json")

    def render_completed(self):
        sid, sess = get_session(self)
        if not sess or not sess.get("completed"):
            self.redirect("/")
            return

        score = current_score(sess)
        bar = status_bar(sess)
        body = f"""
        {bar}
        <div class="landing">
          <div class="letter-card" style="text-align:center; max-width:480px;">
            <h2 style="color:var(--brown-dark);">✅ Both Tasks Complete</h2>
            <p>The sealed envelope has given up all its secrets.</p>
            <p style="font-size:1.1rem;"><strong>Flag:</strong> {FLAG}</p>
            <p style="font-size:1.3rem;"><strong>Final Score: {score} / 100</strong></p>
            <p style="color:var(--ink-soft);font-size:0.85rem;">Copy this flag and submit it via the 🚩 button above to unlock the next chapter.</p>
          </div>
        </div>
        """
        self.send_html(page_shell("Task Complete", body))


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"WEB-04 challenge server running on {HOST}:{PORT}")
    server.serve_forever()
