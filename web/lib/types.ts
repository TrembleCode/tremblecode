export interface AgentTemplate {
  id: string;
  role_key: string;
  display_name: string;
  description: string;
  system_prompt_md: string;
  model: string;
  default_count: number;
  color: string;
  kind: "lead" | "dev" | "qa";
  is_builtin: boolean;
}

export interface ProjectAgent {
  id: string;
  name: string;
  role_key: string;
  kind: string;
  model: string;
  state: string;
  current_task_id: string | null;
  workspace_path: string | null;
  last_activity_at: string | null;
}

export interface Project {
  id: string;
  name: string;
  slug: string;
  description: string;
  status: string;
  prd_md: string;
  host_dir: string | null;
  container_id: string | null;
  image_variant: string;
  port_base: number | null;
  config_json: {
    roster?: { role_key: string; count: number; model?: string | null }[];
    ports?: Record<string, number>;
  };
  created_at: string;
  updated_at: string;
}

export interface ProjectDetail extends Project {
  agents: ProjectAgent[];
}

export interface Task {
  id: string;
  task_key: string;
  title: string;
  description_md: string;
  role_key: string;
  status: string;
  assignee_agent_id: string | null;
  branch: string | null;
  dependencies: string[];
  estimate_h: number | null;
  milestone_id: string | null;
  blocked_reason: string | null;
}

export interface Message {
  id: string;
  project_id: string;
  from_participant: string;
  to_participant: string;
  thread_id: string | null;
  subject: string;
  body_md: string;
  priority: string;
  ack_requested: boolean;
  status: "queued" | "notified" | "delivered" | "acked" | "expired";
  task_key: string | null;
  created_at: string;
  acked_at: string | null;
  ack_note: string;
}

export interface Escalation {
  id: string;
  project_id: string;
  agent_name: string;
  type: string;
  topic: string;
  body_md: string;
  options: string[];
  blocking: boolean;
  status: "open" | "answered" | "dismissed";
  response_md: string | null;
  created_at: string;
}

export interface DiscussionMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface UserStory {
  id: string;
  story_key: string;
  role: string;
  action: string;
  benefit: string;
  acceptance_md: string;
}

export interface Milestone {
  id: string;
  key: string;
  name: string;
  description: string;
  sort: number;
  status: "pending" | "active" | "gate_open" | "approved";
}

export interface Plan {
  id: string;
  version: number;
  status: "draft" | "approved" | "rejected";
  specs_md: string;
  risks_md: string;
  user_stories: UserStory[];
  milestones: Milestone[];
  tasks: Task[];
}

export interface AgentCost {
  agent: string;
  cost_usd: number;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
}

export interface CostSummary {
  total_usd: number;
  total_tokens: number;
  by_agent: AgentCost[];
  by_day: { day: string; cost_usd: number }[];
  by_model: { model: string; cost_usd: number }[];
}

export interface ServiceInfo {
  id: string;
  name: string;
  agent_name: string;
  container_port: number;
  host_port: number;
  status: string;
}

export interface McpSuggestion {
  id: string;
  name: string;
  reason: string;
  env_keys: string[];
  status: "proposed" | "approved" | "rejected" | "installed";
}

export interface WikiNode {
  path: string;
  name: string;
  type: "file" | "dir";
  children?: WikiNode[];
}

export interface WikiTree {
  tree: WikiNode[];
}
