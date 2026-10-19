# Inspector evidence

Captured with the MCP Inspector CLI:

```
npx @modelcontextprotocol/inspector --cli .venv/Scripts/python.exe -m server.main --method <method>
```

- `inspector-tools-list.txt` — `tools/list`
- `inspector-call-spike.txt` — `tools/call logs_query_errors service=checkout` (the spike)
- `inspector-call-error.txt` — `tools/call` with an invalid service (error result)
- `inspector-resource-schema.txt` — `resources/read db://schema`

For human-visible screenshots of the Inspector UI, run
`npx @modelcontextprotocol/inspector .venv/Scripts/python.exe -m server.main`
and save PNGs into this folder.
