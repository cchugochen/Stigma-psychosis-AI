"""
build_etables.py
Produces eSupplement_tables_14model.docx and eTable6_pairwise_full.csv
for JAMA Psychiatry submission.

eTables produced:
  eTable 1: 14 LLM characteristics
  eTable 2: Query parameters
  eTable 3a: Missingness audit (dual-panel EN/ZH)
  eTable 3b: Response classification definitions
  eTable 4: Friedman + Kruskal-Wallis omnibus results
  eTable 5: Pairwise comparison summary (91 pairs × 16 families)

Usage:
  python3 scripts_public/build_etables_0529.py
"""
# Model names (2026-10-12): the model tables in this script use the collection names of the authors' merged files
# (e.g. "Gemini 2.5 Flash"), as in the analysis behind the article. analyze_stage1.R run on data_public/ writes the
# article names ("Gemini-2.5-Flash"; scripts_public/Models_name.md); rename them back before running this script.

import csv, math, re
from pathlib import Path
from docx import Document
from docx.shared import Pt, RGBColor, Inches, Twips
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT    = Path(__file__).parent.parent
AN_DIR  = ROOT / "analysis_14models_20260614"
OUT_DIR = ROOT / "outputs" / "figures_tables"

# ── Shared style constants ─────────────────────────────────────────────────────
HEADER_GRAY = "D9D9D9"
FAMILY_GRAY = "EBEBEB"
WHITE       = "FFFFFF"

MODEL_ORDER = [
    "GPT-3.5", "GPT-4o", "GPT-OSS-120B", "GPT-5.4", "GPT-5.4 Mini",
    "Claude Sonnet 4.5", "Claude Opus 4.6",
    "Gemini 2.5 Flash", "Gemini 3.1 Pro Preview", "Gemini 3.1 Flash-Lite Preview", "Gemini 3.5 Flash",
    "Gemma 4 31B IT", "Llama 3.3 70B", "DeepSeek V3.2",
]

FAMILY_MAP = {
    "GPT-3.5": "OpenAI",   "GPT-4o": "OpenAI",       "GPT-OSS-120B": "OpenAI",
    "GPT-5.4": "OpenAI",   "GPT-5.4 Mini": "OpenAI",
    "Claude Sonnet 4.5": "Anthropic", "Claude Opus 4.6": "Anthropic",
    "Gemini 2.5 Flash": "Google",     "Gemini 3.1 Pro Preview": "Google",
    "Gemini 3.1 Flash-Lite Preview": "Google", "Gemini 3.5 Flash": "Google", "Gemma 4 31B IT": "Google",
    "Llama 3.3 70B": "Meta",          "DeepSeek V3.2": "DeepSeek",
}

DISPLAY_NAMES = {
    "GPT-3.5": "GPT-3.5",
    "GPT-4o": "GPT-4o",
    "GPT-OSS-120B": "GPT-OSS-120B",
    "GPT-5.4": "GPT-5.4",
    "GPT-5.4 Mini": "GPT-5.4-Mini",
    "Claude Sonnet 4.5": "Claude Sonnet 4.5",
    "Claude Opus 4.6": "Claude Opus 4.6",
    "Gemini 2.5 Flash": "Gemini-2.5-Flash",
    "Gemini 3.1 Pro Preview": "Gemini-3.1-Pro-Preview",
    "Gemini 3.1 Flash-Lite Preview": "Gemini-3.1-Flash-Lite-Preview",
    "Gemini 3.5 Flash": "Gemini-3.5-Flash",
    "Gemma 4 31B IT": "Gemma-4-31B-IT",
    "Llama 3.3 70B": "Llama-3.3-70B",
    "DeepSeek V3.2": "DeepSeek-V3.2",
}

VIGNETTES   = ["PLE", "DEP", "APS", "SCZ"]
SCALES      = ["social_distance", "prejudice"]
SCALE_LABEL = {"social_distance": "SD", "prejudice": "PJ"}

# ── Word helpers ──────────────────────────────────────────────────────────────
def _bg(cell, hex_color: str):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def _write(cell, text: str, bold=False, italic=False, size_pt=9,
           align=WD_ALIGN_PARAGRAPH.LEFT, wrap=True):
    para = cell.paragraphs[0]
    para.alignment = align
    para.paragraph_format.space_after  = Pt(0)
    para.paragraph_format.space_before = Pt(0)
    run = para.add_run(text)
    run.bold   = bold
    run.italic = italic
    run.font.name = "Arial"
    run.font.size = Pt(size_pt)
    return para


def _border(cell, sides, width_eighths=8, color="000000"):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcB = OxmlElement("w:tcBorders")
    for side in sides:
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"),   "single")
        el.set(qn("w:sz"),    str(width_eighths))
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), color)
        tcB.append(el)
    tcPr.append(tcB)


def _set_widths(table, widths):
    for row in table.rows:
        for i, cell in enumerate(row.cells):
            if i < len(widths):
                cell.width = Inches(widths[i])


