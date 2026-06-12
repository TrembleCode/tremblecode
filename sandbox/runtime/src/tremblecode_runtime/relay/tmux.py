"""tmux helpers. The single most fragile boundary in the system is injecting
text into a live Claude Code prompt — so we only ever inject ONE short line,
gated on the pane actually showing an idle prompt, and verify afterwards.
Message bodies always travel through the MCP tools, never through tmux."""

import asyncio
import logging

logger = logging.getLogger(__name__)


async def _run(*args: str) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        "tmux",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    out, _ = await proc.communicate()
    return proc.returncode, out.decode(errors="replace")


async def has_session(name: str) -> bool:
    code, _ = await _run("has-session", "-t", f"={name}")
    return code == 0


async def new_session(
    name: str, command: str, cwd: str, env: dict[str, str] | None = None
) -> bool:
    args = ["new-session", "-d", "-s", name, "-x", "220", "-y", "50", "-c", cwd]
    for key, value in (env or {}).items():
        args += ["-e", f"{key}={value}"]
    args.append(command)
    code, out = await _run(*args)
    if code != 0:
        logger.error("tmux new-session %s failed: %s", name, out)
    return code == 0


async def kill_session(name: str) -> None:
    await _run("kill-session", "-t", f"={name}")


async def capture_pane(name: str, lines: int = 30) -> str:
    code, out = await _run(
        "capture-pane", "-p", "-t", f"={name}:0.0", "-S", f"-{lines}"
    )
    return out if code == 0 else ""


async def pane_alive(name: str) -> bool:
    """True if the session exists and its pane process hasn't exited."""
    code, out = await _run(
        "list-panes", "-t", f"={name}:0", "-F", "#{pane_dead}"
    )
    return code == 0 and out.strip().splitlines() and out.strip().splitlines()[0] == "0"


def looks_idle(pane_text: str) -> bool:
    """Heuristic: Claude Code's input box is visible and it is not mid-turn.
    The '❯' prompt marker (or the '>' box) shows when awaiting input; spinner
    markers (✻, ✽, 'esc to interrupt') show during a turn."""
    tail = pane_text.rstrip().splitlines()[-15:]
    text = "\n".join(tail)
    if "esc to interrupt" in text:
        return False
    return ("❯" in text) or ("│ >" in text) or text.strip().endswith(">")


async def send_line(name: str, line: str, *, settle: float = 0.5, retries: int = 3) -> bool:
    """Inject a single line + Enter, verifying submission via pane capture."""
    line = line.replace("\n", " ").strip()
    for attempt in range(1, retries + 1):
        code, out = await _run("send-keys", "-t", f"={name}:0.0", "-l", line)
        if code != 0:
            logger.warning("send-keys literal failed (%s): %s", name, out)
            await asyncio.sleep(settle)
            continue
        await asyncio.sleep(settle)
        await _run("send-keys", "-t", f"={name}:0.0", "Enter")
        await asyncio.sleep(settle)
        pane = await capture_pane(name, lines=40)
        # success = the line is no longer sitting unsubmitted in the input box
        if line[:40] in pane and looks_idle(pane):
            # still in the input box, unsubmitted? press Enter once more
            await _run("send-keys", "-t", f"={name}:0.0", "Enter")
            await asyncio.sleep(settle)
            pane = await capture_pane(name, lines=40)
        if line[:40] in pane or not looks_idle(pane):
            return True
        logger.warning("inject attempt %d/%d unverified for %s", attempt, retries, name)
    return False
