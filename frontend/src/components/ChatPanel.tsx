import {
  useEffect,
  useReducer,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import {
  Loader2,
  Paperclip,
  PanelRightClose,
  RotateCcw,
  Send,
  Sparkles,
  Undo2,
  X,
} from "lucide-react";
import type { Editor } from "../editor/Editor";
import { startAreaSelect, touchingIds } from "../editor/areaSelect";
import {
  addImageBelowText,
  agentGenerate,
  agentTurn,
  generateOne,
  pulse,
  replaceImageSrc,
  screenshotWithBox,
  type ChatContext,
  type ChatOption,
  type GeneratePlan,
  type TurnRequest,
} from "../agent";

export interface ChatPanelProps {
  editor: Editor;
  context: ChatContext;
  setContext: (c: ChatContext) => void;
  open: boolean;
  setOpen: (open: boolean) => void;
  areaMode: boolean;
  setAreaMode: (on: boolean) => void;
  onNewVersion: (mutate: (editor: Editor) => Promise<void>) => Promise<void>;
}

const ATTACH_CHOICE = "Attach an inspiration image";
const HISTORY_TURNS = 6;

interface UserMsg {
  role: "user";
  text: string;
  inspiration?: string | null;
}

interface AgentMsg {
  role: "agent";
  steps: string[];
  busy: boolean;
  text?: string;
  error?: string;
  retry?: () => void;
  undoVersion?: number; // editor.version right after our edit; Undo is valid while it still matches
  undone?: boolean;
  choices?: string[];
  options?: ChatOption[];
  apply?: (o: ChatOption) => Promise<void>;
  applied?: number;
}

type Msg = UserMsg | AgentMsg;

const errText = (e: unknown) => (e instanceof Error ? e.message : String(e));

function readAsDataURL(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result));
    r.onerror = () => reject(r.error);
    r.readAsDataURL(file);
  });
}

