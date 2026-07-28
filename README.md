# TestProof

**Proves your automated tests aren't lying.**

A test showing a green checkmark is *supposed* to mean "this works." But some
tests pass while checking nothing real — a fake safety net. As AI writes more
and more tests automatically, nobody is checking whether those tests can be
trusted. **TestProof is the inspector that catches fake tests.**

> Everyone is building AI that *writes* tests. TestProof proves those tests
> can be *trusted*.

---

## See it work

TestProof inspects a test suite and produces a trust scorecard:

```
=======================================================
  TestProof Report  -  test_calculator.py
=======================================================

  TRUSTED  test_add_good
           -> passed both layers

  FAKE     test_add_lazy
           -> Layer 1: no assert - checks nothing

  FAKE     test_add_sneaky
           -> Layer 2: stayed green while app was broken

-------------------------------------------------------
  Trust score: 1 of 3 tests trustworthy (33%)
=======================================================
```

All three tests pass in a normal test run. TestProof proves that only **one**
of them actually protects you.

---

## How it works — a tiered funnel

Cheap checks run first and filter out the obvious fakes; expensive checks only
run on what survives. This keeps it fast and low-cost.

```
   Test suite (all green, look fine)
            |
            v
   Layer 1: READ the tests (cheap, no run)  -->  catches tests with no real check
            |
            v
   Layer 2: BREAK the app (deeper)          -->  catches tests that don't notice bugs
            |
            v
   Layer 5: REPORT  -->  one trust scorecard + score
```

**Layer 1 — Static Scanner:** reads each test *without running it* and flags
tests that contain no real check (no assertion). Fast and free.

**Layer 2 — Mutation Agent:** secretly introduces a bug into the app
(mutation testing), re-runs each test, and flags any test that stays green
while the app is broken — proving it wasn't really checking anything. The app
is always safely restored afterwards.

**Layer 5 — Reporter:** combines both layers into a single scorecard. A test is
**TRUSTED** only if it passes *both* layers.

*Planned:* Layer 3 (security / PII-leak & policy checks) and Layer 4
(multimodal judge for voice/video tests).

---

## Works on any project (config-driven)

TestProof is not hard-wired to one example. Point it at any app + test file by
editing `config.yaml`:

```yaml
app_file: calculator.py
test_file: test_calculator.py
```

Change those two lines and run again — the same tool inspects a completely
different project. (The repo includes a second example, `cart.py`, to
demonstrate this.)

---

## Run it

```bash
# install dependencies
pip install pytest pyyaml

# run the full report (reads config.yaml)
python reporter.py
```

Run individual layers to see each in isolation:

```bash
python scanner.py test_calculator.py   # Layer 1 only
python mutator.py                       # Layer 2 only
```

*(Use `python3` instead of `python` on macOS/Linux.)*

---

## What each layer catches

| Test            | Layer 1 (reads) | Layer 2 (breaks app) | Verdict |
|-----------------|-----------------|----------------------|---------|
| test_add_good   | OK              | OK (caught the bug)  | TRUSTED |
| test_add_lazy   | FAKE            | FAKE                 | FAKE    |
| test_add_sneaky | OK (slips past) | FAKE (exposed)       | FAKE    |

The `sneaky` test is the interesting one: it *has* an assertion so it looks
real, but it only checks the result is a number — not that the number is
correct. Layer 1 can't catch it; Layer 2 does.

---

## Project structure

```
testproof/
   config.yaml          settings: which app / which tests to inspect
   scanner.py           Layer 1 - static scanner
   mutator.py           Layer 2 - mutation agent
   reporter.py          Layer 5 - combined trust scorecard (run this)
   calculator.py        example app 1
   test_calculator.py   tests for example 1
   cart.py              example app 2
   test_cart.py         tests for example 2
```

---

## Tech

Python · Pytest · AST / static analysis · mutation testing · config-driven design

## Status

- [x] Layer 1 — static scanner
- [x] Layer 2 — mutation agent
- [x] Layer 5 — combined reporter / trust score
- [x] Config-driven (runs on any project)
- [ ] Layer 3 — security / PII & policy checks
- [ ] Layer 4 — multimodal (voice / video) judge
- [ ] CI/CD integration (run as a quality gate)