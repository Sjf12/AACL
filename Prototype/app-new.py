# ================================================
# AACL PROTOTYPE
# AACL grammar issuance gated behind authenticated sessions
# ================================================

from flask import Flask, request, jsonify, render_template, session
import uuid
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
import hashlib
import os

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)  # Required for Flask session management

# ================================================
# In-memory user store (replace with DB in production)
# ================================================
users = {
    "alice": {
        "password_hash": hashlib.sha256("alice123".encode()).hexdigest(),
        "balance": 500,
        "allowed_recipients": ["user-123", "user-456", "merchant-001"]
    },
    "bob": {
        "password_hash": hashlib.sha256("bob123".encode()).hexdigest(),
        "balance": 300,
        "allowed_recipients": ["user-123", "merchant-001"]
    }
}

# Grammar store
grammars = {}


# ================================================
# Authentication Decorator
# ================================================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session:
            return jsonify({
                "error": "Unauthorized. Please log in first.",
                "code": "AUTH_REQUIRED"
            }), 401
        return f(*args, **kwargs)
    return decorated


# ================================================
# Routes: Pages
# ================================================
@app.route('/')
def index():
    return render_template('index.html')


# ================================================
# Auth Routes
# ================================================

@app.route('/auth/register', methods=['POST'])
def register():
    """
    Register a new user.
    In the prototype, users are pre-seeded above.
    This endpoint demonstrates extensibility.
    """
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    if username in users:
        return jsonify({"error": "User already exists"}), 409

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    users[username] = {
        "password_hash": hashlib.sha256(password.encode()).hexdigest(),
        "balance": 200,  # Default balance for new users
        "allowed_recipients": ["user-123", "merchant-001"]
    }

    print(f"[AUTH] New user registered: {username}")
    return jsonify({"success": True, "message": f"User '{username}' registered."}), 201


@app.route('/auth/login', methods=['POST'])
def login():
    """
    Authenticate user and establish session.
    Paper Section 6.1 — Authentication Layer.
    """
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    user = users.get(username)
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401

    password_hash = hashlib.sha256(password.encode()).hexdigest()
    if password_hash != user["password_hash"]:
        return jsonify({"error": "Invalid credentials"}), 401

    # Establish session
    session["username"] = username
    session["session_id"] = str(uuid.uuid4())  # Per-session unique ID
    session.permanent = False  # Session expires on browser close

    print(f"[AUTH] User logged in: {username} | Session: {session['session_id']}")
    return jsonify({
        "success": True,
        "message": f"Welcome, {username}!",
        "session_id": session["session_id"],
        "balance": user["balance"]
    })


@app.route('/auth/logout', methods=['POST'])
@login_required
def logout():
    """
    Invalidate session on logout.
    """
    username = session.get("username")
    session.clear()
    print(f"[AUTH] User logged out: {username}")
    return jsonify({"success": True, "message": "Logged out successfully."})


@app.route('/auth/status', methods=['GET'])
def auth_status():
    """
    Check if user is currently authenticated.
    Useful for frontend session state management.
    """
    if "username" in session:
        username = session["username"]
        user = users.get(username, {})
        return jsonify({
            "authenticated": True,
            "username": username,
            "balance": user.get("balance", 0)
        })
    return jsonify({"authenticated": False}), 200


# ================================================
# AACL Routes — Gated Behind Authentication
# ================================================

@app.route('/aacl/issue/<intent>', methods=['POST'])
@login_required  # ← Authentication gate enforced here
def issue_grammar(intent):
    """
    Grammar Issuance — Paper Section 6.2.
    State snapshot is now derived from the authenticated
    user's actual session context, not hardcoded constants.
    """
    if intent != "transfer":
        return jsonify({"error": "Unsupported intent"}), 400

    # Derive state snapshot from authenticated user
    username = session["username"]
    user = users.get(username)

    if not user:
        return jsonify({"error": "User not found"}), 404

    # Paper Section 5.2: State Snapshot
    # Si = Snapshot(u) — captured at issuance time
    snapshot_balance = user["balance"]
    snapshot_recipients = user["allowed_recipients"]

    grammar_id = str(uuid.uuid4())
    entropy = secrets.token_hex(16)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    # Read the intended amount and recipient from the request body
    issue_data = request.get_json(silent=True) or {}
    intended_amount = issue_data.get("amount")
    intended_recipient = issue_data.get("recipient_id")

    # Validate that amount and recipient were provided at issuance time
    if intended_amount is None or intended_recipient is None:
        return jsonify({"error": "amount and recipient_id must be provided at grammar issuance"}), 400

    try:
        intended_amount = float(intended_amount)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid amount"}), 400

    if intended_amount <= 0:
        return jsonify({"error": "Amount must be greater than zero"}), 400

    if intended_amount > snapshot_balance:
        return jsonify({"error": f"Amount exceeds available balance of {snapshot_balance}"}), 400

    if intended_recipient not in snapshot_recipients:
        return jsonify({"error": "Recipient not authorized for this user"}), 400

    grammars[grammar_id] = {
        "intent": intent,
        "entropy": entropy,
        "expires_at": expires_at,
        "used": False,
        "session_id": session["session_id"],   # Bind grammar to session
        "username": username,                   # Bind grammar to user
        "required_keys": ["grammar_id", "intent", "entropy", "recipient_id", "amount"],
        "snapshot": {
            "balance": snapshot_balance,
            "allowed_recipients": snapshot_recipients,
            # Lock EXACT amount and recipient at issuance — any Burp modification = rejected
            "locked_amount": intended_amount,
            "locked_recipient": intended_recipient
        }
    }

    print(f"[AACL] Grammar issued → User: {username} | ID: {grammar_id} | Locked: ₹{intended_amount} → {intended_recipient}")
    return jsonify({
        "grammar_id": grammar_id,
        "intent": intent,
        "entropy": entropy,
        "expires_at": expires_at.isoformat() + "Z",
        "required_keys": ["recipient_id", "amount"]
    })


