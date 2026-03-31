import json
import pathlib
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:8000"
ANALYZE_PATH = "/v1/cases/analyze"


def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def run_case(case_path: pathlib.Path) -> None:
    payload = json.loads(case_path.read_text(encoding="utf-8"))
    response = post_json(f"{BASE_URL}{ANALYZE_PATH}", payload)

    print("=" * 88)
    print(f"Case: {response.get('case_id')}")
    print(f"Recommendation: {response.get('recommendation')}")
    print(f"Confidence: {response.get('confidence')}")
    print(f"Missing Info: {response.get('missing_information')}")
    print(f"Uncertainty: {response.get('uncertainty_reasons')}")
    print("Policy Checks:")
    for check in response.get("policy_checks", []):
        print(f"- {check['rule_id']}: {check['status']}")
    print("Citations:")
    for citation in response.get("citations", []):
        print(f"- {citation['citation_id']} ({citation['doc_id']})")


def main() -> None:
    demo_dir = pathlib.Path(__file__).parent
    cases = [
        demo_dir / "case_approve.json",
        demo_dir / "case_abstain_missing_data.json",
    ]

    try:
        for case_path in cases:
            run_case(case_path)
    except urllib.error.URLError as exc:
        print("Could not reach API. Start the app first:")
        print("python -m uvicorn --app-dir C:/Users/rojab/MyData/credit-ai-platform app.main:app")
        print(f"Error: {exc}")


if __name__ == "__main__":
    main()
