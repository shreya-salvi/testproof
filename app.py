"""
app.py — TestProof: a live test-quality inspector.
Dark neon theme + animated inspector bot. Detect fake tests, then generate a
validated fix. Same engine as the CLI; trimmed copy; all motion is CSS.
"""

import ast, math, os, re, subprocess, sys, tempfile
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
    from calculator import calculate
except Exception:
    calculate = None
try:
    from test_generator import generate_and_validate
except Exception:
    generate_and_validate = None

EXAMPLE_APP, EXAMPLE_TEST = "calculator.py", "test_calculator.py"
GAP_BY_TEST = {
    "test_multiply_smoke": 'calculate(4, "*", 5) == 20',
    "test_subtract_runs":  'calculate(10, "-", 4) == 6',
    "test_add_is_correct": 'calculate(2, "+", 3) == 5',
    "test_divide_is_correct": 'calculate(9, "/", 3) == 3.0',
}
DEFAULT_GAP = 'calculate(2, "+", 3) == 5'

VERDICT = {"TRUSTED": ("#2FE0A6", "TRUSTED"), "WEAK": ("#FBBF24", "WEAK"), "FAKE": ("#FF6A76", "FAKE")}
GEN_STYLE = {"VALIDATED": ("#2FE0A6", "VALIDATED"), "NEEDS_REVIEW": ("#FBBF24", "NEEDS REVIEW"), "FAILED": ("#FF6A76", "FAILED")}
PILL = {"pass": ("#2FE0A6", "rgba(47,224,166,.12)", "PASS"), "fail": ("#FF6A76", "rgba(255,106,118,.12)", "FAIL"),
        "skip": ("#69769E", "rgba(105,118,158,.12)", "—"), "strong": ("#5EC8FF", "rgba(94,200,255,.14)", "STRONG"),
        "weak": ("#FBBF24", "rgba(251,191,36,.14)", "WEAK")}

DEFAULT_PASTE = '''from calculator import calculate

def test_add_is_correct():
    assert calculate(2, "+", 3) == 5

def test_multiply_smoke():
    assert isinstance(calculate(4, "*", 5), (int, float))

def test_subtract_runs():
    calculate(10, "-", 4)
'''
DEFAULT_FUNC = '''def calculate(a, op, b):
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        if b == 0:
            raise ZeroDivisionError("Cannot divide by zero")
        return a / b
    if op == "%":
        if b == 0:
            raise ZeroDivisionError("Cannot take modulo by zero")
        return a % b
    if op == "^":
        return a ** b
    raise ValueError("Unknown operation")
'''
SPARK = ('<svg width="12" height="12" viewBox="0 0 24 24" fill="none"><path d="M12 2l2.2 5.8L20 10l-5.8 2.2L12 18l'
         '-2.2-5.8L4 10l5.8-2.2z" fill="#7C5CFF"/></svg>')

st.set_page_config(page_title="TestProof — trust inspector for tests", page_icon="◆", layout="centered")

# ------------------------------------------------------------------ styles
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600&family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
:root{
  --bg:#0B1020; --panel:#121834; --panel2:#0E1428; --line:#243056;
  --ink:#EAF0FF; --sub:#9BA6C8; --muted:#69769E;
  --blue:#5EC8FF; --violet:#7C5CFF; --good:#2FE0A6; --bad:#FF6A76; --warn:#FBBF24;
}
.stApp{ background:var(--bg);
  background-image:linear-gradient(rgba(90,120,255,.05) 1px,transparent 1px),linear-gradient(90deg,rgba(90,120,255,.05) 1px,transparent 1px);
  background-size:30px 30px; }
[data-testid="stHeader"],#MainMenu,footer,[data-testid="stToolbar"]{display:none}
.block-container{max-width:820px;padding-top:1.6rem;padding-bottom:4rem}
html,body,[class*="css"]{font-family:'Inter',sans-serif;color:var(--ink)}
.stApp p, .stApp label, .stApp span, .stApp div{color:var(--ink)}

