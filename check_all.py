import json
import subprocess
import sys

from src.setup import DATA_FILE


def check_tests():
    """Run all the automated tests."""
    result = subprocess.run([sys.executable, "-m", "pytest", "-q"])
    return result.returncode == 0, "see the test summary above"


def check_data():
    """Check that the data file follows all the rules."""
    from seed import validate

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    errors, _warnings = validate(data)
    return not errors, f"{len(errors)} errors in the data file"


def check_search():
    """Check that the document search finds the right document."""
    from src.rag.search import search

    cards = search("my TV shows nothing")
    sources = [card["source"] for card in cards]
    ok = any(name in sources for name in ("no-signal.md", "channel-not-visible.md"))
    return ok, "top results: " + ", ".join(sources)


def check_guardrail():
    """Check the guardrail on its evaluation messages (it should get at least 21 of 24)."""
    from evaluation.guardrail_eval import CASES
    from src.agent.guardrail import check_escalation

    right = 0
    for message, expected in CASES:
        found = check_escalation(message)
        right += (found["reason"] if found else None) == expected
    return right >= 21, f"{right} of {len(CASES)} correct"


def check_ai():
    """Send one short message to the real AI (uses 1 of your daily requests)."""
    from src.agent.llm import get_client, get_model_name

    client, model = get_client(), get_model_name()
    reply = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Say hello in one short sentence."}],
    )
    text = (reply.choices[0].message.content or "").strip()
    return bool(text), text[:80]


def main():
    checks = [
        ("Automated tests", check_tests),
        ("Data file rules", check_data),
        ("Document search", check_search),
        ("Guardrail score", check_guardrail),
    ]
    if "--with-ai" in sys.argv:
        checks.append(("Real AI answers", check_ai))

    results = []
    for name, function in checks:
        try:
            ok, detail = function()
        except Exception as error:
            ok, detail = False, f"error: {error}"
        results.append((name, ok, detail))

    print("\n" + "=" * 50)
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")
    print("=" * 50)
    if all(ok for _, ok, _ in results):
        print("Everything works.")
    else:
        print("Something failed. Copy the lines above and show them to Claude.")
        sys.exit(1)


if __name__ == "__main__":
    main()