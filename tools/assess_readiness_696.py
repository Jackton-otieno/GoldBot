"""Generate a local, read-only Phase 6.9.6 dashboard and report."""

import argparse
import json
from dataclasses import asdict
from datetime import date
from hashlib import sha256
from html import escape
from pathlib import Path

from goldbot.reporting.readiness_696 import assess

OUTPUT = Path("reports/phase_6_9_6")


def file_hash(path):
    return sha256(path.read_bytes()).hexdigest()


def generate(root, as_of):
    from tools.collect_exness_phase_696 import PHASE_SCOPE
    from tools.summarize_exness_phase_696 import archived_smoke, summarize

    assessment = assess(root, as_of)
    sources = {source.path: source for finding in assessment.findings for source in finding.sources}
    smoke = archived_smoke(root, sources)
    output = root / OUTPUT
    journal = output / "boundary.sqlite3"
    log = output / "boundary-run.txt"
    boundary = {"status": "NO_JOURNAL", "holdout_eligible": False, "exposed": True}
    for path in (journal, log):
        if path.is_file():
            boundary.setdefault("source_sha256", {})[(OUTPUT / path.name).as_posix()] = file_hash(path)
    if journal.is_file():
        try:
            observed = summarize(journal, PHASE_SCOPE)
            incomplete = observed["manifest"]["interrupted_run_pending"]
            boundary.update(observed, status="INTERRUPTED" if incomplete else "JOURNAL_VERIFIED")
        except (OSError, RuntimeError, ValueError, KeyError, TypeError) as error:
            boundary.update(status="INVALID_JOURNAL", error=type(error).__name__)
        except Exception as error:
            boundary.update(status="UNVERIFIED_JOURNAL", error=type(error).__name__)

    payload = {
        "as_of": as_of.isoformat(),
        "decision": assessment.decision,
        "execution_authorized": assessment.execution_authorized,
        "historical_execution_authorized": assessment.historical_execution_authorized,
        "prospective_authorized": assessment.prospective_authorized,
        "blocker_register": [asdict(finding) for finding in assessment.findings],
        "archived_smoke": smoke,
        "boundary_diagnostic": boundary,
    }
    serde = lambda value: value.isoformat()  # Only dates require custom JSON encoding.
    output.mkdir(parents=True, exist_ok=True)
    (output / "assessment.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=serde) + "\n", encoding="utf-8")
    (output / "index.html").write_text(render_dashboard(assessment, smoke, boundary), encoding="utf-8")
    (output / "readiness.md").write_text(render_report(assessment, smoke, boundary), encoding="utf-8")
    return output


def diagnostic_lines(smoke, boundary):
    lines = [f"Phase 6.9.5 archive integrity: {smoke['status']}."]
    if smoke["status"] == "RECONCILED":
        lines.append("The archived journal contains eight quote snapshots and zero admitted M15/H1 "
                     "bar payloads. Between-poll tick coverage is unknown. The opening clock probe "
                     "failed and the paired clock assessment was unavailable.")
    lines.append(f"Phase 6.9.6 boundary diagnostic: {boundary['status']}.")
    if "bars" in boundary:
        lines.append(f"Collector completion status: {boundary['collector_status'] or 'UNFINISHED'}.")
        lines.append(f"Observed {boundary['quote_snapshots']} quote snapshots. Between-poll coverage is unknown.")
        for frame, stats in boundary["bars"].items():
            labels = ", ".join(map(str, stats["raw_boundaries"])) or "none"
            lines.append(f"{frame}: {stats['admitted_observations']} admitted bar observations, counting "
                         f"repeat reads, and {stats['unique_payloads']} unique stored bar payloads. "
                         f"Observed close labels in raw seconds: {labels}.")
        clock = boundary["host_clock_assessment"] or {}
        lines.append(f"Clock bracket assessment: {clock.get('status', 'UNAVAILABLE')}. "
                     "The production UTC mapping is unverified.")
    else:
        lines.append("No boundary bar payloads could be verified. See the bounded run log if available.")
    lines.append("All diagnostic observations are exposed and ineligible for a prospective holdout.")
    return lines


def render_report(assessment, smoke, boundary):
    lines = ["# Phase 6.9.6 integrated readiness", "",
             f"**NO-GO** · Assessed {assessment.as_of.isoformat()} (Africa/Nairobi).",
             "", "Execution, historical execution and prospective authorization are disabled.",
             "", "## Diagnostics", ""]
    lines += [f"- {line}" for line in diagnostic_lines(smoke, boundary)]
    for path, digest in boundary.get("source_sha256", {}).items():
        lines.append(f"- [{path}]({Path(path).name}) · `{digest}`")
    lines += ["", "## Blocker register", ""]
    for finding in assessment.findings:
        item = finding.requirement
        lines += [f"### {item.key.replace('_', ' ').capitalize()} · {finding.status.value}", "",
                  f"{item.scope.value}. {item.kind.value}. {item.detail}", "",
                  f"Required evidence. {item.next_evidence}", ""]
        if finding.issues:
            lines += ["Conditions recorded " + ", ".join(issue.value for issue in finding.issues) + ".", ""]
        for source in finding.sources:
            lines.append(f"- [{source.path}](../../{source.path}) · SHA-256 "
                         f"`{source.actual_sha256 or 'unavailable'}`"
                         + (f" · expected `{source.expected_sha256}` · {source.issue.value}"
                            if source.issue else ""))
        lines.append("")
    return "\n".join(lines)


def render_dashboard(assessment, smoke, boundary):
    cards = []
    for finding in assessment.findings:
        item = finding.requirement
        sources = "".join(
            f'<li><a href="../../{escape(s.path, quote=True)}">{escape(s.path)}</a>'
            f'<code>{escape(s.actual_sha256 or "unavailable")}</code>'
            + (f'<p>{s.issue.value} · Expected <code>{s.expected_sha256}</code></p>' if s.issue else "")
            + '</li>'
            for s in finding.sources
        )
        conditions = " · ".join(issue.value for issue in finding.issues)
        cards.append(f'<article><header><h3>{escape(item.key.replace("_", " ").capitalize())}</h3>'
                     f'<strong>{finding.status.value}</strong></header>'
                     f'<p class="scope">{escape(item.scope.value)} · {escape(item.kind.value)}</p>'
                     f'<p>{escape(item.detail)}</p><p><b>Required evidence</b> {escape(item.next_evidence)}</p>'
                     f'<p class="scope">{escape(conditions)}</p>'
                     f'<details><summary>Source paths and SHA-256</summary><ul>{sources}</ul></details></article>')
    details = "".join(f'<li>{escape(line)}</li>' for line in diagnostic_lines(smoke, boundary))
    for path, digest in boundary.get("source_sha256", {}).items():
        details += (f'<li><a href="{escape(Path(path).name, quote=True)}">{escape(path)}</a>'
                    f'<code>{digest}</code></li>')
    return f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>GoldBot · Phase 6.9.6 readiness</title>
<style>
:root{{color-scheme:dark;background:#14181e;color:#ecf0f4;font:16px/1.55 system-ui,sans-serif}}
*{{box-sizing:border-box}} body{{margin:auto;padding:clamp(1rem,4vw,3rem);max-width:1240px}}
h1{{font-size:clamp(1.85rem,5vw,3rem);line-height:1.12;margin:.3rem 0 1rem}}
h2{{margin-top:2rem}} a{{color:#9dd9f8}} .scope,code{{color:#c1ccd7}}
.hero,article,section.diagnostic{{background:#1c232d;border:1px solid #465366;border-radius:.7rem;padding:1.05rem}}
.decision,strong{{color:#ffd093}} .decision{{font-weight:800;font-size:1.4rem}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,350px),1fr));gap:1rem}}
article header{{display:flex;flex-wrap:wrap;gap:.3rem 1rem;align-items:baseline;justify-content:space-between}}
h3,article p{{margin:.45rem 0}} summary{{cursor:pointer;color:#9dd9f8}}
li{{margin:.35rem 0}} code{{display:block;overflow-wrap:anywhere}} a{{overflow-wrap:anywhere}}
</style>
<main><div class="hero"><div class="scope">Phase 6.9.6 · {assessment.as_of.isoformat()} · Africa/Nairobi</div>
<h1>GoldBot integrated readiness</h1><div class="decision">NO-GO</div>
<p>Execution, historical execution and prospective authorization are disabled.</p>
<nav><a href="#diagnostics">Diagnostics</a> · <a href="#blockers">Blocker register</a> ·
<a href="readiness.md">Report</a> · <a href="assessment.json">JSON</a></nav></div>
<h2 id="diagnostics">Diagnostics</h2><section class="diagnostic"><ul>{details}</ul></section>
<h2 id="blockers">Blocker register</h2><div class="grid">{"".join(cards)}</div></main></html>
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    print(generate(args.root, args.as_of))


if __name__ == "__main__":
    main()
