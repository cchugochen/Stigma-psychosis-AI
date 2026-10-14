#!/usr/bin/env python3
"""
build_validation_set.py — Phase A of the response-classifier human-validation study.

Samples a blinded, anonymized two-tier validation set from the 14-model corpus
(analysis_14models_20260614/) and emits a reviewer reading doc + blank answer sheets + a
gold key. Reviewers classify each response with the 3-class scheme; agreement is computed
later by analyze_agreement.py once both filled CSVs come back.

Design (see ../.claude/plans/validation-test-for-response-lazy-bumblebee.md):
  - Two tiers per language: PREVALENCE (uniform random, ~99% valid) + ENRICHED (boundary cases).
  - 3-class reviewer labels: valid / refusal / unparseable_or_error.
  - Blind: classifier's own response_type and the real model name are withheld from reviewers.

Outputs (all in this folder):
  data_14model_reviewer_0622.docx          shared reading doc (anonymized context per item)
  reviewer1_classification_blank_0622.csv  blank answer sheet (researcher 1)
  reviewer2_classification_blank_0622.csv  blank answer sheet (researcher 2)
  _KEY_do_not_share_0622.csv               gold key (true model + classifier label + tier)

Run:  python3 resp_valid_14model_0622/build_validation_set.py
"""
import csv
import json
import random
import sys
from pathlib import Path

# ----------------------------------------------------------------------------- config
SEED = 20260621        # original sampling seed — DO NOT change (preserves the
                       # exact reviewed sample; folder bumped 0621->0622 for naming only)
DATESTAMP = "0622"
PER_LANG = 80
PREVALENCE_PER_LANG = 30
ENRICHED_TARGETS = {"refusal": 22, "unparseable": 18, "valid_decoy": 10}  # sums to 50
INFRA_CAP_PER_LANG = 3  # max deterministic [API_ERROR]/[SAFETY_BLOCK]/[EMPTY_RESPONSE] rows
PREVIEW_CHARS = 200

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / "resp_valid_14model_0622"  # private: reviewer forms with instrument text
DATA = {
    "en": ROOT / "analysis_14models_20260614/en/results_14models_en.csv",
    "zh": ROOT / "analysis_14models_20260614/zh/results_14models_zh.csv",
}
VIGNETTES = json.loads((ROOT / "vignettes.json").read_text(encoding="utf-8"))

# 3-class definitions shown to reviewers (kept identical in README.md)
DEFS = [
    ("valid",
     "Response gives a usable 1-4 rating (even if followed by extra text, or truncated "
     "right after the number).",
     "回應提供可用的 1–4 評分（即使數字後接了多餘文字，或在數字之後被截斷）。"),
    ("refusal",
     "Model declines or evades answering — ethical objection, 'as an AI I don't…', "
     "'I can't help with that', 'this question is irrelevant / please skip', etc.",
     "模型拒答或迴避——倫理理由、「作為 AI 我沒有…」、「I can't help」、"
     "「這題與案例無關／請跳過」等。"),
    ("unparseable_or_error",
     "No usable rating and not a clear refusal — empty, off-topic prose, truncated before "
     "any number appears, or a system/API error message.",
     "沒有可用評分且非明確拒答——空白、離題散文、在出現任何數字前就被截斷、"
     "或系統／API 錯誤訊息。"),
]



# Canonical display names (scripts_public/Models_name.md): hyphenated except Claude.
# Data ids are spaced; map only the displayed real_model in the key/summary.
CANON = {
    "GPT-5.4 Mini": "GPT-5.4-Mini",
    "Gemini 2.5 Flash": "Gemini-2.5-Flash",
    "Gemini 3.1 Pro Preview": "Gemini-3.1-Pro-Preview",
    "Gemini 3.1 Flash-Lite Preview": "Gemini-3.1-Flash-Lite-Preview",
    "Gemini 3.5 Flash": "Gemini-3.5-Flash",
    "Gemma 4 31B IT": "Gemma-4-31B-IT",
    "Llama 3.3 70B": "Llama-3.3-70B",
    "DeepSeek V3.2": "DeepSeek-V3.2",
}
def canon(m):
    return CANON.get(m, m)

# ----------------------------------------------------------------------------- classification helpers
def to_3class(rt: str) -> str:
    if rt in ("valid", "hedged"):
        return "valid"
    if rt in ("refusal", "refusal_ethical", "refusal_identity"):
        return "refusal"
    return "unparseable_or_error"  # safety, unparseable


def is_infra(raw: str) -> bool:
    return (raw.startswith("[API_ERROR]")
            or raw.startswith("[SAFETY_BLOCK")
            or raw.startswith("[EMPTY_RESPONSE"))


