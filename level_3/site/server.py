#!/usr/bin/env python3
"""
WEB-03 : "ShopNest Order Leak"
Domain      : Cryptography (encoding + weak hash) / Web Security (broken
              access control via robots.txt) overlap
Difficulty  : Moderate

Pure Python standard-library implementation (no Flask, no pip installs).

Flow:
  1. Player "registers"/logs in with any email ending in @gmail.com and
     any password 10+ characters (not the real target - just a gate).
  2. Lands on a ShopNest-style product dashboard (16 items, white/orange
     theme, search bar) with a persistent header: Timer, Score, Tasks,
     Hint x2, README, Logout.
  3. Tasks page has two parts:

     TASK 1 (50 marks): robots.txt discloses THREE paths. Only one of
     them ("/orders-export") actually returns order/token data; the
     other two are decoys that still return plausible-looking content.
     Player must submit the correct path to complete Task 1.

     TASK 2 (50 marks): only unlocked after Task 1. /orders-export
     returns a Base64 "token". Decoding it reveals a JSON blob (order
     details + a User object with username and an MD5 password hash).
     Completing Task 1 also reveals the location of a 100-entry
     password wordlist (not discoverable before that point). Player
     downloads it, runs hashcat against the MD5 hash, and submits the
     cracked plaintext password to complete Task 2.

  4. Timer: 20 minutes (1200s) total. -5 marks per minute elapsed.
     Two SEPARATE one-time hints, one per task, -20 marks each.
  5. Score only ever finalizes once BOTH tasks are solved. If time runs
     out before both are done, final score is forced to 0 - no partial
     credit, matching the "if I can't finish in time, 0 marks" rule.
"""

import http.server
import socketserver
import uuid
import time
import urllib.parse
import html
import json
import base64
from http import cookies

HOST = "0.0.0.0"
PORT = 8000

TOTAL_TIME_BUDGET = 1200          # 20 minutes
MARKS_PER_MINUTE = 5              # time decay
HINT_PENALTY = 20                 # per hint
TASK1_MARKS = 50
TASK2_MARKS = 50

TASK1_CORRECT_PATH = "/orders-export"
REAL_PASSWORD = "Sunflower99"
PASSWORD_HASH = "9c37162badb5fc7a722dc4b236a4e739"  # MD5(Sunflower99)

FLAG = "CTF{b4se64_th3n_h4shc4t_ftw}"

# Entry credentials required to reach this level - revealed by Level 2's
# flag submission.
CHAIN_EMAIL = "musni.trail@gmail.com"
CHAIN_PASSWORD = "SummitGear2026"

# PIN revealed to the player upon submitting THIS level's flag, needed to
# open Level 4's envelope.
NEXT_LEVEL_PIN = "7734"

ORDER_JSON = {
    "status": "success",
    "data": {
        "id": 7,
        "coupon": None,
        "UserId": 25,
        "createdAt": "2026-07-29T11:22:59.838Z",
        "updatedAt": "2026-07-29T11:22:59.838Z",
        "User": {
            "id": 25,
            "username": "r.dalton",
            "email": "r.dalton@shopnest-corp.com",
            "passwordHash": PASSWORD_HASH
        },
        "Products": [
            {
                "id": 6,
                "name": "Banana Juice (1000ml)",
                "description": "Monkeys love it the most.",
                "price": 1.99,
                "deluxePrice": 1.99,
                "image": "banana_juice.jpg",
                "createdAt": "2026-07-29T06:11:28.345Z",
                "updatedAt": "2026-07-29T06:11:28.345Z",
                "deletedAt": None,
                "BasketItem": {
                    "ProductId": 6,
                    "BasketId": 7,
                    "id": 9,
                    "quantity": 3,
                    "createdAt": "2026-07-29T11:22:59.909Z",
                    "updatedAt": "2026-07-29T11:22:59.909Z"
                }
            }
        ]
    }
}
ORDER_TOKEN = base64.b64encode(json.dumps(ORDER_JSON, indent=2).encode()).decode()

