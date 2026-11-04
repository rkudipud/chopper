"""Grade one Chopper audit bundle for a v1 -> v2 migration, deterministically.

Usage: python check_v2.py AUDIT [--baseline V1_AUDIT] [--require-adoption] [--json]

AUDIT and V1_AUDIT are ``.chopper/`` folders (or full copies of one) from
``chopper validate`` / ``chopper trim [--dry-run]``. The report has five parts:

* ``gate``        -- pass/fail checks: run succeeded, one schema version, every
                     vars_file pointer exists, the generated vars sourcing file is
                     emitted and kept with a p4 line, a live trim wrote exactly the
                     preview, no unexpected change against the baseline, and (with
                     ``--require-adoption``) a vars_file pointer is in use.
* ``adoption``    -- none (v1) / schema-only / partial / full / not-applicable.
* ``preview``     -- the ``iproc_source`` lines of ``<flow>_feature_vars.tcl``,
                     built the way Chopper builds it.
* ``delta``       -- with ``--baseline``: every fact that changed (same facts as
                     ``compare_manifests.py``), classed expected / review / unexpected.
* ``suggestions`` -- concrete JSON edits, each tied to evidence in the bundle.

Exit code: 0 when every gate passes or is skipped, 1 otherwise. Stdlib only.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_manifests import _facts, _lines, diff, render  # noqa: E402

_TCL_WORD_ESCAPES = str.maketrans(
    {**{c: f"\\{c}" for c in ' \\"{}[]$;'}, "\t": r"\t", "\r": r"\r", "\n": r"\n", "\v": r"\v", "\f": r"\f"}
)
# ponytail: line-anchored `proc NAME` regex, not a Tcl parser; misses computed names (fine for advice).
_PROC_RE = re.compile(r"^\s*proc\s+(\S+)", re.MULTILINE)
_POINTER = "vars_file"
_LEVELS = {"fix": 0, "improve": 1, "review": 2}
_CLASSES = {"unexpected": 0, "review": 1, "expected": 2}


def _json(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def _version(data: dict[str, Any]) -> str:
    return "v2" if str(data.get("$schema", "")).endswith("-v2") else "v1"


def _expand(entry: str) -> tuple[str, str, str]:
    pure = PurePosixPath(entry)
    return entry, str(pure.with_name(f"tech_{pure.name}")), str(pure.with_name(f"project_{pure.name}"))


def _literal(entry: str) -> bool:
    return not any(c in entry for c in "*?[")


def _short(canonical: str) -> str:
    return canonical.partition("::")[2].split("::")[-1]


def _q(items: list[str]) -> str:
    return ", ".join(json.dumps(i) for i in items)


def _sourced(step: str) -> str | None:
    """Path sourced by a ``source`` / ``iproc_source`` step, flags skipped."""
    words = step.split()
    if not words or words[0] not in ("source", "iproc_source"):
        return None
    paths = [w for w in words[1:] if not w.startswith("-")]
    return paths[0] if paths else None


def _steps(node: Any) -> list[str]:
    """Every stage step string in a base/feature JSON (stages, flow_actions, replacements)."""
    if isinstance(node, list):
        return [s for item in node for s in _steps(item)]
    if not isinstance(node, dict):
        return []
    out: list[str] = []
    for key, value in node.items():
        if key in ("steps", "items") and isinstance(value, list):
            out.extend(v for v in value if isinstance(v, str))
        elif key == "with" and isinstance(value, str):
            out.append(value)
        else:
            out.extend(_steps(value))
    return out


class Bundle:
    """Everything one audit folder says, plus the domain source it was cut from."""

    def __init__(self, audit: Path) -> None:
        self.audit = audit
        self.run = _json(audit / "chopper_run.json", {})
        self.manifest = _json(audit / "compiled_manifest.json", None)
        self.graph = _json(audit / "dependency_graph.json", {})
        self.diags = _json(audit / "diagnostics.json", {"diagnostics": []})["diagnostics"]
        self.p4 = _lines(audit, "p4_commands.txt")
        self.kept = {row.split("\t")[0] for row in _lines(audit, "files_kept.txt")}
        self.domain = Path(self.run.get("domain_path", "."))
        backup = Path(self.run["backup_path"]) if self.run.get("backup_path") else None
        self.root = backup if backup is not None and backup.is_dir() else self.domain
        self.flow = PurePosixPath(self.run.get("domain_path", "domain")).name
        base = _json(audit / "input_base.json", {})
        feats = [_json(p, {}) for p in sorted((audit / "input_features").glob("*.json"))]
        self.layers = [("base", base)] + [(f"feature:{f.get('name', '?')}", f) for f in feats]
        self.project = _json(audit / "input_project.json", None)
        everything = [data for _, data in self.layers] + ([self.project] if self.project else [])
        self.versions = sorted({_version(d) for d in everything})
        self.schema = _version(base)
        self.generated = f"{self.flow}_feature_vars.tcl"
        self._defined: dict[str, set[str]] = {}
        self._files: list[str] | None = None
        self._texts: dict[str, str] | None = None

    def references(self, rel: str) -> bool:
        """True when a stage step or another kept Tcl file names ``rel``'s basename (i.e. something loads it)."""
        # ponytail: basename text match, not a Tcl source trace; a mention in a comment also counts.
        word = re.compile(rf"(?<![\w.-]){re.escape(PurePosixPath(rel).name)}(?![\w.-])")
        if self._texts is None:
            skip = {self.generated}
            self._texts = {
                k: (self.root / k).read_text(encoding="utf-8", errors="replace")
                for k in sorted(self.kept)
                if k.endswith(".tcl") and k not in skip and (self.root / k).is_file()
            }
        steps = [s for _, d in self.layers for s in _steps(d)]
        return any(word.search(s) for s in steps) or any(word.search(t) for k, t in self._texts.items() if k != rel)

    def exists(self, rel: str) -> bool:
        return (self.root / rel).is_file()

    def defined(self, rel: str) -> set[str]:
        if rel not in self._defined:
            path = self.root / rel
            text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
            self._defined[rel] = {name.split("::")[-1] for name in _PROC_RE.findall(text)}
        return self._defined[rel]

    def files(self) -> list[str]:
        if self._files is None:
            skip = {".chopper", "jsons"}
            self._files = sorted(
                p.relative_to(self.root).as_posix()
                for p in self.root.rglob("*")
                if p.is_file() and not skip & set(p.relative_to(self.root).parts)
            )
        return self._files

    def rel(self, path: str) -> str | None:
        try:
            return Path(path).resolve().relative_to(self.domain.resolve()).as_posix()
        except ValueError:
            return None

    def codes(self, code: str) -> list[dict[str, Any]]:
        return [d for d in self.diags if d.get("code") == code]

    def pointers(self) -> list[tuple[str, str, str]]:
        return [(key, _POINTER, data[_POINTER]) for key, data in self.layers if data.get(_POINTER)]

    def pointer_files(self) -> set[str]:
        return {e for key, _, p in self.pointers() for e in (_expand(p) if key != "base" else (p,))}

    def preview(self) -> dict[str, list[str]]:
        if self.schema != "v2":
            return {}
        seen: set[str] = set()
        lines: list[str] = []
        for _, data in self.layers[1:]:
            block = [e for e in _expand(data[_POINTER]) if e not in seen] if data.get(_POINTER) else []
            seen.update(block)
            if block:
                lines.extend([""] if lines else [])
                lines.extend(f"iproc_source -file {e.translate(_TCL_WORD_ESCAPES)} -optional" for e in block)
        return {self.generated: lines}