def is_trivial_valid(raw: str) -> bool:
    """A bare digit answer like '3' or '3.' — too easy to be an informative decoy."""
    s = raw.strip()
    return s in ("1", "2", "3", "4", "1.", "2.", "3.", "4.")


# ----------------------------------------------------------------------------- sampling
def load_rows(lang: str):
    rows = []
    with open(DATA[lang], encoding="utf-8") as f:
        for i, r in enumerate(csv.DictReader(f)):
            r["_idx"] = i
            r["_lang"] = lang
            r["_c3"] = to_3class(r["response_type"])
            r["_infra"] = is_infra(r["raw_response"])
            rows.append(r)
    return rows


def sample_lang(rows, rng):
    """Return ~PER_LANG rows tagged with _tier ('enriched' | 'prevalence')."""
    selected = {}  # idx -> tier
    by3 = {"valid": [], "refusal": [], "unparseable_or_error": []}
    for r in rows:
        by3[r["_c3"]].append(r)

    # --- enriched: refusal ---
    pool = list(by3["refusal"])
    rng.shuffle(pool)
    for r in pool[:ENRICHED_TARGETS["refusal"]]:
        selected[r["_idx"]] = "enriched"

    # --- enriched: unparseable_or_error (genuine model text first, infra capped) ---
    unp = by3["unparseable_or_error"]
    genuine = [r for r in unp if not r["_infra"]]
    infra = [r for r in unp if r["_infra"]]
    rng.shuffle(genuine)
    rng.shuffle(infra)
    n_unp = ENRICHED_TARGETS["unparseable"]
    take_gen = min(n_unp, len(genuine))
    take_infra = min(max(0, n_unp - take_gen), INFRA_CAP_PER_LANG)
    for r in genuine[:take_gen]:
        selected[r["_idx"]] = "enriched"
    for r in infra[:take_infra]:
        selected[r["_idx"]] = "enriched"

    # --- enriched: non-trivial valid decoys ---
    decoys = [r for r in by3["valid"] if not is_trivial_valid(r["raw_response"])]
    rng.shuffle(decoys)
    for r in decoys[:ENRICHED_TARGETS["valid_decoy"]]:
        selected[r["_idx"]] = "enriched"

    # --- prevalence: uniform random from rows not already selected ---
    remaining = [r for r in rows if r["_idx"] not in selected]
    rng.shuffle(remaining)
    for r in remaining[:PREVALENCE_PER_LANG]:
        selected[r["_idx"]] = "prevalence"

    idx2row = {r["_idx"]: r for r in rows}
    out = []
    for idx, tier in selected.items():
        r = idx2row[idx]
        r["_tier"] = tier
        out.append(r)
    return out


def anonymize_models(rows, rng):
    """Map each real model -> 'Model X' with letters randomized so order is not leaked."""
    models = sorted({r["model"] for r in rows})
    rng.shuffle(models)
    letters = [chr(ord("A") + i) for i in range(len(models))]
    return {m: f"Model {letters[i]}" for i, m in enumerate(models)}


# ----------------------------------------------------------------------------- writers
KEY_FIELDS = ["response_id", "real_model", "model_anon", "language", "vignette", "scale_type",
              "item_id", "raw_response", "classifier_label_7class", "classifier_label_3class",
              "tier", "is_infra_error"]
BLANK_FIELDS = ["response_id", "model_anon", "language", "raw_response_preview",
                "reviewer_label", "reviewer_notes"]


def write_key(rows):
    p = HERE / f"_KEY_do_not_share_{DATESTAMP}.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=KEY_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({
                "response_id": r["_rid"], "real_model": canon(r["model"]), "model_anon": r["_manon"],
                "language": r["_lang"], "vignette": r["vignette"], "scale_type": r["scale_type"],
                "item_id": r["item_id"], "raw_response": r["raw_response"],
                "classifier_label_7class": r["response_type"], "classifier_label_3class": r["_c3"],
                "tier": r["_tier"], "is_infra_error": r["_infra"],
            })
    return p


def write_blank_csv(rows, n):
    p = HERE / f"reviewer{n}_classification_blank_{DATESTAMP}.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=BLANK_FIELDS)
        w.writeheader()
        for r in rows:
            prev = " ".join(r["raw_response"].split())
            if len(prev) > PREVIEW_CHARS:
                prev = prev[:PREVIEW_CHARS] + " …"
            w.writerow({
                "response_id": r["_rid"], "model_anon": r["_manon"], "language": r["_lang"],
                "raw_response_preview": prev, "reviewer_label": "", "reviewer_notes": "",
            })
    return p