/** Right-side "Ask makeIt" chat. Edits the design through the same Editor commands as the UI. */
export function ChatPanel({
  editor,
  context,
  setContext,
  open,
  setOpen,
  areaMode,
  setAreaMode,
  onNewVersion,
}: ChatPanelProps) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [draft, setDraft] = useState("");
  const [inspiration, setInspiration] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [, rerender] = useReducer((n: number) => n + 1, 0);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const autoSendAttach = useRef<ChatContext | undefined>(undefined);

  // Keep Undo buttons honest as the canvas changes.
  useEffect(() => {
    const off = editor.onChange(rerender)
    return () => {
      off()
    }
  }, [editor])

  // Parent setters may be fresh closures each render; read them via a ref so area mode isn't restarted.
  const setters = useRef({ setAreaMode, setContext, setOpen })
  setters.current = { setAreaMode, setContext, setOpen }
  useEffect(() => {
    if (!areaMode) return
    return startAreaSelect(editor, (box) => {
      const { setAreaMode, setContext, setOpen } = setters.current
      setAreaMode(false)
      if (!box) return
      setContext({ kind: 'area', box })
      setOpen(true)
    })
  }, [areaMode, editor]);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 0);
  }, [open, context]);

  useEffect(() => {
    listRef.current?.scrollTo({
      top: listRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [msgs]);

  /** Update the agent message at `idx`. */
  const patch = (idx: number, p: Partial<AgentMsg>) =>
    setMsgs((m) =>
      m.map((msg, i) =>
        i === idx && msg.role === "agent" ? { ...msg, ...p } : msg,
      ),
    );
  const step = (idx: number, s: string) =>
    setMsgs((m) =>
      m.map((msg, i) =>
        i === idx && msg.role === "agent"
          ? { ...msg, steps: [...msg.steps, s] }
          : msg,
      ),
    );

  async function send(
    text: string,
    ctx: ChatContext = context,
    attach: string | null = inspiration,
  ) {
    if (!text.trim() || busy) return;
    const prior = msgs;
    const userMsg: UserMsg = { role: "user", text, inspiration: attach };
    const idx = prior.length + 1;
    setMsgs([
      ...prior,
      userMsg,
      { role: "agent", steps: ["Reading the design…"], busy: true },
    ]);
    setDraft("");
    setInspiration(null);
    setBusy(true);
    try {
      await runTurn(idx, text, ctx, attach, prior);
    } catch (e) {
      patch(idx, {
        busy: false,
        error: errText(e),
        retry: () => send(text, ctx, attach),
      });
    } finally {
      setBusy(false);
    }
  }

  async function runTurn(
    idx: number,
    text: string,
    ctx: ChatContext,
    attach: string | null,
    prior: Msg[],
  ) {
    const box = ctx?.kind === "area" ? ctx.box : null;
    const req: TurnRequest = {
      request: text,
      screenshot: await screenshotWithBox(editor, box),
      canvas: editor.summary(),
      context: !ctx
        ? null
        : ctx.kind === "element"
          ? { kind: "element", id: ctx.id }
          : {
              kind: "area",
              box: ctx.box,
              touches: touchingIds(editor, ctx.box),
            },
      inspiration: attach,
      history: prior
        .map((m) => ({
          role: m.role,
          text: m.role === "user" ? m.text : (m.text ?? ""),
        }))
        .filter((m) => m.text)
        .slice(-HISTORY_TURNS),
    };
    const res = await agentTurn(req);
    const reply = res.reply ?? res.question?.text ?? "";

    if (res.intent === "clarify") {
      patch(idx, {
        busy: false,
        text: reply,
        choices: res.question?.choices ?? [],
      });
      return;
    }
    if (res.intent === "swap" && res.options?.length && res.target_id) {
      const id = res.target_id;
      patch(idx, {
        busy: false,
        text: reply,
        options: res.options,
        apply: (o) => replaceImageSrc(editor, id, o.src),
      });
      return;
    }
    if (res.intent === "generate" && res.generate) {
      patch(idx, { text: reply });
      step(idx, "Generating 3 options…");
      const plan = res.generate;
      const { options } = await agentGenerate({
        prompt: plan.prompt,
        box: plan.box,
        transparent: plan.transparent,
        n: 3,
      });
      patch(idx, {
        busy: false,
        options,
        apply: (o) => onNewVersion((ed) => applyGenerated(ed, plan, o.src)),
      });
      return;
    }
    // layout / remove / other
    if (res.ops?.length) {
      step(idx, "Applying changes");
      const before = editor.version;
      const errors: string[] = [];
      await editor.applyOps(res.ops, generateOne, (m) => errors.push(m));
      const target = ctx?.kind === "element" ? ctx.id : res.target_id;
      if (target) pulse(editor, target);
      patch(idx, {
        busy: false,
        text:
          reply +
          (errors.length
            ? `\n(${errors.length} change(s) failed: ${errors[0]})`
            : ""),
        undoVersion: editor.version !== before ? editor.version : undefined,
      });
      return;
    }
    patch(idx, { busy: false, text: reply || "Done." });
  }

  async function undo(idx: number, m: AgentMsg) {
    if (m.undoVersion !== editor.version) return;
    await editor.undo();
    patch(idx, { undone: true });
  }

  async function useOption(idx: number, m: AgentMsg, i: number) {
    if (!m.apply || busy) return;
    setBusy(true);
    try {
      await m.apply(m.options![i]);
      patch(idx, { applied: i });
    } catch (e) {
      patch(idx, { error: errText(e), retry: () => useOption(idx, m, i) });
    } finally {
      setBusy(false);
    }
  }

  function pickChoice(choice: string) {
    if (choice === ATTACH_CHOICE) {
      autoSendAttach.current = context;
      fileRef.current?.click();
    } else send(choice);
  }

  async function onFile(file: File | undefined) {
    if (!file) return;
    const url = await readAsDataURL(file);
    if (autoSendAttach.current !== undefined) {
      const ctx = autoSendAttach.current;
      autoSendAttach.current = undefined;
      send("Use this inspiration image", ctx, url);
    } else {
      setInspiration(url);
      inputRef.current?.focus();
    }
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(draft);
    }
  }

  if (!open)
    return (
      <button className="chat-tab" onClick={() => setOpen(true)}>
        <Sparkles size={16} /> Ask makeIt
      </button>
    );

  return (
    <aside className="chat-panel">
      <div className="chat-head">
        <Sparkles size={18} className="chat-accent" />
        <span className="chat-title">Ask makeIt</span>
        <button
          className="icon-btn"
          title="Close"
          onClick={() => setOpen(false)}
        >
          <PanelRightClose size={18} />
        </button>
      </div>

      <div className="chat-context">
        <span className="chat-chip">{contextLabel(editor, context)}</span>
        {context && (
          <button
            className="chat-chip-x"
            title="Clear"
            onClick={() => setContext(null)}
          >
            <X size={14} />
          </button>
        )}
      </div>

      <div className="chat-list" ref={listRef}>
        {msgs.length === 0 && (
          <p className="chat-empty">
            Ask for a change, e.g. “move the logo to the right” or “make the
            hero image a beach”.
          </p>
        )}
        {msgs.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="chat-msg chat-user">
              {m.inspiration && (
                <img className="chat-insp" src={m.inspiration} alt="" />
              )}
              {m.text}
            </div>
          ) : (
            <AgentBubble
              key={i}
              m={m}
              canUndo={
                m.undoVersion !== undefined &&
                !m.undone &&
                m.undoVersion === editor.version
              }
              busy={busy}
              onUndo={() => undo(i, m)}
              onChoice={pickChoice}
              onUse={(oi) => useOption(i, m, oi)}
            />
          ),
        )}
      </div>

      <div className="chat-compose">
        {inspiration && (
          <div className="chat-attach">
            <img src={inspiration} alt="" /> Inspiration image
            <button title="Remove" onClick={() => setInspiration(null)}>
              <X size={14} />
            </button>
          </div>
        )}
        <div className="chat-inputrow">
          <button
            className="icon-btn"
            title="Attach an inspiration image"
            onClick={() => fileRef.current?.click()}
            disabled={busy}
          >
            <Paperclip size={18} />
          </button>
          <textarea
            ref={inputRef}
            rows={2}
            value={draft}
            placeholder="Ask makeIt to change something…"
            disabled={busy}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
          />
          <button
            className="chat-send"
            title="Send"
            onClick={() => send(draft)}
            disabled={busy || !draft.trim()}
          >
            <Send size={16} />
          </button>
        </div>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          hidden
          onChange={(e) => {
            onFile(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
      </div>
    </aside>
  );
}

function contextLabel(editor: Editor, ctx: ChatContext) {
  if (!ctx) return "Whole design";
  if (ctx.kind === "element") return `Editing: ${ctx.name || ctx.id}`;
  const touches = touchingIds(editor, ctx.box).slice(0, 3);
  return touches.length ? `Area · touches ${touches.join(", ")}` : "Area";
}

/** Apply a chosen generated image on the (new) page. */
async function applyGenerated(editor: Editor, plan: GeneratePlan, src: string) {
  if (plan.mode === "replace" && plan.target_id && editor.find(plan.target_id))
    await replaceImageSrc(editor, plan.target_id, src);
  else await addImageBelowText(editor, src, plan.box, plan.prompt.slice(0, 24));
}

function AgentBubble({
  m,
  canUndo,
  busy,
  onUndo,
  onChoice,
  onUse,
}: {
  m: AgentMsg;
  canUndo: boolean;
  busy: boolean;
  onUndo: () => void;
  onChoice: (c: string) => void;
  onUse: (i: number) => void;
}) {
  return (
    <div className={`chat-msg chat-agent${m.error ? " chat-error" : ""}`}>
      {m.steps.map((s, i) => (
        <div key={i} className="chat-step">
          {m.busy && i === m.steps.length - 1 ? (
            <Loader2 size={13} className="chat-spin" />
          ) : (
            <span className="chat-dot" />
          )}
          {s}
        </div>
      ))}
      {m.text && <p className="chat-text">{m.text}</p>}
      {m.error && (
        <p className="chat-text">
          Something went wrong: {m.error}
          {m.retry && (
            <button className="chat-action" onClick={m.retry} disabled={busy}>
              <RotateCcw size={13} /> Retry
            </button>
          )}
        </p>
      )}
      {m.choices && m.choices.length > 0 && (
        <div className="chat-choices">
          {m.choices.map((c) => (
            <button
              key={c}
              className="chat-choice"
              onClick={() => onChoice(c)}
              disabled={busy}
            >
              {c === ATTACH_CHOICE && <Paperclip size={13} />} {c}
            </button>
          ))}
        </div>
      )}
      {m.options && m.options.length > 0 && (
        <div className="chat-options">
          {m.options.map((o, i) => (
            <div
              key={o.src}
              className={`chat-option${m.applied === i ? " on" : ""}`}
            >
              <img src={o.src} alt={o.label ?? ""} />
              {o.label && <span className="chat-option-label">{o.label}</span>}
              <button
                className="chat-use"
                onClick={() => onUse(i)}
                disabled={busy}
              >
                {m.applied === i ? "Used" : "Use this"}
              </button>
            </div>
          ))}
        </div>
      )}
      {(canUndo || m.undone) && (
        <button
          className="chat-action"
          onClick={onUndo}
          disabled={!canUndo || busy}
        >
          <Undo2 size={13} /> {m.undone ? "Undone" : "Undo"}
        </button>
      )}
    </div>
  );
}
