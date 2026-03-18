# Evaluation & Results

## Overview
This section contains all experimental results for the AACL prototype (5000 requests total).

- **Attack simulation**: 4000 adversarial requests (replay + tampering)
- **Latency measurement**: 5000 valid + invalid requests
- **Environment**: Flask + Python 3.13.7 on localhost (Apple M4, 16 GB RAM)


---

## 7.2 Attack Resistance (4000 Attacks)

| Attack Category          | Total Requests | Blocked | Bypass Rate |
|--------------------------|----------------|---------|-------------|
| Valid Requests           | 1000           | -       | -           |
| Replay Attack            | 1000           | 1000    | 0.0%        |
| Amount Tampering         | 1000           | 1000    | 0.0%        |
| Recipient Tampering      | 1000           | 1000    | 0.0%        |
| Structural Mutation      | 1000           | 1000    | 0.0%        |
| **Total (attacks only)** | **4000**       | **4000**| **0.0%**    |

**All attacks rejected deterministically** before business logic execution.

---

## 7.2 Latency Summary (5000 Runs)

| Operation              | Mean (ms) | Std Dev (ms) |
|------------------------|-----------|--------------|
| Grammar Issuance       | 0.93      | 0.18         |
| Validation (valid)     | 0.66      | 0.26         |
| Validation (invalid)   | 0.78      | 0.24         |
| Baseline (no AACL)     | 0.66      | 0.26         |

**Total overhead**: ~0.93 ms per sensitive action (acceptable for high-value operations).

---

## 7.3 Complexity
- Structural validation: **O(n)** (key-set equality)
- Semantic validation: **O(1)** (locked value comparison)

Empirical results confirm linear scaling with number of request parameters.

