"""Unit tests for relay consumer delivery: silent acks, coalesced message
notifications, control-entry barriers. Redis and tmux are faked."""

import pytest

from tremblecode_runtime.relay import consumers, tmux
from tremblecode_runtime.relay.state import AgentRuntimeState, state


class FakeRedis:
    def __init__(self):
        self.acked: list[str] = []

    async def xack(self, stream, group, entry_id):
        self.acked.append(entry_id)


def _msg(msg_id: str, frm: str = "lead", to: str = "dev") -> dict:
    return {"type": "message", "to": to, "from": frm, "msg_id": msg_id}


@pytest.fixture
def dev_agent(monkeypatch):
    rt = AgentRuntimeState(name="dev", tmux_session="tc-dev")
    rt.mark("idle")
    state.agents.clear()
    state.agents["dev"] = rt

    sent: list[str] = []

    async def fake_send_line(session, line):
        sent.append(line)
        return True

    async def fake_capture(session):
        return "❯ "

    monkeypatch.setattr(tmux, "send_line", fake_send_line)
    monkeypatch.setattr(tmux, "capture_pane", fake_capture)
    monkeypatch.setattr(tmux, "looks_idle", lambda pane: True)

    notified: list[list[str]] = []

    async def fake_mark_notified(client, msg_ids):
        notified.append(msg_ids)

    monkeypatch.setattr(consumers, "_mark_notified", fake_mark_notified)
    yield rt, sent, notified
    state.agents.clear()


def test_solo_ack_receipt_is_silent():
    assert consumers._notify_line({"type": "ack_receipt", "msg_id": "abc"}) is None
    line = consumers._notify_line(
        {"type": "ack_receipt", "msg_id": "abc", "acked_by": "qa-1", "note": "on it"}
    )
    assert line and "on it" in line


def test_coalesced_line_dedups_senders():
    line = consumers._coalesced_line([_msg("a"), _msg("b", frm="qa-1"), _msg("c")])
    assert "3 new messages" in line
    assert line.count("lead") == 1 and "qa-1" in line
    # single entry falls back to the standard per-message line
    single = consumers._coalesced_line([_msg("a")])
    assert "New message from lead" in single


async def test_drain_coalesces_messages_around_barriers(dev_agent):
    rt, sent, notified = dev_agent
    r = FakeRedis()
    entries = [
        ("1", _msg("m1")),
        ("2", _msg("m2", frm="qa-1")),
        ("3", {"type": "clear", "to": "dev", "reason": "t"}),
        ("4", _msg("m4")),
    ]
    assert await consumers._drain_entries(r, None, "dev", "cg:dev", entries)
    # one coalesced line for m1+m2, the /clear barrier, then m4 alone
    assert len(sent) == 3
    assert "2 new messages" in sent[0] and "lead, qa-1" in sent[0]
    assert sent[1] == "/clear"
    assert "New message from lead" in sent[2]
    assert r.acked == ["1", "2", "3", "4"]
    assert notified == [["m1", "m2"], ["m4"]]


async def test_drain_stops_on_failed_barrier(dev_agent, monkeypatch):
    rt, sent, notified = dev_agent

    async def flaky_send_line(session, line):
        if line == "/clear":
            return False
        sent.append(line)
        return True

    monkeypatch.setattr(tmux, "send_line", flaky_send_line)
    r = FakeRedis()
    entries = [
        ("1", _msg("m1")),
        ("2", {"type": "clear", "to": "dev", "reason": "t"}),
        ("3", _msg("m3")),
    ]
    assert not await consumers._drain_entries(r, None, "dev", "cg:dev", entries)
    # m1 flushed and acked before the barrier; the failed clear and the
    # trailing message stay pending for the next idle re-drive
    assert r.acked == ["1"]
    assert notified == [["m1"]]
    assert all("m3" not in line for line in sent)


async def test_drain_acks_foreign_and_invalid_entries(dev_agent):
    rt, sent, notified = dev_agent
    r = FakeRedis()
    entries = [
        ("1", _msg("m1", to="other")),  # not addressed to us
        ("2", {"type": "set_effort", "to": "dev", "level": "bogus"}),
    ]
    assert await consumers._drain_entries(r, None, "dev", "cg:dev", entries)
    assert r.acked == ["1", "2"]
    assert sent == []


async def test_set_effort_and_set_model_inject_slash_commands(dev_agent):
    rt, sent, notified = dev_agent
    r = FakeRedis()
    entries = [
        ("1", {"type": "set_effort", "to": "dev", "level": "medium"}),
        ("2", {"type": "set_model", "to": "dev", "model": "sonnet"}),
    ]
    assert await consumers._drain_entries(r, None, "dev", "cg:dev", entries)
    assert sent == ["/effort medium", "/model sonnet"]
    assert r.acked == ["1", "2"]
