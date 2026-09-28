#!/usr/bin/env python3
"""Repackage a local gstack checkout (~/.claude/skills/gstack) as Claude Cowork plugins.

Cowork does not read ~/.claude/skills and cannot run gstack's bun/bash runtime
(bin/, lib/), so this script copies only the prose (SKILL.md + reference
markdown), rewrites repo paths to ${CLAUDE_PLUGIN_ROOT}, strips PreToolUse hooks
(unsupported in Cowork), and swaps the runtime preamble for a Cowork-aware stub.

Usage:  python3 build.py [--src ~/.claude/skills/gstack]
Re-run after every `/gstack-upgrade`, then commit + push.
"""
import argparse, json, os, re, shutil, sys
from pathlib import Path

CORE = [  # prose / planning / review / docs skills that work without gstack's runtime
    "gstack", "autoplan", "office-hours", "plan-ceo-review", "plan-eng-review",
    "plan-design-review", "plan-devex-review", "spec", "review", "investigate",
    "retro", "health", "document-generate", "document-release", "deslop-shared-libs",
    "learn", "context-save", "context-restore", "plan-tune", "ship",
    "landing-report", "setup-deploy", "design-html", "design-consultation",
]
EXCLUDE = {  # hook-only guards (stripped hooks would give false safety) + self-updater
    "careful", "guard", "freeze", "unfreeze", "gstack-upgrade",
}
SHARED_FILES = ["ETHOS.md", "LICENSE", "scripts/jargon-list.json", "scripts/question-registry.ts"]
TEXT_EXT = {".md", ".json", ".js", ".css", ".html", ".txt", ".template", ".sh", ".ts"}
MAX_FILE = 1_000_000

PREAMBLE_RE = re.compile(
    r'_SS="\$HOME/\.claude/skills/gstack/bin/gstack-skill-start"\n'
    r'\[ -x "\$_SS" \] \|\| _SS="\.claude/skills/gstack/bin/gstack-skill-start"\n'
    r'"\$_SS" --skill "([^"]+)" --model "claude" --parent-pid "\$PPID" \\\n'
    r'  \|\| echo "SKILL_START: unavailable[^"]*"\n'
)
PREAMBLE_STUB = (
    '# Cowork host: gstack\'s bash/bun runtime (bin/) is not bundled in this plugin.\n'
    '# Degraded mode is the normal state here — continue the workflow from the prose.\n'
    'echo "SKILL_START: unavailable — Cowork host (no gstack runtime; preamble degraded, continue the user\'s task)"\n'
)
DEGRADED_RE = re.compile(r"tell\s+the user to run `\./setup` or `/gstack-upgrade`, and proceed with their task\.")
DEGRADED_SUB = "and proceed with their task (on Cowork this is the normal state — never tell the user to run `./setup` or `/gstack-upgrade`)."
PATH_RE = re.compile(r"(?:\$HOME|~)/\.claude/skills/gstack/")

COWORK_NOTE = """> **Cowork host note (gstack-cowork repackaging).** gstack's runtime helpers
> (`${CLAUDE_PLUGIN_ROOT}/bin/*`, `$B`, `$D`, gbrain, codex) are **not bundled** here.
> Any command under `bin/` will fail: treat that as a silent no-op — skip telemetry,
> question-preference, decision/learnings logging and browser steps, never ask the
> user to run `./setup` or `/gstack-upgrade`, and carry on with the prose workflow.
> Reference docs are at `${CLAUDE_PLUGIN_ROOT}/docs/`, `ETHOS.md` and `scripts/`.
> If `CLAUDE_PLUGIN_ROOT` is unset, it is the plugin directory that contains this
> `skills/` folder.

"""

def strip_hooks(fm: str) -> str:
    out, skip = [], False
    for line in fm.splitlines(keepends=True):
        if re.match(r"^hooks:\s*$", line):
            skip = True; continue
        if skip and re.match(r"^[A-Za-z_-]+:", line):
            skip = False
        if not skip:
            out.append(line)
    return "".join(out)

def transform_skill_md(text: str, name: str) -> str:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        raise SystemExit(f"{name}: no frontmatter")
    fm, body = m.group(1), text[m.end():]
    fm = strip_hooks(fm + "\n").rstrip("\n")
    fm = PATH_RE.sub("${CLAUDE_PLUGIN_ROOT}/", fm)  # e.g. cso allowed-tools Bash(...) patterns
    body = PREAMBLE_RE.sub(PREAMBLE_STUB, body)
    body = DEGRADED_RE.sub(DEGRADED_SUB, body)
    body = PATH_RE.sub("${CLAUDE_PLUGIN_ROOT}/", body)
    # insert note after the auto-generated comment lines (if any)
    lines = body.split("\n")
    i = 0
    while i < len(lines) and (lines[i].startswith("<!--") or lines[i].strip() == ""):
        i += 1
    body = "\n".join(lines[:i]) + ("\n" if i else "") + COWORK_NOTE + "\n".join(lines[i:])
    return f"---\n{fm}\n---\n{body}"

def transform_text(text: str) -> str:
    return PATH_RE.sub("${CLAUDE_PLUGIN_ROOT}/", text)

