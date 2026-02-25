# AACL – Artificial Adaptive Control Language

AACL (Artificial Adaptive Control Language) is a language-theoretic state-transition enforcement framework for web applications.

Instead of validating only authentication tokens or headers, AACL treats every sensitive request as a sentence in a server-issued, single-use grammar. Requests are validated using deterministic finite automata (DFA) before reaching application business logic.

Note: This sample website is progress and is not implemented based in AACL model full fledgedly.

---

## 🚀 Motivation

Modern web security mechanisms (CSRF tokens, nonces, JWTs) validate request authenticity and freshness. However, they do not formally constrain whether a request represents a valid state transition in the application.

AACL addresses this gap by enforcing:

- Structural validity
- State consistency
- Single-use constraints
- Deterministic transition enforcement

The goal is to reduce unauthorized state transitions, replay attacks, and structural tampering.

---

## 🧠 Core Idea

AACL models a web application as a state machine.

Let:

- **S** = Set of application states  
- **Gₛ** = Grammar issued for state `s`  
- **L(Gₛ)** = Valid request language  
- **T(s, r)** = State transition function  

A request `r` is valid iff:

1. `r ∈ L(Gₛ)`
2. `T(s, r)` is defined
3. `r` is unused (single-use grammar)
4. `r` is within validity window

If any condition fails, the request is rejected before business logic execution.

---
## 🏗 Starting CryptoVault

1. **Firstly, make sure to install flask python package. If not then use pip3 install flask / pip install flask**
2. **Start the server using the following command:
   - cd CryptoVault && python3 app.py
3. Then access the website in the following URL: http://loclahost:8000

---

## 🏗 Architecture

The system consists of:

1. **Client**
   - Requests grammar before sensitive actions
   - Constructs payload matching server-issued grammar

2. **AACL Gateway**
   - DFA-based validation engine
   - Checks structure, required keys, entropy, expiry
   - Enforces single-use constraints

3. **Application Server**
   - Executes business logic only after AACL validation

Optional:
- AI-assisted grammar refinement (experimental)

---

## 🔒 Security Properties

AACL provides:

- Replay resistance (single-use grammar)
- Structural tamper detection
- State-transition enforcement
- Reduced attack surface for control-flow attacks

AACL complements, but does not replace:

- Input sanitization
- Output encoding
- Parameterized queries
- Authentication systems

---

## 🧪 Proof-of-Concept Demo

The repository includes a sample transactional web application:

- Multi-user login
- Dashboard with dynamic state (user + balance)
- Actions:
  - Change Password ( Doesn't have specific user mechanism )
  - Transfer Money

All sensitive actions are protected by AACL.

### Test Cases

- Replay attack → Rejected
- Modified payload → Rejected
- Expired grammar → Rejected
- Valid request → Executed

---

## ⚙️ Tech Stack

- Python (Flask)
- HTML / CSS / JavaScript
- DFA-based validation logic
- Ephemeral grammar issuance

---

## 📌 Threat Model

Attacker can:

- Observe requests
- Replay requests
- Modify parameters
- Attempt structural tampering

Attacker cannot:

- Break cryptographic primitives
- Compromise server memory

---

## 📊 Current Status

- Phase 1: Language specification ✅
- Phase 2: AACL Gateway + demo app ✅
- Phase 3: Client-side SDK ✅
- Phase 4: Formal DFA validation (On-Going Research)
- Phase 5: Adaptive grammar refinement using AI (future work)

---

## 📖 Research Direction

AACL explores the idea that:

> Security failures in web applications often reduce to unauthorized state transitions.

Future work includes:

- Formal proofs of replay resistance
- Complexity analysis
- Scalability evaluation
- Semantic constraint extensions
- Boundary enforcement models (proxy / browser-side)

---

## ⚠️ Limitations

AACL does not inherently prevent:

- SQL injection
- XSS
- Business logic flaws
- Server-side authorization misconfiguration

It focuses on control-flow integrity and transition enforcement.

---

## 📄 License

This project is released for academic and research purposes.

---

## 👨‍💻 Author

Developed as an independent research project exploring language-theoretic approaches to web security.

---

