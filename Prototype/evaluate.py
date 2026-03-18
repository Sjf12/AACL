# ================================================
# AACL EVALUATION SCRIPT
# 5000 requests across 5 attack categories + valid
# Matches paper Section 7 experimental methodology
# ================================================

import requests
import time
import statistics
import json
import copy
from collections import defaultdict

BASE_URL = "http://localhost:5000"
RUNS_PER_CATEGORY = 1000   # 5 categories × 1000 = 5000 total requests
REPEAT_RUNS = 5            # 5 repetitions of full suite for variance analysis

# ================================================
# Result tracking
# ================================================
results = defaultdict(lambda: {
    "total": 0,
    "correct": 0,        # Expected outcome matched
    "incorrect": 0,      # Unexpected outcome
    "latencies": [],
    "errors": []
})

# ================================================
# Session helpers
# ================================================

def get_session(username, password):
    """Create an authenticated session and return it."""
    s = requests.Session()
    try:
        res = s.post(f"{BASE_URL}/auth/login", json={
            "username": username,
            "password": password
        })
        print(f"[AUTH DEBUG] Login status: {res.status_code}")
        print(f"[AUTH DEBUG] Login response: {res.text[:200]}")
        if res.status_code != 200:
            raise RuntimeError(f"Login HTTP {res.status_code} for {username}: {res.text}")
        data = res.json()
        if not data.get("success"):
            raise RuntimeError(f"Login rejected for {username}: {data}")
        return s
    except requests.exceptions.JSONDecodeError:
        raise RuntimeError(f"Login response not JSON for {username}: {res.text[:200]}")


def reset_balance(session, username, amount):
    """
    Reset user balance via direct endpoint for clean test runs.
    Calls the debug reset route added to app for evaluation purposes.
    """
    res = session.post(f"{BASE_URL}/debug/reset_balance", json={
        "username": username,
        "balance": amount
    })
    print(f"[INFO] Balance reset for {username} → ₹{amount} (status {res.status_code})")


def issue_grammar(session, amount, recipient):
    """Issue a grammar and return full response + latency."""
    start = time.perf_counter()
    res = session.post(f"{BASE_URL}/aacl/issue/transfer", json={
        "amount": amount,
        "recipient_id": recipient
    })
    latency = (time.perf_counter() - start) * 1000
    return res.json(), latency, res.status_code


def execute_transfer(session, payload):
    """Submit a transfer payload and return response + latency."""
    start = time.perf_counter()
    res = session.post(f"{BASE_URL}/transfer", json=payload)
    latency = (time.perf_counter() - start) * 1000
    return res.json(), latency, res.status_code


def build_valid_payload(grammar):
    """Build a correct payload from an issued grammar."""
    return {
        "grammar_id": grammar["grammar_id"],
        "intent":     grammar["intent"],
        "entropy":    grammar["entropy"],
        "recipient_id": "user-123",
        "amount":     100
    }

# ================================================
# Test Categories
# ================================================

def test_valid_request(session, n):
    """
    Category 1: Valid requests — should all succeed (200).
    Baseline for latency comparison.
    """
    cat = "valid_request"
    print(f"\n[TEST] Category 1: Valid Requests ({n} runs)...")

    for i in range(n):
        try:
            grammar, issue_lat, issue_status = issue_grammar(session, 100, "user-123")
            if issue_status != 200:
                results[cat]["incorrect"] += 1
                results[cat]["errors"].append(f"Run {i}: issuance failed ({issue_status})")
                results[cat]["total"] += 1
                continue

            payload = build_valid_payload(grammar)
            resp, exec_lat, status = execute_transfer(session, payload)

            results[cat]["latencies"].append(issue_lat + exec_lat)
            results[cat]["total"] += 1

            if status == 200 and resp.get("success"):
                results[cat]["correct"] += 1
            else:
                results[cat]["incorrect"] += 1
                results[cat]["errors"].append(f"Run {i}: unexpected rejection — {resp}")

        except Exception as e:
            results[cat]["total"] += 1
            results[cat]["incorrect"] += 1
            results[cat]["errors"].append(f"Run {i}: exception — {e}")

    _print_category_summary(cat, expected_pass=True)