def _main_file(name: str, base: bool) -> bool:
    if base:
        return name == "vars.tcl"
    return name.endswith("_vars.tcl") and not name.startswith(("tech_", "project_"))


def _candidates(b: Bundle, key: str, data: dict[str, Any]) -> list[tuple[str, str, str]]:
    """``(kind, file, edit)`` for each vars file this layer could point at without changing output."""
    out = []
    inc = [e for e in (data.get("files") or {}).get("include", []) if _literal(e)]
    pinc = (data.get("procedures") or {}).get("include", [])
    base = key == "base"
    kind = _POINTER
    if not data.get(kind):
        whole = sorted(e for e in inc if _main_file(PurePosixPath(e).name, base))
        covered = sorted(
            p["file"]
            for p in pinc
            if _main_file(PurePosixPath(p["file"]).name, base)
            and b.defined(p["file"])
            and b.defined(p["file"]) <= set(p.get("procs", []))
        )
        if whole:
            x = whole[0]
            drop = [e for e in inc if e in _expand(x)] if not base else [x]
            out.append((kind, x, f'add "{kind}": "{x}"; remove {_q(drop)} from files.include'))
        elif covered:
            x = covered[0]
            out.append((kind, x, f'add "{kind}": "{x}"; remove the procedures.include entry for "{x}"'))
    return out


