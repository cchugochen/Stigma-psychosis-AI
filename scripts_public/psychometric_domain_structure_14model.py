#!/usr/bin/env python3
"""Prejudice Questionnaire domain structure across the 14-model panel (Reviewer 2, Comment 2; Reviewer 1, Comment 5).

Implements analysis_psychometric_20261003/ANALYSIS_PLAN.md, written before any correlation was computed.
Question: across cells (model x vignette, per language), do items in the same a-priori domain correlate more
strongly than items in different domains?

Primary: Spearman rho between item means (56 x 21 matrix per language); delta = mean within-domain rho - mean
between-domain rho; item-label permutation test (domain sizes kept, 10,000 permutations, one-sided).
Pre-specified sensitivity: S1 same-keying pairs only; S2 row-centred item means; S3 Pearson; S4 leave-one-model-out.
Descriptive: keying diagnostic, first-eigenvalue share. Pooled (112 rows) as secondary.

Usage: python scripts_public/psychometric_domain_structure_14model.py
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
AN = REPO / "analysis_14models_20260614"
OUT = REPO / "analysis_psychometric_20261003"
N_PERM = 10_000
SEED = "20261003"
ALPHA = 0.05
DOMAINS = ["disclosure", "treatment_carryover", "traditional_prejudice", "exclusionary",
           "negative_affect", "dangerousness"]
VIGNETTES = ["PLE", "DEP", "APS", "SCZ"]
LANG_LABEL = {"en": "English", "zh": "Mandarin Chinese", "pooled": "Pooled (EN + ZH)"}


def rng_for(label: str) -> np.random.Generator:
    return np.random.default_rng(int(hashlib.sha256(f"{SEED}|{label}".encode()).hexdigest()[:16], 16))


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ── data ─────────────────────────────────────────────────────────────────────
def load():
    frames = []
    for lang in ("en", "zh"):
        d = pd.read_csv(AN / lang / f"results_14models_{lang}.csv", dtype=str,
                        usecols=["model", "vignette", "scale_type", "item_id", "item_domain", "is_reverse",
                                 "response_type", "scored_value"])
        d = d[(d.scale_type == "prejudice") & (d.response_type == "valid")].copy()
        d["score"] = pd.to_numeric(d.scored_value, errors="coerce")
        d = d.dropna(subset=["score"])
        d["language"] = lang
        frames.append(d)
    d = pd.concat(frames, ignore_index=True)
    assert d.score.between(1, 4).all()
    meta = (d.groupby("item_id")
              .agg(domain=("item_domain", "first"), n_dom=("item_domain", "nunique"),
                   reverse=("is_reverse", "first"))
              .reset_index())
    assert (meta.n_dom == 1).all() and set(meta.domain) == set(DOMAINS) and len(meta) == 21
    meta["reverse"] = meta.reverse.str.lower().isin(["true", "1"])
    meta["dom_rank"] = meta.domain.map({k: i for i, k in enumerate(DOMAINS)})
    meta = meta.sort_values(["dom_rank", "item_id"]).reset_index(drop=True)
    items = list(meta.item_id)
    means = (d.groupby(["language", "model", "vignette", "item_id"]).score.mean()
               .unstack("item_id")[items])
    counts = d.groupby(["language", "model", "vignette", "item_id"]).score.size().unstack("item_id")[items]
    return means, counts, meta


def check_against_table5(means: pd.DataFrame) -> float:
    t5 = pd.read_csv(AN / "Table5_item_stigma_profile.csv")
    t5 = t5[t5.Scale == "prejudice"]
    diffs = []
    for _, r in t5.iterrows():
        for lang, L in (("en", "EN"), ("zh", "ZH")):
            for v in VIGNETTES:
                val = r.get(f"Mean_{L}_{v}")
                if pd.isna(val):
                    continue
                diffs.append(abs(means.loc[(lang, r.Model, v), r.Item_ID] - val))
    return float(np.nanmax(diffs)), len(diffs)


# ── statistics ───────────────────────────────────────────────────────────────
def corr(M: pd.DataFrame, method: str) -> np.ndarray:
    return M.corr(method=method, min_periods=10).to_numpy()


def contrast(R: np.ndarray, labels: np.ndarray, keep: np.ndarray | None):
    iu0, iu1 = np.triu_indices(len(labels), 1)
    r = R[iu0, iu1]
    sel = np.ones_like(r, bool) if keep is None else keep[iu0, iu1]
    same = (labels[iu0] == labels[iu1])[sel]
    rr = r[sel]
    w, b = rr[same].mean(), rr[~same].mean()
    return w, b, w - b, int(same.sum()), int((~same).sum())


def perm_test(R: np.ndarray, labels: np.ndarray, keep: np.ndarray | None, rng: np.random.Generator):
    iu0, iu1 = np.triu_indices(len(labels), 1)
    r = R[iu0, iu1]
    sel = np.ones_like(r, bool) if keep is None else keep[iu0, iu1]
    rr = r[sel]
    w, b, obs, nw, nb = contrast(R, labels, keep)
    P = np.stack([rng.permutation(labels) for _ in range(N_PERM)])
    same = (P[:, iu0] == P[:, iu1])[:, sel]
    n_same = same.sum(1)
    ok = (n_same > 0) & (n_same < sel.sum())
    w_p = (same * rr).sum(1) / np.where(n_same > 0, n_same, 1)
    b_p = ((~same) * rr).sum(1) / np.where(sel.sum() - n_same > 0, sel.sum() - n_same, 1)
    null = (w_p - b_p)[ok]
    p = (1 + int((null >= obs - 1e-12).sum())) / (1 + len(null))
    return dict(mean_within=w, mean_between=b, delta=obs, n_within_pairs=nw, n_between_pairs=nb,
                p_perm=p, null_mean=float(null.mean()), null_p95=float(np.quantile(null, 0.95)),
                n_perm=int(len(null))), null


def first_eig_share(R: np.ndarray) -> float:
    ev = np.linalg.eigvalsh(np.nan_to_num(R))
    return float(ev.max() / len(R))


# ── main ─────────────────────────────────────────────────────────────────────
def main():
    OUT.mkdir(exist_ok=True)
    means, counts, meta = load()
    items = list(meta.item_id)
    labels = meta.domain.to_numpy()
    rev = meta.reverse.to_numpy()
    same_key = rev[:, None] == rev[None, :]
    maxdiff, ncomp = check_against_table5(means)
    assert maxdiff < 1e-9, maxdiff

    mats = {lang: means.loc[lang] for lang in ("en", "zh")}
    mats["pooled"] = means.reset_index(level=0, drop=False).set_index("language", append=True)[items]
    for lang, M in mats.items():
        M.to_csv(OUT / f"item_means_prejudice_{lang}.csv")
    shape = {k: list(v.shape) for k, v in mats.items()}
    n_missing = {k: int(v.isna().sum().sum()) for k, v in mats.items()}

    rows, nulls, by_dom, keying, eig, loo = [], {}, [], [], [], []
    analyses = [("primary", "spearman", False, None), ("S1_same_keying", "spearman", False, same_key),
                ("S2_row_centred", "spearman", True, None), ("S3_pearson", "pearson", False, None)]
    for lang, M in mats.items():
        for name, method, centre, keep in analyses:
            if lang == "pooled" and name not in ("primary", "S1_same_keying"):
                continue
            X = M.sub(M.mean(axis=1), axis=0) if centre else M
            R = corr(X, method)
            if name == "primary":
                pd.DataFrame(R, index=items, columns=items).to_csv(OUT / f"correlation_spearman_{lang}.csv")
            res, null = perm_test(R, labels, keep, rng_for(f"{lang}|{name}"))
            rows.append(dict(analysis=name, language=lang, n_rows=M.shape[0], **res))
            nulls[(lang, name)] = (res["delta"], null)
            eig.append(dict(language=lang, analysis=name, first_eigenvalue_share=first_eig_share(R)))
            if name == "primary":
                iu0, iu1 = np.triu_indices(21, 1)
                r = R[iu0, iu1]
                for k, dom in enumerate(DOMAINS):
                    idx = np.where(labels == dom)[0]
                    sub = R[np.ix_(idx, idx)][np.triu_indices(len(idx), 1)]
                    by_dom.append(dict(language=lang, domain=dom, k_items=len(idx), n_pairs=len(sub),
                                       mean_within_rho=float(sub.mean()),
                                       forward_keyed=",".join(meta.item_id[idx][~rev[idx]]) or "-"))
                sk = same_key[iu0, iu1]
                keying.append(dict(language=lang, mean_rho_same_keying=float(r[sk].mean()), n_same=int(sk.sum()),
                                   mean_rho_mixed_keying=float(r[~sk].mean()), n_mixed=int((~sk).sum())))
        if lang != "pooled":
            for model in sorted(M.index.get_level_values("model").unique()):
                Mm = M.drop(index=model, level="model")
                for name, keep in (("primary", None), ("S1_same_keying", same_key)):
                    res, _ = perm_test(corr(Mm, "spearman"), labels, keep, rng_for(f"{lang}|loo|{model}|{name}"))
                    loo.append(dict(language=lang, analysis=name, dropped_model=model, n_rows=Mm.shape[0],
                                    delta=res["delta"], p_perm=res["p_perm"]))

    summ = pd.DataFrame(rows)
    summ.to_csv(OUT / "domain_contrast_summary.csv", index=False)
    pd.DataFrame(by_dom).to_csv(OUT / "domain_within_by_domain.csv", index=False)
    pd.DataFrame(keying).to_csv(OUT / "keying_diagnostic.csv", index=False)
    pd.DataFrame(eig).to_csv(OUT / "eigen_summary.csv", index=False)
    loo_df = pd.DataFrame(loo)
    loo_df.to_csv(OUT / "leave_one_model_out.csv", index=False)
    counts.stack().rename("n_valid").reset_index().to_csv(OUT / "cell_valid_counts.csv", index=False)

    make_figures(mats, labels, meta, nulls)
    verdict = apply_rules(summ)
    write_readme(summ, pd.DataFrame(by_dom), pd.DataFrame(keying), pd.DataFrame(eig), loo_df, meta,
                 shape, n_missing, maxdiff, ncomp, counts, verdict)
    log = dict(run_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"), seed=SEED, n_perm=N_PERM,
               script=str(Path(__file__).relative_to(REPO)), script_sha256=sha256(Path(__file__)),
               inputs={str(p.relative_to(REPO)): sha256(p) for p in
                       [AN / "en/results_14models_en.csv", AN / "zh/results_14models_zh.csv",
                        AN / "Table5_item_stigma_profile.csv"]},
               python=sys.version.split()[0], numpy=np.__version__, pandas=pd.__version__,
               platform=platform.platform())
    (OUT / "run_log.json").write_text(json.dumps(log, indent=1), encoding="utf-8")
    print(summ.round(4).to_string(index=False))
    print("\nverdict:", verdict)


def apply_rules(summ: pd.DataFrame) -> dict:
    """Plan §4: support needs delta > 0 and p < .05 in primary AND S1, in both languages."""
    g = lambda lang, a: summ[(summ.language == lang) & (summ.analysis == a)].iloc[0]
    out = {}
    for lang in ("en", "zh"):
        pr, s1 = g(lang, "primary"), g(lang, "S1_same_keying")
        sig = lambda r: (r.delta > 0) and (r.p_perm < ALPHA)
        if sig(pr) and sig(s1):
            out[lang] = "support"
        elif sig(pr) and not sig(s1):
            out[lang] = "keying"
        elif not sig(pr) and not sig(s1):
            out[lang] = "no_evidence"
        else:
            out[lang] = "keying_matched_only"
    out["overall"] = ("support" if out["en"] == out["zh"] == "support" else
                      "mixed" if "support" in (out["en"], out["zh"]) else out["en"] if out["en"] == out["zh"]
                      else "mixed")
    return out


def make_figures(mats, labels, meta, nulls):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    plt.rcParams.update({"font.family": "Arial", "pdf.fonttype": 42, "ps.fonttype": 42})
    items = list(meta.item_id)
    rev = meta.reverse.to_numpy()
    ticks = [f"{i}{'' if r else ' (F)'}" for i, r in zip(items, rev)]
    fig, axes = plt.subplots(1, 2, figsize=(13, 6.4))
    for ax, lang, tag in zip(axes, ("en", "zh"), ("a", "b")):
        R = mats[lang].corr(method="spearman", min_periods=10).to_numpy()
        im = ax.imshow(R, vmin=-1, vmax=1, cmap="RdBu_r")
        start = 0
        for dom in DOMAINS:
            k = int((labels == dom).sum())
            ax.add_patch(Rectangle((start - 0.5, start - 0.5), k, k, fill=False, lw=1.6, ec="black"))
            start += k
        ax.set_xticks(range(21)); ax.set_yticks(range(21))
        ax.set_xticklabels(ticks, rotation=90, fontsize=7); ax.set_yticklabels(ticks, fontsize=7)
        ax.set_title(f"{LANG_LABEL[lang]} prompts (56 cells)", fontsize=11, fontweight="bold")
        ax.text(-0.16, 1.04, tag, transform=ax.transAxes, fontsize=14, fontweight="bold")
    cb = fig.colorbar(im, ax=axes, shrink=0.75, pad=0.02)
    cb.set_label("Spearman rho between item means across cells")
    fig.text(0.01, 0.01, "Items ordered by a-priori domain (boxes): disclosure, treatment carry-over, traditional "
             "prejudice, exclusionary, negative affect, dangerousness. (F) = forward-keyed item; others reverse-keyed.",
             fontsize=8)
    fig.savefig(OUT / "fig_domain_correlation_heatmap.pdf", bbox_inches="tight")
    fig.savefig(OUT / "fig_domain_correlation_heatmap.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(10, 6.5), sharex=False)
    for c, lang in enumerate(("en", "zh")):
        for r, (name, title) in enumerate((("primary", "All item pairs"),
                                          ("S1_same_keying", "Same-keying pairs only (S1)"))):
            obs, null = nulls[(lang, name)]
            ax = axes[r][c]
            ax.hist(null, bins=60, color="0.75", edgecolor="0.6", linewidth=0.3)
            ax.axvline(obs, color="#B2182B", lw=2)
            ax.set_title(f"{LANG_LABEL[lang]}: {title}", fontsize=10, fontweight="bold")
            ax.set_xlabel("Within-domain minus between-domain mean rho")
            ax.set_ylabel("Permutations")
            ax.text(0.02, 0.92, f"observed = {obs:+.3f}", transform=ax.transAxes, ha="left", fontsize=9,
                    color="#B2182B")
    fig.tight_layout()
    fig.savefig(OUT / "fig_permutation_null.pdf")
    fig.savefig(OUT / "fig_permutation_null.png", dpi=300)
    plt.close(fig)


def fmt_p(p: float) -> str:
    return f"{p:.4f}" if p >= 0.0001 else "< 0.0001"


def write_readme(summ, by_dom, keying, eig, loo, meta, shape, n_missing, maxdiff, ncomp, counts, verdict):
    V = {"support": "支持 domain 結構(主要分析與 S1 皆 Δ > 0 且 p < 0.05)",
         "keying": "結構可歸因於計分方向(主要分析顯著、S1 不顯著)",
         "no_evidence": "沒有證據顯示依循 domain 結構(主要分析與 S1 皆不顯著)",
         "keying_matched_only": "主要分析不顯著、S1 顯著(計畫未預先定義此情形，照實描述)",
         "mixed": "兩種語言結論不同(見各語言)"}
    lines = ["# Prejudice 量表 domain 結構分析(回應 R2-2，兼及 R1-5)", "",
             "- 分析計畫：`ANALYSIS_PLAN.md`(在計算任何相關之前寫定)。程式："
             "`scripts_public/psychometric_domain_structure_14model.py`。執行紀錄與輸入檔雜湊：`run_log.json`。",
             "- 本檔由程式產生，數字都直接取自同資料夾的 CSV。", "",
             "## 1. 資料檢查", "",
             f"- 矩陣大小：英文 {shape['en'][0]} × {shape['en'][1]}、中文 {shape['zh'][0]} × {shape['zh'][1]}、"
             f"合併 {shape['pooled'][0]} × {shape['pooled'][1]}(列 = 模型 × 情境，欄 = 21 題)。",
             f"- 缺格：英文 {n_missing['en']}、中文 {n_missing['zh']}(中文 Claude Sonnet 4.5 的 PLE PJ11 沒有有效回應)。",
             f"- 每格有效回應數：最少 {int(np.nanmin(counts.to_numpy()))}，中位數 {int(np.nanmedian(counts.to_numpy()))}。",
             f"- 與已發表的 `Table5_item_stigma_profile.csv` 比對 {ncomp} 個 item 平均值，最大差 {maxdiff:.1e}。", "",
             "## 2. 主要結果與事先寫定的敏感度分析", "",
             "| 分析 | 語言 | 列數 | 同 domain 平均 ρ(對數) | 不同 domain 平均 ρ(對數) | Δ | 置換 p(單尾) | 置換分布 95 百分位 |",
             "|---|---|---|---|---|---|---|---|"]
    names = {"primary": "主要分析(全部題目對)", "S1_same_keying": "S1 同計分方向題目對", "S2_row_centred": "S2 列中心化",
             "S3_pearson": "S3 Pearson"}
    for _, r in summ.iterrows():
        lines.append(f"| {names[r.analysis]} | {LANG_LABEL[r.language]} | {r.n_rows} | {r.mean_within:.3f} ({r.n_within_pairs}) | "
                     f"{r.mean_between:.3f} ({r.n_between_pairs}) | {r.delta:+.3f} | {fmt_p(r.p_perm)} | {r.null_p95:+.3f} |")
    lines += ["", "來源：`domain_contrast_summary.csv`。", "",
              "## 3. 依計畫 §4 的判讀", "",
              f"- 英文：{V[verdict['en']]}", f"- 中文：{V[verdict['zh']]}", f"- 整體：{V[verdict['overall']]}", "",
              "### 3.1 描述性補充(不屬於事先寫定的判讀規則)", ""]
    for lang in ("en", "zh"):
        between = summ[(summ.language == lang) & (summ.analysis == "primary")].mean_between.iloc[0]
        d = by_dom[by_dom.language == lang]
        above = d[d.mean_within_rho > between]; below = d[d.mean_within_rho <= between]
        e1 = eig[(eig.language == lang) & (eig.analysis == "primary")].first_eigenvalue_share.iloc[0]
        kd = keying[keying.language == lang].iloc[0]
        lines.append(f"- {LANG_LABEL[lang]}：6 個 domain 中 {len(above)} 個的內部平均 ρ 高於不同 domain 的平均({between:.3f})；"
                     f"未高於者：{', '.join(f'{r.domain}({r.mean_within_rho:.3f})' for _, r in below.iterrows()) or '無'}。"
                     f"第一特徵值占 {e1:.1%}；同計分方向題目對平均 ρ {kd.mean_rho_same_keying:.3f}，"
                     f"不同方向 {kd.mean_rho_mixed_keying:.3f}。")
    lines += ["",
              "## 4. 各 domain 內部的平均 ρ(主要分析)", "",
              "| 語言 | domain | 題數 | 對數 | 平均 ρ | 正向計分題 |", "|---|---|---|---|---|---|"]
    for _, r in by_dom.iterrows():
        lines.append(f"| {LANG_LABEL[r.language]} | {r.domain} | {r.k_items} | {r.n_pairs} | {r.mean_within_rho:.3f} | {r.forward_keyed} |")
    lines += ["", "來源：`domain_within_by_domain.csv`。", "",
              "## 5. 描述性指標", "",
              "| 語言 | 同計分方向題目對平均 ρ(對數) | 不同計分方向題目對平均 ρ(對數) |", "|---|---|---|"]
    for _, r in keying.iterrows():
        lines.append(f"| {LANG_LABEL[r.language]} | {r.mean_rho_same_keying:.3f} ({r.n_same}) | {r.mean_rho_mixed_keying:.3f} ({r.n_mixed}) |")
    lines += ["", "| 語言 | 分析 | 第一特徵值占比 |", "|---|---|---|"]
    for _, r in eig.iterrows():
        lines.append(f"| {LANG_LABEL[r.language]} | {names[r.analysis]} | {r.first_eigenvalue_share:.3f} |")
    lines += ["", "來源：`keying_diagnostic.csv`、`eigen_summary.csv`。", "",
              "## 6. S4 逐一剔除模型", "", "| 語言 | 分析 | Δ 範圍 | p 範圍 | p < 0.05 的次數 / 14 |", "|---|---|---|---|---|"]
    for (lang, name), g in loo.groupby(["language", "analysis"], sort=False):
        lines.append(f"| {LANG_LABEL[lang]} | {names[name]} | {g.delta.min():+.3f} 至 {g.delta.max():+.3f} | "
                     f"{fmt_p(g.p_perm.min())} 至 {fmt_p(g.p_perm.max())} | {int((g.p_perm < ALPHA).sum())} |")
    lines += ["", "來源：`leave_one_model_out.csv`。", "",
              "## 7. 圖", "",
              "- `fig_domain_correlation_heatmap.{png,pdf}`：中英文的 21 × 21 題目相關矩陣，依 domain 排序並以方框標出；(F) 為正向計分題。",
              "- `fig_permutation_null.{png,pdf}`：主要分析與 S1 的置換分布與觀察值。", "",
              "## 8. 解讀時的限制(計畫中已寫定)", "",
              "- 這是跨格(模型 × 情境)的共變，不是人類驗證時的跨人共變；描述的是整組模型，不是任何單一模型。",
              "- 各格不是獨立樣本；置換檢定只比較事先定義的分組與隨機分組，不對相關係數做參數推論。",
              "- 正向結果也無法區分態度結構與題目語意相近；語言間差異只是描述，不是正式的 measurement invariance 檢定。",
              "- 沒有人類 item 層級資料可直接比較。"]
    # auto-generated results; Psychometric_draft.md (the former README.md, with hand-written drafts) is never overwritten
    (OUT / "Psychometric_results_auto.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
