# frontend/src/components/CodeExample.tsx

## Purpose
Renders syntax-highlighted, copy-to-clipboard code blocks showing how to connect to a specific vLLM instance endpoint using an API token. Displayed in the Instances page detail drawer and TestInterface.

## Props
```ts
interface CodeExampleProps {
  instance: InstanceRead;         // instance slug and display_name
  token?: string;                 // optional token to pre-fill in examples
  language?: "python" | "curl" | "javascript";  // default: shows all three as tabs
}
```

## Generated Examples

### Python (openai library)
```python
from openai import OpenAI

client = OpenAI(
    base_url="https://llm.ufms.br/v1/{slug}",
    api_key="{token}"
)

response = client.chat.completions.create(
    model="{model_id}",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)
```

### curl
```bash
curl -X POST https://llm.ufms.br/v1/{slug}/chat/completions \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"model": "{model_id}", "messages": [{"role": "user", "content": "Hello!"}]}'
```

### JavaScript (fetch)
```js
const response = await fetch("https://llm.ufms.br/v1/{slug}/chat/completions", {
  method: "POST",
  headers: {
    "Authorization": "Bearer {token}",
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    model: "{model_id}",
    messages: [{ role: "user", content: "Hello!" }]
  })
});
const data = await response.json();
console.log(data.choices[0].message.content);
```

## Contracts
- All example URLs use `https://llm.ufms.br/v1/{slug}/...` — internal ports are never shown.
- If `token` prop is not provided, examples use the placeholder `YOUR_API_TOKEN`.
- Syntax highlighting via `shiki` (server-side compatible) or `prism-react-renderer`.
- Copy button uses the browser Clipboard API with a "Copied!" confirmation toast.

## Typography
- **Tab labels** ("Python", "curl", "JavaScript"): `IBM Plex Sans` 700, `12px` uppercase — small but decisive
- **All code content inside blocks**: `JetBrains Mono` 300, `13px`, line-height `1.65` — monospace is non-negotiable for code; weight 300 keeps dense blocks legible
- **Syntax highlight — keywords/operators**: `JetBrains Mono` 600 — weight shift instead of colour alone for accessibility
- **"Copy" button label**: `IBM Plex Sans` 700, `11px` uppercase
- **"Copied!" confirmation**: `IBM Plex Sans` 200, `11px` — intentionally lighter than the button label to signal a passive state
- The code block background must provide sufficient contrast for `JetBrains Mono` 300 at `13px` — minimum contrast ratio 7:1 (WCAG AAA)
