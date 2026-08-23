"""
app.py — TestProof: a live, self-explaining demo of a test-quality inspector.

Design goals for this version:
  • Show the INPUT (the actual test code) so results have context.
  • Show HOW each verdict was reached (a per-test trace of all three layers).
  • Make the AI layer visible (Gemini's real reasoning, labelled as such).
  • Let a recruiter paste their own tests and have them graded live.

Engine functions come from the same modules the CLI uses. No JS (Streamlit
strips it); all motion is CSS.
"""

import ast
import math
import os
import re
import subprocess
import sys
import tempfile

import streamlit as st

try:
    if "GEMINI_API_KEY" in st.secrets:
        os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass

from scanner import scan_file
from mutator import run_mutation_check
from ai_judge import get_test_sources, judge_test

try:
    from pricing import final_price
except Exception:
    final_price = None

EXAMPLE_APP = "pricing.py"
EXAMPLE_TEST = "test_pricing.py"

VERDICT = {
    "TRUSTED": ("#059669", "TRUSTED"),
    "WEAK":    ("#D97706", "WEAK"),
    "FAKE":    ("#DC2626", "FAKE"),
}

PILL = {
    "pass":   ("#059669", "#E7F6EF", "PASS"),
    "fail":   ("#DC2626", "#FDECEC", "FAIL"),
    "skip":   ("#98A0AC", "#EEF0F3", "—"),
    "strong": ("#4338CA", "#EDECFB", "STRONG"),
    "weak":   ("#D97706", "#FBF1E3", "WEAK"),
}

DEFAULT_PASTE = """from pricing import final_price

def test_price_is_correct():
    # a real check: exact expected value
    assert final_price(100, 20, 10) == 88.0

def test_price_smoke():
    # looks fine, but only checks the type
    assert isinstance(final_price(100, 20, 10), float)

def test_price_runs():
    # no assertion at all
    final_price(100, 20, 10)
"""

SPARK = ('<svg width="12" height="12" viewBox="0 0 24 24" fill="none">'
         '<path d="M12 2l2.2 5.8L20 10l-5.8 2.2L12 18l-2.2-5.8L4 10l5.8-2.2z" '
         'fill="#4338CA"/></svg>')

st.set_page_config(page_title="TestProof — a trust inspector for tests",
                   page_icon="◆", layout="centered")


# --------------------------------------------------------------------------- #
#  Styles
# --------------------------------------------------------------------------- #
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

:root{
  --paper:#F7F8FA; --card:#FFFFFF; --line:#E6E8EC;
  --ink:#16181D; --sub:#5A6472; --muted:#8A93A0;
  --accent:#4338CA; --accent-soft:#EEEDFB;
  --good:#059669; --warn:#D97706; --bad:#DC2626;
}
.stApp{ background:var(--paper); }
[data-testid="stHeader"], #MainMenu, footer, [data-testid="stToolbar"]{ display:none; }
.block-container{ max-width:760px; padding-top:2rem; padding-bottom:4rem; }
html, body, [class*="css"]{ font-family:'Inter',sans-serif; color:var(--ink); }

.tp-top{ display:flex; justify-content:space-between; align-items:center;
  padding-bottom:22px; border-bottom:1px solid var(--line); margin-bottom:34px; }
.tp-brand{ display:flex; align-items:center; gap:9px; font-family:'IBM Plex Mono',monospace;
  font-weight:600; font-size:.9rem; }
.tp-brand .d{ color:var(--accent); }
.tp-by{ font-family:'IBM Plex Mono',monospace; font-size:.76rem; color:var(--muted); }
.tp-by a{ color:var(--accent); text-decoration:none; }

.tp-eyebrow{ font-family:'IBM Plex Mono',monospace; font-size:.72rem;
  letter-spacing:.24em; text-transform:uppercase; color:var(--accent); margin-bottom:14px; }
.tp-head{ font-family:'Fraunces',serif; font-weight:600; font-size:2.7rem;
  line-height:1.08; letter-spacing:-.01em; margin:0 0 18px; }