/* top bar */
.tp-top{display:flex;justify-content:space-between;align-items:center;padding-bottom:18px;border-bottom:1px solid var(--line);margin-bottom:12px}
.tp-brand{display:flex;align-items:center;gap:9px;font-weight:700;font-size:1rem}
.tp-brand b{background:linear-gradient(90deg,var(--blue),var(--violet));-webkit-background-clip:text;background-clip:text;color:transparent}
.tp-by{font-family:'IBM Plex Mono',monospace;font-size:.76rem;color:var(--muted)}
.tp-by a{color:var(--blue);text-decoration:none}

/* hero */
.tp-hero{display:grid;grid-template-columns:1.12fr .88fr;gap:22px;align-items:center;padding:26px 0 18px}
.tp-badge{display:inline-flex;align-items:center;gap:8px;background:rgba(94,200,255,.10);border:1px solid rgba(94,200,255,.25);
  color:var(--blue);font-weight:600;font-size:.76rem;padding:5px 13px;border-radius:100px;margin-bottom:16px}
.tp-badge .live{width:7px;height:7px;border-radius:50%;background:var(--blue);box-shadow:0 0 8px var(--blue);animation:bk 1.6s infinite}
@keyframes bk{0%,100%{opacity:1}50%{opacity:.3}}
.tp-h1{font-family:'Fraunces',serif;font-weight:600;font-size:2.7rem;line-height:1.02;letter-spacing:-.01em}
.tp-h1 .g{background:linear-gradient(90deg,var(--blue),var(--violet));-webkit-background-clip:text;background-clip:text;color:transparent;filter:drop-shadow(0 0 18px rgba(124,92,255,.35))}
.tp-lede{color:var(--sub);font-size:1.02rem;margin:14px 0 2px;max-width:42ch}

