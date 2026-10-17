import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  ChevronDown,
  ChevronRight,
  Plus,
  Search,
  Trash2,
} from "lucide-react";
import { readAsDataUrl } from "./jobs";
import {
  ELEMENT_KINDS,
  addBrandElement,
  getBrandGuide,
  getBrandLibrary,
  saveBrandTopic,
  type BrandRule,
  type BrandTopic,
  type LibraryGroup,
  type RuleLevel,
} from "./brand";

type Tab = "rules" | "elements";
/** A rule being edited; `key` is stable even before the backend assigns an id. */
type DraftRule = BrandRule & { key: string };

let keySeq = 0;
const toDraft = (rules: BrandRule[]): DraftRule[] =>
  rules.map((r) => ({ ...r, key: r.id ?? `new-${++keySeq}` }));
const sameRules = (a: DraftRule[], b: BrandRule[]) =>
  a.length === b.length &&
  a.every(
    (r, i) =>
      r.id === b[i].id && r.level === b[i].level && r.text === b[i].text,
  );

const goHome = () => (window.location.hash = "#/");
const setTopicHash = (id: string) =>
  history.replaceState(null, "", `#/brand/${id}`);

export function BrandPage({ initialTopic }: { initialTopic?: string }) {
  const [tab, setTab] = useState<Tab>("rules");
  const [topics, setTopics] = useState<BrandTopic[] | null>(null);
  const [guideError, setGuideError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | undefined>(
    initialTopic,
  );
  const dirtyRef = useRef(false);

  const loadGuide = () => {
    setGuideError(null);
    getBrandGuide()
      .then((t) => {
        setTopics(t);
        setSelectedId((cur) =>
          cur && t.some((x) => x.id === cur) ? cur : t[0]?.id,
        );
      })
      .catch((e: Error) => setGuideError(e.message));
  };
  useEffect(loadGuide, []);

  const selectTopic = (id: string) => {
    if (id === selectedId) return;
    if (
      dirtyRef.current &&
      !confirm("You have unsaved changes to this topic. Discard them?")
    )
      return;
    dirtyRef.current = false;
    setSelectedId(id);
    setTopicHash(id);
  };

  const openRulesFor = (topicId: string) => {
    if (
      dirtyRef.current &&
      topicId !== selectedId &&
      !confirm("You have unsaved changes to this topic. Discard them?")
    )
      return;
    dirtyRef.current = false;
    setTab("rules");
    setSelectedId(topicId);
    setTopicHash(topicId);
  };

  const onSaved = (t: BrandTopic) =>
    setTopics((all) => (all ?? []).map((x) => (x.id === t.id ? t : x)));
  const selected = topics?.find((t) => t.id === selectedId);
  // On mobile the topic list scrolls sideways; keep the active topic visible.
  useEffect(() => {
    document
      .querySelector(".brand-topics button.on")
      ?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [selectedId, topics, tab]);

  return (
    <div className="brand">
      <header className="header">
        <span className="logo" onClick={goHome}>
          makeIt
        </span>
        <button
          className="icon-btn light"
          title="Back to your designs"
          onClick={goHome}
        >
          <ArrowLeft size={18} />
        </button>
        <div className="brand-head">
          <div className="brand-head-title">Brand guidelines</div>
          <div className="brand-head-sub">
            What makeIt follows when it makes and checks your designs
          </div>
        </div>
      </header>

      <div className="brand-tabs" role="tablist">
        <button
          role="tab"
          aria-selected={tab === "rules"}
          className={tab === "rules" ? "on" : ""}
          onClick={() => setTab("rules")}
        >
          Rules
        </button>
        <button
          role="tab"
          aria-selected={tab === "elements"}
          className={tab === "elements" ? "on" : ""}
          onClick={() => setTab("elements")}
        >
          Elements
        </button>
      </div>

      <main className="brand-body">
        {tab === "rules" ? (
          guideError ? (
            <ErrorBox
              message={`Couldn't load the brand rules (${guideError}).`}
              onRetry={loadGuide}
            />
          ) : topics === null ? (
            <p className="muted">Loading…</p>
          ) : (
            <div className="brand-rules">
              <nav className="brand-topics">
                {topics.map((t) => (
                  <button
                    key={t.id}
                    className={t.id === selectedId ? "on" : ""}
                    onClick={() => selectTopic(t.id)}
                  >
                    <span>{t.title}</span>
                    <span className="brand-count">{t.rules.length}</span>
                  </button>
                ))}
              </nav>
              {selected ? (
                <TopicEditor
                  key={selected.id}
                  topic={selected}
                  onSaved={onSaved}
                  dirtyRef={dirtyRef}
                />
              ) : (
                <p className="muted">Pick a topic.</p>
              )}
            </div>
          )
        ) : (
          <ElementsTab onSeeRules={openRulesFor} />
        )}
      </main>
    </div>
  );
}

function ErrorBox({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="brand-error">
      <span>{message}</span>
      <button className="brand-btn" onClick={onRetry}>
        Retry
      </button>
    </div>
  );
}

function TopicEditor({
  topic,
  onSaved,
  dirtyRef,
}: {
  topic: BrandTopic;
  onSaved: (t: BrandTopic) => void;
  /** Lets the page warn before switching topic with unsaved edits. */
  dirtyRef: { current: boolean };
}) {
  const [rules, setRules] = useState<DraftRule[]>(() => toDraft(topic.rules));
  const [detail, setDetail] = useState(topic.detail ?? "");
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [showGuide, setShowGuide] = useState(false);
  const [focusKey, setFocusKey] = useState<string | null>(null);

  const detailChanged = detail !== (topic.detail ?? "");
  const dirty = detailChanged || !sameRules(rules, topic.rules);
  useEffect(() => {
    dirtyRef.current = dirty;
  }, [dirty, dirtyRef]);
  useEffect(
    () => () => {
      dirtyRef.current = false;
    },
    [dirtyRef],
  );

  const update = (key: string, patch: Partial<BrandRule>) => {
    setSavedFlash(false);
    setRules((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  };
  const remove = (key: string) => {
    setSavedFlash(false);
    setRules((rs) => rs.filter((r) => r.key !== key));
  };
  const add = () => {
    const key = `new-${++keySeq}`;
    setSavedFlash(false);
    setRules((rs) => [...rs, { key, level: "SHOULD", text: "" }]);
    setFocusKey(key);
  };
  const discard = () => {
    setRules(toDraft(topic.rules));
    setDetail(topic.detail ?? "");
    setSaveError(null);
  };

  const save = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      const payload = rules
        .filter((r) => r.text.trim())
        .map(({ id, level, text }) =>
          id ? { id, level, text: text.trim() } : { level, text: text.trim() },
        );
      const updated = await saveBrandTopic(
        topic.id,
        payload,
        detailChanged ? detail : undefined,
      );
      onSaved(updated);
      setRules(toDraft(updated.rules));
      setDetail(updated.detail ?? "");
      setSavedFlash(true);
    } catch (e) {
      setSaveError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="brand-pane">
      <h2>{topic.title}</h2>

      {rules.length === 0 ? (
        <p className="muted brand-empty">No rules yet — add the first one.</p>
      ) : (
        <ul className="brand-rule-list">
          {rules.map((r) => (
            <RuleRow
              key={r.key}
              rule={r}
              autoFocus={r.key === focusKey}
              onLevel={(level) => update(r.key, { level })}
              onText={(text) => update(r.key, { text })}
              onDelete={() => remove(r.key)}
            />
          ))}
        </ul>
      )}

      <button className="brand-add" onClick={add}>
        <Plus size={16} /> Add rule
      </button>

      <div className="brand-guide">
        <button
          className="brand-guide-toggle"
          onClick={() => setShowGuide((s) => !s)}
          aria-expanded={showGuide}
        >
          {showGuide ? <ChevronDown size={16} /> : <ChevronRight size={16} />}{" "}
          Full guide for this topic
        </button>
        {showGuide && (
          <textarea
            className="brand-guide-text"
            value={detail}
            spellCheck={false}
            onChange={(e) => {
              setSavedFlash(false);
              setDetail(e.target.value);
            }}
          />
        )}
      </div>

      <div className="brand-actions">
        {saveError && (
          <span className="brand-save-error">
            Couldn't save ({saveError}).{" "}
            <button className="brand-link" onClick={save}>
              Retry
            </button>
          </span>
        )}
        <button
          className="brand-btn"
          onClick={discard}
          disabled={!dirty || saving}
        >
          Discard
        </button>
        <button
          className="brand-btn primary"
          onClick={save}
          disabled={!dirty || saving}
        >
          {saving
            ? "Saving…"
            : savedFlash && !dirty
              ? "Saved ✓"
              : "Save changes"}
        </button>
      </div>
    </section>
  );
}

function RuleRow({
  rule,
  autoFocus,
  onLevel,
  onText,
  onDelete,
}: {
  rule: DraftRule;
  autoFocus: boolean;
  onLevel: (l: RuleLevel) => void;
  onText: (t: string) => void;
  onDelete: () => void;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  // Grow the textarea to fit its content.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [rule.text]);
  useEffect(() => {
    if (autoFocus) ref.current?.focus();
  }, [autoFocus]);

  const must = rule.level === "MUST";
  return (
    <li className="brand-rule">
      <button
        className={`brand-pill ${must ? "must" : "should"}`}
        title="Click to switch between Must and Should"
        onClick={() => onLevel(must ? "SHOULD" : "MUST")}
      >
        {must ? "Must" : "Should"}
      </button>
      <div className="brand-rule-main">
        {rule.id && <span className="brand-rule-id">{rule.id}</span>}
        <textarea
          ref={ref}
          rows={1}
          className="brand-rule-text"
          value={rule.text}
          placeholder="Describe the rule…"
          onChange={(e) => onText(e.target.value)}
        />
      </div>
      <button className="icon-btn del" title="Delete rule" onClick={onDelete}>
        <Trash2 size={16} />
      </button>
    </li>
  );
}

function ElementsTab({
  onSeeRules,
}: {
  onSeeRules: (topicId: string) => void;
}) {
  const [groups, setGroups] = useState<LibraryGroup[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [adding, setAdding] = useState(false);

  const load = () => {
    setError(null);
    getBrandLibrary()
      .then(setGroups)
      .catch((e: Error) => setError(e.message));
  };
  useEffect(load, []);

  const q = query.trim().toLowerCase();
  const shown = useMemo(
    () =>
      (groups ?? []).map((g) => ({
        ...g,
        items: q
          ? g.items.filter(
              (i) =>
                i.name.toLowerCase().includes(q) ||
                (i.description ?? "").toLowerCase().includes(q),
            )
          : g.items,
      })),
    [groups, q],
  );

  if (error)
    return (
      <ErrorBox
        message={`Couldn't load the brand elements (${error}).`}
        onRetry={load}
      />
    );
  if (groups === null) return <p className="muted">Loading…</p>;

  const anyMatch = shown.some((g) => g.items.length > 0);
  return (
    <div className="brand-elements">
      <div className="brand-toolbar">
        <label className="brand-search">
          <Search size={16} />
          <input
            placeholder="Search elements"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <button className="upload-btn brand-add" onClick={() => setAdding((a) => !a)}>
          <Plus size={16} /> Add element
        </button>
      </div>
      {adding && <AddElementForm onAdded={() => { setAdding(false); load(); }} onCancel={() => setAdding(false)} />}
      {!anyMatch && (
        <p className="muted">
          {q ? "No elements match that search." : "No elements yet."}
        </p>
      )}
      {shown
        .filter((g) => g.items.length > 0)
        .map((g) => (
          <section key={g.id} className="brand-group">
            <div className="brand-group-head">
              <h2>
                {g.title} <span className="brand-count">{g.items.length}</span>
              </h2>
              <button
                className="brand-link"
                onClick={() => onSeeRules(g.topic)}
              >
                See rules →
              </button>
            </div>
            <div className="brand-grid">
              {g.items.map((i) => (
                <div
                  key={i.id}
                  className="brand-card"
                  title={i.usage_note || i.description || i.name}
                >
                  <div className="brand-thumb">
                    <img src={i.src} alt={i.name} loading="lazy" />
                  </div>
                  <div className="brand-card-name">{i.name}</div>
                  {i.colours && i.colours.length > 0 && (
                    <div className="brand-chips">
                      {i.colours.map((c) => (
                        <span
                          key={c}
                          className="brand-chip"
                          style={{ background: c }}
                          title={c}
                        />
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        ))}
    </div>
  );
}


/** Upload an image into one kit category. It shows up in the editor's Elements tab and for the agents. */
function AddElementForm({ onAdded, onCancel }: { onAdded: () => void; onCancel: () => void }) {
  const [kind, setKind] = useState(ELEMENT_KINDS[0].kind);
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!file) return setError("Choose an image first.");
    setBusy(true);
    setError(null);
    try {
      await addBrandElement(kind, name || file.name.replace(/\.[^.]+$/, ""), await readAsDataUrl(file));
      onAdded();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="brand-add-form">
      <label>
        Category
        <select value={kind} onChange={(e) => setKind(e.target.value)}>
          {ELEMENT_KINDS.map((k) => (
            <option key={k.kind} value={k.kind}>{k.title}</option>
          ))}
        </select>
      </label>
      <label>
        Name
        <input placeholder="e.g. green wave corner" value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <label>
        Image
        <input type="file" accept="image/png,image/svg+xml,image/webp,image/jpeg" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      </label>
      {error && <p className="brand-error">{error}</p>}
      <div className="brand-add-actions">
        <button className="brand-link" onClick={onCancel} disabled={busy}>Cancel</button>
        <button className="upload-btn brand-add" onClick={submit} disabled={busy || !file}>
          {busy ? "Adding…" : "Add to kit"}
        </button>
      </div>
    </div>
  );
}
