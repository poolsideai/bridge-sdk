from temporalio.client import Client
from pydantic import BaseModel

class RunDetail(BaseModel):
    agent_id: str
    session_id: str

async def call_agent(prompt: str, agent_id: str) -> tuple[str, RunDetail]:
    # RPC call to agent runtime handler w/ step_id
    pass