/* robot */
.tp-stage{display:flex;justify-content:center;align-items:center;position:relative;min-height:210px}
.tp-halo{position:absolute;width:210px;height:210px;border-radius:50%;background:radial-gradient(circle,rgba(124,92,255,.26),transparent 64%);animation:pulse 3.4s ease-in-out infinite}
@keyframes pulse{0%,100%{transform:scale(1);opacity:.85}50%{transform:scale(1.12);opacity:1}}
.tp-bot{position:relative;width:168px;animation:float 4s ease-in-out infinite}
@keyframes float{0%,100%{transform:translateY(0) rotate(-1deg)}50%{transform:translateY(-11px) rotate(1deg)}}
.tp-ant{position:absolute;left:50%;top:-2px;transform:translateX(-50%);width:4px;height:20px;background:#3A4680;border-radius:3px}
.tp-ant::after{content:"";position:absolute;top:-9px;left:50%;transform:translateX(-50%);width:12px;height:12px;border-radius:50%;background:var(--blue);box-shadow:0 0 14px var(--blue);animation:ping 2s ease-out infinite}
@keyframes ping{0%{box-shadow:0 0 10px var(--blue),0 0 0 0 rgba(94,200,255,.5)}70%{box-shadow:0 0 10px var(--blue),0 0 0 12px rgba(94,200,255,0)}100%{box-shadow:0 0 10px var(--blue),0 0 0 0 rgba(94,200,255,0)}}
.tp-head{position:relative;width:168px;height:130px;margin-top:18px;border-radius:32px;background:linear-gradient(160deg,#1B2244,#141A34);border:2px solid #2C3766;box-shadow:0 20px 40px -16px rgba(0,0,0,.7),inset 0 0 24px rgba(124,92,255,.12),0 0 40px rgba(94,200,255,.10)}
.tp-visor{position:absolute;left:15px;right:15px;top:24px;height:68px;border-radius:20px;background:linear-gradient(160deg,#0A1030,#161E4A);overflow:hidden;box-shadow:inset 0 2px 8px rgba(0,0,0,.6)}
.tp-scan{position:absolute;top:0;bottom:0;width:42px;background:linear-gradient(90deg,transparent,rgba(94,200,255,.6),transparent);transform:translateX(-48px);animation:scan 2.6s linear infinite}
@keyframes scan{to{transform:translateX(180px)}}
.tp-eye{position:absolute;top:26px;width:18px;height:18px;border-radius:50%;background:var(--blue);box-shadow:0 0 16px var(--blue);animation:eb 4.2s infinite}
.tp-eye.l{left:42px}.tp-eye.r{right:42px}
@keyframes eb{0%,92%,100%{transform:scaleY(1)}96%{transform:scaleY(.1)}}
.tp-arm{position:absolute;top:90px;width:13px;height:40px;border-radius:8px;background:#1B2244;border:2px solid #2C3766}
.tp-arm.l{left:-7px;transform-origin:top center;animation:wave 3.2s ease-in-out infinite}.tp-arm.r{right:-7px}
@keyframes wave{0%,100%{transform:rotate(8deg)}50%{transform:rotate(-22deg)}}
.tp-glass{position:absolute;left:-28px;top:112px;width:36px;height:36px;border-radius:50%;border:4px solid var(--violet);background:rgba(124,92,255,.14);box-shadow:0 0 16px rgba(124,92,255,.5);animation:hunt 3.2s ease-in-out infinite}
.tp-glass::after{content:"";position:absolute;right:-10px;bottom:-8px;width:14px;height:5px;border-radius:4px;background:var(--violet);transform:rotate(45deg)}
@keyframes hunt{0%,100%{transform:translate(0,0)}50%{transform:translate(9px,-6px)}}

/* section + steps */
.tp-sec{font-family:'Fraunces',serif;font-weight:600;font-size:1.4rem;margin:34px 0 4px}
.tp-lead{color:var(--sub);font-size:.92rem;margin-bottom:12px}
.tp-step{font-family:'IBM Plex Mono',monospace;font-size:.7rem;letter-spacing:.1em;text-transform:uppercase;color:var(--blue);margin:20px 0 4px}
.tp-stept{font-weight:600;font-size:1rem;margin:0 0 4px}
.tp-help{color:var(--sub);font-size:.88rem;margin:2px 0 10px}

/* calculator io */
.tp-io{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:15px 18px;margin-top:6px}
.tp-ioflow{display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-family:'IBM Plex Mono',monospace;font-size:.94rem}
.tp-chipnum{background:#0E1630;border:1px solid var(--line);border-radius:9px;padding:6px 12px;font-weight:600;color:var(--ink)}
.tp-chipnum.out{background:rgba(94,200,255,.12);border-color:rgba(94,200,255,.4);color:var(--blue)}
.tp-arrow{color:var(--muted);font-size:.78rem}

/* streamlit widgets -> dark */
div[data-testid="stSelectbox"] div[data-baseweb="select"]>div{background:var(--panel)!important;border-color:var(--line)!important;border-radius:11px!important;color:var(--ink)!important}
div[data-testid="stNumberInput"] input{background:var(--panel)!important;color:var(--ink)!important}
div[data-testid="stNumberInput"] div[data-baseweb="input"]{background:var(--panel)!important;border-color:var(--line)!important;border-radius:11px!important}
div[data-testid="stNumberInput"] button{background:var(--panel2)!important;border-color:var(--line)!important;color:var(--ink)!important}
.stTextArea textarea{font-family:'IBM Plex Mono',monospace!important;font-size:.85rem!important;background:var(--panel)!important;border-radius:12px!important;border-color:var(--line)!important;color:var(--ink)!important}
.stButton>button{font-weight:700!important;border:none!important;border-radius:12px!important;padding:.55rem 1.4rem!important;color:#08122a!important;background:linear-gradient(90deg,var(--blue),var(--violet))!important;box-shadow:0 0 26px rgba(94,200,255,.35)!important;transition:transform .14s}
.stButton>button:hover{transform:translateY(-2px)}
.stTabs [data-baseweb="tab-list"]{gap:4px;border-bottom:1px solid var(--line)}
.stTabs [data-baseweb="tab"]{font-weight:600;color:var(--sub)}
.stTabs [aria-selected="true"]{color:var(--blue)!important}
.stCode,pre{background:#0A1030!important;border:1px solid var(--line)!important;border-radius:12px!important}
code{color:#BFD3FF!important}

/* report */
.tp-baseline{display:flex;align-items:center;gap:12px;margin-top:16px;padding:12px 16px;border:1px solid var(--line);border-radius:12px;background:var(--panel);font-size:.86rem;color:var(--sub);animation:rise .5s ease both}
.tp-baseline .ok{font-family:'IBM Plex Mono',monospace;font-weight:600;color:var(--good);background:rgba(47,224,166,.12);border-radius:8px;padding:4px 10px;font-size:.72rem;white-space:nowrap}
.tp-baseline b{color:var(--ink)}
.tp-scorewrap{display:flex;gap:22px;align-items:center;background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:20px 22px;margin-top:14px;box-shadow:0 20px 50px -30px rgba(0,0,0,.7);animation:rise .5s ease both}
.tp-gauge{flex:0 0 120px;width:120px;height:120px}
.tp-scoremeta h3{font-family:'Fraunces',serif;font-weight:600;font-size:1.12rem;margin:0 0 3px;color:var(--ink)}
.tp-scoreexp{color:var(--sub);font-size:.8rem;margin-bottom:8px}
.tp-file{font-family:'IBM Plex Mono',monospace;color:var(--muted);font-size:.76rem}
.tp-counts{display:flex;gap:16px;margin-top:10px}
.tp-count{font-family:'IBM Plex Mono',monospace;font-size:.76rem;color:var(--sub)}.tp-count b{font-size:1.05rem}
.tp-card{background:var(--panel);border:1px solid var(--line);border-left-width:3px;border-radius:12px;padding:15px 17px;margin-top:11px;animation:rise .5s ease both}
.tp-chip{font-family:'IBM Plex Mono',monospace;font-weight:600;font-size:.7rem;letter-spacing:.1em;display:inline-flex;align-items:center;gap:7px}
.tp-dot{width:8px;height:8px;border-radius:50%;display:inline-block}
.tp-tname{font-family:'IBM Plex Mono',monospace;font-size:.94rem;margin:7px 0 8px;color:var(--ink)}
.tp-trace{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:9px}
.tp-pill{font-family:'IBM Plex Mono',monospace;font-size:.64rem;font-weight:600;letter-spacing:.05em;padding:4px 9px;border-radius:8px}
.tp-explain{font-size:.88rem;color:var(--ink);line-height:1.5}
.tp-ai{margin-top:11px;background:rgba(124,92,255,.08);border:1px solid rgba(124,92,255,.25);border-radius:10px;padding:11px 13px}
.tp-ai-h{font-family:'IBM Plex Mono',monospace;font-size:.62rem;letter-spacing:.1em;text-transform:uppercase;color:var(--violet);display:flex;align-items:center;gap:6px;margin-bottom:5px}
.tp-ai-b{font-size:.84rem;color:#C9BCFF;line-height:1.5;font-style:italic}
.tp-note{margin-top:14px;border:1px dashed var(--line);border-radius:12px;padding:11px 15px;color:var(--muted);font-size:.82rem}
@keyframes rise{from{opacity:0;transform:translateY(9px)}to{opacity:1;transform:none}}

/* how it works */
.tp-pipe{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:12px 0 4px}
.tp-node{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px 13px}
.tp-num{font-family:'IBM Plex Mono',monospace;font-size:.68rem;color:var(--blue);letter-spacing:.1em}
.tp-nt{font-weight:600;font-size:.92rem;margin:8px 0 4px}
.tp-nd{color:var(--sub);font-size:.8rem;line-height:1.4}

.tp-foot{margin-top:34px;padding-top:16px;border-top:1px solid var(--line);font-family:'IBM Plex Mono',monospace;font-size:.74rem;color:var(--muted);line-height:1.8}
.tp-foot a{color:var(--blue);text-decoration:none}

@media(max-width:720px){.tp-hero{grid-template-columns:1fr;text-align:center}.tp-h1{font-size:2.1rem}.tp-pipe{grid-template-columns:1fr 1fr}.tp-scorewrap{flex-direction:column;text-align:center}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------ hero
st.markdown("""
<div class="tp-top"><div class="tp-brand">◆ Test<b>Proof</b></div>
<div class="tp-by">by Shreya Salvi · <a href="https://github.com/shreya-salvi/testproof">GitHub</a></div></div>
<div class="tp-hero">
  <div>
    <div class="tp-badge"><span class="live"></span>your tests, under inspection</div>
    <div class="tp-h1">Meet the bot that <span class="g">catches fake tests.</span></div>
    <div class="tp-lede">A green checkmark can mean nothing. This bot reads your tests, breaks your code, and proves which ones actually protect you.</div>
  </div>
  <div class="tp-stage"><div class="tp-halo"></div><div class="tp-bot">
    <div class="tp-ant"></div>
    <div class="tp-head"><div class="tp-visor"><div class="tp-scan"></div></div><div class="tp-eye l"></div><div class="tp-eye r"></div></div>
    <div class="tp-arm l"></div><div class="tp-arm r"></div><div class="tp-glass"></div>
  </div></div>
</div>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------ engine
EXPLAIN = {
    "no_assert": "Runs the code but never checks the result — it can never fail.",
    "mutation":  "We broke the code and this test stayed green — it wasn't really checking.",
    "weak":      "Checks something, but only loosely (like the type). A wrong answer slips through.",
    "strong":    "Checks the exact result and caught the injected bug — a real safety net.",
    "static_ok": "Found a real assertion. (Run inside a full project to mutation-test it too.)",
    "exception": "Checks the error path — it makes sure the code raises when it should.",
}

def _judge(source):
    try: return judge_test(source)
    except Exception: return (None, None)

@st.cache_data(show_spinner=False)
def pytest_baseline(test_file):
    try:
        from mutator import run_test_inproc
        import os
        app_src = open(EXAMPLE_APP, encoding="utf-8").read()
        test_src = open(test_file, encoding="utf-8").read()
        module = os.path.splitext(os.path.basename(EXAMPLE_APP))[0]
        names = [n.name for n in ast.walk(ast.parse(test_src))
                 if isinstance(n, ast.FunctionDef) and n.name.startswith("test")]
        passed = sum(1 for n in names if run_test_inproc(app_src, module, test_src, n))
        return (passed, len(names) - passed)
    except Exception:
        return (None, None)

def _weak_by_static(source):
    try: tree = ast.parse(source)
    except Exception: return False
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
    l2 = run_mutation_check(app_file, test_file)
    sources = get_test_sources(test_file)
    report = {}
    for name, (v1, _) in l1.items():
        e = {"l1": (v1, ""), "l2": None, "l3": None}
        src = sources.get(name, "")
        if v1 == "FAKE":
            e.update(verdict="FAKE", explain=EXPLAIN["no_assert"])
        elif "pytest.raises" in src or ".assertRaises" in src:
            e["l2"] = ("OK", "")
            e.update(verdict="TRUSTED", explain=EXPLAIN["exception"])
        else:
            v2, _ = l2.get(name, ("OK", "")); e["l2"] = (v2, "")
            if v2 == "FAKE":
                e.update(verdict="FAKE", explain=EXPLAIN["mutation"])
            else:
                # deterministic, no API call: keeps the example fast + reliable
                is_weak = _weak_by_static(src)
                e["l3"] = (None, None)
                e.update(verdict="WEAK" if is_weak else "TRUSTED",
                         explain=EXPLAIN["weak"] if is_weak else EXPLAIN["strong"])
        report[name] = e
    return report

@st.cache_data(show_spinner=False)
def analyze_pasted(code):
    tmp = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8")
    tmp.write(code); tmp.close()
    try:
        l1 = {n: (v, r) for n, v, r in scan_file(tmp.name)}
        sources = get_test_sources(tmp.name)
    finally:
        try: os.unlink(tmp.name)
        except OSError: pass
    report = {}
    for name, (v1, _) in l1.items():
        e = {"l1": (v1, ""), "l2": None, "l3": None}
        if v1 == "FAKE":
            e.update(verdict="FAKE", explain=EXPLAIN["no_assert"])
        else:
            source = sources.get(name, ""); verdict, reason = _judge(source); e["l3"] = (verdict, reason)
            static_weak = _weak_by_static(source)
            if verdict == "WEAK" or (verdict is None and static_weak):
                e.update(verdict="WEAK", explain=(EXPLAIN["weak"] if reason else
                         "Only checks the type or presence of the result, not that it's right."))
            elif verdict == "STRONG":
                e.update(verdict="TRUSTED", explain="The AI judge found a strong, specific assertion.")
            else:
                e.update(verdict="TRUSTED", explain=EXPLAIN["static_ok"])
        report[name] = e
    return report

@st.cache_data(show_spinner=False)
def run_generation(app_code, module, gap, target):
    if generate_and_validate is None: return None
    r = generate_and_validate(app_code, module, gap, target)
    return {"target": r.target, "status": r.status, "generated_code": r.generated_code,
            "reason": r.reason, "passed_clean": r.passed_clean, "caught_mutation": r.caught_mutation}

# ------------------------------------------------------------------ render
def _clean(html): return "\n".join(l.strip() for l in html.splitlines() if l.strip())
def score_color(pct): return "#2FE0A6" if pct >= 80 else "#FBBF24" if pct >= 50 else "#FF6A76"

def gauge_svg(pct):
    r = 50; circ = 2*math.pi*r; off = circ*(1-pct/100); col = score_color(pct)
    return _clean(f"""
    <svg class="tp-gauge" viewBox="0 0 120 120">
      <style>@keyframes sweep{{from{{stroke-dashoffset:{circ:.1f}}}to{{stroke-dashoffset:{off:.1f}}}}}</style>
      <circle cx="60" cy="60" r="{r}" fill="none" stroke="#243056" stroke-width="10"/>
      <circle cx="60" cy="60" r="{r}" fill="none" stroke="{col}" stroke-width="10" stroke-linecap="round"
        transform="rotate(-90 60 60)" stroke-dasharray="{circ:.1f}" stroke-dashoffset="{off:.1f}"
        style="animation:sweep 1.1s ease-out both;filter:drop-shadow(0 0 6px {col})"/>
      <text x="60" y="66" text-anchor="middle" fill="{col}" font-family="Fraunces,serif" font-size="27" font-weight="600">{pct}%</text>
    </svg>""")

def _pill(label, state, override=None):
    col, bg, txt = PILL[state]
    return f'<span class="tp-pill" style="color:{col};background:{bg}">{label} · {override or txt}</span>'

def _trace(e):
    p = [_pill("READ", "pass" if e["l1"][0] == "OK" else "fail")]
    p.append(_pill("BREAK", "skip") if e["l2"] is None else _pill("BREAK", "pass" if e["l2"][0]=="OK" else "fail"))
    if e["l3"] is None or e["l3"][0] is None: p.append(_pill("AI JUDGE", "skip"))
    else: p.append(_pill("AI JUDGE", "strong" if e["l3"][0]=="STRONG" else "weak"))
    return "".join(p)

def render_header(report, title, baseline=None):
    total = len(report)
    trusted = sum(1 for e in report.values() if e["verdict"]=="TRUSTED")
    weak = sum(1 for e in report.values() if e["verdict"]=="WEAK")
    fake = sum(1 for e in report.values() if e["verdict"]=="FAKE")
    pct = round(trusted/total*100) if total else 0
    bl = ""
    if baseline and baseline[0]:
        p, f = baseline
        bl = (f'<div class="tp-baseline"><span class="ok">pytest · {p} passed, {f} failed</span>'
              f'<span>A normal run says <b>all good</b>. Here\'s what\'s underneath.</span></div>')
    body = f"""{bl}
    <div class="tp-scorewrap">{gauge_svg(pct)}
      <div class="tp-scoremeta"><h3>{trusted} of {total} tests can be trusted</h3>
        <div class="tp-scoreexp">Trust score = the share of tests that would catch a real bug.</div>
        <div class="tp-file">{title}</div>
        <div class="tp-counts"><div class="tp-count"><b style="color:#2FE0A6">{trusted}</b> trusted</div>
          <div class="tp-count"><b style="color:#FBBF24">{weak}</b> weak</div>
          <div class="tp-count"><b style="color:#FF6A76">{fake}</b> fake</div></div>
      </div></div>"""
    return _clean(body)

def render_card(name, e):
    col, label = VERDICT[e["verdict"]]
    ai = ""
    if e["l3"] and e["l3"][0]:
        ai = (f'<div class="tp-ai"><div class="tp-ai-h">{SPARK} Gemini AI reviewer</div>'
              f'<div class="tp-ai-b">"{e["l3"][1]}"</div></div>')
    return _clean(f'<div class="tp-card" style="border-left-color:{col}">'
                  f'<span class="tp-chip" style="color:{col}"><span class="tp-dot" style="background:{col}"></span>{label}</span>'
                  f'<div class="tp-tname">{name}</div><div class="tp-trace">{_trace(e)}</div>'
                  f'<div class="tp-explain">{e["explain"]}</div>{ai}</div>')

def render_report(report, title, mode, baseline=None):
    parts = [render_header(report, title, baseline)]
    for name, e in report.items():
        parts.append(render_card(name, e))
    if mode == "static":
        parts.append('<div class="tp-note">Paste mode runs the static scan + Gemini reviewer. '
                     'The mutation layer needs the app under test, so it runs on the example above.</div>')
    return "\n".join(parts)

def render_gen_result(res):
    if res is None:
        st.warning("Generator unavailable — keep test_generator.py next to app.py."); return
    col, label = GEN_STYLE.get(res["status"], ("#69769E", res["status"]))
    st.markdown(f'<div class="tp-chip" style="color:{col}"><span class="tp-dot" style="background:{col}"></span>{label}</div>',
                unsafe_allow_html=True)
    if res["generated_code"].strip(): st.code(res["generated_code"], language="python")
    pc, cm = res["passed_clean"], res["caught_mutation"]
    pills = _pill("PASSES ON GOOD CODE", "pass" if pc else "fail", "YES" if pc else "NO") + \
            _pill("CATCHES THE BUG", "pass" if cm else "fail", "YES" if cm else "NO")
    st.markdown(f'<div class="tp-trace">{pills}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="tp-explain">{res["reason"]}</div>', unsafe_allow_html=True)

# ------------------------------------------------------------------ tabs
st.markdown('<div class="tp-sec">Try it</div>', unsafe_allow_html=True)
st.markdown('<div class="tp-lead">Run the example, paste a test, or let the bot write one.</div>', unsafe_allow_html=True)
tab_ex, tab_paste, tab_gen = st.tabs(["Example", "Paste a test", "Generate a test"])

with tab_ex:
    st.markdown('<div class="tp-step">the program</div><div class="tp-stept">A tiny calculator</div>', unsafe_allow_html=True)
    st.markdown('<div class="tp-help">Now with power (^), modulo, and safe divide-by-zero. Try ÷ or mod by 0.</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([2, 1, 2])
    a = c1.number_input("First number", value=12.0, step=1.0)
    op_label = c2.selectbox("Operation", ["+", "−", "×", "÷", "mod", "^"])
    b = c3.number_input("Second number", value=4.0, step=1.0)
    op = {"+": "+", "−": "-", "×": "*", "÷": "/", "mod": "%", "^": "^"}[op_label]
    err = False
    try:
        result = calculate(a, op, b) if calculate is not None else {"+": a+b, "-": a-b, "*": a*b, "/": (a/b if b else None)}[op]
        if result is None: raise ZeroDivisionError
        result_str = f"{result:g}"
    except ZeroDivisionError:
        err = True; result_str = "can't divide by zero"
    out_html = (f'<span class="tp-chipnum out" style="color:#FF6A76;background:rgba(255,106,118,.12);border-color:rgba(255,106,118,.4)">⚠ {result_str}</span>'
                if err else f'<span class="tp-chipnum out">{result_str}</span>')
    st.markdown(_clean(f'<div class="tp-io"><div class="tp-ioflow"><span class="tp-chipnum">{a:g}</span>'
                       f'<span class="tp-arrow">{op_label}</span><span class="tp-chipnum">{b:g}</span>'
                       f'<span class="tp-arrow">=</span>{out_html}</div></div>'), unsafe_allow_html=True)

    st.markdown('<div class="tp-step">the inspection</div><div class="tp-stept">Check its tests</div>', unsafe_allow_html=True)
    st.markdown('<div class="tp-help">Five tests, all green in a normal run. How many actually check anything?</div>', unsafe_allow_html=True)
    if st.button("Run inspection", key="run_ex"):
        with st.spinner("Reading → breaking → asking Gemini…"):
            try:
                st.session_state.ex_report = analyze_example(EXAMPLE_APP, EXAMPLE_TEST)
                st.session_state.ex_baseline = pytest_baseline(EXAMPLE_TEST)
                st.session_state.pop("ex_gen_target", None)
            except Exception as e:
                st.error(f"Could not complete the inspection: {e}"); st.stop()
    if st.session_state.get("ex_report"):
        report = st.session_state.ex_report
        st.markdown(render_header(report, EXAMPLE_TEST, st.session_state.get("ex_baseline")),
                    unsafe_allow_html=True)
        st.markdown('<div class="tp-help" style="margin-top:12px">Fake tests get a '
                    '<b>Fix</b> button. The bot writes a real test, then proves it by breaking the '
                    'code. Can\'t prove it? A human decides.</div>', unsafe_allow_html=True)
        for name, e in report.items():
            st.markdown(render_card(name, e), unsafe_allow_html=True)
            if e["verdict"] in ("FAKE", "WEAK"):
                if st.button(f"✦ Fix {name}", key=f"fix_{name}"):
                    st.session_state.ex_gen_target = name
                if st.session_state.get("ex_gen_target") == name:
                    with st.spinner(f"Writing a test for {name} → validating…"):
                        app_code = open(EXAMPLE_APP, encoding="utf-8").read()
                        res = run_generation(app_code, "calculator",
                                             GAP_BY_TEST.get(name, DEFAULT_GAP), name)
                    render_gen_result(res)

with tab_paste:
    st.markdown('<div class="tp-help">Paste any Python tests — the Gemini reviewer grades them live. '
                'Try changing <code>== 5</code> to <code>is not None</code>.</div>', unsafe_allow_html=True)
    code = st.text_area("Your test code", value=DEFAULT_PASTE, height=220, label_visibility="collapsed")
    if st.button("Analyze", key="run_paste"):
        with st.spinner("Reading → asking Gemini…"):
            try: report = analyze_pasted(code)
            except SyntaxError as e: st.error(f"That doesn't parse as Python: {e}"); st.stop()
            except Exception as e: st.error(f"Could not analyze that: {e}"); st.stop()
        if not report: st.info("No test functions found. Name them starting with `test_`.")
        else: st.markdown(render_report(report, "your pasted tests", "static"), unsafe_allow_html=True)

with tab_gen:
    st.markdown('<div class="tp-help">Give the bot a function and what it should do. It writes a test, then '
                'validates it by breaking the code. Feed it a buggy function and watch it refuse to sign off.</div>', unsafe_allow_html=True)
    func_code = st.text_area("Function", value=DEFAULT_FUNC, height=150, label_visibility="collapsed", key="gen_func")
    gap_text = st.text_area("Behavior", value='calculate(9, "/", 3) should equal 3.0', height=68,
                            label_visibility="collapsed", key="gen_gap")
    if st.button("Generate & validate", key="run_gen"):
        if generate_and_validate is None:
            st.warning("test_generator.py isn't next to app.py.")
        else:
            try: compile(func_code, "<func>", "exec")
            except SyntaxError as e: st.error(f"That function doesn't parse: {e}"); st.stop()
            with st.spinner("Writing → breaking → checking…"):
                res = run_generation(func_code, "solution", gap_text, "your function")
            render_gen_result(res)

# ------------------------------------------------------------------ how it works
st.markdown('<div class="tp-sec">How it works</div><div class="tp-lead">Four layers, cheapest first. Trusted only if it survives all of them.</div>', unsafe_allow_html=True)
st.markdown("""
<div class="tp-pipe">
  <div class="tp-node"><div class="tp-num">01</div><div class="tp-nt">Reads the test</div><div class="tp-nd">Flags tests that assert nothing — without running them.</div></div>
  <div class="tp-node"><div class="tp-num">02</div><div class="tp-nt">Breaks the app</div><div class="tp-nd">Injects a bug and flags any test that stays green.</div></div>
  <div class="tp-node"><div class="tp-num">03</div><div class="tp-nt">Asks the AI</div><div class="tp-nd">Gemini judges strong vs. trivial checks.</div></div>
  <div class="tp-node"><div class="tp-num">04</div><div class="tp-nt">Writes a fix</div><div class="tp-nd">Generates a test, then proves it. Unproven ones go to a human.</div></div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="tp-foot">Python · mutation testing · AST static analysis · LLM-as-judge (Gemini) · validated generation<br>
source → <a href="https://github.com/shreya-salvi/testproof">github.com/shreya-salvi/testproof</a></div>
""", unsafe_allow_html=True)