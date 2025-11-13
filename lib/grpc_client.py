"""gRPC client for the Bridge service."""
import grpc
from typing import Optional
from proto import bridge_pb2, bridge_pb2_grpc


class BridgeClient:
    """Client for communicating with the Bridge gRPC service."""

    def __init__(self, host: str = "localhost", port: int = 50051):
        """
        Initialize the Bridge client.

        Args:
            host: The hostname of the Bridge service
            port: The port of the Bridge service
        """
        self.address = f"{host}:{port}"
        self.channel: Optional[grpc.Channel] = None
        self.stub: Optional[bridge_pb2_grpc.BridgeServiceStub] = None

    def connect(self):
        """Establish connection to the Bridge service."""
        self.channel = grpc.insecure_channel(self.address)
        self.stub = bridge_pb2_grpc.BridgeServiceStub(self.channel)

    def close(self):
        """Close the connection to the Bridge service."""
        if self.channel:
            self.channel.close()

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def start_agent(self, prompt: str) -> tuple[str, str, str]:
        """
        Start an agent with the given prompt.

        Args:
            prompt: The prompt to provide to the agent

        Returns:
            Tuple of (agent_id, session_id, exit_result)
        """
        if not self.stub:
            raise RuntimeError("Client not connected. Call connect() first.")

        request = bridge_pb2.S
        response = self.stub.StartAgent(request)

        return response.agent_id, response.session_id, response.exit_result


# Example usage
if __name__ == "__main__":
    # Using context manager
    with BridgeClient(host="localhost", port=50051) as client:
        agent_id, session_id, exit_result = client.start_agent(
            prompt="Execute the analysis workflow"
        )
        print(f"Agent started:")
        print(f"  Agent ID: {agent_id}")
        print(f"  Session ID: {session_id}")
        print(f"  Exit Result: {exit_result}")