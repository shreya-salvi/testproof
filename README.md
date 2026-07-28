# TestProof

**Proves your automated tests aren't lying.**

AI now writes tons of tests, but a test can show green and actually check
nothing. TestProof inspects a test suite and proves which tests are real
and which are fake green checkmarks.

## The idea in one line
Everyone builds AI that *writes* tests. TestProof is the inspector that
proves those tests can be *trusted*.

## How it works (tiered funnel: cheap checks first, expensive last)

1. **Layer 1 - Static Scanner** (cheap, no AI): reads tests without running
   them, catches obvious fakes (tests with no real check).
2. **Layer 2 - Mutation Agent** (runs code): secretly breaks the app and
   checks if the test notices. Catches sneaky fakes. *(coming Day 2)*
3. **Layer 3 - Security / Policy checks**: PII leaks, policy rules. *(later)*
4. **Layer 4 - Multimodal Judge**: judges voice/video test correctness. *(later)*
5. **Layer 5 - Reporter**: scores everything into a trust scorecard. *(later)*

## Project status
- [x] Day 1: calculator app + sample fake tests + Layer 1 static scanner
- [ ] Day 2: Layer 2 mutation testing (catch the sneaky fake)
- [ ] Reporter + scorecard
- [ ] CI/CD integration

## Files
- `calculator.py` - the small app being tested
- `test_calculator.py` - sample tests (1 real, 1 lazy fake, 1 sneaky fake)
- `scanner.py` - Layer 1: the static scanner

## Run it
```bash
# run the tests (they all pass - even the fakes)
python3 -m pytest test_calculator.py -v

# run the scanner (it catches the lazy fake)
python3 scanner.py test_calculator.py
```

## Tech
Python - Pytest - AST / static analysis
