from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import uuid
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'crypto-vault-secret-key-2026'

# Load users from users.txt (create this file in the same folder)
USERS = {}
try:
    with open('users.txt', 'r') as f:
        next(f)  # Skip header if present
        for line in f:
            if line.strip():
                uid, name, bal = line.strip().split('|')
                USERS[uid] = {"id": uid, "name": name, "balance": float(bal)}
except FileNotFoundError:
    print("Warning: users.txt not found! Using default users.")
    USERS = {
        "123": {"id": "123", "name": "Alice Johnson", "balance": 5000.00},
        "456": {"id": "456", "name": "Bob Smith", "balance": 2500.00},
        "789": {"id": "789", "name": "Charlie Lee", "balance": 10000.00}
    }

# In-memory grammar store
GRAMMARS = {}

def issue_grammar(intent, user_id):
    if user_id not in USERS:
        return None

    user = USERS[user_id]
    grammar_id = str(uuid.uuid4())
    entropy = f"entropy-{uuid.uuid4().hex[:12]}"
    expires_at = (datetime.utcnow() + timedelta(minutes=5)).isoformat() + "Z"
    state = f"AUTHENTICATED|USER_{user['id']}|BALANCE_{user['balance']:.2f}"

    required_keys = []
    if intent == "CHANGE_PASSWORD":
        required_keys = ["intent", "state", "entropy", "current_password", "new_password", "confirm_password"]
    elif intent == "TRANSFER_MONEY":
        required_keys = ["intent", "state", "entropy", "recipient_id", "amount", "memo"]

    grammar = {
        "grammar_id": grammar_id,
        "intent": intent,
        "state": state,
        "entropy": entropy,
        "expires_at": expires_at,
        "used": False,
        "required_keys": required_keys
    }
    GRAMMARS[grammar_id] = grammar

    return {
        "grammar_id": grammar_id,
        "intent": intent,
        "state": state,
        "entropy": entropy,
        "expires_at": expires_at,
        "required_keys": required_keys
    }

def validate_and_consume(payload):
    try:
        gid = payload["grammar_id"]
        data = payload["payload"]
    except KeyError:
        return False

    grammar = GRAMMARS.get(gid)
    if not grammar or grammar["used"]:
        return False

    if datetime.utcnow() > datetime.fromisoformat(grammar["expires_at"].rstrip("Z")):
        return False

    if data.get("intent") != grammar["intent"] or data.get("entropy") != grammar["entropy"]:
        return False

    if set(data.keys()) != set(grammar["required_keys"]):
        return False

    # Extract sender ID from state
    state_parts = grammar["state"].split("|USER_")
    if len(state_parts) < 2:
        return False
    sender_id = state_parts[1].split("|")[0]

    # Semantic checks
    if grammar["intent"] == "CHANGE_PASSWORD":
        if data["new_password"] != data["confirm_password"]:
            return False

    if grammar["intent"] == "TRANSFER_MONEY":
        amount = data.get("amount", 0)
        sender_balance = USERS[sender_id]["balance"]
        if amount > sender_balance:
            return False

        # Deduct balance
        USERS[sender_id]["balance"] -= amount

    grammar["used"] = True
    return True

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        if user_id in USERS:
            session['user_id'] = user_id
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid user selection", "error")
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = USERS.get(session['user_id'])
    if not user:
        return redirect(url_for('login'))
    return render_template('dashboard.html', user=user)

@app.route('/aacl/issue/<intent>', methods=['POST'])
def issue(intent):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    grammar = issue_grammar(intent, user_id)
    if not grammar:
        return jsonify({"error": "Invalid user"}), 400
    return jsonify(grammar)

@app.route('/aacl/execute', methods=['POST'])
def execute():
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"status": "ERROR", "message": "Invalid JSON"}), 400

    if validate_and_consume(payload):
        return jsonify({
            "status": "ACTION_EXECUTED",
            "message": "Success! Action performed."
        }), 200

    return jsonify({
        "status": "REJECTED",
        "message": "Invalid, expired, or already used request."
    }), 200

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)