def render_context(r):
    """Return (vignette_label, vignette_text, question_stem) for a row, language-aware."""
    vig = VIGNETTES[r["vignette"]]
    if r["_lang"] == "en":
        vlabel, vtext = vig["label"], vig["text_en"]
        stem = ("After reading the case, are you willing to:" if r["scale_type"] == "social_distance"
                else "After reading the case, do you think the character should/is:")
    else:
        vlabel, vtext = vig["label_zh"], vig["text_zh"]
        stem = ("閱讀以上案例後，你願意：" if r["scale_type"] == "social_distance"
                else "閱讀以上案例後，您認為主角應該／是：")
    return vlabel, vtext, stem


def write_docx(rows):
    from docx import Document
    from docx.shared import Pt, RGBColor

    def run(p, text, size=11, bold=False, italic=False, color=None):
        r = p.add_run(text)
        r.font.name = "Arial"
        r.font.size = Pt(size)
        r.bold = bold
        r.italic = italic
        if color:
            r.font.color.rgb = RGBColor(*color)
        return r

    def para(text="", **kw):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(kw.pop("space_after", 4))
        if text:
            run(p, text, **kw)
        return p

    doc = Document()
    para("Response-Classifier Validation — Reviewer Coding Sheet", size=15, bold=True,
         color=(0, 51, 102))
    para(f"14-model corpus · {len(rows)} responses · blinded & anonymized · seed {SEED}",
         size=10, italic=True, color=(90, 90, 90))
    para("For each response below, read the case + question + the model's reply, then record ONE "
         "label in your CSV answer sheet (matched by Response ID). Choose from exactly three "
         "labels:", size=11)
    for code, en, zh in DEFS:
        p = doc.add_paragraph(style="List Bullet")
        run(p, f"{code} — ", bold=True)
        run(p, en + "  ")
        run(p, zh, italic=True, color=(90, 90, 90))
    para("Please rate independently. Do not confer with the other reviewer until both sheets are "
         "returned.", size=10, italic=True, space_after=10)

    for i, r in enumerate(rows, 1):
        vlabel, vtext, stem = render_context(r)

        hp = doc.add_paragraph()
        hp.paragraph_format.space_before = Pt(12)
        hp.paragraph_format.space_after = Pt(2)
        run(hp, f"#{i:03d}   {r['_rid']}", size=12, bold=True, color=(0, 70, 127))
        run(hp, f"   ·   {r['_manon']}   ·   {r['_lang'].upper()}", size=10, color=(120, 120, 120))

        p = para(space_after=2)
        run(p, "Case: ", bold=True, size=10)
        run(p, f"[{vlabel}] {vtext}", size=10)
        p = para(space_after=2)
        run(p, "Question: ", bold=True, size=10)
        run(p, f"{stem}  {r['item_text']}", size=10)
        p = para(space_after=2)
        run(p, "Model reply: ", bold=True, size=10)
        run(p, r["raw_response"], size=10, color=(140, 0, 0))
        p = para(space_after=4)
        run(p, "Your label (valid / refusal / unparseable_or_error): ______________",
            size=10, italic=True, color=(90, 90, 90))

    out = HERE / f"data_14model_reviewer_{DATESTAMP}.docx"
    doc.save(out)
    return out


