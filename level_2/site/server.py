#!/usr/bin/env python3
"""
WEB-02 : "The Hidden Admin Panel"
Domain      : Web Security (Broken Access Control) / OSINT-Recon overlap
Difficulty  : Easy-Moderate

Pure Python standard-library implementation (no Flask, no pip installs)
so the container never needs to reach PyPI at build time.

Flow:
  1. Player logs in with ANY username + password >=8 chars (fake "normal"
     login - not the real target).
  2. Blog page loads with a countdown timer + colourful sample posts.
  3. robots.txt discloses TWO disallowed paths:
       - /admindetails    -> an accidentally-exposed page leaking the
                              real admin username + password
       - /admindashboard  -> the actual admin login (and, once logged
                              in, the admin dashboard - same URL)
  4. Player visits /admindetails to learn the real admin credentials.
  5. Player logs in at /admindashboard with those credentials. Normal
     user credentials do NOT work there.
  6. From the dashboard, the player deletes the admin account "musni",
     which ends the challenge, shows the flag + final score, and locks
     the session from further action.

Scoring:
  - Start at 100.
  - -1 mark for every 4 seconds elapsed since normal login.
  - Hint costs 25 marks flat (also described to the player as "~1 minute lost").
  - Score floors at 0, never negative.

The countdown timer + live score bar renders on every page once a
session exists (not just the blog page).
"""

import http.server
import socketserver
import uuid
import time
import urllib.parse
import html
import json
from http import cookies

HOST = "0.0.0.0"
PORT = 8000

# Entry credentials required to reach this level - revealed by Level 1's
# flag submission. NOT the same as the in-challenge admin account below.
CHAIN_USERNAME = "musni_trail"
CHAIN_PASSWORD = "Basecamp2026"

# Credentials revealed to the player upon submitting THIS level's flag,
# needed to log into Level 3.
NEXT_LEVEL_EMAIL = "musni.trail@gmail.com"
NEXT_LEVEL_PASSWORD = "SummitGear2026"

ADMIN_USERNAME = "musni"
ADMIN_PASSWORD = "password123"

FLAG = "CTF{r0b0ts_txt_l3aks_th3_p4nel}"

TOTAL_TIME_BUDGET = 400   # seconds, purely for the displayed countdown
SECONDS_PER_MARK = 4
HINT_PENALTY = 25

SESSIONS = {}

BLOG_POSTS = [
    {
        "id": 1,
        "title": "Delightful Mornings: A Guide to Better Coffee",
        "color": "#c9713f",
        "body": "There's nothing quite like a well-brewed cup of coffee to "
                "start the day. In this post we explore grind size, water "
                "temperature, and why timing your pour matters more than "
                "you'd think.",
    },
    {
        "id": 2,
        "title": "Five Minimalist Habits That Actually Stick",
        "color": "#6f9c94",
        "body": "Minimalism isn't about owning nothing - it's about "
                "owning what matters. Here are five small habit changes "
                "that made a real difference in a cluttered daily routine.",
    },
    {
        "id": 3,
        "title": "The Quiet Return of Film Photography",
        "color": "#b5573f",
        "body": "Digital convenience won the war, but film never really "
                "left. A look at why a new generation is rediscovering "
                "the slow, deliberate process of shooting on film.",
    },
    {
        "id": 4,
        "title": "Weekend Trail Notes: Hiking Without a Plan",
        "color": "#7a9b6e",
        "body": "Sometimes the best hikes are the ones with no fixed "
                "route. Notes from a weekend spent following whatever "
                "trail looked interesting.",
    },
]

next_post_id = 5


def new_session():
    sid = uuid.uuid4().hex
    SESSIONS[sid] = {
        "logged_in": False,
        "username": None,
        "login_time": None,
        "hint_used": False,
        "admin_logged_in": False,
        "completed": False,
        "flag_finalized": False,
    }
    return sid


def get_session(handler):
    if "Cookie" in handler.headers:
        c = cookies.SimpleCookie()
        c.load(handler.headers["Cookie"])
        if "session_id" in c:
            sid = c["session_id"].value
            if sid in SESSIONS:
                return sid, SESSIONS[sid]
    return None, None


