"""Claude Code hook bridge: `tremblecode-hook <event> --agent <name>`.

Reads the hook's stdin JSON, POSTs it to the local relay, and prints the
relay's JSON response (Claude Code consumes structured hook output from
stdout). Must NEVER block a turn: short timeouts, exit 0 on any failure.
"""

import json
import os
import sys
import urllib.request


def main() -> int:
    args = sys.argv[1:]
    if not args:
        return 0
    event = args[0]
    agent = os.environ.get("TC_AGENT", "")
    if "--agent" in args:
        try:
            agent = args[args.index("--agent") + 1]
        except IndexError:
            pass

    try:
        hook_payload = json.load(sys.stdin)
    except Exception:
        hook_payload = {}

    relay = os.environ.get("TC_RELAY", "http://127.0.0.1:8765")
    body = json.dumps({"agent": agent, "event": event, "hook": hook_payload}).encode()
    req = urllib.request.Request(
        f"{relay}/hook/{event}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            out = res.read().decode()
            if out and out not in ("{}", "null"):
                sys.stdout.write(out)
    except Exception:
        pass  # never fail the turn
    return 0


if __name__ == "__main__":
    sys.exit(main())