def test_replay_attack(session, n):
    """
    Category 2: Replay attack — resubmit same grammar twice.
    Second submission must be rejected (403).
    """
    cat = "replay_attack"
    print(f"\n[TEST] Category 2: Replay Attack ({n} runs)...")

    for i in range(n):
        try:
            grammar, _, issue_status = issue_grammar(session, 100, "user-123")
            if issue_status != 200:
                results[cat]["total"] += 1
                results[cat]["incorrect"] += 1
                continue

            payload = build_valid_payload(grammar)

            # First submission — should succeed
            execute_transfer(session, payload)

            # Replay — must be rejected
            start = time.perf_counter()
            resp, exec_lat, status = execute_transfer(session, payload)
            results[cat]["latencies"].append((time.perf_counter() - start) * 1000)
            results[cat]["total"] += 1

            if status == 403:
                results[cat]["correct"] += 1
            else:
                results[cat]["incorrect"] += 1
                results[cat]["errors"].append(f"Run {i}: replay was NOT rejected — {resp}")

        except Exception as e:
            results[cat]["total"] += 1
            results[cat]["incorrect"] += 1
            results[cat]["errors"].append(f"Run {i}: exception — {e}")

    _print_category_summary(cat, expected_pass=False)


def test_amount_tampering(session, n):
    """
    Category 3: Amount tampering — change amount after grammar issuance.
    Simulates Burp Suite interception modifying the amount field.
    Must be rejected (403).
    """
    cat = "amount_tampering"
    print(f"\n[TEST] Category 3: Amount Tampering ({n} runs)...")

    tampered_amounts = [1, 50, 99, 999, 9999, 0, -100, 0.01]

    for i in range(n):
        try:
            grammar, _, issue_status = issue_grammar(session, 100, "user-123")
            if issue_status != 200:
                results[cat]["total"] += 1
                results[cat]["incorrect"] += 1
                continue

            payload = build_valid_payload(grammar)

            # Tamper: change amount to something different from what was locked
            tampered = tampered_amounts[i % len(tampered_amounts)]
            payload["amount"] = tampered

            start = time.perf_counter()
            resp, exec_lat, status = execute_transfer(session, payload)
            results[cat]["latencies"].append((time.perf_counter() - start) * 1000)
            results[cat]["total"] += 1

            if status == 403:
                results[cat]["correct"] += 1
            else:
                results[cat]["incorrect"] += 1
                results[cat]["errors"].append(
                    f"Run {i}: tampered amount {tampered} was NOT rejected — {resp}"
                )

        except Exception as e:
            results[cat]["total"] += 1
            results[cat]["incorrect"] += 1
            results[cat]["errors"].append(f"Run {i}: exception — {e}")

    _print_category_summary(cat, expected_pass=False)


def test_recipient_tampering(session, n):
    """
    Category 4: Recipient tampering — change recipient_id after issuance.
    Simulates Burp Suite modifying the recipient field.
    Must be rejected (403).
    """
    cat = "recipient_tampering"
    print(f"\n[TEST] Category 4: Recipient Tampering ({n} runs)...")

    tampered_recipients = [
        "user-456",
        "attacker-001",
        "merchant-999",
        "",
        "' OR 1=1 --",
        "user-123-modified",
        "ADMIN",
        "../etc/passwd"
    ]

    for i in range(n):
        try:
            grammar, _, issue_status = issue_grammar(session, 100, "user-123")
            if issue_status != 200:
                results[cat]["total"] += 1
                results[cat]["incorrect"] += 1
                continue

            payload = build_valid_payload(grammar)

            # Tamper: change recipient to something different from what was locked
            tampered = tampered_recipients[i % len(tampered_recipients)]
            payload["recipient_id"] = tampered

            start = time.perf_counter()
            resp, exec_lat, status = execute_transfer(session, payload)
            results[cat]["latencies"].append((time.perf_counter() - start) * 1000)
            results[cat]["total"] += 1

            if status == 403:
                results[cat]["correct"] += 1
            else:
                results[cat]["incorrect"] += 1
                results[cat]["errors"].append(
                    f"Run {i}: tampered recipient '{tampered}' was NOT rejected — {resp}"
                )

        except Exception as e:
            results[cat]["total"] += 1
            results[cat]["incorrect"] += 1
            results[cat]["errors"].append(f"Run {i}: exception — {e}")

    _print_category_summary(cat, expected_pass=False)


