# Local Computer-Use Agent — 24 GB base-M3 Mac, single-model design (v2)

Decisions locked (2026-09-15): base M3 · any macOS app + Chrome · terminal REPL · confirm-destructive autonomy · lazy vision · markdown memory · uv + Python 3.12 · nothing downloaded yet.

---

## PART A — Original spec (kept for reference, superseded by Part B)

<details><summary>Click to expand v1 spec</summary>

Model Stack & Memory Allocation
All three models stay resident in unified memory with zero swapping:

RoleModelQuant / FormatApprox MemoryNotesPrimary ReasonerQwen3-8B4-bit MLX~5.0 GBMain agent brain – planning, tool calling, decisionsVision Sub-AgentQwen3-VL-8B-Instruct (or strongest 7B/8B available)4-bit MLX~4.0–4.5 GBOnly woken for screen inspectionMemory CompressorQwen3-1.7B or Qwen2.5-1.5B4-bit MLX~1.2–1.5 GBSummarization / long-term memory compressionmacOS + buffers——~5.0 GBSystem + MLX overheadTotal used——~15–16 GBComfortable headroom on 24 GB
2. Controller Architecture (MLX)
Goal: Route text reasoning and vision tasks to isolated local models via tool dispatch.

Runtime: MLX (mlx-lm / Rapid-MLX / LM Studio MLX engine recommended for best tool-calling reliability and speed).
Keep all three models loaded simultaneously.
Primary model (Qwen3-8B) is the only one that talks to the user and decides when vision is needed.

Vision Tool Interface

Expose a single tool to the 8B model:
XML<tool_call name="inspect_screen" instruction="find the submit button and click it">
The 8B model decides when visual verification is required, emits the tool call, and pauses.
Execution Pipeline (Python + MLX)

Controller intercepts inspect_screen.
Takes macOS screenshot + generates Set-of-Mark (SoM) bounding boxes.
Dispatches annotated image + instruction to the local Vision model (Qwen3-VL).
Vision model returns strict JSON only, e.g.
{"target_id": 14, "action": "click"}
Controller executes the action via macOS Accessibility APIs.
Returns result to the 8B model as <tool_result>.
8B model resumes generation at full speed.

3. Latency & Performance Expectations (M3 + MLX)
Standard operations (planning, code, terminal, pure text tools):

45–70 tok/s typical (often 50–65 tok/s in practice on M3)
Vision model stays completely idle → zero overhead

Vision operations (screen inspection / clicks):

Triggered only when the 8B decides it needs visual input
End-to-end latency: ~1.5–2.5 seconds (screenshot + SoM + VLM inference)
After the tool result returns, text generation immediately resumes at full 45–70 tok/s

4. Recommended Exact Models (download these)

Primary: mlx-community/Qwen3-8B-4bit (or the highest-quality 4-bit MLX quant available)
Vision: mlx-community/Qwen3-VL-8B-Instruct-4bit (preferred) or strongest available Qwen3-VL / Qwen2.5-VL 7B–8B 4-bit
Compressor: mlx-community/Qwen3-1.7B-4bit or Qwen2.5-1.5B-Instruct-4bit

This is the cleanest, highest-performing practical stack for a fully local multi-model computer-use agent on a 24 GB M3 Mac right now.

</details>

---

## PART B — What changed and why

| v1 | v2 | Reason |
|---|---|---|
| 3 models: Qwen3-8B text + Qwen3-VL-8B vision + 1.7B compressor | **1 brain: `mlx-community/Qwen3.5-9B-MLX-4bit`** (native VLM) + small compressor | Qwen3.5-9B does text, tools, and screen vision in one model. Drops ~5 GB, drops the cross-model hand-off, drops a whole failure surface. |
| Vision as a separate sub-agent tool | Vision = **an image in the brain's own context** | No JSON-relay between models. Brain sees the SoM screenshot directly and picks the target id itself. |
| 45–70 tok/s | **~16 tok/s measured** (base M3) | Spec assumed M3 Max. The v2 estimate of 22–28 was also optimistic: see the M0 bench table below. |
| 15–16 GB "comfortable" | **~9–11 GB steady, ~13 GB peak** | Single model + KV + compressor + buffers. Real headroom now. |
| Vision latency 1.5–2.5 s | **2–4 s** (prefill of 1.5–2.5k image tokens on base M3) | Mitigated by AX-first routing so most actions never need a screenshot. |
| Runtime: mlx-lm + mlx-vlm | **mlx-vlm only** (handles text-only calls too) | One loader, one KV cache, one process. |

### Added 2026-09-15 — the unified-memory ceiling

Onboarding asks once how much unified memory Workroom may hold, because the honest
answer differs per user and the wrong default ruins the machine either way:

| preset | share | on this 24 GB M3 | for |
|---|---|---|---|
| Alongside your work | 50% | 12 GB, 16k ctx | the Mac you are using |
| All yours | 75% | 18 GB, 32k ctx | the Mac you walk away from |

Two layers, and they are not the same thing. `mlx.set_memory_limit` /
`set_cache_limit` / `set_wired_limit` hold *this process* to the ceiling and
never need a password. `iogpu.wired_limit_mb` is system-wide and does.

**Measured:** Metal reports `max_recommended_working_set_size` of **17.8 GB**
on this machine, so "Alongside your work" needs no sysctl at all and only
"All yours" prompts for admin. Shares are fractions rather than absolutes so
the same two presets work on a 16 GB Air and a 128 GB Studio.

### Why not the other candidates
- **Nemotron-3-Nano-30B-A3B / Qwen3.6-35B-A3B**: MoE decode is fast but **17–22 GB weights** must be resident. No room. Out.
- **Qwythos-9B (GGUF)**: Qwen3.5-9B finetune, always-on `<think>`, llama.cpp only, unverified benchmark claims. Out.
- **ZDTaichu5.0-9B**: best agent benchmarks in class but **no MLX/GGUF**, custom vLLM fork. Revisit if ported.
- **Mistral Small 3.1 24B Q4**: 14 GB, ~6–8 tok/s on base M3. Out.
- **Qwen3.5-27B-4bit**: 17 GB, ~10 tok/s, no KV room. Out.

### Note on forking Claude Code
`github.com/anthropics/claude-code` is the issue tracker, docs, and plugin/skill examples — **the CLI source is not published**. Nothing to fork. What *is* worth stealing from it: the tool schemas (Bash/Read/Edit/Glob/Grep shapes), the `<tool_result>` loop discipline, and the `CLAUDE.md`-style project memory file. All three are adopted below.

---

## PART C — Memory budget (base M3, 24 GB)

| Item | Memory | Notes |
|---|---|---|
| Qwen3.5-9B 4-bit weights | ~5.6 GB | incl. vision tower |
| KV cache @ 16k ctx | ~1.5–2.5 GB | hybrid Gated-DeltaNet layers keep this small vs pure-attention |
| Screenshot image tokens (per call, transient) | +0.3–0.5 GB | 1280 px long edge → ~1.5–2.5k tokens |
| Compressor `mlx-community/Qwen3.5-2B-MLX-4bit` | ~1.5 GB | resident |
| macOS + Chrome + terminal | 6–8 GB | the real variable |
| **Steady state** | **~9–11 GB** | |
| **Peak (vision call + compressor running)** | **~13 GB** | |
| Headroom | ~10 GB | room to go 6-bit (+2 GB) or 32k ctx later |

Set once per boot: `sudo sysctl iogpu.wired_limit_mb=18432`.

---

## PART D — Architecture

```
┌──────────────────────────────────────────────────────────┐
│ REPL (rich)                                              │
└───────────────┬──────────────────────────────────────────┘
                ▼
┌──────────────────────────────────────────────────────────┐
│ loop.py — stream → parse <tool_call> → dispatch → inject │
│           <tool_result> → resume (prompt-cache reuse)    │
└───┬───────────────┬──────────────────┬───────────────────┘
    ▼               ▼                  ▼
 tools/shell   tools/files      tools/screen.inspect
 tools/chrome  tools/memory        │
                                   ▼
                     perception: capture → ax_tree → (AX hit? act) 
                                   │ miss
                                   ▼
                     som.draw → image into brain ctx → brain emits
                     {"target_id": n, "action": ...}
                                   ▼
                     actuation/actions via CGEvent/AX  ← guard.py
    
 compressor (Qwen3.5-2B) — async, off hot path:
   • transcript > 60% ctx → summarize oldest half
   • tool output > 4k chars → summarize before injection
   • session end → append memory/YYYY-MM-DD.md
```

**Brain mode**: `/no_think` default for tool dispatch. `/think` allowed only on an explicit `plan` step or when the brain emits `{"action":"none","confidence":<0.5}` twice.

**Tool schema** (Qwen3.5 native): `<tool_call><function=NAME><parameter=K>V</parameter></function></tool_call>`. Parser accepts this plus a tolerant JSON fallback.

**Tools exposed to the brain**
- `bash(cmd, timeout=60)` — output capped, long output → compressor
- `read_file(path)`, `write_file(path, content)`, `edit_file(path, old, new)`, `glob(pattern)`, `grep(pattern, path)`
- `inspect_screen(instruction, app=None)` — returns either `{"acted": true, "via": "ax"}` or the SoM image + element list for the brain to choose from
- `act(target_id, action, text=None)` — brain calls this after seeing the SoM image
- `chrome(op, ...)` — AppleScript/JS bridge for DOM read + click when the frontmost app is Chrome (cheaper than screenshots)
- `remember(note)` — append to today's memory file

