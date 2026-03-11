# frontend/src/pages/Instances.tsx

## Purpose
Full CRUD UI for vLLM instances. Admins can create, configure, start/stop/restart, and delete instances. All users can view status and connection examples.

## Sections

### Instance Table
- Columns: Name, Model, Status badge, GPU IDs, Ports (internal only — never shown), Actions
- Actions per row: Start / Stop / Restart (admin), View details, Copy connection example

### Create / Edit Drawer (admin only)
Slide-in panel with a form containing:

When opened from a prefill navigation (user clicked a model name on the Models page), all fields derived from the model are pre-populated. The drawer reads `location.state?.prefill` on mount and calls `form.reset(prefill)` before opening.

**Identity**
- `slug` — URL name used in `/v1/{slug}/...`
- `display_name`

**Model**
- `model_id` — searchable dropdown fed by `modelsApi.listLocalModels()`. When prefilled, a non-editable chip shows the incoming model name alongside the dropdown so the user knows it was auto-selected.
- **VRAM estimate** — shown as a read-only hint below the model dropdown once a `model_id` is selected: `Estimated VRAM: ~14 GB`. Fetched from `modelsApi.modelInfo(model_id).vram_required_gb`; displayed as `Unknown` when `null`.

**Hardware**
- `gpu_ids` — multi-select checkboxes per available GPU
- `tensor_parallel_size` — number input

**Batch Parameters**
- `max_num_seqs` — slider (1–1024)
- `enable_chunked_prefill` — toggle
- `max_model_len` — number input with tooltip

**Speculative Decoding** (collapsible section)
- `speculative_model` — model ID or empty
- `speculative_num_draft_tokens` — number input
- Informational note: "Speculative decoding can reduce latency by 1.5–3× for short completions by using a small draft model."

### Connection Examples Drawer
- Shows `CodeExample` component for the selected instance.
- All URLs use `https://llm.ufms.br/v1/{slug}/...` — no internal ports.

## Contracts
- Form validation: `slug` must match `^[a-z0-9-]+$`; `tensor_parallel_size` must equal GPU count or a divisor of it.
- Start/Stop buttons are disabled while `status === "starting"`.
- Config form is read-only (inputs disabled) when `status !== "stopped"`.
- Prefill state (`location.state?.prefill`) is consumed on first mount only; navigating away and back to `/instances` without carrying state does not re-trigger the drawer.

## Typography
- **Page title "Instances"**: `Bricolage Grotesque` 900, `48px`
- **Instance name in table**: `Bricolage Grotesque` 800, `18px`
- **Model ID** (e.g. `mistralai/Mistral-7B`): `JetBrains Mono` 300, `13px` — monospace signals it is a machine identifier
- **Form section labels** ("Hardware", "Batch Parameters"): `IBM Plex Sans` 200, `11px` uppercase tracked — ultra-light for hierarchy contrast
- **Form field values / inputs**: `IBM Plex Sans` 700, `15px`
- **Drawer heading** (e.g. "Edit mistral-7b"): `Bricolage Grotesque` 800, `28px`
- Speculative decoding informational note: `IBM Plex Sans` 200 italic, `13px`
