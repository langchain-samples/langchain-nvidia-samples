"""OpenShell Deep Agent.

General-purpose coding and analysis agent using OpenShell as the on-prem
sandbox provider. Executes code inside a policy-governed OpenShell sandbox
with local filesystem persistence for memory and skills.

Quick start:
  1. Start or select a gateway: openshell gateway start
  2. (Optional) Pre-create a sandbox: openshell sandbox create --name my-sandbox --keep
     Then set: export OPENSHELL_SANDBOX_NAME=my-sandbox
  3. Run: deepagents run src/agent.py:agent
"""

import os
from datetime import datetime

from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model

from src.backend import create_backend
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from src.prompts import AGENT_INSTRUCTIONS

current_date = datetime.now().strftime("%Y-%m-%d")

model = ChatNVIDIA(
    model="nvidia/nemotron-3-super-120b-a12b",
    api_key=os.getenv("NVIDIA_API_KEY"),
    temperature=0.1,
    max_tokens=16384,
)

# model = init_chat_model(
#    os.environ.get("AGENT_MODEL", "anthropic:claude-sonnet-4-6")
# )

agent = create_deep_agent(
    model=model,
    system_prompt=AGENT_INSTRUCTIONS.format(date=current_date),
    memory=["/memory/AGENTS.md"],
    backend=create_backend,
)
