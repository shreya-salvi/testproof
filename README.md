# TestProof

**Proves your automated tests aren't lying.**

A test showing a green checkmark is *supposed* to mean "this works." But some
tests pass while checking nothing real — a fake safety net. As AI writes more
and more tests automatically, nobody is checking whether those tests can be
trusted. **TestProof is the inspector that catches fake tests.**

> Everyone is building AI that *writes* tests. TestProof proves those tests
> can be *trusted*.

**Live demo:** _()_

,-

## See it work

TestProof inspects a test suite and produces a trust scorecard:

```
=======================================================
  TestProof Report  -  test_pricing.py
=======================================================

  TRUSTED  test_price_is_correct
           -> passed Layer 1 (reads) + Layer 2 (breaks app)
           -> Layer 3 (AI): STRONG - asserts the exact expected value

  FAKE     test_price_smoke
           -> Layer 2: stayed green while app was broken

  FAKE     test_price_runs
           -> Layer 1: no assert - checks nothing

,,,,,,,,,,,,,,,,,,,,,,,,,,,-
  Trust score: 1 of 3 tests trustworthy (33%)
=======================================================
```

All three tests pass in a normal `pytest` run. TestProof proves that only
**one** of them actually protects you.

,-

## How it works — a tiered funnel

Cheap checks run first and filter out the obvious fakes; expensive checks only
run on what survives. This keeps it fast and low-cost — the AI layer only
spends API calls on tests that already look trustworthy.

```
   Test suite (all green, looks fine)
            |
            v
   Layer 1: READ the tests (cheap, no run)   ,>  catches tests with no real check
            |
            v
   Layer 2: BREAK the app (mutation testing)  ,>  catches tests that don't notice bugs
            |
            v
   Layer 3: AI REVIEW (survivors only)        ,>  flags weak assertions the others miss
            |
            v
   Report  ,>  one trust scorecard + score
```

**Layer 1 — Static Scanner:** reads each test *without running it* and flags
tests that contain no real check (no assertion). Fast and free.

**Layer 2 — Mutation Agent:** secretly introduces a bug into the app
(mutation testing), re-runs each test, and flags any test that stays green
while the app is broken — proving it wasn't really checking anything. The app
is always safely restored afterwards.

**Layer 3 — AI Test Reviewer:** sends surviving tests to a language model
(Google Gemini) to judge whether each assertion is *strong* (verifies the real
expected value) or *weak* (only checks a type, or that the result isn't null).
Includes retry-with-backoff so temporary rate limits don't crash a run, and
degrades gracefully to a two-layer report if no API key is set.

,-

## Three verdicts

| Verdict   | Meaning                                                        |
|,,,,,-|,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,-|
| `TRUSTED` | Passed every layer that ran.                                  |
| `FAKE`    | Failed a hard, deterministic check (Layer 1 or Layer 2).      |
| `WEAK`    | Survived L1 & L2, but the AI reviewer flagged a soft concern. |

Only `TRUSTED` tests count toward the trust score.

,-

## Why this matters

This isn't a toy problem. Google runs mutation testing as a mandatory part of
code review across thousands of engineers, and teams in finance and healthcare
treat a poor mutation score as a signal to fix tests before shipping. As AI
tools now generate more and more tests, the question "can these tests be
trusted?" is only getting bigger — which is exactly the gap TestProof targets.

,-

## Works on any project (config-driven)

TestProof is not hard-wired to one example. Point it at any app + test file by
editing `config.yaml`:

```yaml
app_file: pricing.py
test_file: test_pricing.py
```

Change those two lines and run again — the same tool inspects a completely
different project.

,-

## Run it

```bash
# install dependencies
pip install pytest pyyaml

# (optional) enable Layer 3 — the AI reviewer
setx GEMINI_API_KEY "your-key-here"        # Windows
# export GEMINI_API_KEY="your-key-here"    # macOS / Linux

# run the full report (reads config.yaml)
python reporter.py
```

Without a `GEMINI_API_KEY`, TestProof still runs Layers 1 and 2 and prints a
full report — it just skips the AI layer.

Run individual layers to see each in isolation:

```bash
python scanner.py test_pricing.py   # Layer 1 only
python mutator.py                   # Layer 2 only
python ai_judge.py                  # Layer 3 only
```

### The web app

An interactive version (this repo's `app.py`) runs the same engine in the
browser with a live pricing-engine demo and a "paste your own test" mode:

```bash
pip install streamlit
streamlit run app.py
```

,-

## Project structure

```
testproof/
   config.yaml          settings: which app / which tests to inspect
   scanner.py           Layer 1 - static scanner
   mutator.py           Layer 2 - mutation agent
   ai_judge.py          Layer 3 - AI test reviewer (Gemini)
   reporter.py          combined trust scorecard (run this)
   app.py               interactive web demo (Streamlit)
   pricing.py           example app under test
   test_pricing.py      tests for the example
```

,-

## Tech

Python · Pytest · AST / static analysis · mutation testing · LLM-as-judge (Gemini) · Streamlit · config-driven design

## Status

- [x] Layer 1 — static scanner
- [x] Layer 2 — mutation agent
- [x] Layer 3 — AI test reviewer (Gemini, with retry-backoff + graceful skip)
- [x] Combined reporter / trust score
- [x] Interactive web app (live demo + paste-your-own-test)
- [x] Config-driven (runs on any project)
- [ ] CI/CD integration (run as a quality gate)
