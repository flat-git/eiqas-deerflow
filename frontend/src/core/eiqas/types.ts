export type Stage = "question" | "plan" | "data" | "analysis" | "review";
export type DataRow = Record<string, string | number | null>;
export type Locator = {
  key: string;
  text: string;
  page?: number;
  row?: number;
  column?: string | number;
  sheet?: string;
  ocr?: boolean;
};
export type PlanContent = {
  question: string;
  methods: { name: string; rationale: string; operation?: string }[];
  required_data: string[];
  assumptions: string[];
  outputs: string[];
  limitations: string[];
};
export type Research = {
  id: string;
  thread_id: string;
  question: string;
  stage: Stage;
  status: string;
  plan: {
    hash: string;
    revision: number;
    confirmed_at: string | null;
    content: PlanContent;
  } | null;
  answerable: string[];
  gaps: string[];
  created_at: string;
  updated_at: string;
};
export type Source = {
  id: string;
  title: string;
  organization: string;
  url: string;
  status: string;
  sha256: string | null;
  retrieved_at: string;
  media_type?: string;
  reason?: string;
};
export type Observation = {
  id: string;
  source_id: string;
  extraction_id: string;
  source_hash: string;
  raw_text: string;
  value: string;
  unit: string;
  subject: string;
  period: string;
  metric: string;
  qualifier: string;
  status: string;
  flags: string[];
  locator: Locator;
};
export type Dataset = {
  id: string;
  title: string;
  rows: DataRow[];
  observations: Observation[];
  input_hash: string;
};
export type Check = {
  name: string;
  passed: boolean;
  actual?: number;
  expected?: number;
};
export type Run = {
  id: string;
  dataset_id: string;
  status: string;
  spec: { method: string; parameters: Record<string, unknown> };
  input_hash: string;
  output_hash?: string;
  started_at: string;
  completed_at: string | null;
  errors?: string[];
  result?: {
    rows: DataRow[];
    tables?: Record<string, DataRow[]>;
    checks: Check[];
    limitations: string[];
  };
};
export type ChartSpec = {
  id: string;
  title: string;
  type: "bar" | "line" | "scatter";
  x: string;
  y: string;
  series?: string | null;
  table?: string;
  filters?: Record<string, string>;
  unit: string;
  explanation: string;
};
export type EvidenceReference = {
  source_id: string;
  extraction_id: string;
  locator_key: string;
  quote: string;
  explanation: string;
  locator: Locator;
};
export type Finding = {
  text: string;
  kind: "fact" | "inference" | "company_reported" | "unknown";
  cells: {
    row: number;
    column: string;
    value: number;
    unit: string;
    observation_ids: string[];
    table?: string;
  }[];
  observation_ids: string[];
  evidence: EvidenceReference[];
};
export type Report = {
  id: string;
  research_id: string;
  run_id: string;
  title: string;
  question: string;
  summary: string;
  findings: Finding[];
  charts: ChartSpec[];
  implications: string[];
  limitations: string[];
  run: Run;
  dataset: Dataset;
  sources: Source[];
  scope: { answerable: string[]; gaps: string[] };
  provenance: string[][];
  table_provenance?: Record<string, string[][]>;
  plan: NonNullable<Research["plan"]>;
  created_at: string;
};
export type Command = { id: string; text: string; hidden?: boolean };
