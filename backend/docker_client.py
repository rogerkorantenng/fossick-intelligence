import asyncio
import json
import uuid
from pathlib import Path
from backend.config import settings


class DockerMCPClient:
    """Calls MCP server tools running inside Docker container."""

    def __init__(self, image_name: str, case_data_path: str):
        self.image_name = image_name
        self.case_data_path = str(Path(case_data_path).resolve())

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        call_payload = json.dumps({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
            "id": str(uuid.uuid4()),
        })

        mcp_server_path = str(Path(__file__).parent.parent / "mcp_server")

        cmd = [
            "docker", "run", "--rm", "-i",
            "-v", f"{self.case_data_path}:/case_data:ro",
            "-v", f"{mcp_server_path}:/fossick/mcp_server:ro",
            "-e", "PYTHONPATH=/fossick",
            self.image_name,
            "python3", "-m", "mcp_server.server"
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            init_msg = json.dumps({
                "jsonrpc": "2.0", "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                           "clientInfo": {"name": "fossick", "version": "1.0.0"}},
                "id": "init"
            }) + "\n"

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=(init_msg + call_payload + "\n").encode()),
                timeout=settings.mcp_timeout
            )

            lines = [l.strip() for l in stdout.decode().split("\n") if l.strip()]
            for line in reversed(lines):
                try:
                    response = json.loads(line)
                    if "result" in response:
                        content = response["result"].get("content", [])
                        if content:
                            return json.loads(content[0].get("text", "{}"))
                except Exception:
                    continue

            return {"error": f"No valid MCP response. stderr: {stderr.decode()[:300]}"}

        except asyncio.TimeoutError:
            return {"error": f"Tool {tool_name} timed out after {settings.mcp_timeout}s"}
        except Exception as e:
            return {"error": str(e)}


def get_docker_client() -> DockerMCPClient:
    return DockerMCPClient(
        image_name=settings.docker_image,
        case_data_path=settings.case_data_path,
    )
