/** Brand guidelines + brand-kit library, served by /api/brand/*. */

export type RuleLevel = "MUST" | "SHOULD";

export interface BrandRule {
  id?: string;
  level: RuleLevel;
  text: string;
}

export interface BrandTopic {
  id: string;
  title: string;
  rules: BrandRule[];
  detail: string;
}

export interface LibraryItem {
  id: string;
  name: string;
  src: string;
  description?: string;
  usage_note?: string;
  colours?: string[];
}

export interface LibraryGroup {
  id: string;
  title: string;
  topic: string;
  items: LibraryItem[];
}

async function json<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json() as Promise<T>;
}

export const getBrandGuide = (): Promise<BrandTopic[]> =>
  fetch("/api/brand/guide")
    .then((r) => json<{ topics: BrandTopic[] }>(r))
    .then((d) => d.topics);

export const saveBrandTopic = (
  topicId: string,
  rules: BrandRule[],
  detail?: string,
): Promise<BrandTopic> =>
  fetch(`/api/brand/guide/${encodeURIComponent(topicId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(detail === undefined ? { rules } : { rules, detail }),
  }).then((r) => json<BrandTopic>(r));

export const getBrandLibrary = (): Promise<LibraryGroup[]> =>
  fetch("/api/brand/library")
    .then((r) => json<{ groups: LibraryGroup[] }>(r))
    .then((d) => d.groups);

export const ELEMENT_KINDS: { kind: string; title: string }[] = [
  { kind: "background_template", title: "Backgrounds" },
  { kind: "bloom", title: "Blooms & cropping" },
  { kind: "charm", title: "Charms" },
  { kind: "product_ui", title: "Product UI" },
  { kind: "illustration", title: "Illustrations" },
  { kind: "logo", title: "Logos" },
];

/** Upload one image as a new brand-kit element. `image` is a data URL. */
export const addBrandElement = (kind: string, name: string, image: string): Promise<LibraryItem> =>
  fetch("/api/brand/library", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind, name, image }),
  }).then((r) => json<LibraryItem>(r));
