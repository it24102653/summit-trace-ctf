#!/usr/bin/env python3
"""
WEB-06 : "The Final Transmission"
Domain      : Digital Forensics (Task 1) / Networking (Task 2)
Difficulty  : Hard (capstone)

Pure Python standard-library implementation (no Flask, no pip installs).

Flow:
  1. Login gate: fixed credentials (revealed by Level 5's flag submission).
  2. Task 1 (Digital Forensics): a JPEG photo has a real ZIP archive
     appended after its EOF, containing a real pcap file. The player
     must recognise the file is carrying a second file (via `file`/
     `binwalk`), carve/extract it, and submit the extracted pcap's
     MD5 hash as proof of a correct extraction.
  3. Task 2 (Networking): the extracted pcap contains real DNS query
     packets - some are decoy/noise traffic, others carry fragments of
     a hidden code as subdomain labels under a shared suffix. Filtering
     by that suffix in Wireshark/tshark and reading the queries IN
     ORDER reconstructs the final code.
  4. No time limit - deduction-only scoring, same pattern as Levels 4-5.
     This is the FINAL stage - completing both tasks and submitting the
     flag closes out the whole campaign, no further credentials.
"""

import http.server
import socketserver
import uuid
import base64
import urllib.parse
import html
import json
from http import cookies

import sys
sys.path.insert(0, "/app")
from assets_data import BASECAMP_PHOTO_B64

HOST = "0.0.0.0"
PORT = 8000

# Entry credentials required to reach this level - revealed by Level 5's
# flag submission.
CHAIN_USERNAME = "musni_final"
CHAIN_PASSWORD = "SummitCode2026"

TASK1_ANSWER = "d18b7afa8ff80d3710fda236b7067ea3"  # MD5 of the extracted pcap
TASK2_ANSWER = "K2SUMMIT2026"

WRONG_PENALTY = 10
HINT1_COST = 10   # Task 1 (Forensics), each of its 2 hints
HINT2_COST = 15   # Task 2 (Networking), each of its 2 hints

FLAG = "CTF{c4rv3_th3n_sn1ff_th3_summit}"

HINTS = {
    "1a": ("Run `file basecamp_photo.jpg` - it will confirm it's a valid "
           "JPEG, but that doesn't mean that's ALL the file contains. "
           "Try `binwalk basecamp_photo.jpg` to scan for other file "
           "signatures hiding after the image data."),
    "1b": ("binwalk should show a Zip archive starting at some byte "
           "offset after the JPEG's own data ends. You can carve it out "
           "manually with:\n"
           "  tail -c +<offset+1> basecamp_photo.jpg > carved.zip\n"
           "(binwalk reports the offset in decimal - add 1 since `tail -c +N` "
           "is 1-indexed.) Then `unzip carved.zip` to get the pcap, and "
           "`md5sum` it for the answer."),
    "2a": ("Open the extracted pcap in Wireshark or `tshark -r "
           "final_transmission.pcap`. Not every packet matters - some are "
           "decoy/noise DNS traffic to unrelated domains. Look for queries "
           "that all share the same unusual domain suffix."),
    "2b": ("Filter with: tshark -r final_transmission.pcap -Y "
           "\"dns.qry.name contains \\\"telemetry\\\"\" -T fields -e dns.qry.name\n"
           "Read the matching queries in the order they appear (by packet "
           "number/timestamp) and take just the first label of each "
           "domain name. Concatenate them together to form the final code."),
}

SESSIONS = {}