def test_structural_mutation(session, n):
    """
    Category 5: Structural mutation — add/remove/rename keys.
    Covers: parameter injection, parameter removal, key renaming.
    Must be rejected (403).
    """
    cat = "structural_mutation"
    print(f"\n[TEST] Category 5: Structural Mutation ({n} runs)...")

    def mutations(payload):
        """Generate different structural mutations of a payload."""
        # Injection: add extra key
        p1 = copy.deepcopy(payload)
        p1["injected_key"] = "malicious_value"

        # Removal: drop required key
        p2 = copy.deepcopy(payload)
        del p2["entropy"]

        # Rename: change key name
        p3 = copy.deepcopy(payload)
        p3["amount_"] = p3.pop("amount")

        # Empty payload
        p4 = {}

        # Only grammar_id
        p5 = {"grammar_id": payload["grammar_id"]}

        # Duplicate key simulation (last value wins in JSON)
        p6 = copy.deepcopy(payload)
        p6["extra_amount"] = 9999

        return [p1, p2, p3, p4, p5, p6]

    for i in range(n):
        try:
            grammar, _, issue_status = issue_grammar(session, 100, "user-123")
            if issue_status != 200:
                results[cat]["total"] += 1
                results[cat]["incorrect"] += 1
                continue

            payload = build_valid_payload(grammar)
            mut_list = mutations(payload)
            mutated = mut_list[i % len(mut_list)]

            start = time.perf_counter()
            resp, exec_lat, status = execute_transfer(session, mutated)
            results[cat]["latencies"].append((time.perf_counter() - start) * 1000)
            results[cat]["total"] += 1

            if status == 403:
                results[cat]["correct"] += 1
            else:
                results[cat]["incorrect"] += 1
                results[cat]["errors"].append(
                    f"Run {i}: structural mutation was NOT rejected — {resp}"
                )

        except Exception as e:
            results[cat]["total"] += 1
            results[cat]["incorrect"] += 1
            results[cat]["errors"].append(f"Run {i}: exception — {e}")

    _print_category_summary(cat, expected_pass=False)


def test_baseline(session, n):
    """
    Baseline: Direct transfer with no AACL grammar (no issuance step).
    Measures raw business logic execution latency for overhead comparison.
    Paper Section 7.2.3.
    """
    cat = "baseline"
    print(f"\n[TEST] Baseline: No AACL ({n} runs)...")

    for i in range(n):
        try:
            start = time.perf_counter()
            res = session.post(f"{BASE_URL}/baseline/transfer", json={
                "amount": 100,
                "recipient_id": "user-123"
            })
            latency = (time.perf_counter() - start) * 1000
            results[cat]["latencies"].append(latency)
            results[cat]["total"] += 1
            results[cat]["correct"] += 1
        except Exception as e:
            results[cat]["total"] += 1
            results[cat]["incorrect"] += 1
            results[cat]["errors"].append(str(e))

    _print_category_summary(cat, expected_pass=True)


# ================================================
# Helpers
# ================================================

