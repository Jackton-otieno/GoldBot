"""Verify the active demo session when explicitly enabled by its operator."""

import json
import os
import sys

from goldbot.core.exness_demo import DemoProfile, VerificationError, verify


def main():
    try:
        profile = DemoProfile.from_environment(os.environ)
        import MetaTrader5 as mt5

        evidence = verify(mt5, profile)
    except VerificationError as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        print("Exness demo verification could not start.", file=sys.stderr)
        return 1
    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
