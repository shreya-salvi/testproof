# reporter.py
# LAYER 5 of TestProof: the Reporter.
# Reads config.yaml, runs all three layers, prints one combined trust scorecard.
#
# Verdicts:
#   TRUSTED - passed every layer that ran
#   FAKE    - failed a hard, deterministic check (Layer 1 or Layer 2)
#   WEAK    - survived L1 & L2, but the AI reviewer (Layer 3) flagged a soft concern
#
# Funnel: the expensive Layer 3 (API calls) only runs on tests that survive the
# cheap layers, and it degrades gracefully if no API key is set.

import yaml
from scanner import scan_file
from mutator import run_mutation_check


def load_config():
    with open("config.yaml") as f:
        return yaml.safe_load(f)


def run_layer3(test_file, survivors):
    """Run the AI reviewer only on tests that passed Layers 1 and 2.

    Returns a dict {name: (verdict, reason)} or None if Layer 3 is unavailable
    (e.g. no API key / network issue), so the report still prints without it.
    """
    if not survivors:
        return {}
    try:
        from ai_judge import get_test_sources, judge_test
        import time

        sources = get_test_sources(test_file)
        results = {}
        for name in survivors:
            code = sources.get(name)
            if code is None:
                continue
            results[name] = judge_test(code)
            time.sleep(4)  # stay under the free-tier rate limit
        return results
    except Exception as e:
        print(f"  (Layer 3 skipped: {e})\n")
        return None


def build_report(app_file, test_file):
    # Layer 1: reading the tests (cheap, no run)
    layer1_list = scan_file(test_file)
    layer1 = {name: (verdict, reason) for name, verdict, reason in layer1_list}

    # Layer 2: breaking the app (mutation testing)
    layer2 = run_mutation_check(app_file, test_file)

    # Funnel: only tests that survived L1 & L2 are worth the expensive L3.
    survivors = [
        name for name in layer1
        if layer1[name][0] == "OK" and layer2.get(name, ("OK", ""))[0] == "OK"
    ]

    # Layer 3: AI reviewer (may be None if unavailable)
    layer3 = run_layer3(test_file, survivors)
    layer3_ran = layer3 is not None

    report = {}
    for name in layer1:
        l1_verdict, l1_reason = layer1[name]
        l2_verdict, l2_reason = layer2.get(name, ("OK", ""))
        l3 = (layer3 or {}).get(name)  # (STRONG/WEAK, reason) or None

        if l1_verdict == "FAKE":
            report[name] = {
                "verdict": "FAKE",
                "detail": f"Layer 1: {l1_reason}",
                "l3": None,
            }
        elif l2_verdict == "FAKE":
            report[name] = {
                "verdict": "FAKE",
                "detail": f"Layer 2: {l2_reason}",
                "l3": None,
            }
        elif l3 is not None and l3[0] == "WEAK":
            report[name] = {
                "verdict": "WEAK",
                "detail": f"Layer 3 (AI): {l3[1]}",
                "l3": l3,
            }
        else:
            report[name] = {
                "verdict": "TRUSTED",
                "detail": "passed every layer",
                "l3": l3,
            }

    return report, layer3_ran


def main():
    cfg = load_config()
    app_file = cfg["app_file"]
    test_file = cfg["test_file"]

    report, layer3_ran = build_report(app_file, test_file)

    total = len(report)
    trusted = sum(1 for r in report.values() if r["verdict"] == "TRUSTED")
    percent = round(trusted / total * 100) if total else 0

    print("\n" + "=" * 55)
    print(f"  TestProof Report  -  {test_file}")
    print("=" * 55 + "\n")

    labels = {"TRUSTED": "TRUSTED", "FAKE": "FAKE   ", "WEAK": "WEAK   "}
    for name, r in report.items():
        print(f"  {labels[r['verdict']]}  {name}")
        if r["verdict"] == "TRUSTED":
            print("           -> passed Layer 1 (reads) + Layer 2 (breaks app)")
            if r["l3"]:
                print(f"           -> Layer 3 (AI): STRONG - {r['l3'][1]}")
            elif layer3_ran:
                print("           -> Layer 3 (AI): not reviewed")
        else:
            print(f"           -> {r['detail']}")
        print()

    weak = sum(1 for r in report.values() if r["verdict"] == "WEAK")
    fake = sum(1 for r in report.values() if r["verdict"] == "FAKE")

    print("-" * 55)
    print(f"  Trust score: {trusted} of {total} tests trustworthy ({percent}%)")
    print(f"  Breakdown: {trusted} trusted / {weak} weak / {fake} fake")
    l3_note = "L3 AI judge" if layer3_ran else "L3 AI judge (skipped)"
    print(f"  Layers: L1 static + L2 mutation + {l3_note}")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    main()