def copy_skill(src_dir: Path, skill_md: Path, dst_dir: Path, name: str) -> int:
    n = 0
    dst_dir.mkdir(parents=True, exist_ok=True)
    (dst_dir / "SKILL.md").write_text(transform_skill_md(skill_md.read_text(), name))
    n += 1
    if src_dir is None:
        return n
    for p in src_dir.rglob("*"):
        if not p.is_file() or p == skill_md: continue
        rel = p.relative_to(src_dir)
        parts = rel.parts
        if "node_modules" in parts or "test" in parts or "tests" in parts: continue
        if p.suffix not in TEXT_EXT or p.name.endswith(".tmpl") or p.name.endswith(".test.ts"): continue
        if p.stat().st_size > MAX_FILE: continue
        out = dst_dir / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            out.write_text(transform_text(p.read_text()))
        except UnicodeDecodeError:
            shutil.copy2(p, out)
        n += 1
    return n

def write_plugin(root: Path, src: Path, pname: str, skills: list[str], version: str, desc: str, upstream: str):
    pdir = root / "plugins" / pname
    if pdir.exists(): shutil.rmtree(pdir)
    total = 0
    for s in skills:
        if s == "gstack":
            total += copy_skill(None, src / "SKILL.md", pdir / "skills" / "gstack", s)
        else:
            total += copy_skill(src / s, src / s / "SKILL.md", pdir / "skills" / s, s)
    # shared reference material
    for rel in SHARED_FILES:
        p = src / rel
        if p.exists():
            out = pdir / rel; out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(transform_text(p.read_text()))
    (pdir / "docs").mkdir(exist_ok=True)
    for p in sorted((src / "docs").glob("*.md")):
        (pdir / "docs" / p.name).write_text(transform_text(p.read_text()))
    (pdir / ".claude-plugin").mkdir(exist_ok=True)
    (pdir / ".claude-plugin" / "plugin.json").write_text(json.dumps({
        "name": pname,
        "version": version,
        "description": desc,
        "author": {"name": "Garry Tan (gstack); Cowork repackaging by kooock"},
        "homepage": upstream,
        "repository": "https://github.com/kooock/gstack-cowork",
        "license": "MIT",
        "keywords": ["gstack", "cowork", "code-review", "planning", "qa", "ship"],
        "skills": "./skills",
    }, indent=2) + "\n")
    return total

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.expanduser("~/.claude/skills/gstack"))
    args = ap.parse_args()
    src, root = Path(args.src), Path(__file__).resolve().parent
    if not (src / "SKILL.md").exists():
        sys.exit(f"gstack checkout not found at {src}")
    version_raw = (src / "VERSION").read_text().strip()          # e.g. 1.91.2.0
    version = ".".join(version_raw.split(".")[:3])
    all_skills = sorted(d.name for d in src.iterdir() if d.is_dir() and (d / "SKILL.md").exists())
    extras = [s for s in all_skills if s not in CORE and s not in EXCLUDE]
    missing = [s for s in CORE if s != "gstack" and s not in all_skills]
    if missing: print("WARN core skills missing in checkout:", missing)
    core = [s for s in CORE if s == "gstack" or s in all_skills]
    upstream = "https://github.com/garrytan/gstack"

    n_core = write_plugin(root, src, "gstack", core, version,
        "gstack for Claude Cowork — planning, review, spec, docs, retro and ship skills from garrytan/gstack, repackaged to run without gstack's local bun/bash runtime.", upstream)
    n_extra = write_plugin(root, src, "gstack-extras", extras, version,
        "gstack skills that depend on host tooling gstack cannot ship into Cowork's sandbox (bundled browser, iOS simulators, codex, gbrain, docker). Installed as-is for experimentation; expect degraded behaviour.", upstream)

    (root / ".claude-plugin").mkdir(exist_ok=True)
    (root / ".claude-plugin" / "marketplace.json").write_text(json.dumps({
        "name": "gstack-cowork",
        "owner": {"name": "kooock"},
        "metadata": {
            "description": "Unofficial Claude Cowork packaging of garrytan/gstack (MIT). Rebuilt from a local gstack checkout by build.py.",
            "version": version,
        },
        "plugins": [
            {"name": "gstack", "source": "./plugins/gstack", "version": version, "category": "development",
             "description": f"gstack core for Cowork ({len(core)} skills): /office-hours, /plan-ceo-review, /plan-eng-review, /plan-design-review, /autoplan, /spec, /review, /investigate, /retro, /ship, /document-generate and more.",
             "keywords": ["gstack", "cowork", "planning", "review"]},
            {"name": "gstack-extras", "source": "./plugins/gstack-extras", "version": version, "category": "development",
             "description": f"gstack skills needing host tooling ({len(extras)} skills: browser QA, iOS, codex, cso, gbrain). Experimental in Cowork.",
             "keywords": ["gstack", "cowork", "experimental"]},
        ],
    }, indent=2) + "\n")
    (root / "BUILD_INFO.json").write_text(json.dumps({
        "gstack_version": version_raw, "core": core, "extras": extras, "excluded": sorted(EXCLUDE),
        "core_files": n_core, "extras_files": n_extra,
    }, indent=2) + "\n")
    print(f"gstack {version_raw}: core={len(core)} skills ({n_core} files), extras={len(extras)} skills ({n_extra} files), excluded={sorted(EXCLUDE)}")

if __name__ == "__main__":
    main()
