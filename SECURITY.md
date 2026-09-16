# Security

## What this software does

Workroom runs shell commands, edits files and (once the perception layer
lands) reads your screen and clicks things, under the direction of a language
model. That is the point of it, and it is also the risk.

The protections are in `agent/actuation/guard.py`:

- **Denied outright**, whatever the model asks: filesystem formatting, raw
  writes to disk devices, recursive deletes aimed at `/` or `$HOME`, disabling
  SIP or Gatekeeper, dumping the keychain.
- **Stops and asks you**: `sudo`, recursive deletes, force pushes,
  `git reset --hard`, piping a download into a shell, killing processes,
  uninstalling software, overwriting a file in place, AppleScript.
- **Never touched**: System Settings, Keychain Access, 1Password, and any URL
  matching a banking or sign-in pattern.

`--dry-run` shows what it would do without doing it. `--yes` skips the
confirmations but *not* the denials.

None of this makes an autonomous agent safe to leave unattended with
credentials on the machine. Treat it as you would a new colleague with your
shell open.

## Reporting a vulnerability

Open a private security advisory through GitHub's "Report a vulnerability"
button on the Security tab, or contact the maintainer directly. Please do not
open a public issue for a way to get past the guard rails.

Describe the class of problem and how to reproduce it. A working
privilege-escalation chain is not needed and is better left out of the report.

## Supply chain

Model weights come from Hugging Face over HTTPS and are cached in
`~/.cache/huggingface`. Workroom does not verify their signatures — it trusts
`huggingface_hub` for that. The repo ids it will fetch are fixed in
`agent/config.py` and are not model-controlled.
