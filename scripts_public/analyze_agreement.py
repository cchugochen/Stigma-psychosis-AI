#!/usr/bin/env python3
"""
analyze_agreement.py — Phase C of the response-classifier human-validation study.

Run AFTER both researchers return their FILLED answer sheets. Computes the
inter-rater reliability and classifier-validity statistics, following the
Guidelines for Reporting Reliability and Agreement Studies (GRRAS; Kottner et al.,
J Clin Epidemiol 2011) and MI-CLAIM Parts 4-5.

Reported coefficients (each with bootstrap 95% CI), by language / tier:
  1. Human-human reliability  : raw agreement (Po), Cohen's kappa, Gwet's AC1,
                                PABAK, Krippendorff's alpha (nominal).
  2. Consensus gold standard  : agreed rows -> consensus; disagreements flagged
                                for adjudication AND bounded by a worst/best-case
                                sensitivity analysis (so the consensus-only figure
                                is not silently optimistic).
  3. Classifier validity      : classifier_3class vs consensus -> agreement
                                coefficients + per-class sensitivity / specificity
                                / PPV / NPV / F1 with Wilson score 95% CIs, plus
                                Byrt prevalence and bias indices.
  4. Error analysis           : confusion matrix + every misclassified/disagreed row.

WHY MORE THAN COHEN'S KAPPA? The corpus is ~99% `valid`. Under such extreme
marginal imbalance Cohen's kappa suffers the Feinstein-Cicchetti "kappa paradox"
(high agreement, paradoxically low/unstable kappa). We therefore co-report
prevalence-robust coefficients — Gwet's AC1 (Gwet 2008; Wongpakaran et al. 2013,
BMC Med Res Methodol) and PABAK (Byrt, Bishop & Carlin, J Clin Epidemiol 1993) —
and read all of them together rather than a single number.

Pure stdlib (no sklearn / irr). Outputs CSVs + validation_report_0622.md here.

Usage:
  python3 resp_valid_14model_0622/analyze_agreement.py \
      [reviewer1_filled.csv] [reviewer2_filled.csv] [_KEY_do_not_share_0622.csv]

Defaults to reviewer{1,2}_classification_filled_0622.csv + _KEY_do_not_share_0622.csv here.
"""
import csv
import math
import random
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent / "resp_valid_14model_0622"  # private validation data
DATESTAMP = "0622"
LABELS = ["valid", "refusal", "unparseable_or_error"]
N_BOOT = 2000
BOOT_SEED = 20260622
Z = 1.959963984540054  # 97.5th normal quantile
NAN = float("nan")

# tolerant normalization of free-typed reviewer labels
NORMALIZE = {
    "valid": "valid", "v": "valid",
    "refusal": "refusal", "refuse": "refusal", "r": "refusal",
    "unparseable_or_error": "unparseable_or_error", "unparseable": "unparseable_or_error",
    "error": "unparseable_or_error", "unparseable/error": "unparseable_or_error",
    "unparsable_or_error": "unparseable_or_error", "u": "unparseable_or_error",
}


# ============================================================ agreement coefficients
def accuracy(a, b):
    return sum(1 for x, y in zip(a, b) if x == y) / len(a) if a else NAN


def cohen_kappa(a, b):
    """Unweighted Cohen's kappa. Undefined (NaN) when no between-category variance."""
    n = len(a)
    if n == 0:
        return NAN
    po = accuracy(a, b)
    ca, cb = Counter(a), Counter(b)
    cats = set(ca) | set(cb)
    if len(cats) < 2:                 # both raters used a single category -> kappa undefined
        return NAN
    pe = sum((ca[c] / n) * (cb[c] / n) for c in cats)
    if pe >= 1.0:
        return NAN                    # degenerate; avoid a misleading kappa = 1.0
    return (po - pe) / (1 - pe)


def gwet_ac1(a, b):
    """Gwet's AC1 — chance-corrected agreement robust to high prevalence / marginal
    imbalance (Gwet 2008). Pe = (1/(q-1)) * sum_k pi_k (1 - pi_k)."""
    n = len(a)
    if n == 0:
        return NAN
    po = accuracy(a, b)
    ca, cb = Counter(a), Counter(b)
    cats = set(ca) | set(cb)
    q = len(cats)
    if q < 2:
        return NAN
    pi = {c: (ca[c] + cb[c]) / (2 * n) for c in cats}
    pe = sum(pi[c] * (1 - pi[c]) for c in cats) / (q - 1)
    if pe >= 1.0:
        return NAN
    return (po - pe) / (1 - pe)


