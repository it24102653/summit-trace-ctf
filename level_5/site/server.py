#!/usr/bin/env python3
"""
WEB-05 : "The Locked Radio"
Domain      : Reverse Engineering
Difficulty  : Moderate

Pure Python standard-library implementation (no Flask, no pip installs).

Scenario:
  musni's basecamp radio relay has gone dark. The only way to reach him
  is through a modified handheld unit he rigged himself - a compiled
  program called radio_lock guards the 8-character access code needed
  to re-open the channel, and it won't just hand it over to anyone who
  asks nicely.

Flow:
  1. Entry gate: 7-digit PIN (revealed by Level 4's flag submission).
  2. Reverse Engineering task: download a real compiled ELF binary
     (radio_lock). It XORs the player's input against a fixed key and
     compares it to a hardcoded encoded byte array - not a plain
     strcmp() - so `strings` alone won't reveal the access code. The
     player must dump the .rodata section (e.g. `objdump -s -j .rodata`)
     and manually XOR-decode it using the key revealed in Hint 2.
  3. No time limit - deduction-only scoring: start at 100, -14 per
     wrong answer, hints cost marks individually and are one-time use.
     Since this level now carries a single task end-to-end, wrong-answer
     and hint penalties are double what earlier levels charged. Once
     solved, the final score is locked and the flag is shown;
     submitting that flag via the top-left Submit Flag box reveals
     Level 6's credentials.
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
from assets_data import RADIO_LOCK_BIN_B64

HOST = "0.0.0.0"
PORT = 8000

# Entry PIN required to reach this level - revealed by Level 4's flag
# submission.
CHAIN_PIN = "5923187"

TASK_ANSWER = "TRAILEND"

# This level carries a single task end-to-end, so penalties are double
# what a per-task share would otherwise be in a multi-task level.
WRONG_PENALTY = 14
HINT_COST = 24   # each of the 2 hints for the Reverse Engineering task

FLAG = "CTF{perm5_l34k_th3n_x0r_cr4ck}"

# Hint text is centralized here so render_tasks() can re-display an
# already-used hint's content after a page reload (e.g. a wrong task
# submission), instead of it only living in transient front-end JS state.
HINT_TEXTS = {
    "2a": ("Download radio_lock and run `strings radio_lock` - notice "
           "the access code is NOT sitting there in plain text like a "
           "simple crackme would have it. The comparison logic does "
           "something to your input before checking it."),
    "2b": ("The program XORs your input against a fixed key byte "
           "before comparing it to a hardcoded array. Dump the "
           "encoded bytes with:\n"
           "  objdump -s -j .rodata radio_lock\n"
           "The XOR key used in this program is 0x5A. Once you have "
           "the encoded bytes, XOR each one with 0x5A to recover the "
           "8-character plaintext code (e.g. in Python: "
           "chr(byte ^ 0x5A) for each byte)."),
}

# Credentials revealed to the player upon submitting THIS level's flag,
# needed for Level 6.
NEXT_LEVEL_USERNAME = "musni_final"
NEXT_LEVEL_PASSWORD = "SummitCode2026"

SESSIONS = {}


def new_session():
    sid = uuid.uuid4().hex
    SESSIONS[sid] = {
        "pin_verified": False,
        "task2_done": False,
        "wrong2": 0,
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
    score -= sess["wrong2"] * WRONG_PENALTY
    if sess["hint2a_used"]:
        score -= HINT_COST
    if sess["hint2b_used"]:
        score -= HINT_COST
    return max(0, score)


def normalize(text):
    return re.sub(r"\s+", " ", text.strip().lower())


def status_bar(sess, extra_buttons=""):
    if not sess or not sess.get("pin_verified"):
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
      <span class="brand">📻 The Locked Radio</span>
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
  flex-wrap: wrap;
  gap: 10px;
}
.navbar .nav-left { display: flex; align-items: center; }
.navbar .flag-btn {
  background: transparent;
  border: 1px solid var(--brown);
  color: var(--brown-dark);
  font-weight: 600;
}
.navbar .flag-btn:hover { background: var(--brown); color: #fff8ec; }
.navbar .flag-btn:disabled { opacity: 0.6; cursor: default; }
.navbar .brand { font-family: 'Fraunces', serif; font-style: italic; font-weight: 500; font-size: 1.15rem; color: var(--brown-dark); }
.navbar .actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
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
  text-align: center;
}
.pin-card {
  background: var(--paper-card);
  border: 1px solid var(--line);
  border-top: 4px solid var(--brown);
  border-radius: 4px;
  padding: 34px 38px;
  max-width: 380px;
  width: 100%;
  box-shadow: 0 12px 34px rgba(90,74,53,0.12);
}
.pin-card h1 { color: var(--ink); font-size: 1.3rem; }
.story-note {
  background: rgba(92,122,77,0.08);
  border-left: 3px solid var(--green);
  padding: 10px 14px;
  font-size: 0.82rem;
  color: var(--ink-soft);
  margin: 14px 0 20px;
  border-radius: 3px;
  text-align: left;
}
.wrap { max-width: 800px; margin: 0 auto; padding: 30px 20px; }
.card {
  background: var(--paper-card);
  border: 1px solid var(--line);
  border-radius: 4px;
  box-shadow: 0 8px 24px rgba(90,74,53,0.08);
  padding: 24px;
  margin-bottom: 20px;
  border-left: 5px solid var(--brown);
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
label { font-size: 0.8rem; color: var(--ink-soft); display:block; margin-top: 12px; font-weight: 600; }
input[type=text] {
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
.error { color: var(--red); font-size: 0.85rem; margin-top: 8px; }
.success-text { color: var(--green-dark); font-size: 0.85rem; margin-top: 8px; font-weight: 600; }
.download-link {
  display: inline-block;
  margin: 10px 0;
  background: transparent;
  border: 1px solid var(--brown);
  color: var(--brown-dark);
  padding: 8px 16px;
  border-radius: 4px;
  text-decoration: none;
  font-size: 0.85rem;
  font-weight: 600;
}
.download-link:hover { background: var(--brown); color: #fff8ec; }
.modal {
  position: fixed; inset: 0; background: rgba(58,47,34,0.45);
  display: flex; align-items: center; justify-content: center;
}
.modal-box {
  background: var(--paper-card); border: 1px solid var(--line); padding: 26px 30px; border-radius: 4px;
  max-width: 460px; width: 90%; color: var(--ink);
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

        if path == "/":
            self.render_landing()
            return
        if path == "/tasks":
            self.render_tasks()
            return
        if path == "/assets/radio_lock":
            self.serve_binary_asset(RADIO_LOCK_BIN_B64, "radio_lock", "application/octet-stream")
            return
        if path == "/hint2a":
            self.handle_hint("hint2a_used", HINT_COST, HINT_TEXTS["2a"])
            return
        if path == "/hint2b":
            self.handle_hint("hint2b_used", HINT_COST, HINT_TEXTS["2b"])
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
        if path == "/task2/submit":
            self.handle_task2_submit()
            return
        if path == "/submit-flag":
            self.handle_submit_flag()
            return

        self.send_text("404 Not Found", status=404)

    # ---------------- PIN gate ----------------
    def render_landing(self, error=None):
        sid, sess = get_session(self)

        if not sess or not sess.get("pin_verified"):
            error_html = f'<p class="error">{html.escape(error)}</p>' if error else ""
            body = f"""
            <div class="landing">
              <div class="pin-card">
                <h1>📻 The Locked Radio</h1>
                <p class="story-note">
                  📖 <strong>Chapter 5 — Reaching Basecamp:</strong> musni's
                  basecamp radio relay has gone dark. The only way to reach
                  him is through a modified handheld unit he rigged himself
                  - locked behind a 7-digit PIN revealed at the end of
                  Chapter 4.
                </p>
                <form method="POST" action="/verify-pin">
                  <label>Enter 7-digit PIN</label>
                  <input type="text" name="pin" maxlength="7" pattern="[0-9]{{7}}"
                         style="text-align:center;font-size:1.2rem;letter-spacing:4px;" required>
                  <button type="submit">Unlock Radio</button>
                </form>
                {error_html}
              </div>
            </div>
            """
            self.send_html(page_shell("The Locked Radio", body))
            return

        self.redirect("/tasks")

    def handle_verify_pin(self):
        sid, sess, set_cookie = get_or_create_session(self)
        form = self.read_form()
        pin = form.get("pin", "").strip()

        if pin == CHAIN_PIN:
            sess["pin_verified"] = True
            self.redirect("/tasks", set_cookie=set_cookie)
            return

        error_html = '<p class="error">Incorrect PIN. This must come from completing Chapter 4.</p>'
        body = f"""
        <div class="landing">
          <div class="pin-card">
            <h1>📻 The Locked Radio</h1>
            <p class="story-note">
              📖 <strong>Chapter 5 — Reaching Basecamp:</strong> musni's
              basecamp radio relay has gone dark. The only way to reach
              him is through a modified handheld unit he rigged himself
              - locked behind a 7-digit PIN revealed at the end of
              Chapter 4.
            </p>
            <form method="POST" action="/verify-pin">
              <label>Enter 7-digit PIN</label>
              <input type="text" name="pin" maxlength="7" pattern="[0-9]{{7}}"
                     style="text-align:center;font-size:1.2rem;letter-spacing:4px;" required>
              <button type="submit">Unlock Radio</button>
            </form>
            {error_html}
          </div>
        </div>
        """
        self.send_html(page_shell("The Locked Radio", body), set_cookie=set_cookie)

    def serve_binary_asset(self, b64_data, filename, content_type):
        sid, sess = get_session(self)
        if not sess or not sess.get("pin_verified"):
            self.redirect("/")
            return
        data = base64.b64decode(b64_data)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ---------------- tasks ----------------
    def render_tasks(self, t2_error=None):
        sid, sess = get_session(self)
        if not sess or not sess.get("pin_verified"):
            self.redirect("/")
            return
        if sess.get("completed"):
            self.redirect("/completed")
            return

        t2_done = sess["task2_done"]

        task_card = f"""
        <div class="card {'done' if t2_done else ''}">
          <div class="task-title">
            <h3>Reverse Engineer the Radio Lock</h3>
            <div>
              <button class="hint-icon-btn" id="hint2aBtn" onclick="askHint('2a', {HINT_COST})" {'disabled' if sess['hint2a_used'] else ''}>💡 Hint 1 (-{HINT_COST})</button>
              <button class="hint-icon-btn" id="hint2bBtn" onclick="askHint('2b', {HINT_COST})" {'disabled' if sess['hint2b_used'] else ''}>💡 Hint 2 (-{HINT_COST})</button>
            </div>
          </div>
          <p>musni's handheld radio unit is guarded by a compiled program
             called <code>radio_lock</code>. It checks an 8-character
             access code, but not with a plain string comparison - you'll
             need to reverse engineer the actual logic to recover the
             code before the relay window closes.</p>
          <a class="download-link" href="/assets/radio_lock" download>⬇ Download radio_lock</a>
          {"<p class='success-text'>✅ Solved!</p>" if t2_done else f'''
          <form method="POST" action="/task2/submit">
            <label>Access code (8 characters)</label>
            <input type="text" name="answer" maxlength="8" placeholder="Enter the 8-character code" required>
            <button type="submit">Submit</button>
          </form>
          {'<p class="error">' + html.escape(t2_error) + '</p>' if t2_error else ''}
          '''}
          <div id="hint2aBox" class="hint-text-box" style="display:{'block' if sess['hint2a_used'] else 'none'};">{html.escape(HINT_TEXTS['2a']) if sess['hint2a_used'] else ''}</div>
          <div id="hint2bBox" class="hint-text-box" style="display:{'block' if sess['hint2b_used'] else 'none'};">{html.escape(HINT_TEXTS['2b']) if sess['hint2b_used'] else ''}</div>
        </div>
        """

        if t2_done:
            sess["completed"] = True
            self.redirect("/completed")
            return

        bar = status_bar(sess)

        body = f"""
        {bar}
        <div class="wrap">
          <h2>📋 Task Panel</h2>
          {task_card}
        </div>

        <div id="hintConfirmModal" class="modal" style="display:none;">
          <div class="modal-box">
            <h3>💡 Use This Hint?</h3>
            <p id="hintConfirmText"></p>
            <button onclick="confirmHint()">Yes, show me the hint</button>
            <button onclick="cancelHint()" style="background:var(--ink-soft);margin-top:8px;">Cancel</button>
          </div>
        </div>

        <script>
          let pendingHintId = null;
          function askHint(id, cost) {{
            pendingHintId = id;
            document.getElementById('hintConfirmText').textContent =
              'This hint costs -' + cost + ' marks and can only be used once. Are you sure you want to view it?';
            document.getElementById('hintConfirmModal').style.display = 'flex';
          }}
          function cancelHint() {{
            document.getElementById('hintConfirmModal').style.display = 'none';
            pendingHintId = null;
          }}
          function confirmHint() {{
            const id = pendingHintId;
            document.getElementById('hintConfirmModal').style.display = 'none';
            if (!id) return;
            fetch('/hint' + id).then(r => r.json()).then(data => {{
              if (data.error) return;
              document.querySelector('.badge').textContent = 'Score: ' + data.score;
              const box = document.getElementById('hint' + id + 'Box');
              box.textContent = data.hint;
              box.style.display = 'block';
              document.getElementById('hint' + id + 'Btn').disabled = true;
              pendingHintId = null;
            }});
          }}
        </script>
        """
        self.send_html(page_shell("Task Panel", body))

    def handle_task2_submit(self):
        sid, sess = get_session(self)
        if not sess or not sess.get("pin_verified"):
            self.redirect("/")
            return
        if sess.get("completed"):
            self.redirect("/completed")
            return

        form = self.read_form()
        guess = form.get("answer", "").strip()

        if guess.upper() == TASK_ANSWER:
            sess["task2_done"] = True
            self.render_tasks()
        else:
            sess["wrong2"] += 1
            self.render_tasks(t2_error="Incorrect code. Make sure you're XOR-decoding the right bytes with the right key.")

    def handle_hint(self, flag_name, cost, hint_text):
        sid, sess = get_session(self)
        if not sess:
            self.send_text(json.dumps({"error": "no session"}), content_type="application/json")
            return
        sess[flag_name] = True
        self.send_text(json.dumps({"hint": hint_text, "score": current_score(sess)}), content_type="application/json")

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
                "🎉 Congratulations! Chapter 5 complete.\n\n"
                "musni's final ascent needs one last login:\n\n"
                f"Username: {NEXT_LEVEL_USERNAME}\n"
                f"Password: {NEXT_LEVEL_PASSWORD}\n\n"
                "Head to Level 6 and log in with these credentials."
            )
            self.send_text(json.dumps({"correct": True, "message": message}), content_type="application/json")
        else:
            self.send_text(json.dumps({"correct": False}), content_type="application/json")

    # ---------------- completion ----------------
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
          <div class="pin-card" style="text-align:center;">
            <h2 style="color:var(--ink);">✅ Radio Unlocked</h2>
            <p>The access code checked out — the relay channel is open again.</p>
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
    print(f"WEB-05 challenge server running on {HOST}:{PORT}")
    server.serve_forever()