**Routing rule in `inspect_screen`**: AX exact label → AX fuzzy ≥0.85 → Chrome DOM (if Chrome) → SoM screenshot to brain → raw-coordinate ask (last resort).

---

## PART E — Repo layout

```
localLLM_lab/
  PLAN.md
  AGENT.md                    # project memory the brain reads at boot (Claude-Code-style CLAUDE.md)
  pyproject.toml              # uv; mlx-vlm, mlx-lm, pyobjc-framework-Quartz,
                              # pyobjc-framework-ApplicationServices, pillow, pydantic, rich, rapidfuzz
  agent/
    config.py
    brain.py                  # Qwen3.5-9B via mlx-vlm: text + image calls, /no_think, prompt cache, tool parser
    compressor.py             # Qwen3.5-2B; async summarize(); memory writer
    loop.py                   # agent loop
    cli.py                    # REPL; flags: --think --dry-run --ctx 16384
    tools/
      registry.py             # schemas → chat-template tools param
      shell.py  files.py  chrome.py  screen.py  memory.py
    perception/
      capture.py              # screencapture → PIL → ≤1280px long edge, Retina scale factor
      ax_tree.py              # AXUIElement walk → [Element(id, role, label, frame)]
      som.py                  # numbered overlays, id→frame map, debug PNG
    actuation/
      actions.py              # click/type/key/scroll via CGEvent + AXPress
      guard.py                # deny-list, dry-run, confirm-destructive, ⌘⇧Esc kill
  memory/                     # YYYY-MM-DD.md written by compressor
  scripts/
    pull_models.py            # hf download of the 2 repos
    bench_tps.py              # tok/s @ 1k / 8k / 16k ctx, /think vs /no_think
    bench_vision.py           # inspect_screen end-to-end latency
  tests/
    test_tool_parser.py  test_ax_tree.py  test_som_mapping.py  test_guard.py
```

---

## PART F — Milestones

**M0 — Environment — DONE 2026-09-15**

Verified rather than assumed:
- `mlx-vlm` **0.7.1 ships a `qwen3_5` model module**, so the Part H
  "no hybrid-attention support" risk is closed. No `mlx-lm` fallback needed
  for the brain.
- Both repo ids in this plan exist and are the most-downloaded variants:
  `Qwen3.5-9B-MLX-4bit` (26k pulls) and `Qwen3.5-2B-MLX-4bit`.
- The 9B really is a VLM: `Qwen3_5ForConditionalGeneration`, a `vision_config`
  block, `image-text-to-text` pipeline. The single-model premise holds.
- **Real download is 5.98 GB, not 5.6** — Part C's weight line was optimistic.
- Metal offers a 17.8 GB working set here (see the ceiling section above).

**Bench, base M3, 24 GB, 12 GB ceiling, `/no_think`** (`scripts/bench_tps.py`):

| prompt | tok/s | peak GB |
|---|---|---|
| 1 000 | 16.3 | 6.54 |
| 8 000 | 16.8 | 7.70 |
| 16 000 | 15.7 | 8.48 |

Two things fall out of this:
- **Speed is flat across context.** The hybrid Gated-DeltaNet layers do what
  Part B hoped: no quadratic falloff from 1k to 16k. 32k context is therefore
  cheap in time, and only costs memory.
- **Decode is bandwidth-bound, not capacity-bound.** Raising the memory
  ceiling does *not* raise tok/s. The two onboarding presets were originally
  written as ~18 vs ~24 tok/s; that was wrong and is now corrected to "same
  speed, twice the context".

Peak memory is well under Part C's ~13 GB estimate: 8.5 GB at 16k context.
Model load from a warm cache is ~7 s.

**M0 — original checklist**
- `uv init --python 3.12`; add `mlx-vlm mlx-lm pyobjc-framework-Quartz pyobjc-framework-ApplicationServices pillow pydantic rich rapidfuzz`.
- `pull_models.py`: `mlx-community/Qwen3.5-9B-MLX-4bit`, `mlx-community/Qwen3.5-2B-MLX-4bit` (fallback `Qwen3.5-4B` if 2B quant missing).
- Smoke test: text gen, image gen (a screenshot), tool-call emission with the chat template's `tools=` param.
- `bench_tps.py` → **record real tok/s in this file**, replace the 22–28 estimate.
- Grant Accessibility + Screen Recording to the terminal app.
- Exit: both models load; tok/s table committed.