def _suggest(b: Bundle, before: Bundle | None = None) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []

    def add(slug: str, level: str, target: str, message: str, edit: str) -> None:
        out.append({"slug": slug, "level": level, "target": target, "message": message, "edit": edit})

    mixed = len(b.versions) > 1
    named = [("project", b.project)] if b.project else []
    for key, data in named + b.layers:
        if _version(data) == "v1":
            new = str(data.get("$schema", "")).replace("-v1", "-v2")
            why = "this run mixes v1 and v2 (VE-41)" if mixed else "v2 enables vars_file pointers"
            add(
                "unflipped-json",
                "fix" if mixed else "improve",
                key,
                f"{key} is still v1; {why}.",
                f'"$schema": "{new}"',
            )

    pfiles = b.pointer_files()
    stems = {d["message"].rsplit("'", 2)[-2] for d in b.codes("VW-15") if d.get("message", "").endswith("'")}
    for key, data in b.layers:
        inc = [e for e in (data.get("files") or {}).get("include", []) if _literal(e)]
        for kind, x, edit in _candidates(b, key, data):
            unloaded = key != "base" and not b.references(x)
            add(
                "pointer-candidate",
                "improve",
                key,
                f'{x} is kept whole; a v2 "{kind}" pointer keeps it'
                + (
                    " (the infra already loads the base file)."
                    if key == "base"
                    else f" and sources it from {b.generated}."
                )
                + (
                    " Nothing references it today (no stage step, no other kept Tcl file), so the pointer"
                    " starts loading it at startup. Confirm it should load."
                    if unloaded
                    else ""
                ),
                edit,
            )
        for kind in (_POINTER,):
            ptr = data.get(kind)
            if not ptr:
                continue
            if before is not None and key != "base" and b.exists(ptr) and not before.references(ptr):
                add(
                    "newly-sourced",
                    "review",
                    key,
                    f"nothing in the baseline references {ptr} (no stage step, no other kept Tcl file); the"
                    f' "{kind}" pointer now loads it at startup from {b.generated}. Confirm it should load.',
                    f'no JSON edit if intended; otherwise remove "{kind}": "{ptr}" and keep it with files.include',
                )
            if not b.exists(ptr):
                match = difflib.get_close_matches(ptr, b.files(), n=1, cutoff=0.6)
                edit = f'"{kind}": "{match[0]}"' if match else f'fix the "{kind}" path or remove the key'
                if match and match[0] in inc:
                    edit += f'; then remove "{match[0]}" from files.include'
                add(
                    "missing-pointer", "fix", key, f"{kind} pointer {ptr} does not exist; its lines load nothing.", edit
                )
            if ptr in inc:
                add(
                    "redundant-pointer-include",
                    "improve",
                    key,
                    f'{ptr} is kept by the "{kind}" pointer already.',
                    f'remove "{ptr}" from files.include',
                )
            if key != "base":
                for variant in _expand(ptr)[1:]:
                    if variant in inc:
                        add(
                            "manual-variant-include",
                            "improve",
                            key,
                            f'{variant} is kept automatically when it exists (variant of the "{kind}" pointer).',
                            f'remove "{variant}" from files.include',
                        )
        for step in sorted(set(_steps(data))):
            path = _sourced(step)
            if path is not None and path in pfiles:
                add(
                    "double-sourcing-step",
                    "fix",
                    key,
                    f"{path} is already loaded at startup (generated sourcing file or infra); this step loads it"
                    " again and resets any tech_/project_ override.",
                    f'remove step "{step}"',
                )
            elif path is not None and step.split()[0] in stems and len(step.split()) > 1 and step.split()[1][:1] == "-":
                add(
                    "step-source-form",
                    "review",
                    key,
                    f'VW-15 for "{step.split()[0]}" is a false positive: the step check reads only "source <path>" /'
                    f' "iproc_source <path>", so "{step}" looks like a call to a missing proc. Nothing is missing.',
                    f"if {path} becomes a vars_file pointer, delete the step; otherwise list {step.split()[0]} in a"
                    " --tool-commands file to silence VW-15 (never add a stub proc)",
                )
        for x in sorted(e for e in (data.get("files") or {}).get("exclude", []) if _literal(e) and not b.exists(e)):
            add(
                "stale-exclude",
                "improve",
                key,
                f"{x} does not exist, so excluding it does nothing (VW-25).",
                f'remove "{x}" from files.exclude',
            )
        if not str(data.get("description", "")).strip():
            add(
                "missing-description",
                "improve",
                key,
                f"{key} has no description.",
                '"description": "<one line: what this layer adds>"',
            )
        if key != "base":
            mains = {_POINTER: data[_POINTER]} if data.get(_POINTER) else {}
            for kind, x, _ in _candidates(b, key, data):
                mains[kind] = x
            for kind, x in sorted(mains.items()):
                for variant in _expand(x)[1:]:
                    if not b.exists(variant):
                        continue
                    if data.get(kind):
                        state = f"is now kept and sourced after {x} by {b.generated}"
                    else:
                        live = any(_sourced(s) == variant for _, d in b.layers for s in _steps(d))
                        state = (
                            "is dropped"
                            if variant not in b.kept
                            else "is kept but never sourced"
                            if not live
                            else "is sourced by a step"
                        )
                        state += f'; a "{kind}" pointer would keep it and source it after {x}'
                    add(
                        "dormant-variant",
                        "review",
                        key,
                        f"{variant} {state}, so its values override {x}. Confirm.",
                        "no JSON edit; if the override is unwanted, remove or rename the file in the domain source",
                    )

    base_json = b.run.get("base_json", "")
    if base_json and PurePosixPath(base_json).stem.casefold() != b.flow.casefold():
        rel = b.rel(base_json) or PurePosixPath(base_json).name
        add(
            "base-name",
            "improve",
            "base",
            f"the base JSON is not named after the flow {b.flow} (VW-28 on v2).",
            f'p4 move {rel} jsons/{b.flow}.json; set "base": "jsons/{b.flow}.json" in the project JSON',
        )

    if b.manifest is not None:
        survivors = {p["canonical_name"]: p.get("selection_source", "") for p in b.manifest["procedures"]["surviving"]}
        traced = set(b.graph.get("pt", []))
        for edge in sorted(b.graph.get("edges", []), key=lambda e: (e["from"], e["to"])):
            if edge.get("status") == "resolved" and edge["from"] in survivors and edge["to"] in traced:
                parts = survivors[edge["from"]].split(":")
                owner = ":".join(parts[:2]) if parts[0] == "feature" else parts[0]
                file, _, name = edge["to"].partition("::")
                add(
                    "traced-callee-dropped",
                    "fix",
                    owner,
                    f"{_short(edge['from'])} is kept and calls {name}, which trace reports but never copies (VW-05).",
                    f'add "{name}" to procedures.include for "{file}"',
                )

    selected = [("base", base_json)] + [("feature", p) for p in b.run.get("feature_jsons", [])]
    selected += [("project", b.run["project_json"])] if b.run.get("project_json") else []
    rels = {b.rel(p) for _, p in selected}
    for key, path in selected:
        rel = b.rel(path)
        if rel and not rel.startswith("jsons/") and rel in b.p4:
            add(
                "project-outside-jsons",
                "fix",
                key if key != "feature" else rel,
                f"{rel} is inside the domain but outside jsons/, so a live trim removes it (exclude_file_list).",
                f"move it to jsons/{PurePosixPath(rel).name} and pass the new path",
            )
    jsons = b.root / "jsons"
    for orphan in sorted(p.relative_to(b.root).as_posix() for p in jsons.rglob("*.json")) if jsons.is_dir() else []:
        if orphan not in rels:
            version = _version(_json(b.root / orphan, {}))
            note = (
                f" It is {version} while this run is {b.schema}; selecting it later fails with VE-41."
                if version != b.schema
                else ""
            )
            add(
                "orphan-json",
                "review",
                orphan,
                f"{orphan} is not selected by this run.{note}",
                "flip it with the rest, add it to a project, or delete it"
                if note
                else "add it to a project or delete it",
            )

    for d in b.codes("VW-29"):
        m = re.search(r"from feature '([^']+)' already sourced by feature '([^']+)'", d.get("message", ""))
        if m:
            add(
                "shared-pointer",
                "review",
                f"feature:{m.group(1)}",
                d["message"],
                f'remove "{_POINTER}" from feature {m.group(1)} or from feature {m.group(2)}',
            )
    for d in b.codes("VW-09"):
        m = re.match(r"'([^']+)'", d.get("message", ""))
        if m and d.get("file") not in pfiles:
            add("file-and-proc-model", "improve", m.group(1), d["message"], d.get("recovery_hint", ""))

    unique = {json.dumps(s, sort_keys=True): s for s in out}
    return sorted(unique.values(), key=lambda s: (_LEVELS[s["level"]], s["target"], s["slug"], s["message"]))


