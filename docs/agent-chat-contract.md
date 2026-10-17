# Agent chat (human-in-the-loop edits): shared contract

Hackathon build, 17 Oct 2026. Three people/agents build against this file in parallel. Don't change a contract without updating this file.

## User flow

- **Right-click an element → "Ask makeIt about this"**: opens the right chat panel. The context chip shows the element, and the cursor goes to the text box.
- **Right-click anywhere → "Select area & ask…"**: area mode. You drag a rectangle on the canvas, then the panel opens with the chip "Area".
- **Typing in the panel**: the context is the current chip. If nothing is selected, the whole design is the context.
- The area box is only **context** that says "this part of the composition". It is not a mask, and the backend never inpaints.

## Intents (backend decides, one Flash call)

| intent | response fields used | frontend does |
|---|---|---|
| `layout` | `ops`, `reply` | `editor.applyOps(ops)` straight away (one undo step). Shows reply + **Undo** button |
| `remove` | `ops` (delete ops), `reply` | same as layout |
| `swap` | `options` (3 brand-kit assets), `reply`, `target_id` | 3 option cards. **Use this** → replaces the target image's src **in place** (same box, same page) |
| `generate` | `generate` plan, `reply` | calls `POST /api/agent/generate`, then shows 3 option cards. **Use this** → **creates a new page above the current one** (copy of the current page) and applies the change on the new page. The old version becomes the page below |
| `clarify` | `question` {text, choices} | shows the question with chip buttons. Clicking a chip sends the chip text as the next user message (same context). The choice "Attach an inspiration image" opens the 📎 file picker instead |
| `other` | `reply`, optional `ops` | shows the reply; applies ops if any |

The generate rule: if the target is an image element, `mode: "replace"` swaps its src in the same box. Otherwise (area or nothing) `mode: "add"` adds a new image layer at `box`, above the background and below the text. In both cases this happens on the **new page**.

## Endpoints

### `POST /api/agent/turn`
Request:
```json
{
  "request": "move the logo to the right",
  "screenshot": "data:image/png;base64,...",   // canvas PNG; if context is an area, the box is drawn on it in orange
  "canvas": { /* editor.summary(): CanvasSummary */ },
  "context": {"kind": "element", "id": "logo"} | {"kind": "area", "box": [x,y,w,h], "touches": ["hero","headline"]} | null,
  "inspiration": "data:image/...;base64,..." | null,  // attached via the 📎 button
  "history": [{"role": "user"|"agent", "text": "..."}]  // last ≤6 messages, so clarify answers have context
}
```
Response:
```json
{
  "intent": "layout|remove|swap|generate|clarify|other",
  "reply": "Moved the logo to the right edge.",
  "ops": [ /* Op[] from frontend/src/editor/types.ts */ ],
  "question": {"text": "What should the new image show?", "choices": ["Describe it", "Attach an inspiration image"]},
  "target_id": "hero",
  "swap": {"kind": "illustration|charm|bloom|product_ui|background_template|logo", "query": "keywords"},  // from Flash; backend turns it into `options`
  "options": [{"label": "Charm · coffee cup", "src": "/assets/brand-kit/..."}],
  "generate": {"prompt": "full image prompt incl. Xero style", "box": [x,y,w,h], "mode": "replace|add", "target_id": "hero"|null, "transparent": false}
}
```
Only fields relevant to the intent are present.

### `POST /api/agent/generate`
Request: `{"prompt": "...", "box": [x,y,w,h], "transparent": false, "n": 3}` → Response: `{"options": [{"src": "/generated/abc.png"}, ...]}`. The images are generated in parallel, sized to the box aspect. This takes about 15–25s, so the UI shows a step "Generating 3 options…".

### Designs: pages
`PUT /api/designs/{id}` body gains `"pages": [{"state": DesignState, "thumbnail": "data:image/png..."}]` (optional). `state` + `thumbnail` stay = **page 1** (top page; used for the home grid). `GET` returns `pages` if saved. A design without `pages` has one page = `state`.

## Frontend interfaces (fixed names)

```ts
// frontend/src/agent.ts  (owned by the chat agent)
export type ChatContext =
  | { kind: 'element'; id: string; name: string }
  | { kind: 'area'; box: [number, number, number, number] }
  | null

// frontend/src/components/ChatPanel.tsx  (owned by the chat agent)
export interface ChatPanelProps {
  editor: Editor
  context: ChatContext
  setContext: (c: ChatContext) => void
  open: boolean
  setOpen: (open: boolean) => void
  areaMode: boolean                       // true → ChatPanel runs area select on the canvas, then sets context + opens
  setAreaMode: (on: boolean) => void
  onNewVersion: (mutate: (editor: Editor) => Promise<void>) => Promise<void>  // provided by EditorPage (pages agent)
}

// ContextMenu (chat agent adds two optional props)
onAsk?: (id: string | null) => void      // "Ask makeIt about this" (id of the right-clicked element)
onSelectArea?: () => void               // "Select area & ask…"
```

`onNewVersion(mutate)` (pages agent): saves the current page → inserts a copy of it as a new page **above** the current one → makes the new page active (loads it into the Fabric canvas) → `await mutate(editor)` → commits + autosaves. The old version stays below, unchanged.
