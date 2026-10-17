import {
  useEffect,
  useReducer,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import {
  BookmarkPlus,
  Check,
  Loader2,
  Paperclip,
  PanelRightClose,
  RotateCcw,
  Send,
  ShieldCheck,
  Sparkles,
  Undo2,
  X,
} from "lucide-react";
import type { Editor } from "../editor/Editor";
import type { Op } from "../editor/types";
import { startAreaSelect, touchingIds } from "../editor/areaSelect";
import {
  addBrandRule,
  addImageBelowText,
  agentCheck,
  agentGenerate,
  agentTurn,
  generateOne,
  pulse,
  replaceImageSrc,
  screenshotWithBox,
  selectionImage,
  type BrandIssue,
  type BrandRuleSuggestion,
  type ChatContext,
  type RuleLevel,
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
const BRAND_FIX_ROUNDS = 2;

interface UserMsg {
  role: "user";
  text: string;
  inspiration?: string | null;
  selection?: string | null; // picture of the selected element / area this message is about
}

interface AgentMsg {
  role: "agent";
  steps: string[];
  busy: boolean;
  text?: string;
  error?: string;
  retry?: () => void;
  undoVersion?: number; // editor.version right after our edit; Undo is valid while it still matches
  undoSteps?: number; // our edit + the brand fixes applied after it
  brand?: { fixed: string[]; needs: BrandIssue[]; kept: number[] };
  override?: { label: string; ops: Op[] };
  overridden?: boolean;
  undone?: boolean;
  choices?: string[];
  options?: ChatOption[];
  apply?: (o: ChatOption) => Promise<void>;
  applied?: number;
  rule?: RuleCard; // "Add to brand guidelines?" suggestion; at most one per message
}

/** Editable state of a brand-rule suggestion. Lives on the message so dismiss/add survive re-renders. */
interface RuleCard {
  suggestion: BrandRuleSuggestion;
  text: string;
  level: RuleLevel;
  status: "open" | "saving" | "error" | "added" | "dismissed";
  addedId?: string;
  addedTopic?: string;
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
  const [contextThumb, setContextThumb] = useState<string | null>(null);
  const [, rerender] = useReducer((n: number) => n + 1, 0);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const autoSendAttach = useRef<ChatContext | undefined>(undefined);

  // Keep Undo buttons honest as the canvas changes.
  // Picture next to the context chip, so you see what the next message is about.
  useEffect(() => {
    let live = true;
    selectionImage(editor, context)
      .then((src) => live && setContextThumb(src))
      .catch(() => live && setContextThumb(null));
    return () => {
      live = false;
    };
  }, [editor, context]);

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
    const selection = await selectionImage(editor, ctx).catch(() => null);
    const userMsg: UserMsg = { role: "user", text, inspiration: attach, selection };
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
      await runTurn(idx, text, ctx, attach, prior, selection);
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
    selection: string | null,
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
      selection_image: selection,
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
    if (res.brand_rule?.text)
      patch(idx, {
        rule: {
          suggestion: res.brand_rule,
          text: res.brand_rule.text,
          level: res.brand_rule.level === "MUST" ? "MUST" : "SHOULD",
          status: "open",
        },
      });

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
        apply: async (o) => {
          await replaceImageSrc(editor, id, o.src);
          await brandCheck(idx, text, [id]);
        },
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
        apply: async (o) => {
          await onNewVersion((ed) => applyGenerated(ed, plan, o.src));
          await brandCheck(idx, text, plan.target_id ? [plan.target_id] : []);
        },
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
      const changed = editor.version !== before;
      patch(idx, {
        text:
          reply +
          (errors.length
            ? `\n(${errors.length} change(s) failed: ${errors[0]})`
            : ""),
        override: res.override?.ops?.length ? res.override : undefined,
      });
      const fixSteps = changed ? await brandCheck(idx, text, changedIds(res.ops)) : 0;
      patch(idx, {
        busy: false,
        undoVersion: changed ? editor.version : undefined,
        undoSteps: 1 + fixSteps,
      });
      return;
    }
    patch(idx, { busy: false, text: reply || "Done." });
  }

  async function undo(idx: number, m: AgentMsg) {
    if (m.undoVersion !== editor.version) return;
    for (let i = 0; i < (m.undoSteps ?? 1); i++) await editor.undo();
    patch(idx, { undone: true });
  }

  /**
   * Brand check after every change: Flash + code checks → apply fixes → code re-check.
   * Whatever is still wrong goes to "Needs you". Returns how many undo steps the fixes added.
   */
  async function brandCheck(idx: number, request: string, changed: string[]): Promise<number> {
    step(idx, "Checking brand rules…");
    const ask = async (vision: boolean) =>
      agentCheck({
        request,
        screenshot: await screenshotWithBox(editor, null),
        canvas: editor.summary(),
        changed_ids: changed,
        vision,
      });
    try {
      // Up to 2 fix rounds; each round's leftovers are re-measured by code.
      let steps = 0;
      const fixed: string[] = [];
      let needs: BrandIssue[] = [];
      for (let round = 0; round < BRAND_FIX_ROUNDS; round++) {
        const res = await ask(true);
        needs = res.issues.filter((i) => i.fixable === false);
        if (!res.ops.length) {
          needs = res.issues;
          break;
        }
        step(idx, round === 0 ? "Fixing brand issues…" : "Fixing what's left…");
        const before = editor.version;
        await editor.applyOps(res.ops, generateOne);
        if (editor.version !== before) steps++;
        fixed.push(...res.fixed);
        const left = (await ask(false)).issues;
        needs = [...needs, ...left];
        if (!left.length) break;
      }
      patch(idx, { brand: { fixed, needs, kept: [] } });
      return steps;
    } catch {
      patch(idx, { brand: { fixed: [], needs: [{ element_id: "", message: "Brand check couldn't run." }], kept: [] } });
      return 0;
    }
  }

  async function applyOverride(idx: number, m: AgentMsg) {
    if (!m.override || busy) return;
    // The override replaces the on-brand version: undo it (and its brand fixes) first, if nothing came after.
    if (m.undoVersion === editor.version)
      for (let i = 0; i < (m.undoSteps ?? 1); i++) await editor.undo();
    await editor.applyOps(m.override.ops, generateOne); // no brand check: off-brand on purpose
    patch(idx, { overridden: true, undoVersion: undefined });
  }

  const patchRule = (idx: number, p: Partial<RuleCard>) =>
    setMsgs((ms) =>
      ms.map((msg, i) =>
        i === idx && msg.role === "agent" && msg.rule
          ? { ...msg, rule: { ...msg.rule, ...p } }
          : msg,
      ),
    );

  async function saveRule(idx: number, rule: RuleCard) {
    if (rule.status === "saving" || !rule.text.trim()) return;
    patchRule(idx, { status: "saving" });
    try {
      const res = await addBrandRule({
        topic: rule.suggestion.topic,
        level: rule.level,
        text: rule.text.trim(),
        ...(rule.suggestion.why ? { why: rule.suggestion.why } : {}),
      });
      patchRule(idx, { status: "added", addedId: res.rule.id, addedTopic: res.topic });
    } catch {
      patchRule(idx, { status: "error" });
    }
  }

  function fixIssue(issue: BrandIssue) {
    const el = editor.summary().elements.find((e) => e.id === issue.element_id);
    send(
      `Fix this brand issue: ${issue.message}`,
      el ? { kind: "element", id: el.id, name: el.name || el.id } : context,
    );
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
        {contextThumb && <img className="chat-ctx-thumb" src={contextThumb} alt="" />}
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
              {m.selection && (
                <img className="chat-selection" src={m.selection} alt="Selected part of the design" />
              )}
              {m.inspiration && (
                <img className="chat-insp" src={m.inspiration} alt="" />
              )}
              {m.text}
            </div>
          ) : (
            <AgentBubble
              key={i}
              m={m}
              onOverride={() => applyOverride(i, m)}
              onRule={(p) => patchRule(i, p)}
              onSaveRule={() => m.rule && saveRule(i, m.rule)}
              onFix={fixIssue}
              onKeep={(k) => m.brand && patch(i, { brand: { ...m.brand, kept: [...m.brand.kept, k] } })}
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

/** Ids an op list touches, so the brand check judges what changed. */
function changedIds(ops: Op[]): string[] {
  return [...new Set(ops.map((o) => ("id" in o ? o.id : undefined)).filter((id): id is string => !!id))];
}

function AgentBubble({
  m,
  canUndo,
  busy,
  onUndo,
  onChoice,
  onUse,
  onOverride,
  onFix,
  onKeep,
  onRule,
  onSaveRule,
}: {
  m: AgentMsg;
  canUndo: boolean;
  busy: boolean;
  onUndo: () => void;
  onChoice: (c: string) => void;
  onUse: (i: number) => void;
  onOverride: () => void;
  onFix: (issue: BrandIssue) => void;
  onKeep: (index: number) => void;
  onRule: (p: Partial<RuleCard>) => void;
  onSaveRule: () => void;
}) {
  const needs = m.brand?.needs.filter((_, i) => !m.brand!.kept.includes(i)) ?? [];
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
              {o.warning && <span className="chat-option-warn">⚠ Off-brand: {o.warning}</span>}
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
      {m.override && !m.overridden && (
        <button className="chat-action" onClick={onOverride} disabled={busy}>
          {m.override.label}
        </button>
      )}
      {m.overridden && <p className="chat-brand-note">Kept your choice, off-brand on purpose.</p>}
      {m.rule &&
        m.rule.status !== "dismissed" &&
        (m.rule.suggestion.on === "now" || m.overridden) && (
          <RuleSuggestion rule={m.rule} onChange={onRule} onSave={onSaveRule} />
        )}
      {m.brand && (
        <div className="chat-brand">
          {m.brand.fixed.length === 0 && needs.length === 0 && (
            <p className="chat-brand-ok"><ShieldCheck size={13} /> On brand</p>
          )}
          {m.brand.fixed.length > 0 && (
            <div className="chat-brand-fixed">
              <strong><ShieldCheck size={13} /> Brand fixes</strong>
              <ul>{m.brand.fixed.map((f) => <li key={f}>{f}</li>)}</ul>
            </div>
          )}
          {needs.length > 0 && (
            <div className="chat-brand-needs">
              <strong>Needs you</strong>
              {m.brand.needs.map((issue, i) =>
                m.brand!.kept.includes(i) ? null : (
                  <div key={i} className="chat-need">
                    <span>{issue.message}</span>
                    {issue.element_id && (
                      <span className="chat-need-actions">
                        <button onClick={() => onFix(issue)} disabled={busy}>Fix it</button>
                        <button onClick={() => onKeep(i)} disabled={busy}>Keep it</button>
                      </span>
                    )}
                  </div>
                ),
              )}
            </div>
          )}
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

/** "Add to brand guidelines?" card: editable rule text + MUST/SHOULD, then saved via /api/brand/rules. */
function RuleSuggestion({
  rule,
  onChange,
  onSave,
}: {
  rule: RuleCard;
  onChange: (p: Partial<RuleCard>) => void;
  onSave: () => void;
}) {
  const title = rule.suggestion.topic_title || rule.suggestion.topic;
  if (rule.status === "added")
    return (
      <p className="rule-added">
        <Check size={13} /> Added as {rule.addedId} to {title} ·{" "}
        <a href={`#/brand/${encodeURIComponent(rule.addedTopic ?? rule.suggestion.topic)}`}>View</a>
      </p>
    );
  const saving = rule.status === "saving";
  return (
    <div className="rule-card">
      <div className="rule-head">
        <BookmarkPlus size={14} /> Add to brand guidelines?
      </div>
      <div className="rule-meta">
        <span className="rule-topic">{title}</span>
        <span className="rule-level" role="group" aria-label="Rule strength">
          {(["MUST", "SHOULD"] as const).map((lv) => (
            <button
              key={lv}
              className={rule.level === lv ? "on" : ""}
              onClick={() => onChange({ level: lv })}
              disabled={saving}
            >
              {lv}
            </button>
          ))}
        </span>
      </div>
      <textarea
        className="rule-text"
        rows={2}
        value={rule.text}
        disabled={saving}
        onChange={(e) => onChange({ text: e.target.value })}
      />
      {rule.suggestion.why && <p className="rule-why">{rule.suggestion.why}</p>}
      {rule.status === "error" && (
        <p className="rule-error">
          Couldn't save —{" "}
          <button className="rule-retry" onClick={onSave}>Retry</button>
        </p>
      )}
      <div className="rule-actions">
        <button className="rule-add" onClick={onSave} disabled={saving || !rule.text.trim()}>
          {saving ? <Loader2 size={13} className="chat-spin" /> : null} Add rule
        </button>
        <button className="rule-dismiss" onClick={() => onChange({ status: "dismissed" })} disabled={saving}>
          Not now
        </button>
      </div>
    </div>
  );
}