@app.route('/transfer', methods=['POST'])
@login_required  # ← Authentication gate enforced here too
def execute_transfer():
    """
    Execution & Validation — Paper Section 6.3.
    Full AACL acceptance condition:
    Accept(w) = w ∈ L(Ai) ∧ Ci(w, Si) ∧ ¬Used_i ∧ t < Ti
    """
    data = request.get_json(silent=True) or {}
    print(f"\n[AACL DEBUG] Received payload: {data}")

    # ── Step 1: Grammar Lookup ──────────────────────────────
    g_id = data.get("grammar_id")
    if not g_id or g_id not in grammars:
        return jsonify({"error": "Invalid grammar instance"}), 403

    g = grammars[g_id]

    # ── Step 1b: Session Binding Check ─────────────────────
    # Ensures grammar can't be used across sessions or users
    if g["session_id"] != session["session_id"]:
        print("[AACL] SESSION MISMATCH → REJECTED")
        return jsonify({"error": "Grammar not valid for current session"}), 403

    if g["username"] != session["username"]:
        print("[AACL] USER MISMATCH → REJECTED")
        return jsonify({"error": "Grammar not valid for current user"}), 403

    # ── Step 2: Single-Use Check (¬Used_i) ─────────────────
    if g["used"]:
        return jsonify({"error": "Grammar already consumed (replay blocked)"}), 403

    # ── Step 3: Expiration Check (t < Ti) ──────────────────
    if datetime.now(timezone.utc) > g["expires_at"]:
        return jsonify({"error": "Grammar expired"}), 403

    # ── Step 4: Intent + Entropy Verification ───────────────
    if g["intent"] != data.get("intent") or g["entropy"] != data.get("entropy"):
        return jsonify({"error": "Intent or entropy mismatch"}), 403

    # ── Step 5: Structural Validation — keys(w) = Σi ───────
    if set(data.keys()) != set(g["required_keys"]):
        return jsonify({"error": "Structural mutation detected"}), 403

    # ── Step 6: Semantic Validation — Ci(w, Si) ────────────
    try:
        amount = float(data["amount"])
        recipient = data["recipient_id"]
    except (ValueError, KeyError):
        return jsonify({"error": "Invalid parameters"}), 403

    locked_amount    = g["snapshot"]["locked_amount"]
    locked_recipient = g["snapshot"]["locked_recipient"]

    print(f"[AACL DEBUG] Received → amount: {amount}, recipient: {recipient}")
    print(f"[AACL DEBUG] Locked   → amount: {locked_amount}, recipient: {locked_recipient}")

    # ── Amount tamper check ─────────────────────────────────
    # Any Burp modification to amount will mismatch the locked value
    if amount != locked_amount:
        print(f"[AACL] AMOUNT TAMPERED → received {amount}, locked {locked_amount} → REJECTED")
        return jsonify({
            "error": "Structural mutation detected: amount has been tampered"
        }), 403

    # ── Recipient tamper check ──────────────────────────────
    
    if recipient != locked_recipient:
        print(f"[AACL] RECIPIENT TAMPERED → received {recipient}, locked {locked_recipient} → REJECTED")
        return jsonify({
            "error": "Structural mutation detected: recipient has been tampered"
        }), 403

    # ── Safety net: balance check against snapshot ──────────
    # Ctransfer(w, Si) = amount(w) <= balance(Si)  [Paper Section 5.5]
    if amount > g["snapshot"]["balance"]:
        print("[AACL] AMOUNT EXCEEDS SNAPSHOT BALANCE → REJECTED")
        return jsonify({"error": f"Amount exceeds authorized balance"}), 403

    
    g["used"] = True

    # Update the live user balance (post-execution state update)
    username = session["username"]
    users[username]["balance"] -= amount

    print(f"[AACL] SUCCESS → ₹{amount} transferred to {recipient} by {username}")
    return jsonify({
        "success": True,
        "message": f"✅ Transferred ₹{amount} to {recipient}. Grammar invalidated.",
        "remaining_balance": users[username]["balance"]
    })


# ================================================
# Optional: View current session info (debug)
# ================================================
@app.route('/debug/session', methods=['GET'])
@login_required
def debug_session():
    return jsonify({
        "username": session.get("username"),
        "session_id": session.get("session_id"),
        "balance": users[session["username"]]["balance"]
    })


if __name__ == '__main__':
    print("🚀 AACL Prototype — Authentication Layer Active")
    print("→ Pre-seeded users: alice / alice123 | bob / bob123")
    print("→ All AACL endpoints require login first")
    app.run(debug=True, port=5000)