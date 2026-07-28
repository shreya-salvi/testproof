# reporter.py
# LAYER 5 of TestProof: the Reporter.
# Reads config.yaml, runs both layers, prints one combined trust scorecard.
# A test is TRUSTED only if it passes BOTH layers.

import yaml
from scanner import scan_file
from mutator import run_mutation_check


def load_config():
    with open("config.yaml") as f:
        return yaml.safe_load(f)


def build_report(app_file, test_file):
    # Layer 1: reading the tests
    layer1_list = scan_file(test_file)
    layer1 = {name: (verdict, reason) for name, verdict, reason in layer1_list}

    # Layer 2: breaking the app
    layer2 = run_mutation_check(app_file, test_file)

    report = {}
    for name in layer1:
        l1_verdict, l1_reason = layer1[name]
        l2_verdict, l2_reason = layer2.get(name, ("OK", ""))

        if l1_verdict == "OK" and l2_verdict == "OK":
            report[name] = ("TRUSTED", "passed both layers")
        elif l1_verdict == "FAKE":
            report[name] = ("FAKE", f"Layer 1: {l1_reason}")
        else:
            report[name] = ("FAKE", f"Layer 2: {l2_reason}")

    return report


def main():
    cfg = load_config()
    app_file = cfg["app_file"]
    test_file = cfg["test_file"]

    report = build_report(app_file, test_file)

    total = len(report)
    trusted = sum(1 for v, _ in report.values() if v == "TRUSTED")
    percent = round(trusted / total * 100) if total else 0

    print("\n" + "=" * 55)
    print(f"  TestProof Report  -  {test_file}")
    print("=" * 55 + "\n")

    for name, (verdict, reason) in report.items():
        label = "TRUSTED" if verdict == "TRUSTED" else "FAKE   "
        print(f"  {label}  {name}")
        print(f"           -> {reason}\n")

    print("-" * 55)
    print(f"  Trust score: {trusted} of {total} tests trustworthy ({percent}%)")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    main()