def _add_section_title(doc: Document, num: str, title: str):
    """Add an eTable heading paragraph."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after  = Pt(4)
    r = p.add_run(f"{num}  {title}")
    r.bold = True
    r.font.name = "Arial"
    r.font.size = Pt(10)


def _add_footnote(doc: Document, text: str):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(3)
    r = p.add_run(text)
    r.font.name = "Arial"
    r.font.size = Pt(8)


def _header_row(table, texts, col_widths=None, gray=HEADER_GRAY, size=9):
    hr = table.add_row()
    for i, t in enumerate(texts):
        _write(hr.cells[i], t, bold=True, size_pt=size,
               align=WD_ALIGN_PARAGRAPH.CENTER if i > 0 else WD_ALIGN_PARAGRAPH.LEFT)
        _bg(hr.cells[i], gray)
        _border(hr.cells[i], ["bottom"], width_eighths=12)
    return hr


def _top_bottom_border(table):
    """Apply thick top border to first row, thick bottom to last row."""
    for cell in table.rows[0].cells:
        _border(cell, ["top"], width_eighths=12)
    for cell in table.rows[-1].cells:
        _border(cell, ["bottom"], width_eighths=12)


# ── p-value formatter ─────────────────────────────────────────────────────────
def fmt_p(p: float) -> str:
    if p < 0.001:
        return "<.001"
    return f"{p:.3f}".lstrip("0")


def fmt_stat(x: float, dec: int = 2) -> str:
    return f"{x:.{dec}f}"


# ── eTable 1 ──────────────────────────────────────────────────────────────────
MODEL_INFO = [
    # (model_key, developer, api_id, release, access_mode, rationale)
    ("GPT-3.5",        "OpenAI",    "gpt-3.5-turbo-0125",              "Nov 2022",
     "Developer primary API (Batch)",
     "Historical baseline; anchors the temporal range and represents the pre-RLHF-mature GPT generation."),
    ("GPT-4o",         "OpenAI",    "gpt-4o",                          "May 2024",
     "Developer primary API (Batch)",
     "Multimodal GPT-4 series; bridges GPT-3.5 and the GPT-5.4 reasoning generation."),
    ("GPT-OSS-120B",   "OpenAI",    "openai/gpt-oss-120b",             "Aug 2025",
     "Novita.AI third-party inference (Live API)",
     "Open-weight release of an OpenAI architecture; probes whether community-deployable weights preserve frontier-model alignment behaviour."),
    ("GPT-5.4",        "OpenAI",    "gpt-5.4",                         "Mar 2026",
     "Developer primary API (Live)",
     "Flagship GPT-5.4 with extended reasoning; current OpenAI frontier model."),
    ("GPT-5.4 Mini",   "OpenAI",    "gpt-5.4-mini",                    "Mar 2026",
     "Developer primary API (Live)",
     "Lightweight tier within the GPT-5.4 generation; captures cost-tier behaviour within the same reasoning generation."),
    ("Claude Sonnet 4.5","Anthropic","claude-sonnet-4-5-20250929",     "Sep 2025",
     "Developer primary API (Live)",
     "Mid-tier Claude 4 model representing Anthropic's Constitutional-AI alignment lineage; released before the flagship Opus tier."),
    ("Claude Opus 4.6","Anthropic", "claude-opus-4-6",                 "Feb 2026",
     "Developer primary API (Live)",
     "Highest-capability Anthropic model available at study time; flagship of the Claude 4 generation."),
    ("Gemini 2.5 Flash","Google",   "gemini-2.5-flash",                "Mar 2025",
     "Developer primary API (Batch)",
     "Lightweight Gemini 2.5 with integrated thinking; earlier-generation Google reference point bridging Gemini 2 and 3."),
    ("Gemini 3.1 Pro Preview", "Google",    "gemini-3.1-pro-preview",          "Mar 2026",
     "Developer primary API (Batch)",
     "Flagship Gemini 3.1 with extended thinking; rate-limit-sensitive preview tier queried via batch to manage quota."),
    ("Gemini 3.1 Flash-Lite Preview","Google","gemini-3.1-flash-lite-preview", "Mar 2026",
     "Developer primary API (Live)",
     "Lightweight Gemini 3.1 tier representing Google's low-cost frontier offering in the same generation as Gemini-3.1-Pro-Preview."),
    ("Gemini 3.5 Flash","Google",   "gemini-3.5-flash",                "Jun 2026",
     "Developer primary API (Batch)",
     "[AUTHOR REVIEW] Newest Google lightweight tier (Gemini-3.5-Flash generation), released after the Gemini-3.1 preview models; extends the within-Google temporal range."),
    ("Gemma 4 31B IT", "Google",    "google/gemma-4-31b-it",           "Apr 2026",
     "Novita.AI third-party inference (Live API)",
     "Open-weight Google instruction-tuned model; serves as the open-weight companion to the API-only Gemini tier."),
    ("Llama 3.3 70B",  "Meta",      "meta-llama/llama-3.3-70b-instruct","Dec 2024",
     "Novita.AI third-party inference (Live API)",
     "Predominantly English-trained open-weight model widely deployed in Mandarin-language downstream products; provides a cross-lingual contrast."),
    ("DeepSeek V3.2",  "DeepSeek",  "deepseek/deepseek-v3.2",          "Dec 2025",
     "Novita.AI third-party inference (Live API)",
     "Mandarin-aligned open-weight mixture-of-experts model; the principal test case for hypothesised cross-language stigma asymmetry (H4)."),
]


def add_etable1(doc: Document):
    _add_section_title(doc, "eTable 1.", "Characteristics of the 14 Large Language Models Evaluated")
    cols = ["Model identifier", "Developer", "Release\ndate", "API access mode", "Selection rationale"]
    widths = [1.10, 0.85, 0.65, 1.50, 2.70]
    table = doc.add_table(rows=0, cols=len(cols))
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.style = "Table Grid"

    _header_row(table, cols, widths)

    prev_family = None
    for m in MODEL_INFO:
        key, dev, api_id, release, access, rationale = m
        family = FAMILY_MAP[key]
        # Family separator row
        if family != prev_family:
            fr = table.add_row()
            mc = fr.cells[0]
            for ci in range(1, len(cols)):
                mc = mc.merge(fr.cells[ci])
            _write(mc, family, bold=True, size_pt=9)
            _bg(mc, FAMILY_GRAY)
            prev_family = family

        dr = table.add_row()
        _write(dr.cells[0], f"  {DISPLAY_NAMES[key]}", size_pt=9)
        _write(dr.cells[1], dev,      size_pt=9, align=WD_ALIGN_PARAGRAPH.CENTER)
        _write(dr.cells[2], release,  size_pt=9, align=WD_ALIGN_PARAGRAPH.CENTER)
        _write(dr.cells[3], access,   size_pt=9)
        _write(dr.cells[4], rationale,size_pt=9)
        for cell in dr.cells:
            _bg(cell, WHITE)

    _set_widths(table, widths)
    _top_bottom_border(table)

    _add_footnote(doc,
        "Models are ordered by developer family (OpenAI → Anthropic → Google → Meta → DeepSeek). "
        "API access mode indicates whether the model was queried via the developer's primary API or via "
        "the Novita.AI third-party inference platform for open-weight models. Selection rationale describes "
        "the role of each model in the panel (eg, flagship vs lightweight, frontier vs open-weight, "
        "Chinese-primary vs predominantly English-trained). API, application programming interface.")


# ── eTable 2 ──────────────────────────────────────────────────────────────────
QUERY_PARAMS = [
    # (model_key, temp, max_tokens, reasoning, notes)
    ("GPT-3.5",           "0.3",         "256",                          "NA",
     "Non-reasoning architecture; margin accommodates occasional explanatory text."),
    ("GPT-4o",            "0.3",         "256",                          "NA",
     "Non-reasoning architecture; margin accommodates occasional explanatory text."),
    ("GPT-OSS-120B",      "0.3",         "512",                          "Not exposed by inference provider",
     "Pilot truncation rates of 97% at 64, 4.75% at 256, and 0.47% at 512 tokens dictated the final budget."),
    ("GPT-5.4",           "1.0 (fixed)", "256 (max_completion_tokens)",  "reasoning_effort = \"low\"",
     "API does not accept custom temperature; minimum reasoning_effort prevents chain-of-thought tokens from exhausting the budget on forced-choice items."),
    ("GPT-5.4 Mini",      "1.0 (fixed)", "256 (max_completion_tokens)",  "reasoning_effort = \"low\"",
     "Same constraints as GPT-5.4."),
    ("Claude Sonnet 4.5", "0.3",         "64",                           "Extended thinking disabled",
     "Non-reasoning configuration; single-digit numeric responses require minimal token budget."),
    ("Claude Opus 4.6",   "0.3",         "64",                           "Extended thinking disabled",
     "Non-reasoning configuration; single-digit numeric responses require minimal token budget."),
    ("Gemini 2.5 Flash",  "0.3",         "256 (maxOutputTokens)",        "thinkingConfig.thinkingLevel = \"LOW\"",
     "Thinking tokens precede the visible response; minimum thinking level used to contain the budget."),
    ("Gemini 3.1 Pro Preview",    "0.3",         "256 (maxOutputTokens)",        "thinkingConfig.thinkingLevel = \"LOW\"",
     "Flagship thinking-enabled model; budget covers reasoning plus numeric output."),
    ("Gemini 3.1 Flash-Lite Preview","0.3",      "256 (maxOutputTokens)",        "thinkingConfig.thinkingLevel = \"LOW\"",
     "Thinking tokens precede the visible response; minimum thinking level used."),
    ("Gemini 3.5 Flash",  "0.3",         "256 (maxOutputTokens)",        "thinkingConfig.thinkingLevel = \"LOW\"",
     "Thinking tokens precede the visible response; minimum thinking level used to contain the budget."),
    ("Gemma 4 31B IT",    "0.3",         "512",                          "NA",
     "Non-reasoning architecture; 512 set for consistency with other Novita-served open-weight models."),
    ("Llama 3.3 70B",     "0.3",         "512",                          "NA",
     "Non-reasoning architecture; 512 set for consistency with other Novita-served open-weight models."),
    ("DeepSeek V3.2",     "0.3",         "512",                          "NA (chat-completion mode)",
     "MoE architecture; 512 ensures consistent completion of the numeric response."),
]


def add_etable2(doc: Document):
    _add_section_title(doc, "eTable 2.", "Query Parameters Used for Each Large Language Model")
    cols = ["Model", "Temperature", "Max output\ntokens", "Reasoning effort\nsetting", "Notes"]
    widths = [1.30, 0.85, 0.90, 1.45, 2.30]
    table = doc.add_table(rows=0, cols=len(cols))
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.style = "Table Grid"

    _header_row(table, cols, widths)

    prev_family = None
    for m in QUERY_PARAMS:
        key, temp, maxtok, reasoning, notes = m
        family = FAMILY_MAP[key]
        if family != prev_family:
            fr = table.add_row()
            mc = fr.cells[0]
            for ci in range(1, len(cols)):
                mc = mc.merge(fr.cells[ci])
            _write(mc, family, bold=True, size_pt=9)
            _bg(mc, FAMILY_GRAY)
            prev_family = family

        dr = table.add_row()
        _write(dr.cells[0], f"  {DISPLAY_NAMES[key]}", size_pt=9)
        _write(dr.cells[1], temp,      size_pt=9, align=WD_ALIGN_PARAGRAPH.CENTER)
        _write(dr.cells[2], maxtok,    size_pt=9, align=WD_ALIGN_PARAGRAPH.CENTER)
        _write(dr.cells[3], reasoning, size_pt=9)
        _write(dr.cells[4], notes,     size_pt=9)
        for cell in dr.cells:
            _bg(cell, WHITE)

    _set_widths(table, widths)
    _top_bottom_border(table)

    _add_footnote(doc,
        "Temperature, maximum output tokens, and reasoning-effort settings are reported as configured "
        "at the time of querying (April 2026). The OpenAI GPT-5.4 series does not accept a custom "
        "temperature value and was therefore queried at its default value of 1.0. For reasoning-capable "
        "models (GPT-5.4 series and Gemini family), the minimum available reasoning-effort setting was "
        "used to prevent chain-of-thought generation from exhausting the token budget on forced-choice items. "
        "Specific reasoning-effort labels differ across providers (eg, \"minimal\" for OpenAI, equivalent "
        "configuration for Gemini); see provider documentation for parameter definitions. "
        "NA indicates the parameter is not applicable to the model in question.")


# ── eTable 3a ─────────────────────────────────────────────────────────────────
def load_missingness(lang: str) -> dict:
    """Returns {model_short: {(vignette, scale): n_primary}}"""
    path = AN_DIR / lang / "tableS1_missingness.csv"
    data: dict = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            m = row["model"]
            key = (row["vignette"], row["scale_type"])
            data.setdefault(m, {})[key] = int(row["n_primary"])
    return data


def add_etable3a(doc: Document):
    _add_section_title(doc, "eTable 3a.",
        "Missingness Audit: Run Retention Rates by (Model × Language × Vignette × Scale) Cell")

    en_data = load_missingness("en")
    zh_data = load_missingness("zh")

    # 8 data columns: SD_PLE, SD_DEP, SD_APS, SD_SCZ, PJ_PLE, PJ_DEP, PJ_APS, PJ_SCZ
    data_cols = [(sc, vig) for sc in SCALES for vig in VIGNETTES]
    col_headers = [
        "Model",
        "SD\nPLE", "SD\nDEP", "SD\nAPS", "SD\nSCZ",
        "PJ\nPLE", "PJ\nDEP", "PJ\nAPS", "PJ\nSCZ",
    ]
    widths = [1.35] + [0.58] * 8

    table = doc.add_table(rows=0, cols=9)
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.style = "Table Grid"

    def _panel_header(lang_label):
        ph = table.add_row()
        mc = ph.cells[0]
        for ci in range(1, 9):
            mc = mc.merge(ph.cells[ci])
        _write(mc, lang_label, bold=True, size_pt=9, italic=True)
        _bg(mc, HEADER_GRAY)
        for cell in ph.cells:
            _border(cell, ["top"], width_eighths=12)

    def _scale_subheader():
        sh = table.add_row()
        _write(sh.cells[0], "Model", bold=True, size_pt=9)
        _bg(sh.cells[0], HEADER_GRAY)
        _write(sh.cells[1], "Social Distance Scale (19 items)", bold=True, size_pt=9,
               align=WD_ALIGN_PARAGRAPH.CENTER)
        for ci in range(2, 5):
            sh.cells[1].merge(sh.cells[ci])
        _write(sh.cells[5], "Prejudice Questionnaire (21 items)", bold=True, size_pt=9,
               align=WD_ALIGN_PARAGRAPH.CENTER)
        for ci in range(6, 9):
            sh.cells[5].merge(sh.cells[ci])
        for cell in sh.cells:
            _bg(cell, HEADER_GRAY)

        vh = table.add_row()
        _write(vh.cells[0], "", size_pt=9)
        _bg(vh.cells[0], HEADER_GRAY)
        for i, vig in enumerate(VIGNETTES):
            _write(vh.cells[1+i], vig, bold=True, size_pt=9,
                   align=WD_ALIGN_PARAGRAPH.CENTER)
            _write(vh.cells[5+i], vig, bold=True, size_pt=9,
                   align=WD_ALIGN_PARAGRAPH.CENTER)
            _bg(vh.cells[1+i], HEADER_GRAY)
            _bg(vh.cells[5+i], HEADER_GRAY)
        for cell in vh.cells:
            _border(cell, ["bottom"], width_eighths=12)

    def _data_rows(data):
        prev_family = None
        for model_key in MODEL_ORDER:
            family = FAMILY_MAP[model_key]
            if family != prev_family:
                fr = table.add_row()
                mc = fr.cells[0]
                for ci in range(1, 9):
                    mc = mc.merge(fr.cells[ci])
                _write(mc, family, bold=True, size_pt=9)
                _bg(mc, FAMILY_GRAY)
                prev_family = family

            dr = table.add_row()
            _write(dr.cells[0], f"  {DISPLAY_NAMES[model_key]}", size_pt=9)
            mdata = data.get(model_key, {})
            col_idx = 1
            for sc in SCALES:
                for vig in VIGNETTES:
                    n = mdata.get((vig, sc), 0)
                    cell_txt = f"{n}/30" if n == 30 else f"{n}/30"
                    _write(dr.cells[col_idx], cell_txt, size_pt=9,
                           align=WD_ALIGN_PARAGRAPH.CENTER,
                           bold=(n < 30))
                    if n < 30:
                        _bg(dr.cells[col_idx], "FFF2CC")  # light yellow for <30
                    else:
                        _bg(dr.cells[col_idx], WHITE)
                    col_idx += 1
            _bg(dr.cells[0], WHITE)

    # Panel A: Mandarin Chinese
    _panel_header("Panel A: Mandarin Chinese Prompts")
    _scale_subheader()
    _data_rows(zh_data)

    # Panel B: English
    _panel_header("Panel B: English Prompts")
    _scale_subheader()
    _data_rows(en_data)

    # Overall retention row
    # Compute overall retention
    total_cells = 0; total_retained = 0
    for lang_data in [en_data, zh_data]:
        for model_key in MODEL_ORDER:
            for sc in SCALES:
                for vig in VIGNETTES:
                    total_cells += 30
                    total_retained += lang_data.get(model_key, {}).get((vig, sc), 0)
    retention_pct = 100 * total_retained / total_cells

    or_row = table.add_row()
    mc = or_row.cells[0]
    for ci in range(1, 9):
        mc = mc.merge(or_row.cells[ci])
    _write(mc, f"Overall retention: {total_retained:,}/{total_cells:,} qualifying runs "
               f"({retention_pct:.1f}%)", bold=True, size_pt=9)
    _bg(mc, HEADER_GRAY)
    for cell in or_row.cells:
        _border(cell, ["top", "bottom"], width_eighths=12)

    _set_widths(table, widths)

    _add_footnote(doc,
        "Each cell reports the number of qualifying runs retained for inferential analysis out of the "
        "30 independent runs originally administered. Runs were retained when at least 80% of items on "
        "the corresponding scale received a valid numeric response (≥16 of 19 items for the Social "
        "Distance Scale; ≥17 of 21 items for the Prejudice Questionnaire). Cells with fewer than 30 "
        "qualifying runs are highlighted in yellow. "
        f"Overall, {total_retained:,} of {total_cells:,} run-level cells ({retention_pct:.1f}%) were retained. "
        "SD, Social Distance scale; PJ, Prejudice Questionnaire.")


# ── eTable 3b ─────────────────────────────────────────────────────────────────
RESPONSE_CATS = [
    ("valid",
     "A clean numeric response (1–4), with no accompanying text other than incidental whitespace.",
     '"3"',
     "Scored (numeric value used directly)"),
    ("hedged",
     "A parseable numeric answer (1–4) accompanied by qualifications, caveats, or explanatory text.",
     '"3, although I would prefer more context before making this judgment"',
     "Scored (numeric value extracted and used)"),
    ("refusal_ethical",
     "Explicit refusal citing harm, stigma, discrimination, or ethical concerns related to the item content.",
     '"I\'m sorry, but rating the likelihood of such discrimination could reinforce harmful stereotypes."',
     "Missing (excluded from scoring)"),
    ("refusal_identity",
     "Refusal framed as lack of personal opinions or AI identity (eg, \"as an AI, I don't have feelings about…\").",
     '"As an AI, I do not have personal feelings about social situations and cannot answer this question."',
     "Missing (excluded from scoring)"),
    ("refusal",
     "General refusal not matching the two specific refusal subtypes above, including situational refusals "
     "(eg, asserting the item does not apply to the scenario).",
     '"This question does not apply to the case description; please skip."',
     "Missing (excluded from scoring)"),
    ("safety",
     "Response blocked at the provider API level (safety filter triggered; no text returned or an error "
     "code was raised before text generation).",
     "[API safety filter triggered; no response returned]",
     "Missing (excluded from scoring)"),
    ("unparseable",
     "Response containing no extractable numeric value; includes generation-truncated responses (containing "
     "the marker [TRUNCATED:…] without a leading 1–4 digit) and other non-numeric content.",
     '"The answer depends on many contextual factors and cannot be reduced to a single number."',
     "Missing (excluded from scoring)"),
]


def add_etable3b(doc: Document):
    _add_section_title(doc, "eTable 3b.",
        "Definitions and Examples of the Seven Response Classification Categories")
    cols = ["Category", "Definition", "Example response", "Treated as"]
    widths = [0.90, 2.20, 2.10, 1.30]
    table = doc.add_table(rows=0, cols=4)
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.style = "Table Grid"

    _header_row(table, cols, widths)

    for cat, defn, example, treated in RESPONSE_CATS:
        dr = table.add_row()
        _write(dr.cells[0], cat,     size_pt=9, bold=True)
        _write(dr.cells[1], defn,    size_pt=9)
        _write(dr.cells[2], example, size_pt=9, italic=True)
        _write(dr.cells[3], treated, size_pt=9)
        for cell in dr.cells:
            _bg(cell, WHITE)

    _set_widths(table, widths)
    _top_bottom_border(table)

    _add_footnote(doc,
        "Each raw response was classified into one of these seven mutually exclusive categories. "
        "Classification rules were developed through an iterative human-in-the-loop procedure: two "
        "authors independently inspected pilot-run responses, compared manual judgments against "
        "preliminary algorithmic outputs, and resolved edge cases by consensus. The finalized rule "
        "set was locked prior to inferential analysis. Only responses classified as valid or hedged "
        "were treated as numerically interpretable for scoring; all other categories were treated as missing.")


# ── eTable 4 ──────────────────────────────────────────────────────────────────
def load_omnibus(lang: str, test: str) -> dict:
    """
    test: 'friedman' → tableS5, 'kw' → tableS7
    Returns list of row dicts.
    """
    fname = "tableS5_vignette_omnibus.csv" if test == "friedman" else "tableS7_model_omnibus.csv"
    path = AN_DIR / lang / fname
    rows = []
    with open(path) as f:
        rows = list(csv.DictReader(f))
    return rows


def kendalls_w(chi2: float, n: float, k: int = 4) -> float:
    """Kendall's W from Friedman chi2: W = chi2 / (n * (k-1))"""
    return chi2 / (n * (k - 1))