def _adoption(b: Bundle) -> dict[str, Any]:
    pointers = [f"{key} {kind} {value}" for key, kind, value in b.pointers()]
    candidates = sorted(f"{key} {kind} {x}" for key, data in b.layers for kind, x, _ in _candidates(b, key, data))
    if b.schema == "v1":
        level = "none"
    elif not pointers:
        level = "schema-only" if candidates else "not-applicable"
    else:
        level = "partial" if candidates else "full"
    return {"level": level, "pointers": pointers, "candidates": candidates}


def _delta(b: Bundle, baseline: Path) -> list[dict[str, str]]:
    gen = {b.generated}
    pfiles = b.pointer_files()
    changes = list(diff(_facts(baseline), _facts(b.audit)))
    file_class: dict[str, tuple[str, str]] = {}

    def file_change(sign: str, key: str, a: Any, c: Any) -> tuple[str, str]:
        if sign == "+":
            if key in gen:
                return "expected", "generated sourcing file"
            return (
                "review",
                "kept (and sourced) automatically by a vars_file pointer" if key in pfiles else "new output file",
            )
        if sign == "-":
            return "unexpected", "file is no longer in the output"
        before, after = ({_short(p) for p in v[1]} if v[0] != "full-copy" else b.defined(key) for v in (a, c))
        if a[0] == "proc-trim" and c[0] == "full-copy":
            back = sorted(after - before)
            if not back:
                return "expected", "now copied whole; same procs as before"
            return "review", f"now copied whole; brings back {', '.join(back)}"
        lost, won = sorted(before - after), sorted(after - before)
        return "review", f"{a[0]} -> {c[0]}; dropped: {', '.join(lost) or '-'}; added: {', '.join(won) or '-'}"

    for sign, section, key, a, c in changes:
        if section == "file":
            file_class[key] = file_change(sign, key, a, c)

    rows = []
    for sign, section, key, a, c in changes:
        if section == "file":
            cls, note = file_class[key]
        elif section == "kept":
            if sign == "-":
                cls, note = "unexpected", "no longer kept"
            elif key in gen:
                cls, note = "expected", "generated sourcing file"
            elif key in pfiles:
                cls, note = "review", "kept (and sourced) automatically by a vars_file pointer"
            else:
                cls, note = "review", "newly kept"
        elif section == "p4":
            words = key.split()
            path = words[-1]
            if words[0] != "p4":
                cls, note = (
                    ("unexpected", "now removed from the client view")
                    if sign == "+"
                    else ("review", "no longer removed; now kept")
                )
            elif path in gen and sign == "+":
                cls, note = "expected", "generated sourcing file"
            else:
                cls, note = file_class.get(path, ("review", "p4 command changed"))
        elif section == "diag":
            if (c or 0) < (a or 0):
                cls, note = "expected", "warning cleared or reduced"
            elif key == "VW-28":
                cls, note = "review", "rename the base JSON after the flow to clear it"
            elif key[1:2] == "I":
                cls, note = "review", "new info diagnostic"
            else:
                cls, note = "unexpected", "new or increased diagnostic"
        elif section == "proc":
            cls, note = "review", "proc now kept" if sign == "+" else "proc no longer kept; confirm nothing calls it"
        else:
            cls, note = "review", "stage changed; confirm removed steps are covered by the generated sourcing files"
        rows.append({"class": cls, "line": render(sign, section, key, a, c).rstrip(), "note": note})
    return sorted(rows, key=lambda r: (_CLASSES[r["class"]], r["line"]))


