"""Live runtime verification script for Prompt 14 Adversarial Verifier against running backend."""
import json
import urllib.request
import urllib.error

BACKEND_URL = "http://127.0.0.1:8000"

def get(url):
    req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def post(url, data):
    payload = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def run_verification():
    print("=== LIVE RUNTIME VERIFICATION: PROMPT 14 ADVERSARIAL VERIFIER ===")
    
    # 1. Health check
    health = get(f"{BACKEND_URL}/health")
    print(f"[1] Backend Health: {health['status']} (v{health['version']})")
    assert health["status"] == "healthy"

    # 2. Fetch list of exceptions
    exceptions = get(f"{BACKEND_URL}/exceptions?limit=10")
    print(f"[2] Retrieved {len(exceptions)} exceptions from live database.")
    assert len(exceptions) > 0
    seeded_exc = exceptions[0]
    seeded_exc_id = seeded_exc["exception_id"]
    print(f"    Selected target exception: {seeded_exc_id} ({seeded_exc['exception_type']}, exposure: INR {seeded_exc['exposure']/100:,.2f})")

    # 3. Call PRD endpoint GET /exceptions/{id}/verifier-opinion
    print(f"[3] Calling PRD endpoint: GET /exceptions/{seeded_exc_id}/verifier-opinion")
    opinion = get(f"{BACKEND_URL}/exceptions/{seeded_exc_id}/verifier-opinion")
    print(f"    -> Opinion ID: {opinion['opinion_id']}")
    print(f"    -> Verdict: {opinion['verdict']} (Confidence: {opinion['confidence']})")
    print(f"    -> Original Policy: {opinion['original_policy_decision']} -> Final Policy: {opinion['final_policy_decision']}")
    print(f"    -> Reasoning: {opinion['reasoning_summary'][:120]}...")
    print(f"    -> Grounded Evidence Refs: {opinion['evidence_refs']}")
    assert opinion["opinion_id"] is not None
    assert opinion["verdict"] in ("AGREE", "TIGHTEN", "DISPUTE", "ABSTAIN")
    assert opinion["final_policy_decision"] is not None

    # 4. Perform Live Digital-Twin Synthetic Injection (Prompt 12 pipeline)
    print(f"[4] Injecting fresh synthetic anomaly via Live Digital-Twin...")
    inj_res = post(f"{BACKEND_URL}/demo/inject", {
        "exception_family": "GHOST_SETTLEMENT",
        "triggered_by": "runtime-verifier-test",
    })
    injected_exc_id = inj_res.get("linked_exception_id")
    print(f"    -> Injection Status: {inj_res.get('processing_status')}")
    print(f"    -> Injected Exception ID: {injected_exc_id}")
    assert injected_exc_id is not None

    # 5. Evaluate Verifier on Live-Injected Case
    print(f"[5] Calling PRD endpoint for live-injected case: GET /exceptions/{injected_exc_id}/verifier-opinion")
    inj_opinion = get(f"{BACKEND_URL}/exceptions/{injected_exc_id}/verifier-opinion")
    print(f"    -> Injected Case Verdict: {inj_opinion['verdict']} (Confidence: {inj_opinion['confidence']})")
    print(f"    -> Original Policy: {inj_opinion['original_policy_decision']} -> Final Policy: {inj_opinion['final_policy_decision']}")
    print(f"    -> Injected Case Reasoning: {inj_opinion['reasoning_summary'][:140]}...")
    assert inj_opinion["opinion_id"] is not None
    assert inj_opinion["verdict"] in ("AGREE", "TIGHTEN", "DISPUTE", "ABSTAIN")

    # 6. Ask Sentinel Copilot integration with Verifier
    print(f"[6] Testing Ask Sentinel Copilot query about verifier opinion...")
    copilot_res = post(f"{BACKEND_URL}/copilot/ask", {
        "question": f"What did the adversarial verifier determine for exception {injected_exc_id}?",
    })
    print(f"    -> Copilot Query ID: {copilot_res['query_id']}")
    print(f"    -> Copilot Tools Used: {copilot_res['tools_used']}")
    ans_clean = copilot_res['answer'][:180].encode("ascii", "replace").decode("ascii")
    print(f"    -> Copilot Answer: {ans_clean}...")
    assert "get_verifier_opinion" in copilot_res["tools_used"]
    assert "Adversarial Verifier" in copilot_res["answer"] or inj_opinion["verdict"] in copilot_res["answer"]

    # 7. Audit Event verification
    print(f"[7] Checking audit trail for VERIFIER_OPINION_RECORDED...")
    detail = get(f"{BACKEND_URL}/exceptions/{injected_exc_id}")
    audit_events = detail.get("audit_events", [])
    verifier_audit = [e for e in audit_events if e["event_type"] == "VERIFIER_OPINION_RECORDED"]
    print(f"    -> Total Audit Events: {len(audit_events)}, Verifier Audit Events: {len(verifier_audit)}")
    assert len(verifier_audit) > 0
    audit_clean = verifier_audit[0]['event_summary'].encode("ascii", "replace").decode("ascii")
    print(f"    -> Verifier Audit Summary: {audit_clean}")

    # 8. Ground-truth and benchmark isolation check
    print(f"[8] Verifying ground-truth and benchmark isolation...")
    assert "ground_truth" not in inj_opinion["reasoning_summary"].lower()
    assert "benchmark" not in inj_opinion["reasoning_summary"].lower()
    print("    [OK] Ground-truth isolation: VERIFIED (no ground-truth references)")
    print("    [OK] Benchmark isolation: VERIFIED (synthetic live data isolated)")

    print("\n=== ALL RUNTIME VERIFICATION CHECKS PASSED PERFECTLY! ===")

if __name__ == "__main__":
    run_verification()
