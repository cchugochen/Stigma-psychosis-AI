#!/usr/bin/env python3
"""Elicitation sensitivity collection, 4 models (npj Digital Medicine revision).

Arms (one process per model; arms and languages interleaved by blocked randomization):
  persona       item-by-item, original prompt + one leading role sentence   30 runs
  original_oct  item-by-item, original prompt, concurrent comparator        10 runs
  fullscale     one call per vignette with all 40 items, original prompt
                with only its last line changed to a one-line-per-item format 30 runs

The original collector (scripts_public/run_stigma_study.py) is imported,
not modified. Item-level arms call its run_experiment(); only build_system_prompt
and _csv_path_for_config are swapped per block.

Usage (run from anywhere; paths resolve from the repo root):
  python collect_frames_4model.py --model claude --smoke
  caffeinate -i python collect_frames_4model.py --model claude
"""
import argparse, contextlib, hashlib, importlib.util, io, json, os, platform, random, sys, time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
COLLECTOR = REPO / "scripts_public" / "run_stigma_study.py"
RAW_ROOT = REPO / "results_20260930_4models"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fullscale_lib as fs  # noqa: E402

spec = importlib.util.spec_from_file_location("rss", COLLECTOR)
rss = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rss)

# --- 1. keys: load_env() only runs inside main() of the original script --------
rss.ENV_FILE = REPO / ".env"
rss.load_env()

MODELS = {  # key: (provider, model_id)
    "claude":   ("anthropic", "claude-sonnet-4-5-20250929"),
    "gpt54":    ("openai",    "gpt-5.4"),
    "gemini35": ("google",    "gemini-3.5-flash"),
    "gptoss":   ("novita",    "openai/gpt-oss-120b"),
}
N_RUNS = {"Humanlike": 30, "Original_oct": 10, "Fullscale": 30}
TEMPERATURE = 0.3          # 2. original CLI default, copied onto every model in main()
DELAY_S = 1.0              # original CLI default
SEED = "20260930"
PERSONA_LINE = {"en": "Please role-play as a human research participant.", "zh": "請扮演人類受試者。"}
API_ERROR_ABORT = 0.05

# --- 3. keep the original builder; persona calls it, never the module attribute -
_ORIG_SYSTEM = rss.build_system_prompt
_ORIG_CSV_PATH = rss._csv_path_for_config


def persona_system(lang="en"):
    return PERSONA_LINE[lang] + "\n" + _ORIG_SYSTEM(lang)