def _print_category_summary(cat, expected_pass):
    r = results[cat]
    total = r["total"]
    correct = r["correct"]
    lats = r["latencies"]

    rejection_rate = (correct / total * 100) if total > 0 else 0
    mean_lat = statistics.mean(lats) if lats else 0
    std_lat  = statistics.stdev(lats) if len(lats) > 1 else 0

    label = "Pass Rate" if expected_pass else "Rejection Rate"
    print(f"  {label}: {correct}/{total} ({rejection_rate:.1f}%)")
    print(f"  Mean latency: {mean_lat:.2f} ms | Std Dev: {std_lat:.2f} ms")
    if r["errors"][:3]:
        print(f"  Sample errors: {r['errors'][:3]}")


def print_final_report():
    print("\n" + "=" * 65)
    print("AACL EVALUATION REPORT — 5000 Requests")
    print("=" * 65)

    categories = [
        ("valid_request",       "Valid Requests",         True),
        ("replay_attack",       "Replay Attack",          False),
        ("amount_tampering",    "Amount Tampering",       False),
        ("recipient_tampering", "Recipient Tampering",    False),
        ("structural_mutation", "Structural Mutation",    False),
    ]

    total_requests  = 0
    total_correct   = 0
    all_issue_lats  = []
    all_valid_lats  = []
    all_invalid_lats = []

    print(f"\n{'Category':<25} {'Total':>6} {'Correct':>8} {'Rate':>7} {'Mean(ms)':>10} {'Std(ms)':>8}")
    print("-" * 65)

    for key, label, is_pass in categories:
        r = results[key]
        total   = r["total"]
        correct = r["correct"]
        lats    = r["latencies"]
        rate    = (correct / total * 100) if total > 0 else 0
        mean    = statistics.mean(lats) if lats else 0
        std     = statistics.stdev(lats) if len(lats) > 1 else 0

        total_requests += total
        total_correct  += correct

        if is_pass:
            all_valid_lats.extend(lats)
        else:
            all_invalid_lats.extend(lats)

        print(f"{label:<25} {total:>6} {correct:>8} {rate:>6.1f}% {mean:>10.2f} {std:>8.2f}")

    print("-" * 65)
    overall_rate = (total_correct / total_requests * 100) if total_requests > 0 else 0
    print(f"{'TOTAL':<25} {total_requests:>6} {total_correct:>8} {overall_rate:>6.1f}%")

    print("\n── Latency Summary ────────────────────────────────────────")

    if all_valid_lats:
        print(f"  Valid execution   → Mean: {statistics.mean(all_valid_lats):.2f} ms | "
              f"Std: {statistics.stdev(all_valid_lats):.2f} ms | "
              f"Min: {min(all_valid_lats):.2f} ms | Max: {max(all_valid_lats):.2f} ms")

    if all_invalid_lats:
        print(f"  Invalid/Attack    → Mean: {statistics.mean(all_invalid_lats):.2f} ms | "
              f"Std: {statistics.stdev(all_invalid_lats):.2f} ms | "
              f"Min: {min(all_invalid_lats):.2f} ms | Max: {max(all_invalid_lats):.2f} ms")

    if results["baseline"]["latencies"]:
        blats = results["baseline"]["latencies"]
        print(f"  Baseline (no AACL)→ Mean: {statistics.mean(blats):.2f} ms | "
              f"Std: {statistics.stdev(blats):.2f} ms")

        if all_valid_lats:
            overhead = statistics.mean(all_valid_lats) - statistics.mean(blats)
            overhead_pct = (overhead / statistics.mean(blats)) * 100
            print(f"  AACL Overhead     → +{overhead:.2f} ms (+{overhead_pct:.1f}%)")

    print("\n── Attack Resistance Summary ───────────────────────────────")
    attack_cats = [
        ("replay_attack",       "Replay Attack"),
        ("amount_tampering",    "Amount Tampering"),
        ("recipient_tampering", "Recipient Tampering"),
        ("structural_mutation", "Structural Mutation"),
    ]
    for key, label in attack_cats:
        r = results[key]
        total = r["total"]
        blocked = r["correct"]
        bypassed = r["incorrect"]
        rate = (blocked / total * 100) if total > 0 else 0
        print(f"  {label:<25} Blocked: {blocked}/{total} ({rate:.1f}%) | "
              f"Bypassed: {bypassed}")

    print("\n── Paper Comparison (Table 2) ──────────────────────────────")
    paper_values = {
        "Grammar Issuance":      (11.26, 1.98),
        "Validation (valid)":    (8.74,  1.52),
        "Validation (invalid)":  (8.31,  1.47),
        "Baseline":              (3.92,  0.96),
    }
    print(f"  {'Operation':<25} {'Paper Mean':>12} {'Measured Mean':>14}")
    print(f"  {'-'*52}")

    measured_valid   = statistics.mean(all_valid_lats) if all_valid_lats else 0
    measured_invalid = statistics.mean(all_invalid_lats) if all_invalid_lats else 0
    measured_baseline= statistics.mean(results["baseline"]["latencies"]) if results["baseline"]["latencies"] else 0

    measured = {
        "Validation (valid)":   measured_valid,
        "Validation (invalid)": measured_invalid,
        "Baseline":             measured_baseline,
    }
    for op, (pmean, pstd) in paper_values.items():
        mval = measured.get(op, 0)
        print(f"  {op:<25} {pmean:>10.2f}ms {mval:>12.2f}ms")

    print("\n" + "=" * 65)
    print("Evaluation complete.")
    print("=" * 65)