WORDLIST = None  # populated at startup below


def build_wordlist():
    import random
    random.seed(42)
    prefixes = ["Sun", "Moon", "Star", "Rain", "Cloud", "Ocean", "River", "Forest",
                "Mountain", "Desert", "Winter", "Summer", "Spring", "Autumn", "Fire",
                "Ice", "Storm", "Thunder", "Shadow", "Light"]
    suffixes = ["flower", "shine", "dust", "wave", "fall", "light", "storm", "dream",
                "wind", "fire", "bird", "wolf", "tiger", "eagle", "dragon"]
    words = set()
    while len(words) < 99:
        w = random.choice(prefixes) + random.choice(suffixes) + str(random.randint(10, 99))
        words.add(w)
    words = list(words)[:99]
    words.insert(random.randint(20, 79), REAL_PASSWORD)
    return "\n".join(words) + "\n"


WORDLIST = build_wordlist()

PRODUCTS = [
    {"name": "Trucker Cap", "price": "12.99", "icon": "🧢"},
    {"name": "Baseball Cap - Navy", "price": "14.99", "icon": "🧢"},
    {"name": "Snapback - Teal", "price": "13.50", "icon": "🧢"},
    {"name": "Graphic Tee - Pink", "price": "19.99", "icon": "👕"},
    {"name": "Denim Jacket", "price": "45.00", "icon": "🧥"},
    {"name": "Chukka Boots", "price": "59.99", "icon": "👢"},
    {"name": "Oxford Shoes", "price": "64.00", "icon": "👞"},
    {"name": "Leather Wallet", "price": "24.99", "icon": "👛"},
    {"name": "Canvas Wallet", "price": "17.50", "icon": "👛"},
    {"name": "Fitted Cap - Black", "price": "15.99", "icon": "🧢"},
    {"name": "Dress Shoes - Brown", "price": "69.99", "icon": "👞"},
    {"name": "Heels - Red", "price": "39.99", "icon": "👠"},
    {"name": "Platform Heels", "price": "42.00", "icon": "👠"},
    {"name": "Tactical Backpack", "price": "34.99", "icon": "🎒"},
    {"name": "Canvas Backpack", "price": "29.99", "icon": "🎒"},
    {"name": "Crossbody Bag - Red", "price": "27.50", "icon": "👜"},
]

SESSIONS = {}


