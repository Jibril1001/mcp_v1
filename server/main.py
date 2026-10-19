import logging
import sys

from mcp.server import MCPServer

logging.basicConfig(level=logging.INFO, stream=sys.stderr)

mcp = MCPServer("Incident Detective")


@mcp.tool()
def ping(message: str = "hello") -> str:
    """Health check. Returns the message back so you can confirm the server is alive."""
    return f"pong: {message}"


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
