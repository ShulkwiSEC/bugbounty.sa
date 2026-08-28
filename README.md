# bugbounty-sa-mcp

Read-only MCP server for [bugbounty.sa](https://bugbounty.sa). Provides 15 tools and 1 resource for querying programs, reports, finances, researchers, companies, and notifications. **No mutations** — report submissions stay manual.

## Setup

```bash
export ACCOUNT_TOKEN="your-bugbounty-sa-token"
```

Install:

```bash
uv tool install .
# or
pip install -e .
```

Run (stdio):

```bash
bugbounty-sa-mcp
```

## MCP Client Config

```json
{
  "mcpServers": {
    "bugbounty-sa": {
      "command": "bugbounty-sa-mcp",
      "env": { "ACCOUNT_TOKEN": "<your-token>" }
    }
  }
}
```

Or with `uv run`:

```json
{
  "mcpServers": {
    "bugbounty-sa": {
      "command": "uv",
      "args": ["run", "bugbounty-sa-mcp"],
      "cwd": "/path/to/bugbounty-sa-mcp",
      "env": { "ACCOUNT_TOKEN": "<your-token>" }
    }
  }
}
```

## Safety

This server is **strictly read-only**. All endpoints are `GET` requests. No `POST`, `PUT`, `PATCH`, or `DELETE` calls are made. Report submissions, profile updates, and any other mutations remain manual actions on the bugbounty.sa web interface.