.tp-head em{ font-style:italic; color:var(--accent); }
.tp-sub{ font-size:1.06rem; line-height:1.65; color:var(--sub); max-width:60ch; }

.tp-problem{ margin:30px 0 8px; padding:20px 22px; background:var(--accent-soft);
  border-radius:14px; border:1px solid #E3E1F7; }
.tp-problem b{ color:var(--ink); }
.tp-problem span{ color:#4B5563; line-height:1.6; font-size:.96rem; }

.tp-sec{ font-family:'Fraunces',serif; font-weight:600; font-size:1.5rem; margin:44px 0 6px; }
.tp-seclead{ color:var(--sub); font-size:.98rem; line-height:1.6; margin-bottom:14px; }
.tp-help{ color:var(--sub); font-size:.9rem; line-height:1.55; margin:4px 0 12px; }
.tp-codelabel{ font-family:'IBM Plex Mono',monospace; font-size:.7rem; letter-spacing:.14em;
  text-transform:uppercase; color:var(--muted); margin:14px 0 6px; }

.tp-pipe{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; margin:14px 0 4px; }
.tp-node{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:16px 15px; }
.tp-num{ font-family:'IBM Plex Mono',monospace; font-size:.7rem; color:var(--accent); letter-spacing:.12em; }
.tp-nt{ font-weight:600; font-size:.98rem; margin:8px 0 4px; }
.tp-nd{ color:var(--sub); font-size:.84rem; line-height:1.45; }

div[data-testid="stSelectbox"] div[data-baseweb="select"]>div{
  background:var(--card)!important; border-color:var(--line)!important; border-radius:11px!important; }
.stTextArea textarea{ font-family:'IBM Plex Mono',monospace!important; font-size:.86rem!important;
  background:var(--card)!important; border-radius:12px!important; border-color:var(--line)!important; color:var(--ink)!important; }
.stButton>button{ font-family:'Inter',sans-serif!important; font-weight:600!important;
  border:none!important; border-radius:11px!important; padding:.55rem 1.3rem!important;
  color:#fff!important; background:var(--accent)!important;
  box-shadow:0 4px 14px rgba(67,56,202,.25)!important; transition:.15s; }
.stButton>button:hover{ transform:translateY(-1px); box-shadow:0 8px 20px rgba(67,56,202,.35)!important; }
.stTabs [data-baseweb="tab"]{ font-weight:600; }

.tp-step{ font-family:'IBM Plex Mono',monospace; font-size:.72rem; letter-spacing:.14em;
  text-transform:uppercase; color:var(--accent); margin:22px 0 4px; }
.tp-stept{ font-weight:600; font-size:1.02rem; margin:0 0 6px; }
.tp-io{ background:var(--card); border:1px solid var(--line); border-radius:14px;
  padding:16px 18px; margin-top:6px; }
.tp-ioflow{ display:flex; align-items:center; gap:10px; flex-wrap:wrap;
  font-family:'IBM Plex Mono',monospace; font-size:.92rem; margin-top:4px; }
.tp-chipnum{ background:#F2F3F6; border:1px solid var(--line); border-radius:9px;
  padding:6px 11px; font-weight:600; }
.tp-chipnum.out{ background:var(--accent-soft); border-color:#D9D6F5; color:var(--accent); }
.tp-arrow{ color:var(--muted); font-size:.78rem; white-space:nowrap; }
.tp-baseline{ display:flex; align-items:center; gap:12px; margin-top:18px;
  padding:13px 18px; border:1px solid var(--line); border-radius:12px; background:var(--card);
  font-size:.88rem; color:var(--sub); line-height:1.4; animation:rise .45s ease both; }
.tp-baseline .ok{ font-family:'IBM Plex Mono',monospace; font-weight:600; color:var(--good);
  background:#E7F6EF; border-radius:8px; padding:4px 10px; font-size:.74rem; white-space:nowrap; }
.tp-baseline b{ color:var(--ink); }
.tp-scorewrap{ display:flex; gap:24px; align-items:center; background:var(--card);
  border:1px solid var(--line); border-radius:18px; padding:22px 24px; margin-top:18px;
  box-shadow:0 6px 24px rgba(20,24,40,.05); animation:rise .5s ease both; }
.tp-gauge{ flex:0 0 128px; width:128px; height:128px; }
.tp-scoremeta h3{ font-family:'Fraunces',serif; font-weight:600; font-size:1.15rem; margin:0 0 3px; }
.tp-scoreexp{ color:var(--sub); font-size:.82rem; line-height:1.45; margin-bottom:8px; }
.tp-file{ font-family:'IBM Plex Mono',monospace; color:var(--muted); font-size:.78rem; }
.tp-counts{ display:flex; gap:16px; margin-top:12px; }
.tp-count{ font-family:'IBM Plex Mono',monospace; font-size:.76rem; color:var(--sub); }
.tp-count b{ font-size:1.05rem; }

.tp-card{ background:var(--card); border:1px solid var(--line); border-left-width:3px;
  border-radius:12px; padding:16px 18px; margin-top:12px; box-shadow:0 2px 10px rgba(20,24,40,.04);
  animation:rise .5s ease both; }
.tp-chip{ font-family:'IBM Plex Mono',monospace; font-weight:600; font-size:.72rem;
  letter-spacing:.12em; display:inline-flex; align-items:center; gap:7px; }
.tp-dot{ width:8px; height:8px; border-radius:50%; display:inline-block; }
.tp-tname{ font-family:'IBM Plex Mono',monospace; font-size:.96rem; margin:7px 0 8px; }
.tp-trace{ display:flex; gap:7px; flex-wrap:wrap; margin-bottom:9px; }
.tp-pill{ font-family:'IBM Plex Mono',monospace; font-size:.66rem; font-weight:600;
  letter-spacing:.05em; padding:4px 9px; border-radius:8px; }
.tp-explain{ font-size:.9rem; color:var(--ink); line-height:1.5; }
.tp-ai{ margin-top:11px; background:linear-gradient(180deg,#F3F2FD,#FBFBFE);
  border:1px solid #E3E1F7; border-radius:10px; padding:11px 13px; }
.tp-ai-h{ font-family:'IBM Plex Mono',monospace; font-size:.64rem; letter-spacing:.1em;
  text-transform:uppercase; color:var(--accent); display:flex; align-items:center; gap:6px; margin-bottom:5px; }
.tp-ai-b{ font-size:.85rem; color:#3A3550; line-height:1.5; font-style:italic; }
.tp-note{ margin-top:14px; border:1px dashed var(--line); border-radius:12px;
  padding:12px 15px; color:var(--muted); font-size:.83rem; background:var(--card); }
@keyframes rise{ from{opacity:0; transform:translateY(9px)} to{opacity:1; transform:none} }

.tp-skills{ display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:14px; }
.tp-skill{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:15px 16px; }
.tp-skill h4{ font-size:.92rem; margin:0 0 4px; }
.tp-skill p{ color:var(--sub); font-size:.83rem; line-height:1.45; margin:0; }
.tp-skill .k{ font-family:'IBM Plex Mono',monospace; font-size:.66rem; color:var(--accent);
  letter-spacing:.1em; text-transform:uppercase; }

.tp-foot{ margin-top:40px; padding-top:16px; border-top:1px solid var(--line);
  font-family:'IBM Plex Mono',monospace; font-size:.74rem; color:var(--muted); line-height:1.8; }
.tp-foot a{ color:var(--accent); text-decoration:none; }

@media (max-width:640px){
  .tp-head{ font-size:2.1rem; }
  .tp-pipe, .tp-skills{ grid-template-columns:1fr; }
  .tp-scorewrap{ flex-direction:column; text-align:center; }
}
</style>
""", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
#  Header + hero + problem
# --------------------------------------------------------------------------- #
st.markdown("""
<div class="tp-top">
  <div class="tp-brand">◆ Test<span class="d">Proof</span></div>
  <div class="tp-by">by Shreya Salvi · <a href="https://github.com/shreya-salvi/testproof">GitHub</a></div>
</div>
<div class="tp-eyebrow">Test-quality inspector</div>
<h1 class="tp-head">A passing test can still be <em>lying.</em></h1>
<div class="tp-sub">A green checkmark is supposed to mean the code works. But a test
can pass while asserting nothing real — a safety net with no net. As AI writes
more and more of our tests, this blind spot is growing. TestProof inspects a test
suite and proves which tests can actually be trusted.</div>
<div class="tp-problem"><span><b>The problem it solves:</b> teams ship code behind a
wall of green checkmarks, but nobody checks whether those checkmarks mean anything.
TestProof is the inspector that catches fake tests before they give false confidence.</span></div>
""", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
#  Engine (per-layer detail)
# --------------------------------------------------------------------------- #
EXPLAIN = {
    "no_assert": "This test runs the code but never checks the result — it can never fail.",
    "mutation":  "We secretly broke the code and this test stayed green, so it wasn't really checking the output.",
    "weak":      "It checks something, but only loosely (like the type), so a wrong answer could slip through.",
    "strong":    "It checks the exact expected result and caught the bug we injected — a real safety net.",
    "static_ok": "The static scan found a real assertion. (Run it inside a full project to also mutation-test it.)",
}


def _judge(source):
    try:
        return judge_test(source)          # (STRONG|WEAK, reason)
    except Exception:
        return (None, None)


@st.cache_data(show_spinner=False)
def pytest_baseline(test_file):
    """Run the tests normally, so we can show 'these all pass' as the baseline.

    That contrast is the proof: a normal run says everything is fine, while
    TestProof shows most of the tests protect you from nothing.
    """
    try:
        out = subprocess.run(
            [sys.executable, "-m", "pytest", test_file, "-q", "--no-header"],
            capture_output=True, text=True, timeout=90)
        text = out.stdout + out.stderr
        p = re.search(r"(\d+) passed", text)
        f = re.search(r"(\d+) failed", text)
        return (int(p.group(1)) if p else None, int(f.group(1)) if f else 0)
    except Exception:
        return (None, None)


def _weak_by_static(source):
    """Flag trivially weak assertions without the AI, so paste mode stays
    reliable and consistent even if the model is momentarily unavailable."""
    try:
        tree = ast.parse(source)
    except Exception:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            seg = (ast.get_source_segment(source, node) or "").lower()
            if ("isinstance" in seg or "is not none" in seg or "is none" in seg
                    or "!= none" in seg or seg.strip() in ("assert true", "assert 1")):
                return True
    return False


@st.cache_data(show_spinner=False)
def analyze_example(app_file, test_file):
    l1 = {n: (v, r) for n, v, r in scan_file(test_file)}
    l2 = run_mutation_check(app_file, test_file)          # {name:(verdict,reason)}
    sources = get_test_sources(test_file)
    report = {}
    for name, (v1, _) in l1.items():
        e = {"l1": (v1, ""), "l2": None, "l3": None}
        if v1 == "FAKE":
            e.update(verdict="FAKE", explain=EXPLAIN["no_assert"])
        else:
            v2, _ = l2.get(name, ("OK", ""))
            e["l2"] = (v2, "")
            if v2 == "FAKE":
                e.update(verdict="FAKE", explain=EXPLAIN["mutation"])
            else:
                verdict, reason = _judge(sources.get(name, ""))
                e["l3"] = (verdict, reason)
                if verdict == "WEAK":
                    e.update(verdict="WEAK", explain=EXPLAIN["weak"])
                else:
                    e.update(verdict="TRUSTED", explain=EXPLAIN["strong"])
        report[name] = e
    return report


@st.cache_data(show_spinner=False)
def analyze_pasted(code):
    # Safe: neither scan_file nor judge_test executes the pasted code.
    tmp = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8")
    tmp.write(code)
    tmp.close()
    try:
        l1 = {n: (v, r) for n, v, r in scan_file(tmp.name)}
        sources = get_test_sources(tmp.name)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
    report = {}
    for name, (v1, _) in l1.items():
        e = {"l1": (v1, ""), "l2": None, "l3": None}   # no mutation on pasted code
        if v1 == "FAKE":
            e.update(verdict="FAKE", explain=EXPLAIN["no_assert"])
        else:
            source = sources.get(name, "")
            verdict, reason = _judge(source)
            e["l3"] = (verdict, reason)
            static_weak = _weak_by_static(source)
            if verdict == "WEAK" or (verdict is None and static_weak):
                e.update(verdict="WEAK",
                         explain=reason and EXPLAIN["weak"] or
                         "This assertion only checks the type or presence of the "
                         "result, not that it's actually right.")
            elif verdict == "STRONG":
                e.update(verdict="TRUSTED",
                         explain="The AI judge found a strong, specific assertion.")
            else:
                e.update(verdict="TRUSTED", explain=EXPLAIN["static_ok"])
        report[name] = e
    return report


# --------------------------------------------------------------------------- #
#  Rendering
# --------------------------------------------------------------------------- #
def _clean(html):
    return "\n".join(line.strip() for line in html.splitlines() if line.strip())


def score_color(pct):
    return "#059669" if pct >= 80 else "#D97706" if pct >= 50 else "#DC2626"


def gauge_svg(pct):
    r = 52
    circ = 2 * math.pi * r
    offset = circ * (1 - pct / 100)
    col = score_color(pct)
    return _clean(f"""
    <svg class="tp-gauge" viewBox="0 0 128 128">
      <style>@keyframes sweep{{from{{stroke-dashoffset:{circ:.1f}}}to{{stroke-dashoffset:{offset:.1f}}}}}</style>
      <circle cx="64" cy="64" r="{r}" fill="none" stroke="#E6E8EC" stroke-width="11"/>
      <circle cx="64" cy="64" r="{r}" fill="none" stroke="{col}" stroke-width="11"
        stroke-linecap="round" transform="rotate(-90 64 64)"
        stroke-dasharray="{circ:.1f}" stroke-dashoffset="{offset:.1f}"
        style="animation:sweep 1.1s ease-out both"/>
      <text x="64" y="60" text-anchor="middle" fill="{col}"
        font-family="Fraunces, serif" font-size="29" font-weight="600">{pct}%</text>
      <text x="64" y="80" text-anchor="middle" fill="#8A93A0"
        font-family="IBM Plex Mono, monospace" font-size="9" letter-spacing="2">TRUST</text>
    </svg>""")


def _pill(label, state, override=None):
    col, bg, txt = PILL[state]
    return (f'<span class="tp-pill" style="color:{col};background:{bg}">'
            f'{label} · {override or txt}</span>')


def _trace(e):
    pills = [_pill("READ", "pass" if e["l1"][0] == "OK" else "fail")]
    if e["l2"] is None:
        pills.append(_pill("BREAK", "skip"))
    else:
        pills.append(_pill("BREAK", "pass" if e["l2"][0] == "OK" else "fail"))
    if e["l3"] is None or e["l3"][0] is None:
        pills.append(_pill("AI JUDGE", "skip"))
    else:
        state = "strong" if e["l3"][0] == "STRONG" else "weak"
        pills.append(_pill("AI JUDGE", state))
    return "".join(pills)


def render_report(report, title, mode, baseline=None):
    total = len(report)
    trusted = sum(1 for e in report.values() if e["verdict"] == "TRUSTED")
    weak = sum(1 for e in report.values() if e["verdict"] == "WEAK")
    fake = sum(1 for e in report.values() if e["verdict"] == "FAKE")
    pct = round(trusted / total * 100) if total else 0

    baseline_html = ""
    if baseline and baseline[0]:
        passed, failed = baseline
        baseline_html = (
            f'<div class="tp-baseline"><span class="ok">pytest · {passed} passed, '
            f'{failed} failed</span><span>A normal test run says <b>everything is '
            f'fine</b>. Here is what TestProof found underneath.</span></div>')

    cards = []
    for name, e in report.items():
        col, label = VERDICT[e["verdict"]]
        ai = ""
        if e["l3"] and e["l3"][0]:
            ai = (f'<div class="tp-ai"><div class="tp-ai-h">{SPARK} Gemini AI reviewer'
                  f'</div><div class="tp-ai-b">"{e["l3"][1]}"</div></div>')
        cards.append(f"""
        <div class="tp-card" style="border-left-color:{col}">
          <span class="tp-chip" style="color:{col}"><span class="tp-dot" style="background:{col}"></span>{label}</span>
          <div class="tp-tname">{name}</div>
          <div class="tp-trace">{_trace(e)}</div>
          <div class="tp-explain">{e["explain"]}</div>
          {ai}
        </div>""")

    note = ""
    if mode == "static":
        note = ('<div class="tp-note">Paste mode runs the static scanner and the '
                'Gemini AI reviewer, which read your tests without running them. The '
                'mutation layer needs the app under test, so it runs on the example '
                'projects above.</div>')

    body = f"""
    {baseline_html}
    <div class="tp-scorewrap">
      {gauge_svg(pct)}
      <div class="tp-scoremeta">
        <h3>{trusted} of {total} tests can be trusted</h3>
        <div class="tp-scoreexp">Trust score = the share of your tests that would actually catch a bug.</div>
        <div class="tp-file">{title}</div>
        <div class="tp-counts">
          <div class="tp-count"><b style="color:#059669">{trusted}</b> trusted</div>
          <div class="tp-count"><b style="color:#D97706">{weak}</b> weak</div>
          <div class="tp-count"><b style="color:#DC2626">{fake}</b> fake</div>
        </div>
      </div>
    </div>
    {''.join(cards)}
    {note}"""
    return _clean(body)


# --------------------------------------------------------------------------- #
#  See it work
# --------------------------------------------------------------------------- #
st.markdown('<div class="tp-sec">See it work</div>', unsafe_allow_html=True)
st.markdown('<div class="tp-seclead">Watch the inspector read the tests, break the '
            'code, and let the AI grade what survives.</div>', unsafe_allow_html=True)

tab_ex, tab_paste = st.tabs(["Example project", "Paste your own test"])

with tab_ex:
    # ---- Step 1: the program (live input -> output) ----
    st.markdown('<div class="tp-step">Step 1 — the program</div>', unsafe_allow_html=True)
    st.markdown('<div class="tp-stept">A tiny pricing engine</div>', unsafe_allow_html=True)
    st.markdown('<div class="tp-help">It takes a base price, applies a discount, then '
                'adds tax. Change the numbers and watch it work — this is the real code '
                'running.</div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    base = c1.number_input("Base price ($)", value=100.0, min_value=0.0, step=10.0)
    disc = c2.number_input("Discount (%)", value=20.0, min_value=0.0, max_value=100.0, step=5.0)
    tax = c3.number_input("Tax (%)", value=10.0, min_value=0.0, step=1.0)

    discounted = base * (1 - disc / 100)
    out = final_price(base, disc, tax) if final_price else round(discounted * (1 + tax / 100), 2)
    st.markdown(_clean(f"""
    <div class="tp-io"><div class="tp-ioflow">
      <span class="tp-chipnum">${base:,.2f}</span>
      <span class="tp-arrow">− {disc:.0f}% off →</span>
      <span class="tp-chipnum">${discounted:,.2f}</span>
      <span class="tp-arrow">+ {tax:.0f}% tax →</span>
      <span class="tp-chipnum out">${out:,.2f}</span>
    </div></div>"""), unsafe_allow_html=True)

    # ---- Step 2: the inspection ----
    st.markdown('<div class="tp-step">Step 2 — the inspection</div>', unsafe_allow_html=True)
    st.markdown('<div class="tp-stept">Now check the tests written for it</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="tp-help">Three tests were written for this pricing engine, '
                'and all of them pass in a normal run. TestProof grades those three — so '
                'this result is the same every time, because the tests don\'t change. '
                'To watch the score change with different code, use the '
                '<b>“Paste your own test”</b> tab.</div>', unsafe_allow_html=True)
    if st.button("Run inspection", type="primary", key="run_ex"):
        with st.spinner("Reading tests → breaking the app → consulting Gemini…"):
            try:
                report = analyze_example(EXAMPLE_APP, EXAMPLE_TEST)
                baseline = pytest_baseline(EXAMPLE_TEST)
            except Exception as e:
                st.error(f"Could not complete the inspection: {e}")
                st.stop()
        st.markdown(render_report(report, EXAMPLE_TEST, "full", baseline),
                    unsafe_allow_html=True)

with tab_paste:
    st.markdown('<div class="tp-help"><b>Test your own code here.</b> Paste any Python '
                'tests, click Analyze, and the Gemini AI reviewer grades them live — '
                'nothing is pre-saved. Try weakening an assertion (e.g. change <code>== '
                '88.0</code> to <code>is not None</code>) and re-run to watch the verdict '
                'change.</div>', unsafe_allow_html=True)
    code = st.text_area("Your test code", value=DEFAULT_PASTE, height=230,
                        label_visibility="collapsed")
    if st.button("Analyze my tests", type="primary", key="run_paste"):
        with st.spinner("Reading your tests → asking Gemini…"):
            try:
                report = analyze_pasted(code)
            except SyntaxError as e:
                st.error(f"That doesn't parse as Python: {e}")
                st.stop()
            except Exception as e:
                st.error(f"Could not analyze that: {e}")
                st.stop()
        if not report:
            st.info("No test functions found. Name them starting with `test_`.")
        else:
            st.markdown(render_report(report, "your pasted tests", "static"),
                        unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
#  How it works
# --------------------------------------------------------------------------- #
st.markdown('<div class="tp-sec">How it works</div>', unsafe_allow_html=True)
st.markdown('<div class="tp-seclead">Three layers, cheapest first. A test is '
            'trusted only if it survives all of them.</div>', unsafe_allow_html=True)
st.markdown("""
<div class="tp-pipe">
  <div class="tp-node"><div class="tp-num">LAYER 01</div>
    <div class="tp-nt">Reads the test</div>
    <div class="tp-nd">Static analysis flags tests that assert nothing — without running them.</div></div>
  <div class="tp-node"><div class="tp-num">LAYER 02</div>
    <div class="tp-nt">Breaks the app</div>
    <div class="tp-nd">Injects a bug into the code and flags any test that stays green.</div></div>
  <div class="tp-node"><div class="tp-num">LAYER 03</div>
    <div class="tp-nt">Asks the AI</div>
    <div class="tp-nd">Gemini judges whether the assertion is strong or merely trivial.</div></div>
</div>
""", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
#  What this demonstrates
# --------------------------------------------------------------------------- #
st.markdown('<div class="tp-sec">What this demonstrates</div>', unsafe_allow_html=True)
st.markdown('<div class="tp-seclead">The engineering decisions behind the tool.</div>',
            unsafe_allow_html=True)
st.markdown("""
<div class="tp-skills">
  <div class="tp-skill"><div class="k">static analysis</div>
    <h4>AST parsing</h4><p>Reads test code as a syntax tree to catch missing assertions without executing it.</p></div>
  <div class="tp-skill"><div class="k">fault injection</div>
    <h4>Mutation testing</h4><p>Deliberately breaks the app to expose tests that never really checked behavior.</p></div>
  <div class="tp-skill"><div class="k">llm evaluation</div>
    <h4>AI-as-judge</h4><p>Uses Gemini with structured JSON output to grade how strong each assertion is.</p></div>
  <div class="tp-skill"><div class="k">architecture</div>
    <h4>Tiered pipeline</h4><p>Cheap checks gate expensive ones, so the costly AI layer only runs when it matters.</p></div>
  <div class="tp-skill"><div class="k">reliability</div>
    <h4>Production hardening</h4><p>Retry-with-backoff on rate limits and graceful fallback when the AI layer is offline.</p></div>
  <div class="tp-skill"><div class="k">design</div>
    <h4>Config-driven</h4><p>Point it at any project's files — the same tool inspects a completely different codebase.</p></div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="tp-foot">
  Python · Pytest · AST static analysis · mutation testing · LLM-as-judge (Gemini)<br>
  source &nbsp;→&nbsp; <a href="https://github.com/shreya-salvi/testproof">github.com/shreya-salvi/testproof</a>
</div>
""", unsafe_allow_html=True)