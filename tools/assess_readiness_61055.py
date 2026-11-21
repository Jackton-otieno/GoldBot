"""Write the consolidated offline readiness assessment to a fresh directory."""

import argparse
from datetime import date
import json
from pathlib import Path

from goldbot.reporting.readiness_61055 import build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    for name, content in build(root, args.as_of).items():
        with (args.output / name).open("x", encoding="utf-8", newline="\n") as output:
            json.dump(content, output, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False)
            output.write("\n")


if __name__ == "__main__":
    main()
