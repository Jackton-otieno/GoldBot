"""Write the offline prospective protocol draft and separate readiness states."""

import argparse
from datetime import date
import json
from pathlib import Path

from goldbot.reporting.prospective_6106 import PROPOSAL, candidate_registry, exposure_map, readiness


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    reports = {
        "proposed-protocol.json": PROPOSAL,
        "candidate-registry.json": candidate_registry(root).envelope(),
        "exposure-map.json": exposure_map(root).envelope(),
        "readiness.json": readiness(root, args.as_of),
    }
    for name, content in reports.items():
        with (args.output / name).open("x", encoding="utf-8", newline="\n") as output:
            json.dump(content, output, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False)
            output.write("\n")


if __name__ == "__main__":
    main()