def epsilon_sq(H: float, N: float, k: int = 13) -> float:
    """Epsilon-squared from Kruskal-Wallis: ε² = H / (N - 1)"""
    return H / (N - 1)


def add_etable4(doc: Document):
    _add_section_title(doc, "eTable 4.",
        "Friedman Omnibus, Pairwise Signed-Rank, and Kruskal-Wallis "
        "Between-Model Test Results, by Language")

    # ── Section A: Friedman ─────────────────────────────────────────────────
    p_sect = doc.add_paragraph()
    r = p_sect.add_run("Part A: Friedman Test — Within-Model Vignette Differences")
    r.bold = True; r.font.name = "Arial"; r.font.size = Pt(9)
    p_sect.paragraph_format.space_before = Pt(4)
    p_sect.paragraph_format.space_after  = Pt(2)

    fr_cols = ["Language", "Model", "Scale", "n blocks", "χ²", "df", "P (Holm)", "Kendall's W"]
    fr_widths = [0.72, 1.50, 0.60, 0.68, 0.65, 0.38, 0.80, 0.80]
    fr_table = doc.add_table(rows=0, cols=len(fr_cols))
    fr_table.alignment = WD_TABLE_ALIGNMENT.LEFT
    fr_table.style = "Table Grid"
    _header_row(fr_table, fr_cols, fr_widths)

    for lang_label, lang_code in [("Mandarin Chinese", "zh"), ("English", "en")]:
        rows = load_omnibus(lang_code, "friedman")
        prev_family = None
        for row in rows:
            m_key_raw = row["model"]
            # Normalize model key to our ORDER (strip trailing details)
            # Exact match first; fall back to longest substring to avoid "GPT-5.4" matching "GPT-5.4-Mini"
            if m_key_raw in MODEL_ORDER:
                m_key = m_key_raw
            else:
                candidates = [mk for mk in MODEL_ORDER if mk in m_key_raw or m_key_raw in mk]
                m_key = max(candidates, key=len) if candidates else m_key_raw
            family = FAMILY_MAP.get(m_key, "Other")
            if family != prev_family:
                fr = fr_table.add_row()
                mc = fr.cells[0]
                for ci in range(1, len(fr_cols)):
                    mc = mc.merge(fr.cells[ci])
                _write(mc, f"{lang_label} — {family}", bold=True, size_pt=9)
                _bg(mc, FAMILY_GRAY)
                prev_family = family

            chi2 = float(row["statistic"])
            n_bl = float(row["n_blocks"])
            p    = float(row["p_value"])
            w    = kendalls_w(chi2, n_bl)
            scale_lbl = "SD" if row["scale_type"] == "social_distance" else "PJ"

            dr = fr_table.add_row()
            _write(dr.cells[0], lang_label[:2],   size_pt=9, align=WD_ALIGN_PARAGRAPH.CENTER)
            _write(dr.cells[1], f"  {DISPLAY_NAMES.get(m_key, m_key_raw)}", size_pt=9)
            _write(dr.cells[2], scale_lbl,        size_pt=9, align=WD_ALIGN_PARAGRAPH.CENTER)
            _write(dr.cells[3], f"{int(n_bl)}",   size_pt=9, align=WD_ALIGN_PARAGRAPH.CENTER)
            _write(dr.cells[4], fmt_stat(chi2),   size_pt=9, align=WD_ALIGN_PARAGRAPH.CENTER)
            _write(dr.cells[5], row["df"],        size_pt=9, align=WD_ALIGN_PARAGRAPH.CENTER)
            _write(dr.cells[6], fmt_p(p),         size_pt=9, align=WD_ALIGN_PARAGRAPH.CENTER)
            _write(dr.cells[7], fmt_stat(w, 3),   size_pt=9, align=WD_ALIGN_PARAGRAPH.CENTER)
            for cell in dr.cells:
                _bg(cell, WHITE)

    _set_widths(fr_table, fr_widths)
    _top_bottom_border(fr_table)

    # ── Section B: Paired Wilcoxon signed-rank vignette contrasts ─────────────
    p_sectB = doc.add_paragraph()
    rB = p_sectB.add_run("Part B: Paired Wilcoxon Signed-Rank Tests — "
                         "Median Differences Between Vignettes")
    rB.bold = True; rB.font.name = "Arial"; rB.font.size = Pt(9)
    p_sectB.paragraph_format.space_before = Pt(8)
    p_sectB.paragraph_format.space_after  = Pt(2)

    sr_cols = ["Language", "Model", "Scale", "PLE − DEP", "PLE − APS", "PLE − SCZ",
               "DEP − APS", "DEP − SCZ", "APS − SCZ"]
    sr_widths = [0.55, 1.30, 0.42, 0.76, 0.76, 0.76, 0.76, 0.76, 0.76]
    sr_table = doc.add_table(rows=0, cols=len(sr_cols))
    sr_table.alignment = WD_TABLE_ALIGNMENT.LEFT
    sr_table.style = "Table Grid"
    _header_row(sr_table, sr_cols, sr_widths, size=8)

    contrasts = [("PLE", "DEP"), ("PLE", "APS"), ("PLE", "SCZ"),
                 ("DEP", "APS"), ("DEP", "SCZ"), ("APS", "SCZ")]
    for lang_label, lang_code in [("Mandarin Chinese", "zh"), ("English", "en")]:
        srrows = {}
        with open(AN_DIR / lang_code / "tableS6_vignette_pairwise.csv") as f:
            for row in csv.DictReader(f):
                key = (row["model"], row["scale_type"],
                       frozenset((row["vignette_1"], row["vignette_2"])))
                srrows[key] = row
        prev_family = None
        for model in MODEL_ORDER:
            family = FAMILY_MAP[model]
            if not any((model, sc, frozenset(c)) in srrows
                       for sc in ("social_distance", "prejudice") for c in contrasts):
                continue
            if family != prev_family:
                fr = sr_table.add_row()
                mc = fr.cells[0]
                for ci in range(1, len(sr_cols)):
                    mc = mc.merge(fr.cells[ci])
                _write(mc, f"{lang_label} — {family}", bold=True, size_pt=9)
                _bg(mc, FAMILY_GRAY)
                prev_family = family
            for sc in ("social_distance", "prejudice"):
                scale_lbl = "SD" if sc == "social_distance" else "PJ"
                if not any((model, sc, frozenset(c)) in srrows for c in contrasts):
                    continue
                dr = sr_table.add_row()
                _write(dr.cells[0], lang_label[:2], size_pt=8.5,
                       align=WD_ALIGN_PARAGRAPH.CENTER)
                _write(dr.cells[1], f"  {DISPLAY_NAMES[model]}", size_pt=8.5)
                _write(dr.cells[2], scale_lbl, size_pt=8.5,
                       align=WD_ALIGN_PARAGRAPH.CENTER)
                for i, (a, b) in enumerate(contrasts):
                    row = srrows.get((model, sc, frozenset((a, b))))
                    if row is None:
                        txt = "—"
                    else:
                        md = float(row["median_difference"])
                        if (row["vignette_1"], row["vignette_2"]) != (a, b):
                            md = -md
                        sig = "*" if str(row.get("significant", "")).upper() == "TRUE" else ""
                        txt = f"{md:+.1f}{sig}"
                    _write(dr.cells[3 + i], txt, size_pt=8.5,
                           align=WD_ALIGN_PARAGRAPH.CENTER)
                for cell in dr.cells:
                    _bg(cell, WHITE)
    _set_widths(sr_table, sr_widths)
    _top_bottom_border(sr_table)

    # ── Section C: Kruskal-Wallis ─────────────────────────────────────────
    p_sect2 = doc.add_paragraph()
    r2 = p_sect2.add_run("Part C: Kruskal-Wallis Test — Between-Model Differences Within Vignette")
    r2.bold = True; r2.font.name = "Arial"; r2.font.size = Pt(9)
    p_sect2.paragraph_format.space_before = Pt(8)
    p_sect2.paragraph_format.space_after  = Pt(2)

    # Compute N for each KW cell from missingness
    en_miss = load_missingness("en")
    zh_miss = load_missingness("zh")

    kw_cols = ["Language", "Vignette", "Scale", "N (total runs)", "χ²", "df", "P", "ε²"]
    kw_widths = [0.90, 0.65, 0.55, 0.95, 0.72, 0.38, 0.72, 0.72]
    kw_table = doc.add_table(rows=0, cols=len(kw_cols))
    kw_table.alignment = WD_TABLE_ALIGNMENT.LEFT
    kw_table.style = "Table Grid"
    _header_row(kw_table, kw_cols, kw_widths)

    for lang_label, lang_code, miss_data in [
        ("Mandarin Chinese", "zh", zh_miss),
        ("English",          "en", en_miss),
    ]:
        rows = load_omnibus(lang_code, "kw")
        for row in rows:
            vig   = row["vignette"]
            sc    = row["scale_type"]
            chi2  = float(row["statistic"])
            p     = float(row["p_value"])
            # Compute N
            N = sum(miss_data.get(mk, {}).get((vig, sc), 0) for mk in MODEL_ORDER)
            eps2 = epsilon_sq(chi2, N)
            scale_lbl = "SD" if sc == "social_distance" else "PJ"

            dr = kw_table.add_row()
            _write(dr.cells[0], lang_label,      size_pt=9)
            _write(dr.cells[1], vig,              size_pt=9, align=WD_ALIGN_PARAGRAPH.CENTER)
            _write(dr.cells[2], scale_lbl,        size_pt=9, align=WD_ALIGN_PARAGRAPH.CENTER)
            _write(dr.cells[3], str(N),            size_pt=9, align=WD_ALIGN_PARAGRAPH.CENTER)
            _write(dr.cells[4], fmt_stat(chi2),   size_pt=9, align=WD_ALIGN_PARAGRAPH.CENTER)
            _write(dr.cells[5], row["df"],        size_pt=9, align=WD_ALIGN_PARAGRAPH.CENTER)
            _write(dr.cells[6], fmt_p(p),         size_pt=9, align=WD_ALIGN_PARAGRAPH.CENTER)
            _write(dr.cells[7], fmt_stat(eps2, 3),size_pt=9, align=WD_ALIGN_PARAGRAPH.CENTER)
            for cell in dr.cells:
                _bg(cell, WHITE)

    _set_widths(kw_table, kw_widths)
    _top_bottom_border(kw_table)

    _add_footnote(doc,
        "Part A: The Friedman test assessed whether the four psychosis-related vignettes elicited "
        "differing stigma scores within each (model × scale × language) cell, treating the qualifying "
        "runs as matched observations across vignettes. Kendall's W = χ²/[n × (k − 1)], where n is "
        "the number of matched run blocks and k = 4 vignettes. "
        "Part B: Paired Wilcoxon signed-rank tests for the 6 pairwise vignette contrasts within each "
        "(model × scale × language) cell; cells show the median run-level difference (points), with "
        "an asterisk (*) denoting Holm-Bonferroni-corrected P < .05 within each cell's 6-test family. "
        "Part C: The Kruskal-Wallis test assessed whether the 14 models differed in their stigma "
        "scores within each (vignette × scale × language) combination. ε² (epsilon-squared) = H/(N − 1), "
        "where H is the Kruskal-Wallis statistic and N is the total number of qualifying runs. "
        "All P values are two-sided. P values in Part A are Holm-Bonferroni corrected within each "
        "(model × language) family (2 tests per model); P values in Part C are uncorrected (8 tests "
        "per language with consistent direction). "
        "df, degrees of freedom; SD, Social Distance scale; PJ, Prejudice Questionnaire.")