def new_session():
    sid = uuid.uuid4().hex
    SESSIONS[sid] = {
        "logged_in": False,
        "email": None,
        "login_time": None,
        "task1_done": False,
        "task2_done": False,
        "hint1_used": False,
        "hint2_used": False,
        "completed": False,
        "timed_out": False,
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


def current_raw_score(sess):
    """Milestone-based score: 50 per task solved, minus time/hint penalties."""
    raw = (TASK1_MARKS if sess.get("task1_done") else 0) + \
          (TASK2_MARKS if sess.get("task2_done") else 0)
    minutes = elapsed_seconds(sess) // 60
    time_penalty = minutes * MARKS_PER_MINUTE
    hint_penalty = (HINT_PENALTY if sess.get("hint1_used") else 0) + \
                   (HINT_PENALTY if sess.get("hint2_used") else 0)
    return max(0, raw - time_penalty - hint_penalty)


def status_bar(sess):
    if not sess or not sess.get("login_time"):
        return ""
    remaining = max(0, TOTAL_TIME_BUDGET - elapsed_seconds(sess))
    score = current_raw_score(sess)
    flag_done = sess.get("flag_finalized")
    return f"""
    <div class="navbar">
      <div class="nav-left">
        <button class="icon-btn flag-btn" onclick="openFlagModal()" {'disabled' if flag_done else ''}>
          {'🎉 Chapter Complete' if flag_done else '🚩 Submit Flag'}
        </button>
      </div>
      <span class="brand">🛒 ShopNest</span>
      <div class="actions">
        <span class="timer" id="timer">⏱ --:--</span>
        <span class="timer" id="scoreBox">Score: {score}</span>
        <a class="icon-btn" href="/dashboard">🏬 Shop</a>
        <a class="icon-btn" href="/tasks">📋 Tasks</a>
        <button class="icon-btn" onclick="showReadme()" title="README">📄 README</button>
        <a class="icon-btn" href="/logout">🚪 Logout</a>
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
        <button onclick="closeModal('flagModal')" style="background:var(--ink-soft);margin-top:8px;">Close</button>
      </div>
    </div>
    <div id="readmeModal" class="modal" style="display:none;">
      <div class="modal-box">
        <h3>📄 README — WEB-03: ShopNest Order Leak</h3>
        <p><strong>Domain:</strong> Cryptography (encoding + weak hashing) / Web Security recon</p>
        <p><strong>Task 1 (50 marks):</strong> Find the correct hidden endpoint that
           actually contains order/token data.</p>
        <p><strong>Task 2 (50 marks):</strong> Decode the token, crack the leaked
           password hash using the revealed wordlist, and submit the real password.</p>
        <p><strong>Scoring:</strong> Timer is 20 minutes. -5 marks per minute elapsed.
           Each task has its own hint, costing 20 marks if used.
           If time runs out before BOTH tasks are complete, final score is 0.</p>
        <p><strong>Flag format:</strong> CTF{{...}}</p>
        <button onclick="closeModal('readmeModal')">Close</button>
      </div>
    </div>
    <script>
      let remaining = {remaining};
      let timedOut = false;
      function tick() {{
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
      tick();
      setInterval(tick, 1000);
      function showReadme() {{ document.getElementById('readmeModal').style.display='flex'; }}
      function closeModal(id) {{ document.getElementById(id).style.display='none'; }}
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
h2, h3, h4 { font-family: 'Fraunces', serif; font-weight: 600; }
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
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.82rem;
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
  font-size: 0.82rem;
}
.wrap { max-width: 1000px; margin: 26px auto; padding: 0 20px; }
.searchbar {
  width: 100%;
  padding: 12px 16px;
  border: 1px solid var(--line);
  border-radius: 4px;
  margin-bottom: 20px;
  font-size: 0.95rem;
  font-family: 'Public Sans', sans-serif;
  background: #fbf6ea;
  color: var(--ink);
}
.grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.product-card {
  background: var(--paper-card);
  border: 1px solid var(--line);
  border-radius: 4px;
  padding: 14px;
  text-align: center;
  box-shadow: 0 4px 14px rgba(90,74,53,0.08);
}
.product-card .swatch {
  height: 90px;
  border-radius: 3px;
  margin-bottom: 10px;
  background: linear-gradient(135deg, var(--green), var(--brown));
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 2.2rem;
}
.product-card h4 { margin: 6px 0 4px; font-size: 0.9rem; }
.product-card .price { color: var(--brown-dark); font-weight: 700; }
.login-wrap {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 90vh;
}
.login-card {
  background: var(--paper-card);
  padding: 34px 38px;
  border-radius: 4px;
  box-shadow: 0 12px 34px rgba(90,74,53,0.12);
  width: 100%;
  max-width: 380px;
  border: 1px solid var(--line);
  border-top: 4px solid var(--brown);
}
.login-card h2 { margin-top: 0; color: var(--ink); }
label { font-size: 0.8rem; color: var(--ink-soft); display:block; margin-top: 12px; font-weight: 600; }
input[type=text], input[type=email], input[type=password], textarea {
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
.success { color: var(--green-dark); font-size: 0.85rem; margin-top: 10px; }
.card {
  background: var(--paper-card);
  border: 1px solid var(--line);
  border-radius: 4px;
  box-shadow: 0 8px 24px rgba(90,74,53,0.08);
  padding: 24px;
  margin-bottom: 20px;
  border-left: 5px solid var(--brown);
}
.card.locked { opacity: 0.55; }
.task-badge {
  display: inline-block;
  background: rgba(138,90,52,0.08);
  color: var(--brown-dark);
  border: 1px solid var(--brown);
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 0.75rem;
  margin-left: 8px;
}
.task-badge.done { background: rgba(92,122,77,0.12); color: var(--green-dark); border-color: var(--green); }
.hint-btn {
  width: auto;
  background: var(--paper-card);
  color: var(--brown-dark);
  border: 1px solid var(--brown);
  padding: 6px 14px;
  font-size: 0.8rem;
  margin-top: 10px;
}
.modal {
  position: fixed; inset: 0; background: rgba(58,47,34,0.45);
  display: flex; align-items: center; justify-content: center;
  z-index: 999;
}
.modal-box {
  background: var(--paper-card); border: 1px solid var(--line); padding: 26px 30px; border-radius: 4px;
  max-width: 460px; width: 90%;
}
code {
  background: rgba(92,122,77,0.1);
  padding: 1px 6px;
  border-radius: 4px;
  color: var(--green-dark);
  font-family: 'IBM Plex Mono', monospace;
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

    def check_timeout(self, sess):
        if sess and not sess.get("completed") and elapsed_seconds(sess) >= TOTAL_TIME_BUDGET:
            self.redirect("/timeout")
            return True
        return False

    # ------------------ GET ------------------
    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path

        if path == "/robots.txt":
            self.send_text(
                "User-agent: *\n"
                "Disallow: /orders-export\n"
                "Disallow: /admin-notes\n"
                "Disallow: /server-status\n"
            )
            return
        if path in ("/", "/login"):
            self.render_login()
            return
        if path == "/dashboard":
            self.render_dashboard()
            return
        if path == "/tasks":
            self.render_tasks()
            return
        if path == "/logout":
            sid, sess = get_session(self)
            if sess:
                sess["logged_in"] = False
            self.redirect("/login")
            return
        if path == "/orders-export":
            self.render_orders_export()
            return
        if path == "/admin-notes":
            self.send_text(
                "INTERNAL NOTES\n--------------\n"
                "Reminder: rotate the staging DB creds next sprint.\n"
                "Also the office coffee machine is broken again.\n"
            )
            return
        if path == "/server-status":
            self.send_text(
                "OK - uptime 42d 6h\n"
                "cpu: 12%\nmem: 38%\ndisk: 61%\n"
            )
            return
        if path == "/password-wordlist":
            sid, sess = get_session(self)
            if not sess or not sess.get("task1_done"):
                self.send_text("403 Forbidden - complete Task 1 first", status=403)
                return
            self.send_text(WORDLIST)
            return
        if path == "/hint1":
            self.handle_hint1()
            return
        if path == "/hint2":
            self.handle_hint2()
            return
        if path == "/completed":
            self.render_completed()
            return
        if path == "/timeout":
            self.render_timeout()
            return

        self.send_text("404 Not Found", status=404)

    # ------------------ POST ------------------
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

    # ---------- login ----------
    def render_login(self, error=None):
        error_html = f'<p class="error">{html.escape(error)}</p>' if error else ""
        body = f"""
        <div class="login-wrap">
          <div class="login-card">
            <h2>🛒 ShopNest — Sign In</h2>
            <div class="hint-sample">
              📖 <strong>Chapter 3 — Gearing Up:</strong> musni is shopping
              for trip gear. You'll need the credentials found at the end of
              Chapter 2 to sign in.
            </div>
            <form method="POST" action="/login">
              <label>Email</label>
              <input type="email" name="email" placeholder="you@gmail.com" required>
              <label>Password</label>
              <input type="password" name="password" required>
              <button type="submit">Log In</button>
            </form>
            {error_html}
          </div>
        </div>
        """
        self.send_html(page_shell("ShopNest - Sign In", body))

    def handle_login(self):
        form = self.read_form()
        email = form.get("email", "").strip()
        password = form.get("password", "")

        if email.lower() != CHAIN_EMAIL.lower() or password != CHAIN_PASSWORD:
            self.render_login(error="Incorrect credentials. These must come from completing the previous chapter.")
            return

        sid = new_session()
        SESSIONS[sid]["logged_in"] = True
        SESSIONS[sid]["email"] = email
        SESSIONS[sid]["login_time"] = time.time()

        self.redirect("/dashboard", set_cookie=f"session_id={sid}; Path=/; HttpOnly")

    # ---------- dashboard (shop) ----------
    def render_dashboard(self):
        sid, sess = get_session(self)
        if not sess or not sess["logged_in"]:
            self.redirect("/login")
            return
        if self.check_timeout(sess):
            return
        if sess.get("completed"):
            self.redirect("/timeout" if sess.get("timed_out") else "/completed")
            return

        cards = "".join(f"""
          <div class="product-card" data-name="{html.escape(p['name'].lower())}">
            <div class="swatch">{p['icon']}</div>
            <h4>{html.escape(p['name'])}</h4>
            <div class="price">${p['price']}</div>
          </div>
        """ for p in PRODUCTS)

        bar = status_bar(sess)
        body = f"""
        {bar}
        <div class="wrap">
          <input type="text" class="searchbar" id="searchBox" placeholder="Search products..." onkeyup="filterProducts()">
          <div class="grid" id="productGrid">
            {cards}
          </div>
        </div>
        <script>
          function filterProducts() {{
            const q = document.getElementById('searchBox').value.toLowerCase();
            document.querySelectorAll('.product-card').forEach(card => {{
              card.style.display = card.dataset.name.includes(q) ? '' : 'none';
            }});
          }}
        </script>
        """
        self.send_html(page_shell("ShopNest - Shop", body))

    # ---------- tasks page ----------
    def render_tasks(self, task1_msg=None, task2_msg=None):
        sid, sess = get_session(self)
        if not sess or not sess["logged_in"]:
            self.redirect("/login")
            return
        if self.check_timeout(sess):
            return
        if sess.get("completed"):
            self.redirect("/timeout" if sess.get("timed_out") else "/completed")
            return

        bar = status_bar(sess)
        t1_badge = '<span class="task-badge done">✓ Complete</span>' if sess["task1_done"] else '<span class="task-badge">Pending</span>'
        t2_badge = '<span class="task-badge done">✓ Complete</span>' if sess["task2_done"] else '<span class="task-badge">Pending</span>'

        t1_msg_html = f'<p class="{"success" if sess["task1_done"] else "error"}">{html.escape(task1_msg)}</p>' if task1_msg else ""
        t2_msg_html = f'<p class="{"success" if sess["task2_done"] else "error"}">{html.escape(task2_msg)}</p>' if task2_msg else ""

        task1_disabled = "disabled" if sess["task1_done"] else ""
        hint1_disabled = "disabled" if sess["hint1_used"] else ""

        task2_locked_class = "" if sess["task1_done"] else "locked"
        task2_inner = ""
        if not sess["task1_done"]:
            task2_inner = "<p style='color:var(--ink-soft);'>🔒 Complete Task 1 first to unlock this task and reveal the wordlist location.</p>"
        else:
            task2_disabled = "disabled" if sess["task2_done"] else ""
            hint2_disabled = "disabled" if sess["hint2_used"] else ""
            task2_inner = f"""
            <p>Now that Task 1 is solved, a password wordlist has been made available at:
               <code>/password-wordlist</code></p>
            <p>Decode the token from <code>/orders-export</code> (it's Base64), find the
               <code>passwordHash</code> field, then use <strong>hashcat</strong> with the
               wordlist to crack it. Submit the real plaintext password below.</p>
            <form method="POST" action="/task2/submit">
              <label>Cracked Password</label>
              <input type="text" name="answer" required {task2_disabled}>
              <button type="submit" {task2_disabled}>Submit Task 2</button>
            </form>
            {t2_msg_html}
            <button class="hint-btn" onclick="getHint(2)" {hint2_disabled} id="hint2Btn">💡 Hint 2 (-20 marks)</button>
            """

        body = f"""
        {bar}
        <div class="wrap">
          <div class="card">
            <h2>Task 1: Find the Real Order Endpoint {t1_badge}</h2>
            <p>Somewhere on this server, an endpoint exposes real order data
               (including a leaked access token). Two other endpoints look
               similar but are decoys. Find the <strong>correct</strong> path.</p>
            <form method="POST" action="/task1/submit">
              <label>File Path (e.g. /something)</label>
              <input type="text" name="answer" placeholder="/..." required {task1_disabled}>
              <button type="submit" {task1_disabled}>Submit Task 1</button>
            </form>
            {t1_msg_html}
            <button class="hint-btn" onclick="getHint(1)" {hint1_disabled} id="hint1Btn">💡 Hint 1 (-20 marks)</button>
          </div>

          <div class="card {task2_locked_class}">
            <h2>Task 2: Crack the Leaked Password {t2_badge}</h2>
            {task2_inner}
          </div>
        </div>

        <div id="hintModal" class="modal" style="display:none;">
          <div class="modal-box">
            <h3>💡 Hint</h3>
            <p id="hintTextBox">Are you sure? This costs 20 marks (~4 minutes).</p>
            <button id="confirmHintBtn" onclick="confirmHint()">Yes, show me anyway</button>
            <button id="hintCancelBtn" onclick="closeModal('hintModal')" style="background:var(--ink-soft);margin-top:8px;">Cancel</button>
          </div>
        </div>

        <script>
          let pendingHint = null;
          let hint1Used = {str(sess["hint1_used"]).lower()};
          let hint2Used = {str(sess["hint2_used"]).lower()};

          function getHint(n) {{
            if (n === 1 && hint1Used) return;
            if (n === 2 && hint2Used) return;
            pendingHint = n;
            document.getElementById('hintModal').style.display='flex';
          }}

          function confirmHint() {{
            if (pendingHint === null) return;
            if (pendingHint === 1 && hint1Used) return;
            if (pendingHint === 2 && hint2Used) return;

            fetch('/hint' + pendingHint).then(r => r.json()).then(data => {{
              document.getElementById('hintTextBox').innerHTML = data.hint;
              document.getElementById('scoreBox').textContent = 'Score: ' + data.score;

              const confirmBtn = document.getElementById('confirmHintBtn');
              confirmBtn.textContent = 'Hint revealed above ✓';
              confirmBtn.disabled = true;
              remaining = Math.max(0, remaining - 240); // -4 minutes shown on the timer
              const cancelBtn = document.getElementById('hintCancelBtn');
              if (cancelBtn) cancelBtn.textContent = 'Close';

              if (pendingHint === 1) {{
                hint1Used = true;
                const b = document.getElementById('hint1Btn');
                if (b) {{ b.disabled = true; b.style.opacity = '0.4'; }}
              }} else {{
                hint2Used = true;
                const b = document.getElementById('hint2Btn');
                if (b) {{ b.disabled = true; b.style.opacity = '0.4'; }}
              }}
            }});
          }}
        </script>
        """
        self.send_html(page_shell("ShopNest - Tasks", body))

    def handle_hint1(self):
        sid, sess = get_session(self)
        if not sess:
            self.send_text(json.dumps({"error": "no session"}), content_type="application/json")
            return
        sess["hint1_used"] = True
        hint_text = ("Ever checked a site's <code>robots.txt</code> file? It often lists "
                     "paths the owner doesn't want indexed - which makes it a great place "
                     "to find things they'd rather you not stumble onto. Try "
                     "<code>/robots.txt</code>, then test each disclosed path to see which "
                     "one actually returns order data.")
        self.send_text(
            json.dumps({"hint": hint_text, "score": current_raw_score(sess)}),
            content_type="application/json",
        )

    def handle_hint2(self):
        sid, sess = get_session(self)
        if not sess:
            self.send_text(json.dumps({"error": "no session"}), content_type="application/json")
            return
        sess["hint2_used"] = True
        hint_text = (
            "Step by step: 1) Visit <code>/orders-export</code> and copy the "
            "<code>token</code> value. 2) Decode it - in a Kali terminal: "
            "<code>echo 'TOKEN_HERE' | base64 -d</code>. 3) In the decoded JSON, find "
            "<code>passwordHash</code> - that's an MD5 hash. 4) Save it to a file, e.g. "
            "<code>echo 'HASH_HERE' &gt; hash.txt</code>. 5) Download the wordlist from "
            "<code>/password-wordlist</code> and save it as <code>wordlist.txt</code>. "
            "6) Crack it: <code>hashcat -m 0 -a 0 hash.txt wordlist.txt</code>. "
            "7) View the result: <code>hashcat -m 0 hash.txt --show</code>. "
            "8) Submit the cracked password (the part after the colon) into the Task 2 box."
        )
        self.send_text(
            json.dumps({"hint": hint_text, "score": current_raw_score(sess)}),
            content_type="application/json",
        )

    # ---------- recon endpoints ----------
    def render_orders_export(self):
        self.send_text(
            json.dumps({"status": "success", "token": ORDER_TOKEN}, indent=2),
            content_type="application/json",
        )

    # ---------- task submissions ----------
    def handle_task1_submit(self):
        sid, sess = get_session(self)
        if not sess:
            self.redirect("/login")
            return
        if self.check_timeout(sess):
            return

        form = self.read_form()
        answer = form.get("answer", "").strip()

        if answer == TASK1_CORRECT_PATH:
            sess["task1_done"] = True
            self.render_tasks(task1_msg=f"✅ Correct! {TASK1_MARKS} marks awarded. Task 2 is now unlocked.")
        else:
            self.render_tasks(task1_msg="❌ That path doesn't contain the real order data. Try again.")

    def handle_task2_submit(self):
        sid, sess = get_session(self)
        if not sess:
            self.redirect("/login")
            return
        if self.check_timeout(sess):
            return
        if not sess.get("task1_done"):
            self.redirect("/tasks")
            return

        form = self.read_form()
        answer = form.get("answer", "").strip()

        if answer == REAL_PASSWORD:
            sess["task2_done"] = True
            sess["completed"] = True
            self.redirect("/completed")
        else:
            self.render_tasks(task2_msg="❌ Incorrect password. Check your hashcat output and try again.")

    # ---------- completion / timeout ----------
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
                "🎉 Congratulations! Chapter 3 complete.\n\n"
                "musni is finally on the trail. The envelope waiting at "
                "Level 4 is locked with a 4-digit PIN:\n\n"
                f"PIN: {NEXT_LEVEL_PIN}\n\n"
                "Head to Level 4 and enter it to open the envelope."
            )
            self.send_text(json.dumps({"correct": True, "message": message}), content_type="application/json")
        else:
            self.send_text(json.dumps({"correct": False}), content_type="application/json")

    def render_completed(self):
        sid, sess = get_session(self)
        if not sess or not sess.get("completed") or sess.get("timed_out"):
            self.redirect("/login")
            return

        score = current_raw_score(sess)
        bar = status_bar(sess)
        body = f"""
        {bar}
        <div class="login-wrap">
          <div class="login-card" style="text-align:center;">
            <h2>✅ Task Complete</h2>
            <p>Both tasks solved. The leaked token was decoded and the password cracked.</p>
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
        if sess.get("completed") and not sess.get("timed_out"):
            self.redirect("/completed")
            return

        sess["completed"] = True
        sess["timed_out"] = True

        body = """
        <div class="login-wrap">
          <div class="login-card" style="text-align:center;">
            <h2>⏰ Time's Up</h2>
            <p>You ran out of time before completing both tasks.</p>
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
    print(f"WEB-03 challenge server running on {HOST}:{PORT}")
    server.serve_forever()
