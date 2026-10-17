import { useEffect, useRef, useState } from "react";
import { BookOpen, ExternalLink, Shapes, Upload } from "lucide-react";
import type { Editor } from "../editor/Editor";

type Tab = "elements" | "uploads" | "brand";
interface Bucket {
  title: string;
  items: { id: string; name: string; url: string }[];
}
interface BrandSection {
  title: string;
  pages: string[];
}

/** Fetch JSON with a few retries: the backend may be mid-reload when the editor opens. */
function useJson<T>(url: string, initial: T): T {
  const [data, setData] = useState<T>(initial);
  useEffect(() => {
    let tries = 0;
    let timer = 0;
    const load = () =>
      fetch(url)
        .then((r) => (r.ok ? r.json() : Promise.reject()))
        .then(setData)
        .catch(() => {
          if (++tries < 5) timer = window.setTimeout(load, 1500);
        });
    load();
    return () => clearTimeout(timer);
  }, [url]);
  return data;
}

export function LeftPanel({
  editor,
  inspiration,
}: {
  editor: Editor | null;
  inspiration?: string | null;
  onFit?: () => void;
}) {
  const [tab, setTab] = useState<Tab>("elements");
  const [uploads, setUploads] = useState<string[]>([]);
  const buckets = useJson<Bucket[]>("/api/elements", []);
  const brand = useJson<BrandSection[]>("/api/brand-pages", []);
  const fileRef = useRef<HTMLInputElement>(null);

  const add = async (src: string) => {
    if (!editor) return;
    const size = Math.min(editor.width, editor.height) * 0.45;
    const img = await editor.addImage({
      src,
      x: (editor.width - size) / 2,
      y: (editor.height - size) / 2,
      width: size,
      height: size,
    });
    editor.canvas.setActiveObject(img);
    editor.canvas.requestRenderAll();
    editor.commit();
  };

  const onFiles = (files: FileList | null) => {
    for (const f of Array.from(files ?? [])) {
      const reader = new FileReader();
      reader.onload = () => {
        const url = String(reader.result);
        setUploads((u) => [url, ...u]);
        add(url);
      };
      reader.readAsDataURL(f);
    }
  };

  return (
    <aside className="left">
      <nav className="rail">
        <button
          className={tab === "elements" ? "on" : ""}
          onClick={() => setTab("elements")}
        >
          <span className="rail-icon">
            <Shapes size={20} />
          </span>
          Elements
        </button>
        <button
          className={tab === "uploads" ? "on" : ""}
          onClick={() => setTab("uploads")}
        >
          <span className="rail-icon">
            <Upload size={20} />
          </span>
          Uploads
        </button>
        <button
          className={tab === "brand" ? "on" : ""}
          onClick={() => setTab("brand")}
        >
          <span className="rail-icon">
            <BookOpen size={20} />
          </span>
          Brand
        </button>
      </nav>
      <div className="panel">
        {tab === "elements" &&
          (buckets.length === 0 ? (
            <p className="muted">No elements yet — is the backend running?</p>
          ) : (
            buckets.map((b) => (
              <section key={b.title}>
                <h4>{b.title}</h4>
                <div className="grid">
                  {b.items.map((it) => (
                    <button
                      key={it.id}
                      className="thumb"
                      onClick={() => add(it.url)}
                      title={`${it.name} — add to page`}
                    >
                      <img src={it.url} loading="lazy" alt={it.name} />
                    </button>
                  ))}
                </div>
              </section>
            ))
          ))}
        {tab === "brand" && (
          <>
            <a className="upload-btn" href="#/brand">
              <ExternalLink size={16} /> Open brand guidelines
            </a>
            <p className="muted">
              The brand book pages the agent follows. Click a page to view it
              full size.
            </p>
            {brand.map((s) => (
              <section key={s.title}>
                <h4>{s.title}</h4>
                <div className="pages">
                  {s.pages.map((u) => (
                    <a
                      key={u}
                      className="thumb page"
                      href={u}
                      target="_blank"
                      rel="noreferrer"
                      title="View full size"
                    >
                      <img src={u} loading="lazy" alt="" />
                    </a>
                  ))}
                </div>
              </section>
            ))}
          </>
        )}
        {tab === "uploads" && (
          <>
            <button
              className="upload-btn"
              onClick={() => fileRef.current?.click()}
            >
              <Upload size={16} /> Upload files
            </button>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              multiple
              hidden
              onChange={(e) => onFiles(e.target.files)}
            />
            {inspiration && (
              <section>
                <h4>Inspiration</h4>
                <p className="muted">The ad this design was made from.</p>
                <button
                  className="thumb inspiration"
                  onClick={() => add(inspiration)}
                  title="Add to page"
                >
                  <img src={inspiration} alt="Inspiration ad" />
                </button>
              </section>
            )}
            <div className="grid">
              {uploads.map((u) => (
                <button
                  key={u.slice(-40)}
                  className="thumb"
                  onClick={() => add(u)}
                >
                  <img src={u} alt="" />
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </aside>
  );
}
