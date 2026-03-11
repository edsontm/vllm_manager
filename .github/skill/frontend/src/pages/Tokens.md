# frontend/src/pages/Tokens.tsx

## Purpose
UI for managing per-user API tokens. Regular users see and manage their own tokens only; admins can view tokens for any user.

## Layout
- **Header**: "Your API Tokens" (or "Tokens for {username}" if admin viewing another user)
- **Token List**: table with Name, Scope (instance names or "All"), Last Used, Expiry, Status, Actions (Revoke)
- **Generate Token** button → opens Generate Token modal

## Generate Token Modal
Fields:
- `name` — human label (required)
- `scoped_instance_ids` — multi-select of available instances (optional; empty = all)
- `expires_at` — date picker (optional; default = never)

On success:
- Shows a **one-time reveal dialog** with the raw token in a read-only input + copy-to-clipboard button.
- Warning: "This token will not be shown again. Copy it now."
- Dialog cannot be dismissed without checking a "I have copied the token" checkbox.

## Contracts
- The raw token value is never stored in component state beyond the reveal dialog.
- "Revoke" is immediate with no undo (but the user can generate a new token).
- Token list never shows the token value — only metadata.
- Scope column shows instance `display_name` values, not internal IDs or ports.

## Typography
- **Page title "API Tokens"**: `Bricolage Grotesque` 900, `48px`
- **Token name in table**: `IBM Plex Sans` 700, `15px`
- **Raw token in one-time reveal dialog**: `JetBrains Mono` 600, `14px` — monospace is mandatory for tokens; makes character-by-character reading possible
- **Reveal dialog warning text**: `IBM Plex Sans` 700, `14px`, accent colour — must be visually alarming
- **"Last used" timestamp**: `IBM Plex Sans` 200, `13px`
- **Expiry date**: `JetBrains Mono` 300, `13px` — date as data