def pabak(a, b):
    """Prevalence-Adjusted Bias-Adjusted Kappa, q-category form: (q*Po - 1)/(q - 1)
    (Byrt, Bishop & Carlin 1993, generalized)."""
    n = len(a)
    if n == 0:
        return NAN
    q = len(set(a) | set(b))
    if q < 2:
        return NAN
    return (q * accuracy(a, b) - 1) / (q - 1)


def krippendorff_alpha(a, b):
    """Krippendorff's alpha, nominal metric, two raters, complete data."""
    n = len(a)
    if n == 0:
        return NAN
    cats = set(a) | set(b)
    if len(cats) < 2:
        return NAN
    o = Counter()
    for x, y in zip(a, b):
        o[(x, y)] += 1
        o[(y, x)] += 1
    ntot = 2 * n
    nc = {c: sum(o[(c, k)] for k in cats) for c in cats}
    num = sum(o[(c, k)] for c in cats for k in cats if c != k)            # observed disagreements
    den = sum(nc[c] * nc[k] for c in cats for k in cats if c != k)        # expected disagreements
    if den == 0:
        return NAN
    return 1 - (ntot - 1) * num / den


# ============================================================ per-class diagnostic metrics
def per_class(gold, pred, label):
    tp = sum(1 for g, p in zip(gold, pred) if g == label and p == label)
    fp = sum(1 for g, p in zip(gold, pred) if g != label and p == label)
    fn = sum(1 for g, p in zip(gold, pred) if g == label and p != label)
    tn = sum(1 for g, p in zip(gold, pred) if g != label and p != label)
    n = tp + fp + fn + tn
    div = lambda x, y: x / y if y else NAN
    sens, ppv = div(tp, tp + fn), div(tp, tp + fp)
    return {"n_gold": tp + fn, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "sensitivity": sens, "specificity": div(tn, tn + fp),
            "ppv": ppv, "npv": div(tn, tn + fn), "f1": div(2 * tp, 2 * tp + fp + fn),
            # Byrt one-vs-rest 2x2 indices (gold present/absent x classifier present/absent)
            "prevalence_index": div(abs(tp - tn), n),
            "bias_index": div(abs(fp - fn), n)}


