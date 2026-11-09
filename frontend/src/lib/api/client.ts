import { get } from "svelte/store";
import { auth } from "$lib/auth";

export class ApiError extends Error {
  status: number;
  code?: string;
  details: unknown;
  constructor(status: number, body: any) {
    super(typeof body?.detail === "string" ? body.detail : `HTTP ${status}`);
    this.status = status;
    this.code = body?.code;
    this.details = body?.details;
  }
}

const BASE = "/api/v1";

async function req<T>(
  method: string,
  path: string,
  opts: { body?: unknown; params?: Record<string, string | undefined>; form?: FormData; raw?: boolean } = {},
): Promise<T> {
  const url = new URL(BASE + path, window.location.origin);
  if (opts.params) {
    for (const [k, v] of Object.entries(opts.params)) if (v !== undefined && v !== "") url.searchParams.set(k, v);
  }
  const headers: Record<string, string> = {};
  const token = get(auth).token;
  if (token) headers["Authorization"] = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (opts.form) {
    body = opts.form;
  } else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  const res = await fetch(url, { method, headers, body, credentials: "include" });
  if (!res.ok) {
    let detail: any = {};
    try {
      detail = await res.json();
    } catch {
      detail = { detail: res.statusText };
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  const ct = res.headers.get("content-type") ?? "";
  if (opts.raw) return (await res.blob()) as T;
  return (ct.includes("json") ? res.json() : res.text()) as Promise<T>;
}

export async function download(path: string, filename: string): Promise<void> {
  const token = get(auth).token;
  const res = await fetch(BASE + path, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!res.ok) throw new ApiError(res.status, await res.json().catch(() => ({})));
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: string;
  email: string;
}
export interface PartSummary {
  part_number: string;
  name: string;
  part_type: string;
}
export interface Revision {
  id: string;
  revision: string;
  status: string;
  change_reason: string;
  attributes: Record<string, unknown>;
  created_at: string;
}
export interface Part {
  id: string;
  part_number: string;
  name: string;
  description: string | null;
  part_type: string;
  class_id: string;
  created_at: string;
  revisions: Revision[];
}
export interface PartClass {
  id: string;
  code: string;
  name: string;
}
export interface BomItem {
  id: string;
  position: number;
  quantity: number;
  unit: string;
  component_part_number: string;
  component_revision: string;
  component_status: string;
}
export interface WhereUsed {
  parent_part_number: string;
  parent_revision: string;
  parent_status: string;
  depth: number;
}
export interface BomDiff {
  part_number: string;
  rev_a: string;
  rev_b: string;
  added: Record<string, unknown>[];
  removed: Record<string, unknown>[];
  changed: Record<string, unknown>[];
}
export interface Ecr {
  id: string;
  number: string;
  description: string;
  status: string;
  created_at: string;
  ecos?: Eco[];
}
export interface Eco {
  id: string;
  number: string;
  status: string;
  ecr_number: string;
  created_at: string;
  affected?: AffectedRevision[];
}
export interface AffectedRevision {
  revision_id: string;
  part_number: string;
  revision: string;
  status: string;
}
export interface Confirmation {
  id: string;
  action: string;
  summary: string;
  status: string;
  payload: Record<string, unknown>;
  created_at: string;
  expires_at: string;
}
export interface Report {
  report_id: string;
  template: string;
  created_by: string;
  created_at: string;
  content_snapshot?: Record<string, any>;
  pdf_available?: boolean;
}
export interface DocumentSummary {
  doc_number: string;
  title: string;
  doc_type: string;
}
export interface DocFile {
  id: string;
  filename: string;
  mime_type: string;
  is_original: boolean;
  has_derivative: boolean;
}
export interface DocRevision {
  id: string;
  revision: string;
  status: string;
  change_reason: string;
  created_at: string;
  files: DocFile[];
}
export interface Document {
  id: string;
  doc_number: string;
  doc_type: string;
  title: string;
  revisions: DocRevision[];
  links: { part_number: string; link_type: string }[];
}

export const api = {
  login: (email: string, password: string) => req<TokenResponse>("POST", "/auth/login", { body: { email, password } }),
  listParts: (query?: string, classCode?: string) => req<PartSummary[]>("GET", "/parts", { params: { query, class_code: classCode } }),
  getPart: (pn: string) => req<Part>("GET", `/parts/${encodeURIComponent(pn)}`),
  createPart: (data: { name: string; description?: string; part_type: string; class_code: string; attributes?: Record<string, unknown>; reason?: string }) =>
    req<Part>("POST", "/parts?direct=true", { body: data }),
  createRevision: (pn: string, change_reason: string) => req<Revision>("POST", `/parts/${encodeURIComponent(pn)}/revisions?direct=true`, { body: { change_reason } }),
  transitionRevision: (id: string, to_status: string, reason: string) =>
    req<Revision>("POST", `/revisions/${id}/transition?direct=true`, { body: { to_status, reason } }),
  getBom: (pn: string, rev?: string) => req<BomItem[]>("GET", `/bom/parts/${encodeURIComponent(pn)}`, { params: { rev } }),
  whereUsed: (pn: string) => req<WhereUsed[]>("GET", `/bom/parts/${encodeURIComponent(pn)}/where-used`),
  bomDiff: (pn: string, revA: string, revB: string) =>
    req<BomDiff>("GET", `/bom/parts/${encodeURIComponent(pn)}/diff`, { params: { rev_a: revA, rev_b: revB } }),
  listEcrs: (status?: string) => req<Ecr[]>("GET", "/ecrs", { params: { status } }),
  getEcr: (nr: string) => req<Ecr>("GET", `/ecrs/${encodeURIComponent(nr)}`),
  createEcr: (description: string, reason?: string) => req<Ecr>("POST", "/ecrs?direct=true", { body: { description, reason } }),
  transitionEcr: (nr: string, to_status: string, reason: string) => req<Ecr>("POST", `/ecrs/${encodeURIComponent(nr)}/transition?direct=true`, { body: { to_status, reason } }),
  createEco: (ecrNumber: string, reason?: string) => req<Eco>("POST", `/ecrs/${encodeURIComponent(ecrNumber)}/ecos?direct=true`, { body: { reason } }),
  listEcos: (status?: string) => req<Eco[]>("GET", "/ecos", { params: { status } }),
  getEco: (nr: string) => req<Eco>("GET", `/ecos/${encodeURIComponent(nr)}`),
  transitionEco: (nr: string, to_status: string, reason: string) => req<Eco>("POST", `/ecos/${encodeURIComponent(nr)}/transition?direct=true`, { body: { to_status, reason } }),
  addAffected: (eco: string, part_number: string, revision?: string, reason?: string) =>
    req<AffectedRevision>("POST", `/ecos/${encodeURIComponent(eco)}/affected-revisions?direct=true`, { body: { part_number, revision, reason } }),
  removeAffected: (eco: string, revisionId: string) => req<void>("DELETE", `/ecos/${encodeURIComponent(eco)}/affected-revisions/${revisionId}`),
  listConfirmations: (status?: string) => req<Confirmation[]>("GET", "/confirmations", { params: { status } }),
  approve: (id: string) => req<Confirmation>("POST", `/confirmations/${id}/approve`),
  reject: (id: string) => req<Confirmation>("POST", `/confirmations/${id}/reject`),
  listReports: () => req<Report[]>("GET", "/reports"),
  getReport: (id: string) => req<Report>("GET", `/reports/${encodeURIComponent(id)}`),
  createReport: (pn: string, reason?: string) => req<Report>("POST", `/reports/parts/${encodeURIComponent(pn)}?direct=true`, { body: { reason } }),
  listDocuments: (query?: string) => req<DocumentSummary[]>("GET", "/documents", { params: { query } }),
  getDocument: (nr: string) => req<Document>("GET", `/documents/${encodeURIComponent(nr)}`),
  createDocument: (title: string, doc_type: string, reason?: string) => req<Document>("POST", "/documents?direct=true", { body: { title, doc_type, reason } }),
  uploadFile: (docNumber: string, revision: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return req<DocFile>("POST", `/documents/${encodeURIComponent(docNumber)}/revisions/${encodeURIComponent(revision)}/files?direct=true`, { form });
  },
  stats: () => req<{ users: number; parts: number; open_confirmations: number }>("GET", "/admin/stats"),
  partClasses: () => req<PartClass[]>("GET", "/admin/part-classes"),
  auditLog: (limit = 30) => req<any[]>("GET", "/admin/audit-log", { params: { limit: String(limit) } }),
};