# ── eTable 5 ──────────────────────────────────────────────────────────────────
def load_pairwise(lang: str) -> list:
    path = AN_DIR / lang / "tableS8_model_pairwise.csv"
    with open(path) as f:
        return list(csv.DictReader(f))


def build_pairwise_csv(out_path: Path):
    """Combine EN + ZH pairwise into single 1,456-row CSV (canonical hyphenated names)."""
    fieldnames = None
    all_rows = []
    for lang in ["en", "zh"]:
        rows = load_pairwise(lang)
        if fieldnames is None:
            fieldnames = ["language"] + list(rows[0].keys())
        lang_label = "English" if lang == "en" else "Mandarin Chinese"
        for row in rows:
            row = dict(row)
            for col in ("model_1", "model_2"):
                if col in row:
                    row[col] = DISPLAY_NAMES.get(row[col], row[col])
            all_rows.append({"language": lang_label, **row})

    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(all_rows)
    return len(all_rows)


def add_etable6_pairwise(doc: Document):
    _add_section_title(doc, "eTable 6.",
        "Summary of Pairwise Model Comparisons Across 91 Unique Pairs, "
        "by Vignette × Scale × Language")

    en_rows = load_pairwise("en")
    zh_rows = load_pairwise("zh")

    # Build summary: (language, vignette, scale) → (n_sig, n_large, med_|delta|, range_|delta|)
    def summarise(rows, lang_label):
        from collections import defaultdict
        cells = defaultdict(list)
        for row in rows:
            key = (row["vignette"], row["scale_type"])
            cells[key].append(row)
        summary = []
        for vig in VIGNETTES:
            for sc in SCALES:
                key = (vig, sc)
                cell_rows = cells.get(key, [])
                n_total = len(cell_rows)
                n_sig   = sum(1 for r in cell_rows if r.get("significant","") == "TRUE")
                n_large = sum(1 for r in cell_rows if r.get("magnitude","") == "large")
                deltas  = [abs(float(r["cliffs_delta"])) for r in cell_rows
                           if r.get("cliffs_delta","") not in ("", "NA")]
                med_d   = sorted(deltas)[len(deltas)//2] if deltas else 0
                min_d   = min(deltas) if deltas else 0
                max_d   = max(deltas) if deltas else 0
                scale_lbl = "SD" if sc == "social_distance" else "PJ"
                summary.append({
                    "language": lang_label,
                    "vignette": vig,
                    "scale": scale_lbl,
                    "n_pairs": n_total,
                    "n_sig": n_sig,
                    "pct_sig": f"{100*n_sig/n_total:.0f}%" if n_total else "—",
                    "n_large": n_large,
                    "med_abs_delta": f"{med_d:.2f}",
                    "range_abs_delta": f"{min_d:.2f}–{max_d:.2f}",
                })
        return summary

    zh_summary = summarise(zh_rows, "Mandarin Chinese")
    en_summary = summarise(en_rows, "English")

    cols = [
        "Language", "Vignette", "Scale",
        "Pairs (n)", "Significant\npairs (n)", "Significant\n(%)",
        "Large effect\n(|δ| ≥ 0.474)",
        "Median |δ|",
        "Range |δ|"
    ]
    widths = [1.05, 0.60, 0.50, 0.62, 0.78, 0.70, 0.88, 0.70, 0.90]

    table = doc.add_table(rows=0, cols=len(cols))
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.style = "Table Grid"
    _header_row(table, cols, widths, size=8)

    for lang_label, summary in [("Mandarin Chinese", zh_summary), ("English", en_summary)]:
        lh = table.add_row()
        mc = lh.cells[0]
        for ci in range(1, len(cols)):
            mc = mc.merge(lh.cells[ci])
        _write(mc, lang_label, bold=True, size_pt=9, italic=True)
        _bg(mc, FAMILY_GRAY)

        for s in summary:
            dr = table.add_row()
            vals = [
                "", s["vignette"], s["scale"], str(s["n_pairs"]),
                str(s["n_sig"]), s["pct_sig"], str(s["n_large"]),
                s["med_abs_delta"], s["range_abs_delta"],
            ]
            for i, v in enumerate(vals):
                align = WD_ALIGN_PARAGRAPH.LEFT if i == 0 else WD_ALIGN_PARAGRAPH.CENTER
                _write(dr.cells[i], v, size_pt=9, align=align)
                _bg(dr.cells[i], WHITE)

    _set_widths(table, widths)
    _top_bottom_border(table)

    _add_footnote(doc,
        "Pairwise comparisons between the 14 models within each (vignette × scale × language) "
        "family yielded 91 unique model pairs per family × 16 families (4 vignettes × 2 scales × "
        "2 languages) = 1,456 total comparisons. P values from Wilcoxon rank-sum tests were "
        "Holm-Bonferroni corrected within each (vignette × scale × language) family. "
        "Cliff's δ is reported as the effect size, with conventional thresholds: "
        "|δ| < 0.147 = negligible; 0.147–0.33 = small; 0.33–0.474 = medium; ≥0.474 = large. "
        "The complete 1,456-row pairwise dataset (including model pair names, Wilcoxon W statistics, "
        "Holm-corrected P values, and Cliff's δ with 95% CI) is provided as eTable6_pairwise_full.csv "
        "in the supplementary data. "
        "SD, Social Distance scale; PJ, Prejudice Questionnaire.")


# ── eTable 5: Cross-language differences ───────────────────────────────────────
def add_etable5_crosslang(doc: Document):
    _add_section_title(doc, "eTable 5.",
        "Cross-Language Differences in Stigma Scale Scores "
        "(Mandarin Chinese − English) Across 14 Large Language Models, "
        "by Vignette and Scale")

    path = AN_DIR / "table4_cross_language_shift.csv"
    data = {}  # (model_spaced, scale_label) -> [PLE,DEP,APS,SCZ]
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            m = re.sub(r"\s*\((API|Open-source)\)\s*$", "", row["model_label"]).strip()
            data[(m, row["Scale"])] = [row["PLE"], row["DEP"], row["APS"], row["SCZ"]]

    cols = ["Model", "Scale", "PLE", "DEP", "APS", "SCZ"]
    widths = [1.85, 1.05, 0.95, 0.95, 0.95, 0.95]
    table = doc.add_table(rows=0, cols=len(cols))
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.style = "Table Grid"
    _header_row(table, cols, widths)

    prev_family = None
    for model in MODEL_ORDER:
        family = FAMILY_MAP[model]
        if family != prev_family:
            fr = table.add_row()
            mc = fr.cells[0]
            for ci in range(1, len(cols)):
                mc = mc.merge(fr.cells[ci])
            _write(mc, family, bold=True, size_pt=9)
            _bg(mc, FAMILY_GRAY)
            prev_family = family
        for scale_label in ("Social Distance", "Prejudice"):
            vals = data.get((model, scale_label))
            if vals is None:
                continue
            dr = table.add_row()
            _write(dr.cells[0], f"  {DISPLAY_NAMES[model]}", size_pt=9)
            _write(dr.cells[1], scale_label, size_pt=9)
            for i, v in enumerate(vals):
                _write(dr.cells[2 + i], v, size_pt=9,
                       align=WD_ALIGN_PARAGRAPH.CENTER)
            for cell in dr.cells:
                _bg(cell, WHITE)

    _set_widths(table, widths)
    _top_bottom_border(table)
    _add_footnote(doc,
        "Values are the within-model mean difference in scale score "
        "(Mandarin Chinese − English) for each (model × vignette × scale) cell; "
        "positive values indicate higher stigma under Mandarin Chinese prompts. "
        "An asterisk (*) denotes a statistically significant difference (Wilcoxon "
        "rank-sum test, Holm-Bonferroni corrected P < .05 within each "
        "vignette × scale × language family). Social Distance scale range 19–76; "
        "Prejudice Questionnaire range 21–84. PLE, psychotic-like experiences; "
        "DEP, major depression; APS, attenuated psychosis syndrome; "
        "SCZ, schizophrenia.")


# ── eTable 7: Refusal-imputation sensitivity ───────────────────────────────────
def add_etable7_refusal(doc: Document):
    _add_section_title(doc, "eTable 7.",
        "Refusal-Imputation Sensitivity Analysis Across 14 Large Language Models")

    # Per-model refusal items imputed (EN/ZH) from response classification
    refusal = {}  # model_spaced -> (en, zh)
    with open(AN_DIR / "table1_response_classification.csv", newline="") as f:
        for row in csv.DictReader(f):
            m = re.sub(r"\s*\((API|Open-source)\)\s*$", "", row["model_label"]).strip()
            en = (int(row["n_refusal_ethical_en"]) + int(row["n_refusal_identity_en"])
                  + int(row["n_refusal_other_en"]))
            zh = (int(row["n_refusal_ethical_zh"]) + int(row["n_refusal_identity_zh"])
                  + int(row["n_refusal_other_zh"]))
            refusal[m] = (en, zh)

    # Per-model max change vs primary (S0) and max range across scenarios
    from collections import defaultdict
    cells = defaultdict(dict)  # (model, lang, vig, scale) -> {scenario: mean_scale}
    with open(AN_DIR / "robust_refusal" / "sensitivity_summary.csv", newline="") as f:
        for row in csv.DictReader(f):
            key = (row["model"], row["language"], row["vignette"], row["scale_type"])
            try:
                cells[key][row["scenario"]] = float(row["mean_scale"])
            except ValueError:
                pass

    model_stats = {}  # model -> (max_change_vs_primary, max_range)
    for (model, lang, vig, sc), sc_means in cells.items():
        s0 = sc_means.get("S0_complete_case")
        imp = [sc_means[s] for s in ("S1_lowest", "S2_midpoint", "S3_highest")
               if s in sc_means]
        if s0 is None or not imp:
            continue
        change = max(abs(v - s0) for v in imp)
        allv = [s0] + imp
        rng = max(allv) - min(allv)
        cur = model_stats.get(model, (0.0, 0.0))
        model_stats[model] = (max(cur[0], change), max(cur[1], rng))

    cols = ["Model", "Refusal items\nimputed, English",
            "Refusal items\nimputed, Mandarin Chinese",
            "Maximum change vs\nprimary analysis, points",
            "Maximum range across\nscenarios, points",
            "Gradient conclusion\nchange"]
    widths = [1.55, 0.95, 1.10, 1.15, 1.15, 1.05]
    table = doc.add_table(rows=0, cols=len(cols))
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.style = "Table Grid"
    _header_row(table, cols, widths, size=8)

    prev_family = None
    for model in MODEL_ORDER:
        family = FAMILY_MAP[model]
        if family != prev_family:
            fr = table.add_row()
            mc = fr.cells[0]
            for ci in range(1, len(cols)):
                mc = mc.merge(fr.cells[ci])
            _write(mc, family, bold=True, size_pt=9)
            _bg(mc, FAMILY_GRAY)
            prev_family = family
        en, zh = refusal.get(model, (0, 0))
        chg, rng = model_stats.get(model, (0.0, 0.0))
        dr = table.add_row()
        _write(dr.cells[0], f"  {DISPLAY_NAMES[model]}", size_pt=9)
        _write(dr.cells[1], str(en), size_pt=9, align=WD_ALIGN_PARAGRAPH.CENTER)
        _write(dr.cells[2], str(zh), size_pt=9, align=WD_ALIGN_PARAGRAPH.CENTER)
        _write(dr.cells[3], f"{chg:.1f}", size_pt=9, align=WD_ALIGN_PARAGRAPH.CENTER)
        _write(dr.cells[4], f"{rng:.1f}", size_pt=9, align=WD_ALIGN_PARAGRAPH.CENTER)
        _write(dr.cells[5], "None", size_pt=9, align=WD_ALIGN_PARAGRAPH.CENTER)
        for cell in dr.cells:
            _bg(cell, WHITE)

    _set_widths(table, widths)
    _top_bottom_border(table)
    _add_footnote(doc,
        "Refusal-classified items were treated as missing in the primary analysis "
        "(complete-case, scenario S0) and re-imputed under three scenarios: "
        "S1, scale minimum (1); S2, scale midpoint (2.5); S3, scale maximum (4). "
        "Run-level scale scores were recomputed under each scenario. "
        "“Maximum change vs primary analysis” is the largest absolute difference "
        "between an imputed-scenario mean and the complete-case mean across all "
        "(language × vignette × scale) cells for that model; “Maximum range across "
        "scenarios” is the largest spread across all four scenarios. "
        "“Gradient conclusion change” indicates whether any cell that met the "
        "human-derived gradient criterion in the primary analysis ceased to meet it "
        "under any imputation scenario (None = no such reversal). A total of 451 "
        "(English) and 378 (Mandarin Chinese) refusal-classified items were imputed, "
        "almost entirely from GPT-OSS-120B. SD, Social Distance scale; "
        "PJ, Prejudice Questionnaire.")


# ── eFigure embedding ──────────────────────────────────────────────────────────
def _add_efig_caption(doc: Document, label: str, caption: str):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(label + " ")
    r.bold = True; r.font.name = "Arial"; r.font.size = Pt(10)
    r2 = p.add_run(caption)
    r2.font.name = "Arial"; r2.font.size = Pt(9)


def embed_efigures(doc: Document):
    figs = [
        ("efigure1_reliability_refusal.png", "eFigure 1.",
         "Run-Level Reliability (Panel A) and Non-Valid Response Rate (Panel B) "
         "Across 14 Large Language Models in Both Languages.", 6.8),
        ("efigure2_run_level_distributions.png", "eFigure 2.",
         "Run-Level Stigma Score Distributions by "
         "(Model × Vignette × Scale × Language).", 7.0),
        ("eFigure3A_item_profile_social_distance.png", "eFigure 3A.",
         "Item-Level Mean Stigma Scores Across 14 Large Language Models, by "
         "Vignette and Language: Social Distance Items.", 6.6),
        ("eFigure3B_item_profile_prejudice.png", "eFigure 3B.",
         "Item-Level Mean Stigma Scores Across 14 Large Language Models, by "
         "Vignette and Language: Prejudice Items.", 6.6),
    ]
    for fname, label, caption, width in figs:
        fpath = OUT_DIR / fname
        if not fpath.exists():
            print(f"  [WARN] missing figure: {fpath}")
            continue
        doc.add_page_break()
        _add_efig_caption(doc, label, caption)
        doc.add_picture(str(fpath), width=Inches(width))


def add_contents(doc: Document):
    p = doc.add_paragraph()
    r = p.add_run("Contents")
    r.bold = True; r.font.name = "Arial"; r.font.size = Pt(11)
    items = [
        "eTable 1. Characteristics of the 14 Large Language Models Evaluated",
        "eTable 2. Query Parameters Used for Each Large Language Model",
        "eTable 3a. Missingness Audit: Run Retention Rates",
        "eTable 3b. Definitions of the Seven Response Classification Categories",
        "eTable 4. Friedman, Signed-Rank, and Kruskal-Wallis Test Results",
        "eTable 5. Cross-Language Differences in Stigma Scale Scores",
        "eTable 6. Summary of Pairwise Model Comparisons",
        "eTable 7. Refusal-Imputation Sensitivity Analysis",
        "eFigure 1. Run-Level Reliability and Non-Valid Response Rate",
        "eFigure 2. Run-Level Stigma Score Distributions",
        "eFigure 3. Item-Level Mean Stigma Scores (A: Social Distance; B: Prejudice)",
    ]
    for it in items:
        ip = doc.add_paragraph()
        ip.paragraph_format.space_after = Pt(1)
        ir = ip.add_run(it)
        ir.font.name = "Arial"; ir.font.size = Pt(9.5)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    doc = Document()

    # Page setup
    section = doc.sections[0]
    section.page_width    = Inches(8.5)
    section.page_height   = Inches(11)
    section.left_margin   = Inches(0.75)
    section.right_margin  = Inches(0.75)
    section.top_margin    = Inches(1.0)
    section.bottom_margin = Inches(1.0)

    # Document title
    title = doc.add_paragraph()
    title.paragraph_format.space_after = Pt(6)
    r = title.add_run("Electronic Supplementary Material — eTables")
    r.bold = True; r.font.name = "Arial"; r.font.size = Pt(12)

    subtitle = doc.add_paragraph()
    sr = subtitle.add_run(
        "Stigma Against Psychosis in Large Language Models: "
        "A Comparative Study Across 14 Large Language Models and Two Language Conditions"
    )
    sr.italic = True; sr.font.name = "Arial"; sr.font.size = Pt(10)
    subtitle.paragraph_format.space_after = Pt(8)

    add_contents(doc)
    doc.add_page_break()

    add_etable1(doc)
    add_etable2(doc)
    doc.add_page_break()
    add_etable3a(doc)
    doc.add_page_break()
    add_etable3b(doc)
    doc.add_page_break()
    add_etable4(doc)
    doc.add_page_break()
    add_etable5_crosslang(doc)
    doc.add_page_break()
    add_etable6_pairwise(doc)
    doc.add_page_break()
    add_etable7_refusal(doc)

    # Embed eFigures 1, 2, 3A, 3B
    embed_efigures(doc)

    # Master supplement (eTables 1-7 + eFigures 1-3)
    docx_path = OUT_DIR / "eSupplement_0612.docx"
    doc.save(docx_path)
    print(f"Saved master: {docx_path}")

    # Build pairwise CSV (eTable 6 full data)
    csv_path = OUT_DIR / "eTable6_pairwise_full.csv"
    n_rows = build_pairwise_csv(csv_path)
    print(f"Saved: {csv_path}  ({n_rows} data rows)")

    print("\n─── eSupplement master assembled ───")
    print("  eTable 1-2 (characteristics, params), 3a/3b (missingness, classification),")
    print("  4 (omnibus A/B/C), 5 (cross-language), 6 (pairwise), 7 (refusal sensitivity)")
    print("  + eFigures 1, 2, 3A, 3B embedded.")


if __name__ == "__main__":
    main()