def new_session():
    sid = uuid.uuid4().hex
    SESSIONS[sid] = {
        "logged_in": False,
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


def status_bar(sess):
    if not sess or not sess.get("logged_in"):
        return ""
    score = current_score(sess)
    flag_done = sess.get("flag_finalized")
    return f"""
    <div class="navbar">
      <div class="nav-left">
        <button class="icon-btn flag-btn" onclick="openFlagModal()" {'disabled' if flag_done else ''}>
          {'🏔️ Campaign Complete' if flag_done else '🚩 Submit Flag'}
        </button>
      </div>
      <span class="brand">🌄 The Final Transmission</span>
      <div class="actions">
        <span class="badge">Score: {score}</span>
      </div>
    </div>
    <div id="flagModal" class="modal" style="display:none;">
      <div class="modal-box">
        <h3>🚩 Submit Flag to Finish</h3>
        <p>Once you've found this level's flag, paste it below to complete
           the entire campaign.</p>
        <input type="text" id="flagInputBox" placeholder="CTF{{...}}" style="width:100%;padding:9px;border:1px solid #4a4470;border-radius:6px;margin:8px 0;background:#0d1128;color:#ffd166;">
        <button onclick="submitFlag()">Submit Flag</button>
        <p id="flagModalMsg" class="error"></p>
        <div id="nextLevelBox" style="display:none;background:#1a2540;border:1px solid #ffd166;border-radius:6px;padding:12px 14px;margin-top:10px;white-space:pre-line;font-size:0.9rem;color:#ffd166;"></div>
        <button onclick="document.getElementById('flagModal').style.display='none'" style="background:#4a4470;margin-top:8px;">Close</button>
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
              document.querySelectorAll('.flag-btn').forEach(b => {{ b.disabled = true; b.textContent = '🏔️ Campaign Complete'; }});
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
{body}
</body>
</html>"""


BASE_CSS = """
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: 'Segoe UI', Arial, sans-serif;
  background: #0d1128;
  color: #e8e4ff;
}
.navbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 28px;
  background: #151a3a;
  border-bottom: 3px solid #ffd166;
  flex-wrap: wrap;
  gap: 10px;
}
.navbar .nav-left { display: flex; align-items: center; }
.navbar .flag-btn {
  background: rgba(255,209,102,0.15);
  border: 1px solid #ffd166;
  color: #ffd166;
}
.navbar .flag-btn:hover { background: #ffd166; color: #0d1128; }
.navbar .flag-btn:disabled { opacity: 0.6; cursor: default; }
.navbar .brand { font-weight: 700; font-size: 1.2rem; color: #ffd166; }
.navbar .actions { display: flex; gap: 10px; align-items: center; }
.badge {
  background: #262c56;
  color: #ffd166;
  padding: 6px 14px;
  border-radius: 6px;
  font-weight: 700;
  font-size: 0.85rem;
  border: 1px solid #ffd166;
}
.login-wrap {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 90vh;
  padding: 20px;
}
.login-card {
  background: #151a3a;
  border: 1px solid #ffd166;
  border-radius: 12px;
  padding: 34px 38px;
  max-width: 400px;
  width: 100%;
  box-shadow: 0 6px 30px rgba(0,0,0,0.5);
}
.login-card h1, .login-card h2 { color: #ffd166; }
.story-note {
  background: #0d1128;
  border-left: 3px solid #ffd166;
  padding: 10px 14px;
  font-size: 0.82rem;
  color: #c9c3f0;
  margin: 14px 0 20px;
  border-radius: 4px;
  text-align: left;
}
.wrap { max-width: 820px; margin: 0 auto; padding: 30px 20px; }
.card {
  background: #151a3a;
  border-radius: 10px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.4);
  padding: 24px;
  margin-bottom: 20px;
  border-left: 5px solid #ffd166;
}
.card.done { border-left-color: #4fd18a; }
.task-title { display:flex; justify-content:space-between; align-items:center; flex-wrap: wrap; gap: 8px; }
.hint-icon-btn {
  background: #262c56;
  border: 1px solid #ffd166;
  color: #ffd166;
  padding: 5px 10px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.78rem;
}
.hint-icon-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.hint-text-box {
  background: #0d1128;
  border: 1px dashed #ffd166;
  padding: 12px 14px;
  border-radius: 6px;
  font-size: 0.85rem;
  margin-top: 10px;
  white-space: pre-wrap;
  color: #c9c3f0;
}
label { font-size: 0.8rem; color: #c9c3f0; display:block; margin-top: 12px; }
input[type=text] {
  width: 100%;
  padding: 9px 10px;
  border: 1px solid #ffd166;
  border-radius: 6px;
  margin-top: 4px;
  font-size: 0.95rem;
  background: #0d1128;
  color: #e8e4ff;
}
button, .btn {
  margin-top: 14px;
  background: #ffd166;
  color: #0d1128;
  border: none;
  padding: 10px;
  border-radius: 6px;
  cursor: pointer;
  width: 100%;
  font-size: 0.9rem;
  font-weight: 700;
}
button:hover { background: #e6b84f; }
.error { color: #ff6b6b; font-size: 0.85rem; margin-top: 8px; }
.success-text { color: #4fd18a; font-size: 0.85rem; margin-top: 8px; font-weight: 600; }
.download-link {
  display: inline-block;
  margin: 10px 0;
  background: #262c56;
  border: 1px solid #ffd166;
  color: #ffd166;
  padding: 8px 16px;
  border-radius: 6px;
  text-decoration: none;
  font-size: 0.85rem;
  font-weight: 600;
}
.download-link:hover { background: #ffd166; color: #0d1128; }
.modal {
  position: fixed; inset: 0; background: rgba(0,0,0,0.7);
  display: flex; align-items: center; justify-content: center;
}
.modal-box {
  background: #151a3a; padding: 26px 30px; border-radius: 10px;
  max-width: 460px; width: 90%; color: #e8e4ff; border: 1px solid #ffd166;
}
code { background: #0d1128; padding: 1px 5px; border-radius: 3px; color: #ffd166; }
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

        if path in ("/", "/login"):
            self.render_login()
            return
        if path == "/tasks":
            self.render_tasks()
            return
        if path == "/assets/basecamp_photo.jpg":
            self.serve_binary_asset()
            return
        if path.startswith("/hint"):
            hint_id = path.replace("/hint", "")
            if hint_id in HINTS:
                self.handle_hint(hint_id)
                return
        if path == "/completed":
            self.render_completed()
            return

        self.send_text("404 Not Found", status=404)

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path

        if path == "/login":
            self.handle_login()
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

    # ---------------- login ----------------
    def render_login(self, error=None):
        error_html = f'<p class="error">{html.escape(error)}</p>' if error else ""
        body = f"""
        <div class="login-wrap">
          <div class="login-card">
            <h2>🌄 Basecamp Radio Log — Sign In</h2>
            <div class="story-note">
              📖 <strong>Chapter 6 — The Final Transmission:</strong> This is
              the last system musni left behind before his final push to the
              summit. You'll need the credentials found at the end of
              Chapter 5 to sign in.
            </div>
            <form method="POST" action="/login">
              <label>Username</label>
              <input type="text" name="username" required>
              <label>Password</label>
              <input type="text" name="password" required>
              <button type="submit">Log In</button>
            </form>
            {error_html}
          </div>
        </div>
        """
        self.send_html(page_shell("Basecamp Radio Log", body))

    def handle_login(self):
        form = self.read_form()
        username = form.get("username", "").strip()
        password = form.get("password", "")

        if username != CHAIN_USERNAME or password != CHAIN_PASSWORD:
            self.render_login(error="Incorrect credentials. These must come from completing the previous chapter.")
            return

        sid = new_session()
        SESSIONS[sid]["logged_in"] = True

        self.redirect("/tasks", set_cookie=f"session_id={sid}; Path=/; HttpOnly")

    def serve_binary_asset(self):
        sid, sess = get_session(self)
        if not sess or not sess.get("logged_in"):
            self.redirect("/")
            return
        data = base64.b64decode(BASECAMP_PHOTO_B64)
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Disposition", 'attachment; filename="basecamp_photo.jpg"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ---------------- tasks ----------------
    def hint_box_html(self, sess, hint_id):
        used = sess.get(f"hint{hint_id}_used")
        text = HINTS[hint_id] if used else ""
        display = "block" if used else "none"
        return f'<div id="hint{hint_id}Box" class="hint-text-box" style="display:{display};">{html.escape(text)}</div>'

    def render_tasks(self, t1_error=None, t2_error=None):
        sid, sess = get_session(self)
        if not sess or not sess.get("logged_in"):
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
            <h3>Task 1: Recover the Hidden Data (Digital Forensics)</h3>
            <div>
              <button class="hint-icon-btn" id="hint1aBtn" onclick="getHint('1a')" {'disabled' if sess['hint1a_used'] else ''}>💡 Hint 1 (-{HINT1_COST})</button>
              <button class="hint-icon-btn" id="hint1bBtn" onclick="getHint('1b')" {'disabled' if sess['hint1b_used'] else ''}>💡 Hint 2 (-{HINT1_COST})</button>
            </div>
          </div>
          <p>A photo from musni's basecamp is below. It looks like an
             ordinary JPEG, but it's hiding a second file. Find it,
             extract it, and submit the MD5 hash of the extracted file.</p>
          <a class="download-link" href="/assets/basecamp_photo.jpg" download>⬇ Download basecamp_photo.jpg</a>
          {"<p class='success-text'>✅ Solved!</p>" if t1_done else f'''
          <form method="POST" action="/task1/submit">
            <label>MD5 hash of the extracted file</label>
            <input type="text" name="answer" placeholder="Enter the MD5 hash" required>
            <button type="submit">Submit</button>
          </form>
          {'<p class="error">' + html.escape(t1_error) + '</p>' if t1_error else ''}
          '''}
          {self.hint_box_html(sess, "1a")}
          {self.hint_box_html(sess, "1b")}
        </div>
        """

        task2_card = f"""
        <div class="card {'done' if t2_done else ''}">
          <div class="task-title">
            <h3>Task 2: Reconstruct the Signal (Networking)</h3>
            <div>
              <button class="hint-icon-btn" id="hint2aBtn" onclick="getHint('2a')" {'disabled' if sess['hint2a_used'] else ''}>💡 Hint 1 (-{HINT2_COST})</button>
              <button class="hint-icon-btn" id="hint2bBtn" onclick="getHint('2b')" {'disabled' if sess['hint2b_used'] else ''}>💡 Hint 2 (-{HINT2_COST})</button>
            </div>
          </div>
          <p>Analyse the pcap file you extracted in Task 1. Somewhere in
             the traffic, a hidden code is split across several DNS
             queries - mixed in with unrelated decoy traffic. Reconstruct
             the code and submit it below.</p>
          {"<p class='success-text'>✅ Solved!</p>" if t2_done else f'''
          <form method="POST" action="/task2/submit">
            <label>Reconstructed code</label>
            <input type="text" name="answer" placeholder="Enter the reconstructed code" required>
            <button type="submit">Submit</button>
          </form>
          {'<p class="error">' + html.escape(t2_error) + '</p>' if t2_error else ''}
          '''}
          {self.hint_box_html(sess, "2a")}
          {self.hint_box_html(sess, "2b")}
        </div>
        """

        if t1_done and t2_done:
            sess["completed"] = True
            self.redirect("/completed")
            return

        bar = status_bar(sess)

        body = f"""
        {bar}
        <div class="wrap">
          <h2 style="color:#ffd166;">📋 Task Panel</h2>
          {task1_card}
          {task2_card}
        </div>
        <script>
          const hintCosts = {{"1a": {HINT1_COST}, "1b": {HINT1_COST}, "2a": {HINT2_COST}, "2b": {HINT2_COST}}};
          function getHint(id) {{
            if (!confirm('Use this hint? It will cost ' + hintCosts[id] + ' marks.')) return;
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
        if not sess or not sess.get("logged_in"):
            self.redirect("/")
            return
        if sess.get("completed"):
            self.redirect("/completed")
            return

        form = self.read_form()
        guess = form.get("answer", "").strip().lower()

        if guess == TASK1_ANSWER:
            sess["task1_done"] = True
            self.render_tasks()
        else:
            sess["wrong1"] += 1
            self.render_tasks(t1_error="Incorrect hash. Make sure you extracted the exact right file.")

    def handle_task2_submit(self):
        sid, sess = get_session(self)
        if not sess or not sess.get("logged_in"):
            self.redirect("/")
            return
        if sess.get("completed"):
            self.redirect("/completed")
            return

        form = self.read_form()
        guess = form.get("answer", "").strip()

        if guess.upper().replace("-", "").replace(" ", "") == TASK2_ANSWER:
            sess["task2_done"] = True
            self.render_tasks()
        else:
            sess["wrong2"] += 1
            self.render_tasks(t2_error="Incorrect code. Check the packet order and which queries actually belong to the hidden message.")

    def handle_hint(self, hint_id):
        sid, sess = get_session(self)
        if not sess:
            self.send_text(json.dumps({"error": "no session"}), content_type="application/json")
            return
        cost = HINT1_COST if hint_id.startswith("1") else HINT2_COST
        sess[f"hint{hint_id}_used"] = True
        self.send_text(json.dumps({"hint": HINTS[hint_id], "score": current_score(sess)}), content_type="application/json")

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
                "🏔️ CAMPAIGN COMPLETE!\n\n"
                "musni reached the summit. His final transmission confirms "
                "he made it safely - the whole trail, from an exposed "
                "laptop terminal to a radio signal on the mountaintop, has "
                "been followed end to end.\n\n"
                "There is no next level. Thanks for playing through the "
                "entire journey!"
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
        <div class="login-wrap">
          <div class="login-card" style="text-align:center;">
            <h2>✅ Both Tasks Complete</h2>
            <p>The hidden pcap was recovered and the signal reconstructed.</p>
            <p style="font-size:1.1rem;"><strong>Flag:</strong> {FLAG}</p>
            <p style="font-size:1.3rem;"><strong>Final Score: {score} / 100</strong></p>
            <p style="color:#c9c3f0;font-size:0.85rem;">Copy this flag and submit it via the 🚩 button above to complete the full campaign.</p>
          </div>
        </div>
        """
        self.send_html(page_shell("Task Complete", body))


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"WEB-06 challenge server running on {HOST}:{PORT}")
    server.serve_forever()