def elapsed_seconds(sess):
    if not sess or not sess.get("login_time"):
        return 0
    return int(time.time() - sess["login_time"])


def current_score(sess):
    e = elapsed_seconds(sess)
    score = 100 - (e // SECONDS_PER_MARK)
    if sess.get("hint_used"):
        score -= HINT_PENALTY
    return max(0, score)


def status_bar(sess, extra_buttons=""):
    """Reusable top status bar with live timer + score, rendered on
       EVERY page once a session with an active login_time exists."""
    if not sess or not sess.get("login_time"):
        return ""
    remaining = max(0, TOTAL_TIME_BUDGET - elapsed_seconds(sess))
    score = current_score(sess)
    flag_done = sess.get("flag_finalized")
    stopped = sess.get("completed") or flag_done
    return f"""
    <div class="navbar">
      <div class="nav-left">
        <button class="icon-btn flag-btn" onclick="openFlagModal()" {'disabled' if flag_done else ''}>
          {'🎉 Chapter Complete' if flag_done else '🚩 Submit Flag'}
        </button>
      </div>
      <span class="brand">📰 DailyByte Blog</span>
      <div class="actions">
        <span class="timer" id="timer">⏱ --:--</span>
        <span class="timer" id="scoreBox">Score: {score}</span>
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
        <button onclick="closeFlagModal()" style="background:var(--ink-soft);margin-top:8px;">Close</button>
      </div>
    </div>

    <script>
      function openFlagModal() {{ document.getElementById('flagModal').style.display='flex'; }}
      function closeFlagModal() {{ document.getElementById('flagModal').style.display='none'; }}
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
    <script>
      let remaining = {remaining};
      let timedOut = {str(stopped).lower()};
      function tick() {{
        if (timedOut) return;
        if (remaining > 0) remaining--;
        const m = Math.floor(remaining/60).toString().padStart(2,'0');
        const s = (remaining%60).toString().padStart(2,'0');
        const t = document.getElementById('timer');
        if (t) t.textContent = '⏱ ' + m + ':' + s;
        if (remaining <= 0 && !timedOut) {{
          timedOut = true;
          window.location = '/timeout';
        }}
      }}
      if (!timedOut) {{
        tick();
        setInterval(tick, 1000);
      }}
    </script>
    """


def page_shell(title, body, extra_head=""):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{html.escape(title)}</title>
<style>{BASE_CSS}</style>
{extra_head}
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
  --red-dark: #8f3423;
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
h2, h3 { font-family: 'Fraunces', serif; font-weight: 600; }
.navbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 28px;
  background: var(--paper-card);
  color: var(--ink);
  border-bottom: 1px solid var(--line);
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
.navbar .brand { font-family: 'Fraunces', serif; font-style: italic; font-weight: 500; font-size: 1.15rem; letter-spacing: 0.3px; color: var(--brown-dark); }
.navbar .actions { display: flex; gap: 14px; align-items: center; }
.navbar .icon-btn {
  background: transparent;
  border: 1px solid var(--brown);
  color: var(--brown-dark);
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
  text-decoration: none;
  font-family: 'Public Sans', sans-serif;
}
.navbar .icon-btn:hover { background: var(--brown); color: #fff8ec; }
.timer {
  font-weight: 600;
  font-family: 'IBM Plex Mono', monospace;
  background: rgba(92,122,77,0.08);
  color: var(--green-dark);
  border: 1px solid var(--green);
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 0.85rem;
}
.wrap { max-width: 900px; margin: 30px auto; padding: 0 20px; }
.card {
  background: var(--paper-card);
  border: 1px solid var(--line);
  border-radius: 4px;
  box-shadow: 0 8px 24px rgba(90,74,53,0.08);
  padding: 24px;
  margin-bottom: 20px;
}
.login-wrap {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 80vh;
}
.login-card {
  background: var(--paper-card);
  border: 1px solid var(--line);
  padding: 34px 38px;
  border-radius: 4px;
  box-shadow: 0 12px 34px rgba(90,74,53,0.12);
  width: 100%;
  max-width: 380px;
}
.login-card h2 { margin-top: 0; }
.hint-sample {
  background: rgba(92,122,77,0.08);
  border-left: 3px solid var(--green);
  padding: 10px 14px;
  font-size: 0.85rem;
  border-radius: 3px;
  margin-bottom: 18px;
  color: var(--ink-soft);
}
.leak-box {
  background: rgba(138,90,52,0.08);
  border: 1px dashed var(--brown);
  padding: 16px 18px;
  border-radius: 4px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.95rem;
  color: var(--brown-dark);
}
label { font-size: 0.8rem; color: var(--ink-soft); display:block; margin-top: 12px; font-weight: 600; }
input[type=text], input[type=password], textarea {
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
  margin-top: 18px;
  background: var(--brown);
  color: #fff8ec;
  border: none;
  padding: 11px;
  border-radius: 4px;
  cursor: pointer;
  width: 100%;
  font-size: 0.95rem;
  font-family: 'Public Sans', sans-serif;
  font-weight: 600;
}
button:hover, .btn:hover { background: var(--brown-dark); }
.error { color: var(--red); font-size: 0.85rem; margin-top: 10px; }
.blog-post {
  border-left: 6px solid var(--line);
  padding: 14px 18px;
  margin-bottom: 14px;
  border-radius: 4px;
  background: var(--paper-card);
  border-top: 1px solid var(--line);
  border-right: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
}
.blog-post h3 { margin: 0 0 6px; }
.admin-post-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--line);
  padding: 10px 0;
}
.admin-post-row form { display: inline; margin: 0; width: auto; }
.admin-post-row button {
  width: auto;
  padding: 6px 12px;
  margin: 0 0 0 6px;
  font-size: 0.8rem;
}
.danger { background: var(--red); }
.danger:hover { background: var(--red-dark); }
.modal {
  position: fixed; inset: 0; background: rgba(58,47,34,0.45);
  display: flex; align-items: center; justify-content: center;
}
.modal-box {
  background: var(--paper-card); border: 1px solid var(--line); padding: 26px 30px; border-radius: 4px;
  max-width: 420px; width: 90%;
}
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

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path

        if path == "/robots.txt":
            self.send_text(
                "User-agent: *\n"
                "Disallow: /admindetails\n"
                "Disallow: /admindashboard\n"
            )
            return
        if path == "/" or path == "/login":
            self.render_login()
            return
        if path == "/blog":
            self.render_blog()
            return
        if path == "/hint":
            self.handle_hint()
            return
        if path == "/logout":
            sid, sess = get_session(self)
            if sess:
                sess["logged_in"] = False
            self.redirect("/login")
            return
        if path == "/admindetails":
            self.render_admindetails()
            return
        if path == "/admindashboard":
            self.render_admindashboard()
            return
        if path == "/completed":
            self.render_completed()
            return
        if path == "/timeout":
            self.render_timeout()
            return

        self.send_text("404 Not Found", status=404)

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path

        if path == "/login":
            self.handle_login()
            return
        if path == "/admindashboard":
            self.handle_admindashboard_login()
            return
        if path == "/admin/add-post":
            self.handle_add_post()
            return
        if path == "/admin/delete-post":
            self.handle_delete_post()
            return
        if path == "/admin/delete-admin":
            self.handle_delete_admin()
            return
        if path == "/submit-flag":
            self.handle_submit_flag()
            return

        self.send_text("404 Not Found", status=404)

    # ---------- normal login ----------
    def render_login(self, error=None):
        error_html = f'<p class="error">{html.escape(error)}</p>' if error else ""
        body = f"""
        <div class="login-wrap">
          <div class="login-card">
            <h2>📰 DailyByte Blog — Sign In</h2>
            <div class="hint-sample">
              📖 <strong>Chapter 2 — The Trail Continues:</strong> This is
              musni's travel blog. You'll need the credentials found at the
              end of Chapter 1 to sign in.
            </div>
            <form method="POST" action="/login">
              <label>Username</label>
              <input type="text" name="username" required>
              <label>Password</label>
              <input type="password" name="password" required>
              <button type="submit">Log In</button>
            </form>
            {error_html}
          </div>
        </div>
        """
        self.send_html(page_shell("DailyByte Blog - Sign In", body))

    def handle_login(self):
        form = self.read_form()
        username = form.get("username", "").strip()
        password = form.get("password", "")

        if username != CHAIN_USERNAME or password != CHAIN_PASSWORD:
            self.render_login(error="Incorrect credentials. These must come from completing the previous chapter.")
            return

        sid = new_session()
        SESSIONS[sid]["logged_in"] = True
        SESSIONS[sid]["username"] = username
        SESSIONS[sid]["login_time"] = time.time()

        self.redirect("/blog", set_cookie=f"session_id={sid}; Path=/; HttpOnly")

    # ---------- blog ----------
    def render_blog(self):
        sid, sess = get_session(self)
        if not sess or not sess["logged_in"]:
            self.redirect("/login")
            return
        if not sess.get("completed") and elapsed_seconds(sess) >= TOTAL_TIME_BUDGET:
            self.redirect("/timeout")
            return

        posts_html = "".join(
            f"""<div class="blog-post" style="border-left-color:{p['color']}">
                  <h3>{html.escape(p['title'])}</h3>
                  <p>{html.escape(p['body'])}</p>
                </div>"""
            for p in BLOG_POSTS
        )

        buttons = """
          <button class="icon-btn" id="hintIconBtn" onclick="getHint()" title="Hint (-25 marks)">💡 Hint</button>
          <button class="icon-btn" onclick="showReadme()" title="README">📄 README</button>
          <a class="icon-btn" href="/logout">🚪 Logout</a>
        """
        bar = status_bar(sess, buttons)

        body = f"""
        {bar}
        <div class="wrap">
          <div class="card">
            <h2>Welcome, {html.escape(sess['username'])} 👋</h2>
            <p>You're logged in as a normal reader. Browse the posts below.</p>
          </div>
          {posts_html}
        </div>

        <div id="hintModal" class="modal" style="display:none;">
          <div class="modal-box">
            <h3>💡 Hint</h3>
            <p id="hintTextBox">Are you sure? This costs 25 marks (~1 minute).</p>
            <button id="confirmHintBtn" onclick="confirmHint()">Yes, show me anyway</button>
            <button id="hintCancelBtn" onclick="closeModal('hintModal')" style="background:var(--ink-soft);margin-top:8px;">Cancel</button>
          </div>
        </div>

        <div id="readmeModal" class="modal" style="display:none;">
          <div class="modal-box">
            <h3>📄 README — WEB-02: The Hidden Admin Panel</h3>
            <p><strong>Domain:</strong> Web Security (Broken Access Control) / OSINT-Recon</p>
            <p><strong>Task:</strong> Somewhere, an administrator account exists.
               Find a way to reach the admin panel and remove that admin account.</p>
            <p><strong>Scoring:</strong> Start at 100. -1 mark per 4 seconds elapsed.
               Hint costs 25 marks.</p>
            <p><strong>Flag format:</strong> CTF{{...}}</p>
            <button onclick="closeModal('readmeModal')">Close</button>
          </div>
        </div>

        <script>
          let hintUsed = false;
          function showReadme() {{ document.getElementById('readmeModal').style.display='flex'; }}
          function closeModal(id) {{ document.getElementById(id).style.display='none'; }}
          function getHint() {{
            if (hintUsed) return; // hint already used - button is a no-op now
            document.getElementById('hintModal').style.display='flex';
          }}
          function confirmHint() {{
            if (hintUsed) return; // guard against double-fire
            fetch('/hint').then(r => r.json()).then(data => {{
              hintUsed = true;
              document.getElementById('hintTextBox').textContent = data.hint;
              document.getElementById('scoreBox').textContent = 'Score: ' + data.score;
              remaining = Math.max(0, remaining - 60); // only ever applied once now
              const confirmBtn = document.getElementById('confirmHintBtn');
              confirmBtn.textContent = 'Hint revealed above ✓';
              confirmBtn.disabled = true;
              const cancelBtn = document.getElementById('hintCancelBtn');
              if (cancelBtn) cancelBtn.textContent = 'Close';
              const btn = document.getElementById('hintIconBtn');
              btn.disabled = true;
              btn.style.opacity = '0.4';
              btn.title = 'Hint already used';
            }});
          }}
        </script>
        """
        self.send_html(page_shell("DailyByte Blog", body))

    def handle_hint(self):
        sid, sess = get_session(self)
        if not sess:
            self.send_text(json.dumps({"error": "no session"}), content_type="application/json")
            return
        sess["hint_used"] = True
        hint_text = ("Ever checked a site's robots.txt file? Some site owners "
                     "accidentally tell search engines - and you - exactly "
                     "which paths they don't want found. There's more than "
                     "one entry in there. Try /robots.txt.")
        self.send_text(
            json.dumps({"hint": hint_text, "score": current_score(sess)}),
            content_type="application/json",
        )

    # ---------- leaked credentials page ----------
    def render_admindetails(self):
        sid, sess = get_session(self)
        bar = status_bar(sess)
        body = f"""
        {bar}
        <div class="wrap">
          <div class="card">
            <h2>⚠ Internal Notes (should not be public)</h2>
            <div class="leak-box">
              # TODO: remove before deploy!!<br>
              admin_username = "{ADMIN_USERNAME}"<br>
              admin_password = "{ADMIN_PASSWORD}"<br>
              admin_login_url = "/admindashboard"
            </div>
            <p style="color:var(--ink-soft);font-size:0.85rem;margin-top:14px;">
              This page was left publicly accessible by mistake - a classic
              example of relying on an unlisted URL instead of real access
              control.
            </p>
          </div>
        </div>
        """
        self.send_html(page_shell("Internal Notes", body))

    # ---------- combined admin login + dashboard ----------
    def render_admindashboard(self, error=None):
        sid, sess = get_session(self)

        if sess and sess.get("completed"):
            self.redirect("/timeout" if sess.get("timed_out") else "/completed")
            return
        if sess and not sess.get("completed") and elapsed_seconds(sess) >= TOTAL_TIME_BUDGET:
            self.redirect("/timeout")
            return

        if sess and sess.get("admin_logged_in"):
            self.render_dashboard_content(sess)
            return

        error_html = f'<p class="error">{html.escape(error)}</p>' if error else ""
        bar = status_bar(sess)
        body = f"""
        {bar}
        <div class="login-wrap">
          <div class="login-card">
            <h2>🔒 Administrator Access</h2>
            <p style="font-size:0.85rem;color:var(--ink-soft);">Restricted panel. Authorized personnel only.</p>
            <form method="POST" action="/admindashboard">
              <label>Admin Username</label>
              <input type="text" name="username" required>
              <label>Admin Password</label>
              <input type="password" name="password" required>
              <button type="submit">Log In</button>
            </form>
            {error_html}
          </div>
        </div>
        """
        self.send_html(page_shell("Administrator Access", body))

    def handle_admindashboard_login(self):
        form = self.read_form()
        username = form.get("username", "").strip()
        password = form.get("password", "")

        sid, sess = get_session(self)
        set_cookie = None
        if not sess:
            sid = new_session()
            sess = SESSIONS[sid]
            sess["login_time"] = time.time()
            set_cookie = f"session_id={sid}; Path=/; HttpOnly"

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            sess["admin_logged_in"] = True
            if set_cookie:
                self.send_response(200)
                self.send_header("Set-Cookie", set_cookie)
                self.end_headers()
                self.wfile.write(page_shell(
                    "Admin Dashboard", self.dashboard_body(sess)
                ).encode("utf-8"))
            else:
                self.render_dashboard_content(sess)
            return

        self.render_admindashboard(error="Invalid administrator credentials.")

    def dashboard_body(self, sess):
        rows = "".join(f"""
          <div class="admin-post-row">
            <span>{html.escape(p['title'])}</span>
            <span>
              <form method="POST" action="/admin/delete-post" style="display:inline">
                <input type="hidden" name="id" value="{p['id']}">
                <button class="danger" type="submit">Delete</button>
              </form>
            </span>
          </div>
        """ for p in BLOG_POSTS)

        buttons = '<a class="icon-btn" href="/logout">🚪 Logout</a>'
        bar = status_bar(sess, buttons)

        return f"""
        {bar}
        <div class="wrap">
          <div class="card">
            <h2>Manage Blog Posts</h2>
            {rows}
            <form method="POST" action="/admin/add-post" style="margin-top:20px;">
              <label>New Post Title</label>
              <input type="text" name="title" required>
              <label>New Post Body</label>
              <textarea name="body" rows="3" required></textarea>
              <button type="submit">Add Post</button>
            </form>
          </div>
          <div class="card" style="border: 2px solid #d90429;">
            <h2>⚠ Danger Zone</h2>
            <p>Current administrator account: <strong>{ADMIN_USERNAME}</strong></p>
            <form method="POST" action="/admin/delete-admin"
                  onsubmit="return confirm('This will permanently remove the admin account and end the task. Continue?');">
              <button class="danger" type="submit">Delete Admin Account "{ADMIN_USERNAME}"</button>
            </form>
          </div>
        </div>
        """

    def render_dashboard_content(self, sess):
        self.send_html(page_shell("Admin Dashboard", self.dashboard_body(sess)))

    def handle_add_post(self):
        global next_post_id
        sid, sess = get_session(self)
        if not sess or not sess.get("admin_logged_in"):
            self.redirect("/admindashboard")
            return
        form = self.read_form()
        title = form.get("title", "Untitled")
        body_text = form.get("body", "")
        BLOG_POSTS.append({
            "id": next_post_id,
            "title": title,
            "body": body_text,
            "color": "#7a9b6e",
        })
        next_post_id += 1
        self.redirect("/admindashboard")

    def handle_delete_post(self):
        sid, sess = get_session(self)
        if not sess or not sess.get("admin_logged_in"):
            self.redirect("/admindashboard")
            return
        form = self.read_form()
        try:
            pid = int(form.get("id", "-1"))
        except ValueError:
            pid = -1
        global BLOG_POSTS
        BLOG_POSTS[:] = [p for p in BLOG_POSTS if p["id"] != pid]
        self.redirect("/admindashboard")

    def handle_delete_admin(self):
        sid, sess = get_session(self)
        if not sess or not sess.get("admin_logged_in"):
            self.redirect("/admindashboard")
            return
        sess["completed"] = True
        sess["admin_logged_in"] = False
        self.redirect("/completed")

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
                "🎉 Congratulations! Chapter 2 complete.\n\n"
                "musni's next stop needs an account you can only reach with "
                "this email and password:\n\n"
                f"Email: {NEXT_LEVEL_EMAIL}\n"
                f"Password: {NEXT_LEVEL_PASSWORD}\n\n"
                "Head to Level 3 and log in with these credentials."
            )
            self.send_text(json.dumps({"correct": True, "message": message}), content_type="application/json")
        else:
            self.send_text(json.dumps({"correct": False}), content_type="application/json")

    def render_completed(self):
        sid, sess = get_session(self)
        if not sess or not sess.get("completed"):
            self.redirect("/login")
            return

        score = current_score(sess)
        bar = status_bar(sess)
        body = f"""
        {bar}
        <div class="login-wrap">
          <div class="login-card" style="text-align:center;">
            <h2>✅ Task Complete</h2>
            <p>Administrator account <strong>{ADMIN_USERNAME}</strong> has been removed.</p>
            <p style="font-size:1.1rem;"><strong>Flag:</strong> {FLAG}</p>
            <p style="font-size:1.3rem;"><strong>Final Score: {score} / 100</strong></p>
            <p style="color:var(--ink-soft);font-size:0.85rem;">Copy this flag and submit it via the 🚩 button above to unlock the next chapter.</p>
          </div>
        </div>
        """
        self.send_html(page_shell("Task Complete", body))

    def render_timeout(self):
        sid, sess = get_session(self)
        if not sess:
            self.redirect("/login")
            return

        # If the player already solved it before time ran out, honour that -
        # don't overwrite a real success with a timeout failure.
        if sess.get("completed") and not sess.get("timed_out"):
            self.redirect("/completed")
            return

        sess["completed"] = True
        sess["timed_out"] = True

        body = """
        <div class="login-wrap">
          <div class="login-card" style="text-align:center;">
            <h2>⏰ Time's Up</h2>
            <p>You ran out of time before completing the objective.</p>
            <p style="font-size:1.3rem;"><strong>Final Score: 0 / 100</strong></p>
            <p style="color:var(--ink-soft);font-size:0.85rem;">This session has ended. There is no way back to the challenge.</p>
          </div>
        </div>
        """
        self.send_html(page_shell("Time's Up", body))

class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"WEB-02 challenge server running on {HOST}:{PORT}")
    server.serve_forever()
