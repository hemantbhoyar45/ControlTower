import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState, type FormEvent } from "react";
import { ArrowUpDown } from "lucide-react";
import { appHead } from "@/lib/head";
import { displayJobStatus, jobsQuery, submitJob, type JobStatus } from "@/lib/api";
import { PageHeader, StatusBadge, Table, td, TableSkeleton, Empty } from "@/components/app/ui";

export const Route = createFileRoute("/_app/jobs/")({
  head: appHead("Jobs", "Batch jobs, execution status, return codes and timing."),
  component: JobsPage,
});

const statuses: ("all" | JobStatus)[] = ["all", "queued", "running", "completed", "failed", "cancelled"];

function JobsPage() {
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useQuery(jobsQuery());
  const [q, setQ] = useState("");
  const [st, setSt] = useState<(typeof statuses)[number]>("all");
  const [asc, setAsc] = useState(true);
  const [content, setContent] = useState("");
  const submission = useMutation({
    mutationFn: submitJob,
    onSuccess: async (job) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["jobs"] }),
        queryClient.invalidateQueries({ queryKey: ["jobs", job.id] }),
      ]);
      setContent("");
    },
  });
  const rows = useMemo(
    () =>
      (data ?? [])
        .filter(
          (job) =>
            (st === "all" || job.status === st) &&
            `${job.name} ${job.id} ${job.steps.map((step) => step.program).join(" ")}`
              .toLowerCase()
              .includes(q.toLowerCase()),
        )
        .sort((a, b) => (asc ? 1 : -1) * a.created_at.localeCompare(b.created_at)),
    [data, q, st, asc],
  );

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    submission.mutate(content);
  }

  return (
    <div>
      <PageHeader
        title="Jobs"
        subtitle="Submit and monitor persisted batch jobs"
        actions={
          <details className="relative">
            <summary className="cursor-pointer rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground">
              Submit JCL
            </summary>
            <form
              onSubmit={handleSubmit}
              className="absolute right-0 z-10 mt-2 w-[min(90vw,34rem)] rounded-xl border border-border bg-card p-4 shadow-xl"
            >
              <label htmlFor="job-jcl" className="text-sm font-medium">
                JCL source
              </label>
              <textarea
                id="job-jcl"
                required
                minLength={1}
                maxLength={1_000_000}
                value={content}
                onChange={(event) => setContent(event.target.value)}
                placeholder={"//SAMPLE JOB (ACCT),'DEMO'\n//STEP01 EXEC PGM=GREET"}
                className="mt-2 min-h-40 w-full rounded-lg border border-border bg-background p-3 font-mono text-xs"
              />
              {submission.error && (
                <p className="mt-2 text-sm text-destructive" role="alert">
                  {submission.error.message}
                </p>
              )}
              {submission.data && (
                <p className="mt-2 text-sm text-success" role="status">
                  Submitted job {submission.data.name}.
                </p>
              )}
              <button
                type="submit"
                disabled={submission.isPending || !content.trim()}
                className="mt-3 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
              >
                {submission.isPending ? "Submitting…" : "Submit job"}
              </button>
            </form>
          </details>
        }
      />
      {error && (
        <p className="mb-4 text-sm text-destructive" role="alert">
          {error.message}
        </p>
      )}
      <div className="mb-4 flex flex-wrap gap-2">
        <input
          value={q}
          onChange={(event) => setQ(event.target.value)}
          placeholder="Filter by job or program"
          className="h-9 w-56 rounded-lg border border-border bg-card px-3 text-sm outline-none focus:ring-2 focus:ring-ring/20"
        />
        <div className="flex flex-wrap gap-1 rounded-lg border border-border bg-card p-1">
          {statuses.map((status) => (
            <button
              key={status}
              onClick={() => setSt(status)}
              className={`rounded-md px-2.5 py-1 text-xs capitalize ${st === status ? "bg-navy text-primary-foreground" : "hover:bg-muted"}`}
            >
              {status}
            </button>
          ))}
        </div>
        <button
          onClick={() => setAsc((value) => !value)}
          className="ml-auto inline-flex items-center gap-1 text-xs text-muted-foreground"
        >
          <ArrowUpDown className="h-3.5 w-3.5" /> Sort {asc ? "oldest first" : "newest first"}
        </button>
      </div>
      {isLoading ? (
        <TableSkeleton />
      ) : rows.length === 0 ? (
        <Empty text="No jobs match these filters." />
      ) : (
        <Table head={["Job", "Steps / programs", "Status", "Return code", "Created", "Finished"]}>
          {rows.map((job) => (
            <tr key={job.id} className="hover:bg-surface">
              <td className={td}>
                <Link
                  to="/jobs/$jobId"
                  params={{ jobId: job.id }}
                  className="font-mono font-medium text-navy hover:underline"
                >
                  {job.name}
                </Link>
                <span className="block max-w-48 truncate font-mono text-[10px] text-muted-foreground">
                  {job.id}
                </span>
              </td>
              <td className={`${td} font-mono text-xs`}>
                {job.steps.map((step) => step.program).join(", ") || "—"}
              </td>
              <td className={td}>
                <StatusBadge s={displayJobStatus(job.status)} />
              </td>
              <td
                className={`${td} font-mono text-xs ${job.status === "failed" ? "text-destructive" : ""}`}
              >
                {job.return_code === null ? "—" : String(job.return_code).padStart(4, "0")}
              </td>
              <td className={`${td} font-mono text-xs`}>
                {new Date(job.created_at).toLocaleString()}
              </td>
              <td className={`${td} font-mono text-xs`}>
                {job.finished_at ? new Date(job.finished_at).toLocaleString() : "—"}
              </td>
            </tr>
          ))}
        </Table>
      )}
    </div>
  );
}