def wilson_ci(x, m, z=Z):
    """Wilson score interval for a binomial proportion x/m (Newcombe 1998)."""
    if m == 0:
        return (NAN, NAN)
    p = x / m
    d = 1 + z * z / m
    centre = (p + z * z / (2 * m)) / d
    half = z * math.sqrt(p * (1 - p) / m + z * z / (4 * m * m)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


# ============================================================ bootstrap CI (for coefficients)
def bootstrap_ci(gold, pred, metric_fn, n_boot=N_BOOT, seed=BOOT_SEED):
    """Non-parametric percentile bootstrap over rated items (resampled with
    replacement). Suitable for coefficients with no simple closed-form SE
    (kappa, AC1, PABAK, alpha). Per-class proportions use Wilson intervals instead."""
    rng = random.Random(seed)
    n = len(gold)
    if n == 0:
        return (NAN, NAN)
    vals = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        v = metric_fn([gold[i] for i in idx], [pred[i] for i in idx])
        if v == v:  # drop NaN resamples (degenerate draws)
            vals.append(v)
    if not vals:
        return (NAN, NAN)
    vals.sort()
    lo = vals[max(0, int(math.floor(0.025 * (len(vals) - 1))))]
    hi = vals[min(len(vals) - 1, int(math.ceil(0.975 * (len(vals) - 1))))]
    return (lo, hi)


def f3(x):
    return "NA" if x != x else f"{x:.3f}"


def ci3(lohi):
    lo, hi = lohi
    return "NA" if lo != lo else f"[{lo:.3f}, {hi:.3f}]"


# ============================================================ io
def read_csv(p):
    # utf-8-sig: the HTML reviewer form writes a UTF-8 BOM; without -sig the first
    # header becomes "﻿response_id" and every lookup fails.
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def norm_label(raw, response_id, who, problems):
    s = (raw or "").strip().lower()
    if s == "":
        problems.append(f"{who} {response_id}: BLANK label")
        return None
    if s in NORMALIZE:
        return NORMALIZE[s]
    problems.append(f"{who} {response_id}: unrecognized label '{raw}'")
    return None


def load_reviewer(path, who, problems):
    out = {}
    for r in read_csv(path):
        out[r["response_id"]] = norm_label(r.get("reviewer_label"), r["response_id"], who, problems)
    return out


# ============================================================ coefficient blocks
COEF_FUNS = [("cohen_kappa", cohen_kappa), ("gwet_ac1", gwet_ac1),
             ("pabak", pabak), ("krippendorff_alpha", krippendorff_alpha)]
COEF_COLS = []
for _name, _f in COEF_FUNS:
    COEF_COLS += [_name, _name + "_95ci"]


def coef_block(x, y):
    """Raw agreement + all four chance-corrected coefficients, each with bootstrap CI."""
    out = {"n": len(x), "pct_agreement": f3(accuracy(x, y))}
    for name, fn in COEF_FUNS:
        out[name] = f3(fn(x, y))
        out[name + "_95ci"] = ci3(bootstrap_ci(x, y, fn))
    return out


# ============================================================ main
def main():
    args = sys.argv[1:]
    r1_path = Path(args[0]) if len(args) > 0 else HERE / f"reviewer1_classification_filled_{DATESTAMP}.csv"
    r2_path = Path(args[1]) if len(args) > 1 else HERE / f"reviewer2_classification_filled_{DATESTAMP}.csv"
    key_path = Path(args[2]) if len(args) > 2 else HERE / f"_KEY_do_not_share_{DATESTAMP}.csv"

    for p in (r1_path, r2_path, key_path):
        if not p.exists():
            sys.exit(f"ERROR: missing input {p}\n"
                     f"Provide the two FILLED reviewer CSVs (and the key) as arguments, e.g.\n"
                     f"  python3 {Path(__file__).name} reviewer1_filled.csv reviewer2_filled.csv")

    key = {r["response_id"]: r for r in read_csv(key_path)}
    problems = []
    r1 = load_reviewer(r1_path, "R1", problems)
    r2 = load_reviewer(r2_path, "R2", problems)

    ids = [rid for rid in key if rid in r1 and rid in r2]
    if problems:
        print("WARNING: label issues (excluded from analysis):")
        for m in problems[:40]:
            print("  -", m)
    ids = [i for i in ids if r1[i] in LABELS and r2[i] in LABELS]
    if not ids:
        sys.exit("ERROR: no usable rows (reviewer sheets appear unfilled / unreadable).")

    lang = {i: key[i]["language"] for i in ids}
    tier = {i: key[i]["tier"] for i in ids}
    clf = {i: key[i]["classifier_label_3class"] for i in ids}

    # ---- 1. human-human reliability ----
    def hh_block(sub):
        x = [r1[i] for i in sub]
        y = [r2[i] for i in sub]
        return {**coef_block(x, y), "n_disagree": sum(1 for i in sub if r1[i] != r2[i])}

    hh_rows = [{"stratum": "overall", **hh_block(ids)}]
    for lg in ("en", "zh"):
        sub = [i for i in ids if lang[i] == lg]
        if sub:
            hh_rows.append({"stratum": f"language={lg}", **hh_block(sub)})
    write_rows(HERE / f"human_human_agreement_{DATESTAMP}.csv",
               ["stratum", "n", "pct_agreement", *COEF_COLS, "n_disagree"], hh_rows)

    # ---- 2. consensus + adjudicated gold standard ----
    # Raw human consensus: a label only where the two reviewers independently agree.
    consensus = {i: (r1[i] if r1[i] == r2[i] else None) for i in ids}
    consensus_ids = [i for i in ids if consensus[i] is not None]
    raw_disagreed = [i for i in ids if consensus[i] is None]

    # Optional adjudication of the human disagreements -> final gold standard.
    # Absent file => behaviour is identical to the pre-adjudication run (bounds only).
    # §1 human-human reliability is left untouched (always on the raw independent labels).
    adj_path = HERE / f"adjudication_{DATESTAMP}.csv"
    adjudication = {}
    if adj_path.exists():
        for r in read_csv(adj_path):
            lab = norm_label(r.get("adjudicated_label"), r["response_id"], "ADJ", problems)
            if lab in LABELS:
                adjudication[r["response_id"]] = lab

    gold = dict(consensus)
    for i in raw_disagreed:
        if i in adjudication:
            gold[i] = adjudication[i]
    agreed = [i for i in ids if gold[i] is not None]
    disagreed = [i for i in ids if gold[i] is None]
    fully_adjudicated = bool(adjudication) and not disagreed

    # ---- 3a. classifier vs consensus (agreed subset), coefficients by stratum ----
    def clf_block(sub):
        g = [gold[i] for i in sub]
        p = [clf[i] for i in sub]
        out = {"n": len(sub), "accuracy": f3(accuracy(g, p)),
               "accuracy_95ci": ci3(bootstrap_ci(g, p, accuracy))}
        for name, fn in COEF_FUNS:
            out[name] = f3(fn(g, p))
            out[name + "_95ci"] = ci3(bootstrap_ci(g, p, fn))
        return out

    strata = [("overall", agreed)]
    for tname in ("prevalence", "enriched"):
        strata.append((f"tier={tname}", [i for i in agreed if tier[i] == tname]))
    for lg in ("en", "zh"):
        strata.append((f"language={lg}", [i for i in agreed if lang[i] == lg]))
    clf_rows = [{"stratum": s, **clf_block(sub)} for s, sub in strata if sub]
    write_rows(HERE / f"classifier_vs_consensus_{DATESTAMP}.csv",
               ["stratum", "n", "accuracy", "accuracy_95ci", *COEF_COLS], clf_rows)

    # ---- 3b. adjudicated point estimate + full-sample sensitivity bounds ----
    # Sensitivity bounds are always computed on the RAW human disagreements (treating
    # each as classifier-wrong = worst, or classifier-correct-if-it-matched-either-
    # reviewer = best). When an adjudication resolves every disagreement, the single
    # adjudicated point estimate over all rated items is reported as primary.
    n_all = len(ids)
    correct_consensus = sum(1 for i in consensus_ids if consensus[i] == clf[i])
    best_extra = sum(1 for i in raw_disagreed if clf[i] in (r1[i], r2[i]))
    adj_rows = []
    if fully_adjudicated:
        correct_adj = sum(1 for i in agreed if gold[i] == clf[i])
        adj_rows.append(
            {"scenario": "adjudicated (final, primary)", "n": n_all,
             "accuracy": f3(correct_adj / n_all if n_all else NAN),
             "note": "human disagreements resolved by R1/R2 consensus; single adjudicated point estimate"})
    adj_rows += [
        {"scenario": "consensus_only", "n": len(consensus_ids),
         "accuracy": f3(correct_consensus / len(consensus_ids) if consensus_ids else NAN),
         "note": "reviewer-agreed subset only (excludes the human disagreements)"},
        {"scenario": "full_sample_worst_case", "n": n_all,
         "accuracy": f3(correct_consensus / n_all if n_all else NAN),
         "note": "every human disagreement counted as classifier-WRONG (lower bound)"},
        {"scenario": "full_sample_best_case", "n": n_all,
         "accuracy": f3((correct_consensus + best_extra) / n_all if n_all else NAN),
         "note": "disagreement counts CORRECT if classifier matched either reviewer (upper bound)"},
    ]
    write_rows(HERE / f"classifier_adjudication_bounds_{DATESTAMP}.csv",
               ["scenario", "n", "accuracy", "note"], adj_rows)

    # ---- 3c. per-class diagnostic metrics (Wilson CIs) on the gold subset ----
    g = [gold[i] for i in agreed]
    p = [clf[i] for i in agreed]
    pc_rows = []
    for lab in LABELS:
        m = per_class(g, p, lab)
        sens_ci = wilson_ci(m["tp"], m["tp"] + m["fn"])
        spec_ci = wilson_ci(m["tn"], m["tn"] + m["fp"])
        ppv_ci = wilson_ci(m["tp"], m["tp"] + m["fp"])
        npv_ci = wilson_ci(m["tn"], m["tn"] + m["fn"])
        pc_rows.append({"label": lab, "n_gold": m["n_gold"], "tp": m["tp"], "fp": m["fp"],
                        "fn": m["fn"], "tn": m["tn"],
                        "sensitivity": f3(m["sensitivity"]), "sensitivity_95ci": ci3(sens_ci),
                        "specificity": f3(m["specificity"]), "specificity_95ci": ci3(spec_ci),
                        "ppv": f3(m["ppv"]), "ppv_95ci": ci3(ppv_ci),
                        "npv": f3(m["npv"]), "npv_95ci": ci3(npv_ci),
                        "f1": f3(m["f1"]),
                        "prevalence_index": f3(m["prevalence_index"]),
                        "bias_index": f3(m["bias_index"])})
    write_rows(HERE / f"classifier_perclass_{DATESTAMP}.csv",
               ["label", "n_gold", "tp", "fp", "fn", "tn",
                "sensitivity", "sensitivity_95ci", "specificity", "specificity_95ci",
                "ppv", "ppv_95ci", "npv", "npv_95ci", "f1",
                "prevalence_index", "bias_index"], pc_rows)

    # ---- 4. confusion matrix (rows=gold standard, cols=classifier) ----
    cm = Counter((gold[i], clf[i]) for i in agreed)
    cm_rows = []
    for g_lab in LABELS:
        row = {"gold\\classifier": g_lab}
        for pred in LABELS:
            row[pred] = cm.get((g_lab, pred), 0)
        row["row_total"] = sum(cm.get((g_lab, pred), 0) for pred in LABELS)
        cm_rows.append(row)
    write_rows(HERE / f"confusion_matrix_{DATESTAMP}.csv",
               ["gold\\classifier", *LABELS, "row_total"], cm_rows)

    # ---- disagreements (for adjudication + error analysis) ----
    dis_rows = []
    for i in ids:
        hh_dis = r1[i] != r2[i]
        clf_dis = consensus[i] is not None and consensus[i] != clf[i]
        if hh_dis or clf_dis:
            k = key[i]
            dis_rows.append({
                "response_id": i, "language": lang[i], "tier": tier[i],
                "reviewer1": r1[i], "reviewer2": r2[i],
                "consensus": consensus[i] or "DISAGREE",
                "adjudicated_label": adjudication.get(i, ""),
                "final_gold": gold[i] or "UNADJUDICATED",
                "classifier_3class": clf[i],
                "classifier_7class": k["classifier_label_7class"],
                "kind": ("human_human" if hh_dis else "") + ("|clf_vs_consensus" if clf_dis else ""),
                "real_model": k["real_model"], "model_anon": k["model_anon"],
                "raw_response": " ".join(k["raw_response"].split())[:300],
            })
    write_rows(HERE / f"disagreements_{DATESTAMP}.csv",
               ["response_id", "language", "tier", "reviewer1", "reviewer2", "consensus",
                "adjudicated_label", "final_gold",
                "classifier_3class", "classifier_7class", "kind", "real_model", "model_anon",
                "raw_response"], dis_rows)

    write_report(ids, agreed, disagreed, hh_rows, clf_rows, adj_rows, pc_rows, cm_rows, dis_rows, key,
                 r1_path, r2_path, consensus_ids, raw_disagreed, fully_adjudicated)
    print(f"Analyzed {len(ids)} rows ({len(agreed)} gold, {len(disagreed)} unadjudicated).")
    print(f"Wrote 7 CSVs + validation_report_{DATESTAMP}.md to {HERE.name}/")


# ============================================================ writers
def write_rows(path, fieldnames, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def interpret(kappa_str):
    try:
        k = float(kappa_str)
    except ValueError:
        return ""
    for thr, lab in [(0.81, "almost perfect"), (0.61, "substantial"), (0.41, "moderate"),
                     (0.21, "fair"), (0.0, "slight")]:
        if k >= thr:
            return f" ({lab}, Landis & Koch)"
    return " (poor)"


def write_report(ids, agreed, disagreed, hh_rows, clf_rows, adj_rows, pc_rows, cm_rows, dis_rows, key,
                 r1_path, r2_path, consensus_ids, raw_disagreed, fully_adjudicated):
    hh = hh_rows[0]
    clf = clf_rows[0]
    prevalence_clf = next((r for r in clf_rows if r["stratum"] == "tier=prevalence"), None)
    enriched_clf = next((r for r in clf_rows if r["stratum"] == "tier=enriched"), None)

    L = []
    L.append(f"# Response-Classifier Validation — Results ({DATESTAMP})\n")
    L.append("3-class scheme: `valid` / `refusal` / `unparseable_or_error`. Two independent "
             "researchers; classifier compared to their consensus. Reliability reported per GRRAS "
             "(Kottner et al., J Clin Epidemiol 2011). Because the corpus is ~99% `valid`, we "
             "co-report prevalence-robust coefficients (Gwet's AC1, PABAK) alongside Cohen's "
             f"kappa to guard against the kappa paradox. Bootstrap 95% CIs ({N_BOOT} resamples) "
             "for coefficients; Wilson score 95% CIs for per-class proportions.\n")
    L.append(f"- Items rated by both reviewers: **{len(ids)}**")
    if fully_adjudicated:
        L.append(f"- Independent reviewer consensus (R1==R2): **{len(consensus_ids)}**; human "
                 f"disagreements: **{len(raw_disagreed)}**, resolved by R1/R2 consensus and folded "
                 f"into the final gold standard → gold N=**{len(agreed)}**")
    else:
        L.append(f"- Reviewer consensus (agreed): **{len(agreed)}**;  disagreements needing "
                 f"adjudication: **{len(disagreed)}**")
    L.append(f"- Reviewer files: `{r1_path.name}`, `{r2_path.name}`\n")

    def coef_line(row):
        return (f"Cohen's κ = **{row['cohen_kappa']}** {row['cohen_kappa_95ci']}"
                f"{interpret(row['cohen_kappa'])}; Gwet's AC1 = **{row['gwet_ac1']}** "
                f"{row['gwet_ac1_95ci']}; PABAK = {row['pabak']} {row['pabak_95ci']}; "
                f"Krippendorff's α = {row['krippendorff_alpha']} {row['krippendorff_alpha_95ci']}; "
                f"raw agreement = {row.get('pct_agreement', row.get('accuracy', 'NA'))}")

    L.append("## 1. Human–human reliability (R1 vs R2)\n")
    L.append(f"- {coef_line(hh)} (n={hh['n']}, {hh['n_disagree']} disagreements).")
    L.append("- Read AC1/PABAK as the prevalence-robust ceiling; a low Cohen's κ next to a high "
             "AC1 is the signature of the kappa paradox under imbalanced marginals, not poor "
             "reliability.\n")

    L.append("## 2. Classifier vs human consensus\n")
    gold_desc = ("the adjudicated gold standard: reviewer-agreed items + human disagreements "
                 "resolved by R1/R2 consensus" if fully_adjudicated
                 else "human consensus, reviewer-agreed items only")
    L.append(f"- **Overall** (n={clf['n']}, {gold_desc}): accuracy = **{clf['accuracy']}** "
             f"{clf['accuracy_95ci']}; {coef_line(clf)}.")
    if prevalence_clf:
        L.append(f"- Prevalence tier (real-world mix): accuracy = {prevalence_clf['accuracy']} "
                 f"{prevalence_clf['accuracy_95ci']}, AC1 = {prevalence_clf['gwet_ac1']} "
                 f"{prevalence_clf['gwet_ac1_95ci']} (n={prevalence_clf['n']}).")
    if enriched_clf:
        L.append(f"- Enriched tier (boundary cases): κ = {enriched_clf['cohen_kappa']} "
                 f"{enriched_clf['cohen_kappa_95ci']}, AC1 = {enriched_clf['gwet_ac1']} "
                 f"{enriched_clf['gwet_ac1_95ci']} (n={enriched_clf['n']}).")
    L.append("")

    if fully_adjudicated:
        L.append("### 2b. Adjudicated point estimate & full-sample sensitivity bounds\n")
        L.append("The human disagreements were resolved by consensus discussion between the two "
                 "original reviewers (blind to the classifier's own label) and folded into the final "
                 "gold standard. Primary adjudicated estimate, with the pre-adjudication sensitivity "
                 "bounds retained for transparency:")
    else:
        L.append("### 2b. Adjudication sensitivity (full-sample bounds)\n")
        L.append("Consensus-only analysis excludes the hardest items (human disagreements) and can be "
                 "optimistic. Bounding the true accuracy over all rated items:")
    for r in adj_rows:
        L.append(f"- {r['scenario']}: accuracy = **{r['accuracy']}** (n={r['n']}) — {r['note']}.")
    if not fully_adjudicated:
        L.append("Adjudicate `disagreements_*.csv` and re-run for a single point estimate.")
    L.append("")

    L.append("## 3. Per-class performance (classifier vs consensus, Wilson 95% CIs)\n")
    L.append("| label | n | sensitivity [95% CI] | specificity [95% CI] | PPV [95% CI] | "
             "NPV [95% CI] | F1 |")
    L.append("|---|---|---|---|---|---|---|")
    for r in pc_rows:
        L.append(f"| {r['label']} | {r['n_gold']} | {r['sensitivity']} {r['sensitivity_95ci']} | "
                 f"{r['specificity']} {r['specificity_95ci']} | {r['ppv']} {r['ppv_95ci']} | "
                 f"{r['npv']} {r['npv_95ci']} | {r['f1']} |")
    L.append("")

    L.append("## 4. Confusion matrix (rows = consensus, cols = classifier)\n")
    L.append("| gold \\ clf | " + " | ".join(LABELS) + " | total |")
    L.append("|---|" + "---|" * (len(LABELS) + 1))
    for r in cm_rows:
        L.append("| " + r["gold\\classifier"] + " | "
                 + " | ".join(str(r[c]) for c in LABELS) + f" | {r['row_total']} |")
    L.append("")

    L.append("## 5. Error analysis (misclassified / disagreed rows)\n")
    if dis_rows:
        by_model = Counter(r["real_model"] for r in dis_rows if "clf_vs_consensus" in r["kind"])
        by_7 = Counter(r["classifier_7class"] for r in dis_rows if "clf_vs_consensus" in r["kind"])
        L.append(f"- {len(dis_rows)} rows flagged (see `disagreements_{DATESTAMP}.csv`).")
        if by_model:
            L.append("- Classifier↔consensus disagreements by model: "
                     + ", ".join(f"{m} ({n})" for m, n in by_model.most_common()))
        if by_7:
            L.append("- …by classifier 7-class label: "
                     + ", ".join(f"{m} ({n})" for m, n in by_7.most_common()))
    else:
        L.append("- No disagreements: classifier matched human consensus on every rated item.")
    L.append("")

    L.append("## Methods notes & caveats (state in the manuscript)\n")
    L.append("1. **Coefficient choice.** With ~99% `valid`, Cohen's κ is paradox-prone "
             "(Feinstein & Cicchetti 1990); Gwet's AC1 (Gwet 2008) and PABAK (Byrt et al. 1993) "
             "are prevalence-robust and are the recommended primary statistics here "
             "(Wongpakaran et al. 2013). κ undefined (NaN) means a stratum had no "
             "between-category variance.")
    L.append("2. **Internal, not external, validity.** Classifier regex rules were iteratively "
             "tuned on this corpus (Bug 5–8 fixes), so these are apparent/internal-validity "
             "estimates and may be optimistic; rules are frozen and the human gold standard is "
             "independent. A fully external test needs a fresh response collection.")
    if fully_adjudicated:
        L.append("3. **Adjudication (done).** The human disagreements were resolved to a final gold "
                 "standard by consensus between the two original reviewers, blind to the classifier "
                 "label; the headline is the single adjudicated estimate over all rated items. §2b "
                 "retains the pre-adjudication worst/best bounds for transparency. Human–human "
                 "reliability (§1) is reported on the original independent labels, pre-adjudication.")
    else:
        L.append("3. **Adjudication.** The headline uses the consensus (agreed) subset; §2b bounds the "
                 "effect of excluded disagreements. For the manuscript, adjudicate disagreements to a "
                 "final gold standard and report the single adjudicated estimate.")
    L.append("4. **Clustering.** Responses are nested within model/item; the item-level bootstrap "
             "treats them as exchangeable, which may modestly understate CI width. Given the "
             "validation sample is a per-response audit this is acceptable; a model-cluster "
             "bootstrap is a possible robustness check.")
    L.append("5. **Realized-category coverage.** Of the 7 a-priori classifier categories, only "
             "`valid` / `refusal` / `unparseable` (+2 `refusal_identity`) occur; "
             "`hedged` / `refusal_ethical` / `safety` are empty (n=0). The 3-class scheme validates "
             "100% of realized categories and the score-critical valid-vs-non-valid boundary.")
    L.append("6. This validates **only** the classifier (reviewer Point 7); construct validity "
             "(Point 1) and cross-language confounds (Point 4) are separate work items.\n")

    (HERE / f"validation_report_{DATESTAMP}.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