def _gate(
    b: Bundle,
    preview: dict[str, list[str]],
    adoption: dict[str, Any],
    delta: list[dict[str, str]] | None,
    require: bool,
) -> list[dict[str, str]]:
    def row(check: str, ok: bool | None, detail: str) -> dict[str, str]:
        return {"check": check, "status": "skip" if ok is None else "pass" if ok else "fail", "detail": detail}

    errors = sorted(d["code"] for d in b.diags if d.get("severity") == "error")
    run_ok = b.run.get("exit_code") == 0 and not errors
    gates = [
        row("run-ok", run_ok, f"exit {b.run.get('exit_code')}; errors: {', '.join(errors) or 'none'}"),
        row("one-version", len(b.versions) == 1, ", ".join(b.versions)),
    ]
    v2 = b.schema == "v2"
    missing = sorted(d.get("message", "") for d in b.codes("VW-27"))
    gates.append(row("pointer-targets", None if not v2 else not missing, "; ".join(missing) or "all pointers exist"))
    if not v2 or b.manifest is None:
        gates.append(row("generated-files", None, "v1 run" if not v2 else "no compiled manifest"))
    else:
        treat = {f["path"]: f["treatment"] for f in b.manifest["files"]}
        bad = [
            name
            for name in sorted(preview)
            if treat.get(name) != "generated"
            or name not in b.kept
            or not any(
                line.split()[:2] in (["p4", "add"], ["p4", "edit"]) and line.split()[-1] == name for line in b.p4
            )
        ]
        gates.append(
            row("generated-files", not bad, f"not emitted/kept/p4: {', '.join(bad)}" if bad else "emitted")
        )
    if not v2 or b.run.get("mode") != "live" or not run_ok:
        gates.append(row("generated-content", None, "needs a successful live v2 trim"))
    else:
        bad = []
        for name, lines in sorted(preview.items()):
            path = b.domain / name
            text = path.read_text(encoding="utf-8") if path.is_file() else ""
            written = text.split("# Feature ", 1)[1].splitlines()[2:] if "# Feature " in text else None
            bad += [] if written == lines else [name]
        gates.append(
            row("generated-content", not bad, f"differs from preview: {', '.join(bad)}" if bad else "matches preview")
        )
    if delta is None:
        gates.append(row("baseline-delta", None, "no --baseline"))
    else:
        n = sum(r["class"] == "unexpected" for r in delta)
        gates.append(row("baseline-delta", n == 0, f"{n} unexpected change(s)"))
    level = adoption["level"]
    if require:
        gates.append(
            row(
                "adoption",
                v2 and bool(b.pointers()),
                f"level {level}; requires v2 with at least one vars_file pointer",
            )
        )
    else:
        gates.append(row("adoption", None, f"level {level} (enforce with --require-adoption)"))
    return gates