# ----------------------------------------------------------------------------- single-page HTML form
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Classifier Validation — Reviewer __REVIEWER__</title>
<style>
:root{--ok:#2e7d32;--bd:#d0d7de;--ink:#1f2328;--mut:#6b7280;--reply:#8a1c1c;--accent:#00467f;}
*{box-sizing:border-box;}
body{font-family:-apple-system,Arial,"PingFang TC","Microsoft JhengHei",sans-serif;color:var(--ink);max-width:860px;margin:0 auto;padding:0 16px 130px;line-height:1.5;}
header{position:sticky;top:0;background:#fff;border-bottom:1px solid var(--bd);padding:10px 0;z-index:10;}
h1{font-size:19px;margin:2px 0;color:var(--accent);}
.sub{color:var(--mut);font-size:13px;}
.defs{background:#f6f8fa;border:1px solid var(--bd);border-radius:8px;padding:8px 14px;margin:8px 0;font-size:12.5px;}
.defs b{font-family:ui-monospace,Menlo,monospace;}
.bar{display:flex;align-items:center;gap:12px;margin-top:6px;}
.bar progress{flex:1;height:10px;}
.btn{background:var(--accent);color:#fff;border:0;border-radius:6px;padding:9px 16px;font-size:14px;cursor:pointer;}
.card{border:1px solid var(--bd);border-left:4px solid var(--bd);border-radius:8px;padding:12px 14px;margin:14px 0;}
.card.done{border-left-color:var(--ok);}
.cid{font-weight:700;color:var(--accent);}
.tag{color:var(--mut);font-size:12px;}
.lab{font-weight:700;font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.04em;}
.case,.q{font-size:14px;margin:6px 0;}
.reply{font-family:ui-monospace,Menlo,monospace;white-space:pre-wrap;color:var(--reply);background:#fff7f7;border:1px solid #f0d6d6;border-radius:6px;padding:8px 10px;margin:6px 0;font-size:13px;}
.opts{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px;}
.opt{border:1px solid var(--bd);border-radius:20px;padding:7px 14px;cursor:pointer;font-size:14px;user-select:none;}
.opt input{margin-right:6px;}
.opt.sel{border-color:var(--accent);background:#eaf2fb;font-weight:600;}
.notes{width:100%;margin-top:8px;font-size:13px;padding:6px 8px;border:1px solid var(--bd);border-radius:6px;}
.miss{color:#b00;}
footer{position:fixed;bottom:0;left:0;right:0;background:#fff;border-top:1px solid var(--bd);padding:10px 16px;}
.fwrap{max-width:860px;margin:0 auto;display:flex;align-items:center;gap:12px;}
</style>
</head>
<body>
<header>
  <h1>Response-Classifier Validation — Reviewer __REVIEWER__</h1>
  <div class="sub">14-model corpus · <span id="total"></span> responses · blinded &amp; anonymized · 每題選一個標籤 / pick one label per item. 進度自動暫存於本機。</div>
  <div class="defs">
    <div><b>valid</b> — usable 1–4 rating (even with extra text / truncated after the number). 有效評分。</div>
    <div><b>refusal</b> — declines / evades (ethical, "as an AI…", "I can't help", "irrelevant / skip"). 拒答或迴避。</div>
    <div><b>unparseable_or_error</b> — no rating &amp; not a clear refusal (empty, off-topic, truncated before any number, API error). 無法解析／錯誤。</div>
  </div>
  <div class="bar"><progress id="prog" value="0" max="1"></progress><span id="count" class="sub"></span></div>
</header>
<main id="items"></main>
<footer><div class="fwrap">
  <button class="btn" id="dl">⬇ Download answers (CSV)</button>
  <span id="status" class="sub"></span>
  <span class="sub" style="margin-left:auto">送回此 CSV 給研究者 / return this CSV</span>
</div></footer>
<script>
const REVIEWER="__REVIEWER__", DATESTAMP="__DATESTAMP__";
const OPTS=["valid","refusal","unparseable_or_error"];
const ITEMS=__DATA__;
const LS="valstudy_"+DATESTAMP+"_rev"+REVIEWER;
const answers=JSON.parse(localStorage.getItem(LS)||"{}");
const esc=s=>String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
function save(){localStorage.setItem(LS,JSON.stringify(answers));}
function answered(){return ITEMS.filter(it=>answers[it.rid]&&answers[it.rid].label).length;}
function update(){const n=answered(),t=ITEMS.length;
  prog.value=n;prog.max=t;count.textContent=n+" / "+t;
  status.innerHTML=n<t?('<span class="miss">'+(t-n)+' unanswered</span>'):"all answered ✓";}
function setLabel(rid,val){(answers[rid]=answers[rid]||{}).label=val;
  const c=document.getElementById("c_"+rid);c.classList.add("done");
  c.querySelectorAll(".opt").forEach(l=>l.classList.toggle("sel",l.querySelector("input").value===val));
  save();update();}
function render(){const root=document.getElementById("items");total.textContent=ITEMS.length;
  ITEMS.forEach(it=>{const a=answers[it.rid]||{};
    const card=document.createElement("section");card.className="card"+(a.label?" done":"");card.id="c_"+it.rid;
    const opts=OPTS.map(o=>'<label class="opt'+(a.label===o?' sel':'')+'"><input type="radio" name="q_'+it.rid+'" value="'+o+'" '+(a.label===o?'checked':'')+'>'+o+'</label>').join("");
    card.innerHTML='<div><span class="cid">#'+String(it.idx).padStart(3,"0")+" "+it.rid+'</span> <span class="tag">· '+it.manon+" · "+it.lang+'</span></div>'+
      '<div class="case"><span class="lab">Case</span> ['+esc(it.vlabel)+"] "+esc(it.vtext)+'</div>'+
      '<div class="q"><span class="lab">Question</span> '+esc(it.stem)+" "+esc(it.item)+'</div>'+
      '<div class="reply">'+esc(it.raw)+'</div>'+
      '<div class="opts">'+opts+'</div>'+
      '<input class="notes" placeholder="notes (optional)" value="'+esc(a.notes||"")+'">';
    root.appendChild(card);
    card.querySelectorAll("input[type=radio]").forEach(r=>r.addEventListener("change",()=>setLabel(it.rid,r.value)));
    card.querySelector(".notes").addEventListener("input",e=>{(answers[it.rid]=answers[it.rid]||{}).notes=e.target.value;save();});
  });update();}
function csvCell(s){s=(s==null?"":String(s));return /[",\n]/.test(s)?'"'+s.replace(/"/g,'""')+'"':s;}
document.getElementById("dl").addEventListener("click",()=>{
  const n=answered();
  if(n<ITEMS.length && !confirm((ITEMS.length-n)+" items unanswered. Download anyway?"))return;
  const head=["response_id","model_anon","language","raw_response_preview","reviewer_label","reviewer_notes"];
  const lines=[head.join(",")];
  ITEMS.forEach(it=>{const a=answers[it.rid]||{};
    lines.push([it.rid,it.manon,it.lang,it.preview,a.label||"",a.notes||""].map(csvCell).join(","));});
  const blob=new Blob(["﻿"+lines.join("\n")],{type:"text/csv;charset=utf-8"});
  const url=URL.createObjectURL(blob),a=document.createElement("a");
  a.href=url;a.download="reviewer"+REVIEWER+"_classification_filled_"+DATESTAMP+".csv";a.click();URL.revokeObjectURL(url);});
render();
</script>
</body>
</html>
"""


def write_html(rows, n):
    items = []
    for i, r in enumerate(rows, 1):
        vlabel, vtext, stem = render_context(r)
        prev = " ".join(r["raw_response"].split())
        if len(prev) > PREVIEW_CHARS:
            prev = prev[:PREVIEW_CHARS] + " …"
        items.append({"idx": i, "rid": r["_rid"], "manon": r["_manon"], "lang": r["_lang"].upper(),
                      "vlabel": vlabel, "vtext": vtext, "stem": stem, "item": r["item_text"],
                      "raw": r["raw_response"], "preview": prev})
    data = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    html = (HTML_TEMPLATE.replace("__REVIEWER__", str(n))
                         .replace("__DATESTAMP__", DATESTAMP)
                         .replace("__DATA__", data))
    p = HERE / f"reviewer{n}_form_{DATESTAMP}.html"
    p.write_text(html, encoding="utf-8")
    return p


# ----------------------------------------------------------------------------- summary
def print_summary(rows, model_map):
    import collections
    by_tier = collections.Counter(r["_tier"] for r in rows)
    by_lang = collections.Counter(r["_lang"] for r in rows)
    by_c3 = collections.Counter(r["_c3"] for r in rows)
    cross = collections.Counter((r["_lang"], r["_tier"], r["_c3"]) for r in rows)
    infra_n = sum(1 for r in rows if r["_infra"])

    print(f"\nTotal selected: {len(rows)}")
    print("by language:", dict(by_lang))
    print("by tier    :", dict(by_tier))
    print("by 3-class :", dict(by_c3))
    print(f"infra-error rows included: {infra_n}")
    print("\nlang/tier/3class composition:")
    for k in sorted(cross):
        print(f"   {k[0]} {k[1]:<10} {k[2]:<20} {cross[k]}")
    print("\nanonymization map (kept only in the key):")
    for real, anon in sorted(model_map.items(), key=lambda kv: kv[1]):
        print(f"   {anon} = {canon(real)}")


def main():
    for lang, path in DATA.items():
        if not path.exists():
            sys.exit(f"ERROR: missing source CSV: {path}")
    rng = random.Random(SEED)
    selected = []
    for lang in ("en", "zh"):
        selected.extend(sample_lang(load_rows(lang), rng))

    model_map = anonymize_models(selected, rng)
    rng.shuffle(selected)
    for i, r in enumerate(selected, 1):
        r["_rid"] = f"R{i:04d}"
        r["_manon"] = model_map[r["model"]]

    k = write_key(selected)
    b1 = write_blank_csv(selected, 1)
    b2 = write_blank_csv(selected, 2)
    d = write_docx(selected)
    h1 = write_html(selected, 1)
    h2 = write_html(selected, 2)
    print_summary(selected, model_map)
    print("\nwrote:")
    for p in (d, h1, h2, b1, b2, k):
        print("  ", p.relative_to(ROOT))


if __name__ == "__main__":
    main()
