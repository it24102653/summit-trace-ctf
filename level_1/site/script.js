/* ==========================================================
   ShadowNet Access Terminal - client-side login + scoring
   ========================================================== */

const ENC_PASS = "TDN0TTNJbiQyMDI2";

const FAIL_PENALTY = 5;
const HINT_PENALTY = 20;
const START_SCORE = 100;

let score = START_SCORE;
let hintUsed = false;
let solved = false;


/* ==========================================================
   LOGIN
   ========================================================== */

const form = document.getElementById("loginForm");
const passwordInput = document.getElementById("password");
const usernameInput = document.getElementById("username");
const message = document.getElementById("message");
const scoreDisplay = document.getElementById("scoreDisplay");


function updateScoreDisplay() {

  scoreDisplay.textContent = `Score: ${score}`;

  scoreDisplay.classList.toggle(
    "dropped",
    score < START_SCORE
  );

}


form.addEventListener("submit", function (e) {

  e.preventDefault();

  if (solved) return;

  const enteredUser = usernameInput.value.trim();
  const enteredPass = passwordInput.value;

  const realPass = atob(ENC_PASS);


  /* Correct login */

  if (
    enteredUser === "admin" &&
    enteredPass === realPass
  ) {

    solved = true;

    message.textContent =
      `[+] ACCESS GRANTED. Welcome back, admin. ` +
      `Flag: CTF{b4s3_64_1sn7_3ncrypt10n} — ` +
      `Final Score: ${score}/100`;

    message.className = "message success";

    passwordInput.disabled = true;

    form.querySelector("button").disabled = true;

  }


  /* Wrong login */

  else {

    score = Math.max(
      0,
      score - FAIL_PENALTY
    );

    updateScoreDisplay();

    message.textContent =
      `[-] ACCESS DENIED. Invalid credentials. ` +
      `Try again. (-${FAIL_PENALTY} marks, Score: ${score})`;

    message.className = "message error";

    message.classList.remove("error");

    void message.offsetWidth;

    message.classList.add("error");

  }

});


/* ==========================================================
   README
   ========================================================== */

const readmeBtn =
  document.getElementById("readmeBtn");

const readmeModal =
  document.getElementById("readmeModal");

const closeReadme =
  document.getElementById("closeReadme");


readmeBtn.addEventListener("click", function () {

  readmeModal.classList.remove("hidden");

});


closeReadme.addEventListener("click", function () {

  readmeModal.classList.add("hidden");

});


readmeModal.addEventListener("click", function (e) {

  if (e.target === readmeModal) {

    readmeModal.classList.add("hidden");

  }

});


/* ==========================================================
   HINT SYSTEM
   ========================================================== */

const hintBtn =
  document.getElementById("hintBtn");

const hintBox =
  document.getElementById("hintBox");

const confirmHintBtn =
  document.getElementById("confirmHint");

const hintText =
  document.getElementById("hintText");

const hintConfirmText =
  document.getElementById("hintConfirmText");


/* ==========================================================
   CLICK ?
   ========================================================== */

hintBtn.addEventListener("click", function () {

  /*
   * If hint was already used,
   * show the hint directly.
   */

  if (hintUsed) {

    hintBox.classList.remove("hidden");

    hintText.classList.remove("hidden");

    return;

  }


  /*
   * First click:
   * show confirmation.
   */

  hintBox.classList.remove("hidden");

  hintConfirmText.classList.remove("hidden");

  confirmHintBtn.classList.remove("hidden");

  hintText.classList.add("hidden");

});


/* ==========================================================
   CLICK "YES, SHOW ME ANYWAY"
   ========================================================== */

confirmHintBtn.addEventListener("click", function () {

  /*
   * Deduct 20 marks only once.
   */

  if (!hintUsed) {

    hintUsed = true;

    score = Math.max(
      0,
      score - HINT_PENALTY
    );

    updateScoreDisplay();

  }


  /*
   * Hide confirmation.
   */

  hintConfirmText.classList.add("hidden");

  confirmHintBtn.classList.add("hidden");


  /*
   * SHOW ACTUAL HINT.
   */

  hintText.classList.remove("hidden");


  /*
   * Keep hint box open.
   */

  hintBox.classList.remove("hidden");

});


/* ==========================================================
   INITIAL SCORE
   ========================================================== */

updateScoreDisplay();


/* ==========================================================
   FLAG SUBMISSION -> UNLOCK NEXT LEVEL
   ========================================================== */

const REAL_FLAG = "Q1RGe2I0czNfNjRfMXNuN18zbmNyeXB0MTBufQ==";
// Base64 of CTF{b4s3_64_1sn7_3ncrypt10n} - kept encoded here so the
// flag isn't sitting in plaintext in view-source, consistent with
// this level's own "don't leave secrets in plain text" lesson.

const NEXT_LEVEL_MSG =
  "🎉 Congratulations! Chapter 1 complete.\n\n" +
  "musni's laptop reveals his blog login for the next leg of the trip:\n\n" +
  "Username: musni_trail\n" +
  "Password: Basecamp2026\n\n" +
  "Head to Level 2 and log in with these credentials.";

let flagSubmitted = false;

const flagBtn = document.getElementById("flagBtn");
const flagModal = document.getElementById("flagModal");
const closeFlagModal = document.getElementById("closeFlagModal");
const flagInput = document.getElementById("flagInput");
const submitFlagBtn = document.getElementById("submitFlagBtn");
const flagMessage = document.getElementById("flagMessage");
const nextLevelReveal = document.getElementById("nextLevelReveal");

flagBtn.addEventListener("click", function () {
  flagModal.classList.remove("hidden");
});

closeFlagModal.addEventListener("click", function () {
  flagModal.classList.add("hidden");
});

flagModal.addEventListener("click", function (e) {
  if (e.target === flagModal) flagModal.classList.add("hidden");
});

submitFlagBtn.addEventListener("click", function () {
  if (flagSubmitted) return;

  const guess = flagInput.value.trim();

  if (guess === atob(REAL_FLAG)) {
    flagSubmitted = true;
    flagMessage.textContent = "";
    nextLevelReveal.textContent = NEXT_LEVEL_MSG;
    nextLevelReveal.classList.remove("hidden");
    flagInput.disabled = true;
    submitFlagBtn.disabled = true;
    flagBtn.textContent = "🎉 Chapter Complete";
    flagBtn.disabled = true;
  } else {
    flagMessage.textContent = "Incorrect flag. Keep working on the task above.";
    flagMessage.className = "message error";
  }
});
