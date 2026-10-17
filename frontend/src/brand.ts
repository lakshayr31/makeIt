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
