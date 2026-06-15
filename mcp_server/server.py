import asyncio
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
from mcp_server.tools.timeline import get_timeline
from mcp_server.tools.memory import analyze_memory
from mcp_server.tools.persistence import get_persistence
from mcp_server.tools.integrity import compute_sha256, EvidenceSpoliationError

app = Server("fossick-sift")


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(name="get_timeline",
                   description="Extract filesystem and artifact timeline from disk image using Plaso. Returns structured JSON.",
                   inputSchema={"type": "object", "properties": {
                       "image_path": {"type": "string"},
                       "earliest": {"type": "string"},
                       "latest": {"type": "string"},
                       "artifact_types": {"type": "array", "items": {"type": "string"}},
                   }, "required": ["image_path"]}),
        types.Tool(name="analyze_memory",
                   description="Analyze memory image with Volatility 3. Returns structured process list, network, injections.",
                   inputSchema={"type": "object", "properties": {
                       "image_path": {"type": "string"},
                       "plugins": {"type": "array", "items": {"type": "string"}},
                   }, "required": ["image_path"]}),
        types.Tool(name="get_persistence",
                   description="Extract persistence mechanisms: AmCache, Prefetch, Registry. Returns structured indicators.",
                   inputSchema={"type": "object", "properties": {
                       "image_path": {"type": "string"},
                   }, "required": ["image_path"]}),
        types.Tool(name="verify_file_hash",
                   description="Verify SHA-256 hash of forensic image for evidence integrity.",
                   inputSchema={"type": "object", "properties": {
                       "image_path": {"type": "string"},
                       "expected_sha256": {"type": "string"},
                   }, "required": ["image_path"]}),
        types.Tool(name="verify_write_block",
                   description="Canary test: attempt to write to evidence image and confirm OS-level :ro mount blocks it.",
                   inputSchema={"type": "object", "properties": {
                       "image_path": {"type": "string"},
                   }, "required": ["image_path"]}),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        if name == "get_timeline":
            result = await get_timeline(
                image_path=arguments["image_path"],
                earliest=arguments.get("earliest", ""),
                latest=arguments.get("latest", ""),
                artifact_types=arguments.get("artifact_types"),
            )
        elif name == "analyze_memory":
            result = await analyze_memory(
                image_path=arguments["image_path"],
                plugins=arguments.get("plugins"),
            )
        elif name == "get_persistence":
            result = await get_persistence(image_path=arguments["image_path"])
        elif name == "verify_file_hash":
            current = compute_sha256(arguments["image_path"])
            matches = current == arguments.get("expected_sha256", "")
            return [types.TextContent(type="text", text=json.dumps(
                {"matches": matches, "actual": current, "expected": arguments.get("expected_sha256", "")}))]
        elif name == "verify_write_block":
            import os
            canary_path = arguments["image_path"] + ".canary"
            try:
                with open(canary_path, "w") as f:
                    f.write("canary")
                os.remove(canary_path)
                return [types.TextContent(type="text", text=json.dumps(
                    {"write_blocked": False, "error_message": "CRITICAL: Write succeeded — evidence not protected"}))]
            except (OSError, PermissionError) as e:
                return [types.TextContent(type="text", text=json.dumps(
                    {"write_blocked": True, "error_message": str(e)}))]
        else:
            return [types.TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
        return [types.TextContent(type="text", text=json.dumps(result.model_dump(), default=str))]
    except EvidenceSpoliationError as e:
        return [types.TextContent(type="text", text=json.dumps({"error": "EVIDENCE_SPOLIATION", "detail": str(e)}))]
    except Exception as e:
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
