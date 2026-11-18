import { queryOptions } from "@tanstack/react-query";
import type { JobStatus as DisplayJobStatus } from "@/lib/demo/data";

export type JobStatus = "queued" | "running" | "completed" | "failed" | "blocked" | "cancelled";

export interface JobStep {
  id: number;
  job_id: string;
  name: string;
  program: string;
  position: number;
  status: JobStatus;
  return_code: number | null;
  stdout: string;
  stderr: string;
  executor: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface Job {
  id: string;
  name: string;
  status: JobStatus;
  jcl: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  return_code: number | null;
  stdout: string;
  stderr: string;
  steps: JobStep[];
}

export interface Dataset {
  name: string;
  organization: string;
  record_count: number;
  created_at: string;
  updated_at: string;
}

export interface DatasetDetail extends Dataset {
  records: string[];
}

export interface DailyReport {
  date: string;
  jobs: number;
  completed: number;
  failed: number;
  cancelled: number;
  success_rate: number;
  avg_duration_seconds: number;
}

export interface ReportSummary {
  total_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  cancelled_jobs: number;
  active_jobs: number;
  success_rate: number;
  avg_duration_seconds: number;
  daily: DailyReport[];
}

export interface ParsedJCL {
  job_name: string;
  steps: {
    name: string;
    program: string;
    datasets: { name: string; dataset: string | null; inline_data: string[] }[];
  }[];
}

export interface SystemMetrics {
  total_jobs: number;
  queued_jobs: number;
  running_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  cancelled_jobs: number;
  database_bytes: number;
  queue_depth: number;
  executor: string;
  gnucobol_available: boolean;
}

export interface VsamCustomer {
  customer_id: string;
  name: string;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function displayJobStatus(status: JobStatus): DisplayJobStatus {
  return status === "queued" ? "waiting" : status;
}

const apiBaseUrl = import.meta.env["VITE_API_BASE_URL"] ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const body = await response.text();
    let message = `Request failed (${response.status})`;
    if (body) {
      try {
        const parsed: unknown = JSON.parse(body);
        if (
          typeof parsed === "object" &&
          parsed !== null &&
          "detail" in parsed &&
          typeof parsed.detail === "string"
        ) {
          message = parsed.detail;
        } else {
          message = body;
        }
      } catch {
        message = body;
      }
    }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const jobsQuery = () =>
  queryOptions({
    queryKey: ["jobs"],
    queryFn: async () => {
      const result = await request<{ items: Job[]; total: number }>("/api/jobs?limit=500");
      return result.items;
    },
    refetchInterval: 5000,
  });

export const jobQuery = (id: string) =>
  queryOptions({
    queryKey: ["jobs", id],
    queryFn: async () => {
      try {
        return await request<Job>(`/api/jobs/${encodeURIComponent(id)}`);
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null;
        throw error;
      }
    },
    refetchInterval: (query) =>
      query.state.data?.status === "queued" || query.state.data?.status === "running"
        ? 2000
        : false,
  });

export const datasetsQuery = () =>
  queryOptions({
    queryKey: ["datasets"],
    queryFn: async () => {
      const result = await request<{ items: Dataset[]; total: number }>("/api/datasets");
      return result.items;
    },
  });

export const datasetQuery = (name: string) =>
  queryOptions({
    queryKey: ["datasets", name],
    queryFn: () => request<DatasetDetail>(`/api/datasets/${encodeURIComponent(name)}`),
  });

export const reportSummaryQuery = () =>
  queryOptions({
    queryKey: ["reports", "summary"],
    queryFn: () => request<ReportSummary>("/api/reports/summary"),
    refetchInterval: 30000,
  });

export const failuresQuery = () =>
  queryOptions({
    queryKey: ["failures"],
    queryFn: async () => {
      const result = await request<{ items: Job[]; total: number }>("/api/jobs?limit=500");
      return result.items
        .filter((job) => job.status === "failed")
        .map((job) => ({
          id: job.id,
          job: job.id,
          severity: "high" as const,
          code: job.return_code === null ? "FAILED" : `RC=${job.return_code}`,
          type: job.stderr || "COBOL step failed.",
          time: job.finished_at ?? job.created_at,
          affected: [] as string[],
          status: "open",
        }));
    },
    refetchInterval: 5000,
  });

export const metricsQuery = () =>
  queryOptions({
    queryKey: ["metrics"],
    queryFn: () => request<SystemMetrics>("/api/metrics"),
    refetchInterval: 5000,
  });

export const vsamCustomersQuery = () =>
  queryOptions({
    queryKey: ["vsam", "customers"],
    queryFn: () => request<VsamCustomer[]>("/api/vsam/customers"),
  });

export const reportJobsQuery = () =>
  queryOptions({
    queryKey: ["reports", "jobs"],
    queryFn: () => request<Job[]>("/api/reports/jobs"),
    refetchInterval: 5000,
  });

export function validateJcl(content: string): Promise<ParsedJCL> {
  return request<ParsedJCL>("/api/jcl/validate", {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

export function submitJob(content: string): Promise<Job> {
  return request<Job>("/api/jobs", {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

export function retryJob(jobId: string): Promise<Job> {
  return request<Job>(`/api/jobs/${encodeURIComponent(jobId)}/retry`, {
    method: "POST",
  });
}

export function cancelJob(jobId: string): Promise<Job> {
  return request<Job>(`/api/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: "POST",
  });
}

export function addVsamCustomer(customer: VsamCustomer): Promise<VsamCustomer> {
  return request<VsamCustomer>("/api/vsam/customers", {
    method: "POST",
    body: JSON.stringify(customer),
  });
}

export function updateVsamCustomer(customerId: string, name: string): Promise<VsamCustomer> {
  return request<VsamCustomer>(`/api/vsam/customers/${encodeURIComponent(customerId)}`, {
    method: "PUT",
    body: JSON.stringify({ name }),
  });
}

export function deleteVsamCustomer(customerId: string): Promise<void> {
  return request<void>(`/api/vsam/customers/${encodeURIComponent(customerId)}`, {
    method: "DELETE",
  });
}

export function createDataset(
  name: string,
  organization: string,
  records: string[],
): Promise<DatasetDetail> {
  return request<DatasetDetail>("/api/datasets", {
    method: "POST",
    body: JSON.stringify({ name, organization, records }),
  });
}

export function replaceDatasetRecords(name: string, records: string[]): Promise<DatasetDetail> {
  return request<DatasetDetail>(`/api/datasets/${encodeURIComponent(name)}/records`, {
    method: "PUT",
    body: JSON.stringify({ records }),
  });
}