def save_results_json():
    """Save raw results to JSON for further analysis."""
    export = {}
    for cat, data in results.items():
        export[cat] = {
            "total": data["total"],
            "correct": data["correct"],
            "incorrect": data["incorrect"],
            "mean_latency_ms": round(statistics.mean(data["latencies"]), 4) if data["latencies"] else 0,
            "std_latency_ms":  round(statistics.stdev(data["latencies"]), 4) if len(data["latencies"]) > 1 else 0,
            "min_latency_ms":  round(min(data["latencies"]), 4) if data["latencies"] else 0,
            "max_latency_ms":  round(max(data["latencies"]), 4) if data["latencies"] else 0,
            "sample_errors":   data["errors"][:5]
        }
    with open("evaluation_results.json", "w") as f:
        json.dump(export, f, indent=2)
    print("\n[INFO] Raw results saved to evaluation_results.json")


# ================================================
# Main
# ================================================

if __name__ == "__main__":
    print("=" * 65)
    print("AACL Evaluation Script — 5000 Requests")
    print(f"Target: {BASE_URL}")
    print("=" * 65)

    # Check server is up
    try:
        r = requests.get(f"{BASE_URL}/auth/status", timeout=3)
        print(f"[INFO] Server reachable — status {r.status_code}")
        print(f"[INFO] Auth status response: {r.text[:100]}")
    except requests.exceptions.ConnectionError:
        print(f"[ERROR] Cannot connect to {BASE_URL}")
        print("→ Make sure app.py is running: python3 app.py")
        exit(1)
    except Exception as e:
        print(f"[ERROR] Server not reachable: {e}")
        exit(1)

    # Login
    print("\n[AUTH] Logging in as alice...")
    try:
        session = get_session("alice", "alice123")
        print("[AUTH] Login successful")
    except Exception as e:
        print(f"[ERROR] {e}")
        exit(1)

    # Reset alice balance before evaluation starts (she needs enough for 1000 valid transfers)
    reset_balance(session, "alice", 999999)

    # Run all test categories
    test_valid_request(session,       RUNS_PER_CATEGORY)
    test_replay_attack(session,       RUNS_PER_CATEGORY)
    test_amount_tampering(session,    RUNS_PER_CATEGORY)
    test_recipient_tampering(session, RUNS_PER_CATEGORY)
    test_structural_mutation(session, RUNS_PER_CATEGORY)
    test_baseline(session,            RUNS_PER_CATEGORY)

    # Print and save
    print_final_report()
    save_results_json()