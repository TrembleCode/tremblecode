"""In-memory agent state shared across relay components."""

import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class AgentRuntimeState:
    name: str
    kind: str = "dev"
    model: str = "sonnet"
    effort: str = "medium"
    workspace: str = ""
    tmux_session: str = ""
    identity_path: str = ""
    # idle | busy | unknown — driven by hooks
    activity: str = "unknown"
    last_hook_at: float = 0.0
    session_started: bool = False
    first_prompt_sent: bool = False
    # consumers wait on this; set by the stop hook to re-drive pending messages
    wake: asyncio.Event = field(default_factory=asyncio.Event)

    def mark(self, activity: str) -> None:
        self.activity = activity
        self.last_hook_at = time.time()
        if activity == "idle":
            self.wake.set()

    @property
    def is_idle(self) -> bool:
        return self.activity == "idle"


class RelayState:
    def __init__(self) -> None:
        self.agents: dict[str, AgentRuntimeState] = {}
        self.project_status: str = ""
        self.extra_env: dict[str, str] = {}

    def get(self, name: str) -> AgentRuntimeState | None:
        return self.agents.get(name)

    def ensure(self, name: str) -> AgentRuntimeState:
        if name not in self.agents:
            self.agents[name] = AgentRuntimeState(name=name)
        return self.agents[name]


state = RelayState()
