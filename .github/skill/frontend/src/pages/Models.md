# frontend/src/pages/Models.tsx

## Purpose
HuggingFace model browser and local model management. Allows admins to search HF, deploy models to new instances, and switch/update models on existing instances.

## Sections

### HuggingFace Browser (tab)
- Search bar → calls `modelsApi.listAvailableModels(search)`
- Model cards: name, download count, ❤ likes, tags, parameter count (if available), licence badge
- **VRAM estimate chip** — displayed on every card next to the parameter count (e.g. `~14 GB VRAM`). Value comes from `HFModelInfo.vram_required_gb` (returned by the backend); shown as `—` when unavailable.
- **Clicking the model name** navigates to the Instances page with a prefilled "Create Instance" drawer. See [Prefill Flow](#prefill-flow) below.
- "Deploy" button on each card → opens deploy wizard

### Local Models (tab)
- List of already-downloaded models with disk size, last-modified date, and **VRAM estimate**.
- **Clicking the model name** triggers the same prefill navigation as the HF browser (see below).
- "Deploy to new instance" button — opens deploy wizard with model pre-filled
- "Delete from disk" button (admin, with confirmation)

### Prefill Flow
When a user clicks a model name (either tab), the router navigates to `/instances` and passes state:
```ts
navigate('/instances', {
  state: {
    prefill: {
      model_id: 'mistralai/Mistral-7B-Instruct-v0.2',
      display_name: 'Mistral 7B Instruct',   // derived from model_id tail
      slug: 'mistral-7b-instruct',            // lowercased, hyphens, truncated to 48 chars
      // tensor_parallel_size and max_model_len left as defaults; user adjusts in drawer
    }
  }
})
```
- `/instances` detects `location.state?.prefill` on mount, opens the Create drawer, and populates the fields.
- Non-admin users are redirected to `/instances` without opening the drawer (they can view but not create).

### Deploy Wizard (modal)
1. **Model info** — confirms model ID, shows parameter count, licence warning if non-commercial, **VRAM estimate**
2. **Instance config** — fills in slug, display_name, GPU assignment, tensor_parallel_size, max_model_len
3. **Download progress** — SSE progress bar (file name + percent); only shown for HF models not yet local
4. **Launch** — creates instance and optionally auto-starts

### Switch Model (on Instances page button, modal here)
- Select a local model from a dropdown
- Confirms the stop → swap → restart flow

## Contracts
- The Deploy Wizard only shows `https://llm.ufms.br/v1/{slug}/` in the final summary — no internal ports.
- Gated models require `HF_TOKEN` to be set (backend returns a clear error if missing).
- Download progress modal cannot be closed mid-download; user must wait or cancel.
- VRAM estimate is informational only; no validation is performed against actual available GPU memory at this layer.

## Typography
- **Page title "Models"**: `Bricolage Grotesque` 900, `48px`
- **Model card primary name** (e.g. `Mistral-7B-Instruct-v0.2`): `Bricolage Grotesque` 800, `18px` — rendered as a clickable link (underline on hover) that triggers the prefill flow
- **Model organisation prefix** (e.g. `mistralai/`): `IBM Plex Sans` 200, `13px` — visually secondary to the model name
- **Parameter count, download count**: `JetBrains Mono` 600, `15px` — numeric data gets monospace treatment
- **VRAM estimate chip** (e.g. `~14 GB VRAM`): `JetBrains Mono` 600, `13px` — amber/yellow chip to signal hardware requirement; sits inline with parameter count
- **Tag badges** (licence, task): `IBM Plex Sans` 200, `11px` uppercase
- **Deploy Wizard step headings**: `Bricolage Grotesque` 800, `24px`
- **Download progress filename**: `JetBrains Mono` 300, `13px`