def system_prompt_for(arm, lang):
    if arm == "Humanlike":
        return persona_system(lang)
    if arm == "Fullscale":
        return fs.fullscale_system_prompt(_ORIG_SYSTEM, lang)
    return _ORIG_SYSTEM(lang)


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sha256_text(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def env_versions():
    v = {"python": platform.python_version()}
    for mod in ("httpx", "h2"):
        try:
            v[mod] = __import__(mod).__version__
        except Exception:
            v[mod] = "unavailable"
    return v


def model_cfg(model_key, fullscale_max_tokens=None):
    provider, model_id = MODELS[model_key]
    spec_ = next(s for s in rss.AVAILABLE_MODELS[provider] if s["model_id"] == model_id)
    cfg = rss.build_model_config(provider, spec_)
    cfg.temperature = TEMPERATURE              # ModelConfig default is 0.0
    if fullscale_max_tokens:
        cfg.max_tokens = fullscale_max_tokens
    return cfg


def out_dir(root, arm, model_key, lang):
    d = root / arm / model_key / lang
    d.mkdir(parents=True, exist_ok=True)
    return d


def csv_path(root, arm, model_key, lang):
    return out_dir(root, arm, model_key, lang) / f"results_{arm}_{lang}.csv"


def completed_runs(root, arm, model_key, lang, vignettes):
    return rss._detect_completed_runs(csv_path(root, arm, model_key, lang), MODELS[model_key][1], lang, vignettes)


def rows_of_run(path, model_id, lang, run):
    return [r for r in rss._read_existing_csv(path)
            if r.get("model_id") == model_id and r.get("language") == lang and str(r.get("run")) == str(run)]


# --- item-by-item block (persona / original_oct) via the original run_experiment -
def run_itemwise(root, arm, model_key, lang, k, vignettes, log):
    rss.build_system_prompt = persona_system if arm == "Humanlike" else _ORIG_SYSTEM
    target = csv_path(root, arm, model_key, lang)
    rss._csv_path_for_config = lambda config, _t=target: _t
    cfg = model_cfg(model_key)
    config = rss.ExperimentConfig(
        n_runs=k, language=lang, output_dir=str(target.parent), temperature=TEMPERATURE,
        models_to_test=[cfg], include_vignettes=list(vignettes), dry_run=False,
        delay_between_calls=DELAY_S, run_label="")
    with contextlib.redirect_stdout(io.StringIO()):
        rss.run_experiment(config)
    rss.build_system_prompt = _ORIG_SYSTEM
    rss._csv_path_for_config = _ORIG_CSV_PATH
    return cfg


# --- full-scale block: one call per vignette, expanded to 40 item rows -----------
def run_fullscale(root, model_key, lang, k, vignettes, max_tokens, calls_log):
    cfg = model_cfg(model_key, fullscale_max_tokens=max_tokens)
    target = csv_path(root, "Fullscale", model_key, lang)
    system = system_prompt_for("Fullscale", lang)
    sd, pj = rss.SOCIAL_DISTANCE_ITEMS, rss.PREJUDICE_ITEMS
    stems = fs.stems_from_question_builder(rss.build_question_prompt, rss.VIGNETTES, sd, pj, lang)
    done_blocks = rss._detect_completed_vignette_blocks(target, cfg.model_id, lang)
    items = [(it, "social_distance") for it in sd] + [(it, "prejudice") for it in pj]
    ids = [it["id"] for it, _ in items]
    for vig in vignettes:
        if (k, vig) in done_blocks:
            continue
        vt = rss.VIGNETTES[vig]["text_zh" if lang == "zh" else "text_en"]
        user = fs.fullscale_user_prompt(vt, stems, sd, pj, lang)
        t0 = datetime.now(timezone.utc).isoformat()
        try:
            raw = rss.call_model(cfg, system, user)
            time.sleep(DELAY_S)
        except Exception as e:
            raw = f"[API_ERROR] {e}"
        frags, info = fs.split_fullscale_reply(raw, ids)
        ts = datetime.now(timezone.utc).isoformat()
        rows = []
        for it, st in items:
            frag = frags[it["id"]]
            rt = rss.classify_response(frag)
            parsed = scored = None
            if rt in ("valid", "hedged"):
                parsed = rss.parse_response(frag)
                if parsed is not None:
                    scored = rss.score_item(parsed, it["reverse"], st)
            rows.append({"model": cfg.name, "model_id": cfg.model_id, "provider": cfg.provider, "run": k,
                         "vignette": vig, "vignette_label": rss.VIGNETTES[vig]["label"], "scale_type": st,
                         "item_id": it["id"], "item_text": it["zh"] if lang == "zh" else it["en"],
                         "item_domain": it.get("domain", ""), "is_reverse": it["reverse"],
                         "is_sensitive": it["id"] in rss.HIGH_SENSITIVITY_ITEMS, "raw_response": frag,
                         "response_type": rt, "parsed_value": parsed, "scored_value": scored,
                         "temperature": TEMPERATURE, "language": lang, "timestamp": ts})
        rss._append_rows_to_csv(target, rows, rss._CSV_FIELDNAMES)
        calls_log.write(json.dumps({"ts_start": t0, "ts_end": ts, "model_key": model_key, "model_id": cfg.model_id,
                                    "lang": lang, "run": k, "vignette": vig, "max_tokens": cfg.max_tokens,
                                    "system_sha256": sha256_text(system), "user_sha256": sha256_text(user),
                                    "raw_response": raw, "parse_info": info}, ensure_ascii=False) + "\n")
        calls_log.flush()
    return cfg


def schedule(model_key):
    rng = random.Random(f"{SEED}-{model_key}")
    out = []
    for c in range(10):
        cycle = []
        for lang in ("en", "zh"):
            cycle += [("Humanlike", lang)] * 3 + [("Original_oct", lang)] + [("Fullscale", lang)] * 3
        rng.shuffle(cycle)
        out += [(c + 1, arm, lang) for arm, lang in cycle]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=sorted(MODELS))
    ap.add_argument("--smoke", action="store_true", help="1 run of each arm x language, PLE only, into _smoke/")
    ap.add_argument("--fullscale-max-tokens", type=int, default=4096)
    a = ap.parse_args()

    provider, model_id = MODELS[a.model]
    key_env = rss.PROVIDER_KEY_NAMES[provider]
    if not os.environ.get(key_env):
        sys.exit(f"ABORT: {key_env} not set after loading {rss.ENV_FILE}")

    root = RAW_ROOT / "_smoke" if a.smoke else RAW_ROOT
    root.mkdir(parents=True, exist_ok=True)
    vignettes = ["PLE"] if a.smoke else list(rss.VIGNETTES.keys())
    if a.smoke:
        plan = [(1, arm, lang) for lang in ("en", "zh") for arm in ("Humanlike", "Original_oct", "Fullscale")]
        n_runs = {arm: 1 for arm in N_RUNS}
    else:
        plan, n_runs = schedule(a.model), N_RUNS

    provenance = {"collector": str(COLLECTOR.relative_to(REPO)), "collector_sha256": sha256_file(COLLECTOR),
                  "collector_hash16_as_logged_by_original": rss._script_hash(),
                  "wrapper_sha256": sha256_file(__file__), "fullscale_lib_sha256": sha256_file(fs.__file__),
                  "seed": f"{SEED}-{a.model}", **env_versions()}
    log = open(root / f"collection_log_{a.model}.jsonl", "a", encoding="utf-8")
    calls_log = open(root / f"Fullscale_calls_{a.model}.jsonl", "a", encoding="utf-8")
    seen = {}
    for pos, (cycle, arm, lang) in enumerate(plan, 1):
        seen[(arm, lang)] = seen.get((arm, lang), 0) + 1
        before = completed_runs(root, arm, a.model, lang, vignettes)
        if len(before) >= seen[(arm, lang)]:
            continue
        missing = sorted(set(range(1, n_runs[arm] + 1)) - before)
        k = missing[0]
        t0 = datetime.now(timezone.utc).isoformat()
        if arm == "Fullscale":
            cfg = run_fullscale(root, a.model, lang, k, vignettes, a.fullscale_max_tokens, calls_log)
        else:
            cfg = run_itemwise(root, arm, a.model, lang, k, vignettes, log)
        after = completed_runs(root, arm, a.model, lang, vignettes)
        rows = rows_of_run(csv_path(root, arm, a.model, lang), model_id, lang, k)
        n_err = sum(1 for r in rows if (r.get("raw_response") or "").startswith("[API_ERROR]"))
        sysp = system_prompt_for(arm, lang)
        rec = {"ts_start": t0, "ts_end": datetime.now(timezone.utc).isoformat(), "pos": pos, "cycle": cycle,
               "model_key": a.model, "model_id": model_id, "arm": arm, "lang": lang, "run": k,
               "vignettes": vignettes, "n_rows_run": len(rows), "n_api_error": n_err,
               "completed_added": sorted(after - before), "system_prompt": sysp,
               "system_prompt_sha256": sha256_text(sysp), "model_cfg": asdict(cfg), **provenance}
        log.write(json.dumps(rec, ensure_ascii=False) + "\n"); log.flush()
        print(f"[{rec['ts_end'][:19]}] {a.model} pos {pos}/{len(plan)} {arm}-{lang} run {k}: "
              f"{len(rows)} rows, {n_err} API errors", flush=True)
        if after - before != {k}:
            sys.exit(f"ABORT: {arm}-{lang} run {k} did not complete cleanly (added {sorted(after - before)})")
        if rows and n_err / len(rows) > API_ERROR_ABORT:
            sys.exit(f"ABORT: {arm}-{lang} run {k} has {n_err}/{len(rows)} API errors")
    print(f"DONE {a.model}", flush=True)


if __name__ == "__main__":
    main()