**M1 — Text-only agent loop — DONE 2026-09-15**

End-to-end on the real model: "how many .py files are in agent/" and "read
pyproject.toml and tell me the Python version" both answered correctly, with
tool calls, in one pass.

One real defect found and fixed, and it is the Part H "4-bit tool-call
malformation" risk showing up exactly as predicted: the quant writes every
parameter value on its own line, so `read_file` received `"\npyproject.toml\n"`
and failed twice before the model fell back to `bash cat`. `_unwrap()` in
`agent/toolcall.py` now strips one newline from each end. Same task afterwards:
**1 tool call instead of 4, 23.6 s instead of 111.8 s.**

Not a 6-bit case: the calls themselves were well formed, only padded.

**M1 — original checklist**
- `brain.py`: chat template with tools, `/no_think`, streaming, stop on `</tool_call>`, prompt-cache reuse across turns.
- Tools: `bash`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`.
- `loop.py` + `cli.py` REPL. `AGENT.md` loaded into system prompt.
- Exit: "find the 5 largest files in ~/Downloads and write a report" end-to-end.

**M2 — Compressor + memory (½ day)**
- Token counter; at 60% ctx async-compress oldest half to `{goals, done, open_issues, facts}`.
- Tool-output cap 4k chars → compressor.
- `memory.py`: `remember()` + session-end summary → `memory/YYYY-MM-DD.md`; last 3 files injected at boot.
- Exit: 50-turn session stays under ctx; next-day session recalls yesterday's facts.

**M3 — Perception without vision (1 day)**
- `capture.py`, `ax_tree.py` (interactive roles only, screen-coord frames, Retina 2× handled), `som.py`.
- `chrome.py`: AppleScript `execute javascript` for DOM query/click; falls back to AX when disabled.
- `inspect_screen` v0: AX/Chrome only; on miss returns element list as text.
- Exit: "click Save in TextEdit" and "click the first search result in Chrome" with zero screenshots.

**M4 — Vision path (1 day)**
- `inspect_screen` on AX miss: SoM PNG → brain context as image + instruction → brain calls `act(target_id, ...)`.
- Strict output contract; one retry on parse failure; `confidence<0.5` → ask user.
- `bench_vision.py`; record latency.
- Exit: works in an Electron app with sparse AX (Slack/Discord).

**M5 — Guard rails (½ day)**
- Deny-list bundle IDs (System Settings, 1Password, banking URLs via Chrome URL read).
- Destructive shell (`rm -rf`, `sudo`, `git push --force`, `> file` on tracked files) → y/n.
- `--dry-run` draws target box, no click. `⌘⇧Esc` event tap → halt flag checked per token.
- Exit: refuses System Settings; hotkey halts mid-stream.

**M6 — Polish → v1 tag (½ day)**
- REPL: collapsed tool calls, SoM debug image path, tok/s in footer.
- Exit: v1.

**Total: ~5 days.**

---

## PART G — Config defaults (edit after M0 bench)

```python
BRAIN       = "mlx-community/Qwen3.5-9B-MLX-4bit"; CTX = 16384; THINK = False
COMPRESSOR  = "mlx-community/Qwen3.5-2B-MLX-4bit"; CTX = 8192;  TRIGGER = 0.60
IMG_MAX_EDGE = 1280
TOOL_OUTPUT_CAP_CHARS = 4000
AX_FUZZY_THRESHOLD    = 0.85
VISION_CONFIDENCE_MIN = 0.50
DENY_BUNDLES = ["com.apple.systempreferences", "com.1password.1password", "com.agilebits.*"]
DENY_URL_PATTERNS = [r".*bank.*", r".*\.paypal\.com", r"accounts\.google\.com/.*password.*"]
MEMORY_FILES_AT_BOOT = 3
```

---

## PART H — Risks

| Risk | Mitigation |
|---|---|
| `mlx-vlm` lacks Qwen3.5 hybrid-attention support or tool-template quirks | Check `mlx-vlm` changelog day 1; fallback `mlx-lm` for text + `mlx-vlm` for image with shared weights dir |
| 4-bit tool-call malformation | Tolerant parser + one retry; if >5% failure in bench, move brain to **6-bit** (+2 GB, fits) |
| Image prefill too slow (>5 s) | Drop to 1024 px long edge; crop to frontmost window instead of full display |
| Retina points vs pixels mismatch | Test on internal + external 1× display in M3 |
| Electron apps hide AX | Set `AXManualAccessibility` true per app; M4 vision path |
| Memory pressure with Chrome open | `memory_pressure` check before image call; warn and skip if >80% |

---

## PART I — Open items

None blocking. Bench numbers (M0) decide 4-bit vs 6-bit and 16k vs 32k ctx.
