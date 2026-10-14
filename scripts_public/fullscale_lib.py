"""Full-scale administration helpers for the 4-model elicitation sensitivity study.

One API call presents one vignette plus all 40 items (19 Social Distance, then
21 Prejudice, same order as the main study). The reply is split back into one
answer fragment per item; each fragment is then judged by the SAME locked
`classify_response()` / `parse_response()` used for item-by-item administration.

Shared by the collector and the merge step so the split logic exists once.
"""
import re

# Last line of the original system prompt is the only change: answering 40 items
# in one reply is incompatible with "Respond with ONLY the number".
ORIGINAL_LAST_LINE = {
    "en": "Respond with ONLY the number, nothing else.",
    "zh": "請只回答數字，不要回答其他內容。",
}
FULLSCALE_LAST_LINE = {
    "en": "Respond with ONLY one line per item in the form ITEM_ID: number, nothing else.",
    "zh": "每題請只回答一行，格式為「題號: 數字」，不要回答其他內容。",
}
FINAL_INSTRUCTION = "Your answers (1-4), one line per item (e.g. SD01: 2):"

# Markers contain no digits and no refusal words, so the locked classifier
# always labels them unparseable.
MISSING = "[FULLSCALE_MISSING]"
AFTER_TRUNCATION = "[FULLSCALE_TRUNCATED_BEFORE_ITEM]"
CONFLICT = "[FULLSCALE_CONFLICT]"

LINE_RE = re.compile(r"(SD|PJ)\s*0?(\d{1,2})\s*[:：.\-]\s*(.*)", re.IGNORECASE)
TRUNC_RE = re.compile(r"\s*\[TRUNCATED:[^\]]*\]\s*$")


def fullscale_system_prompt(original_builder, lang):
    base = original_builder(lang)
    old, new = ORIGINAL_LAST_LINE[lang], FULLSCALE_LAST_LINE[lang]
    if base.count(old) != 1:
        raise RuntimeError(f"original last line not found exactly once ({lang})")
    return base.replace(old, new)


def stems_from_question_builder(build_question_prompt, vignettes, sd_items, pj_items, lang):
    """Recover the two scale stems from the original item-level prompt builder,
    so full-scale prompts cannot drift from the item-level wording."""
    vig_key = next(iter(vignettes))
    stems = {}
    for scale, item in (("social_distance", sd_items[0]), ("prejudice", pj_items[0])):
        p = build_question_prompt(vig_key, item, scale, lang)
        body = p.split("\n\n")
        # "Case description:\n{vt}" | "{stem}\n{it}" | "Your answer (1-4):"
        stems[scale] = body[-2].split("\n")[0]
    return stems


def fullscale_user_prompt(vignette_text, stems, sd_items, pj_items, lang):
    key = "zh" if lang == "zh" else "en"
    lines = ["Case description:", vignette_text, "", stems["social_distance"]]
    lines += [f"{it['id']}. {it[key]}" for it in sd_items]
    lines += ["", stems["prejudice"]]
    lines += [f"{it['id']}. {it[key]}" for it in pj_items]
    lines += ["", FINAL_INSTRUCTION]
    return "\n".join(lines)


def split_fullscale_reply(raw, item_ids):
    """Return ({item_id: fragment}, info). Fragments go to the locked classifier."""
    info = {"truncated": False, "n_found": 0, "conflicts": [], "unknown_ids": []}
    if raw.startswith("[API_ERROR]") or raw.startswith("[SAFETY_BLOCK") or raw.startswith("[EMPTY_RESPONSE"):
        return {i: raw for i in item_ids}, info
    text = raw
    if TRUNC_RE.search(text):
        info["truncated"] = True
        text = TRUNC_RE.sub("", text)
    found = {}
    for line in text.splitlines():
        m = LINE_RE.search(line.strip())
        if not m:
            continue
        iid = f"{m.group(1).upper()}{int(m.group(2)):02d}"
        frag = m.group(3).strip()
        if iid not in item_ids:
            info["unknown_ids"].append(iid)
            continue
        found.setdefault(iid, []).append(frag)
    out = {}
    for iid in item_ids:
        frags = found.get(iid)
        if not frags:
            out[iid] = None
        elif len(set(frags)) > 1:
            out[iid] = CONFLICT
            info["conflicts"].append(iid)
        else:
            out[iid] = frags[0] if frags[0] else None
    info["n_found"] = sum(1 for v in out.values() if v is not None)
    if info["n_found"] == 0:
        # No item lines at all (e.g. a whole-call refusal): every item gets the
        # whole reply, so the locked classifier decides refusal vs unparseable.
        return {i: raw for i in item_ids}, info
    filler = AFTER_TRUNCATION if info["truncated"] else MISSING
    return {i: (v if v is not None else filler) for i, v in out.items()}, info
