# Agent Memory

## Sandbox Environment

This agent executes code in an OpenShell sandbox — an isolated, policy-governed
Linux environment provisioned on-prem. The sandbox provides:
- Python, bash, and common Linux tools
- A writable /sandbox/ directory for scripts and outputs.
- Policy-governed network access (controlled by the active sandbox policy)
- SSH-based file transfer for uploads and downloads

## Workflow

1. Write scripts to /sandbox/<name>.py using write_file
2. Execute with the execute tool: `execute("python /sandbox/<name>.py")`
3. Check output; fix errors and retry if needed (max 2 retries per error)
4. Summarize results for the user

## Key Patterns

- Always create output directories: `os.makedirs("/sandbox", exist_ok=True)`
- Print only summaries to stdout; write full results to /sandbox/results.txt
- Use read_file to retrieve file contents and display to the user
- When network access is denied, check the sandbox policy with: `openshell policy get <name>`

## Self-Improvement

Update this file when you discover reliable patterns or encounter recurring issues
that would be useful to remember across sessions.