def build(audit: Path, baseline: Path | None, require: bool) -> dict[str, Any]:
    b = Bundle(audit)
    preview = b.preview()
    adoption = _adoption(b)
    delta = _delta(b, baseline) if baseline is not None and b.manifest is not None else None
    gate = _gate(b, preview, adoption, delta, require)
    return {
        "schema": b.schema,
        "flow": b.flow,
        "mode": b.run.get("mode", ""),
        "result": "fail" if any(g["status"] == "fail" for g in gate) else "pass",
        "gate": gate,
        "adoption": adoption,
        "preview": preview,
        "delta": delta or [],
        "suggestions": _suggest(b, Bundle(baseline) if baseline is not None else None),
    }


def _text(report: dict[str, Any]) -> str:
    out = [f"schema {report['schema']} | flow {report['flow']} | mode {report['mode']}", "", "GATE"]
    out += [f"  {g['status']:4}  {g['check']:18} {g['detail']}" for g in report["gate"]]
    a = report["adoption"]
    out += ["", f"ADOPTION {a['level']}"]
    out += [f"  pointer    {p}" for p in a["pointers"]] + [f"  candidate  {c}" for c in a["candidates"]]
    for name, lines in report["preview"].items():
        out += ["", f"PREVIEW {name} ({sum(bool(x) for x in lines)} line(s))"] + [f"  | {x}".rstrip() for x in lines]
    if report["delta"]:
        counts = {c: sum(r["class"] == c for r in report["delta"]) for c in _CLASSES}
        out += ["", "DELTA " + ", ".join(f"{n} {c}" for c, n in counts.items())]
        out += [f"  {r['class']:10} {r['line']}\n             {r['note']}" for r in report["delta"]]
    out += ["", f"SUGGESTIONS {len(report['suggestions'])}"]
    out += [
        f"  {s['level']:7} {s['target']}  {s['slug']}\n          {s['message']}\n          edit: {s['edit']}"
        for s in report["suggestions"]
    ]
    out += ["", f"RESULT: {report['result'].upper()}"]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("audit", type=Path, help=".chopper folder (or a copy) to grade")
    parser.add_argument("--baseline", type=Path, help=".chopper folder from the v1 run to diff against")
    parser.add_argument("--require-adoption", action="store_true", help="fail unless a vars_file pointer is in use")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)
    report = build(args.audit, args.baseline, args.require_adoption)
    print(json.dumps(report, indent=2) if args.json else _text(report))
    return 0 if report["result"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
