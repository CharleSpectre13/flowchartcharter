"""python -m flowchartcharter.house_cli <cmd> [arg]"""

from __future__ import annotations

import json
import sys

from .house import dispatch


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    cmd = args[0] if args else "status"
    arg = args[1] if len(args) > 1 else ""
    print(json.dumps(dispatch(cmd, arg), default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
