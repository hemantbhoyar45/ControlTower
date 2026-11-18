import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { appHead } from "@/lib/head";
import { displayJobStatus, jobQuery } from "@/lib/api";
import {
  PageHeader,
  StatusBadge,
  SectionTitle,
  Table,
  td,
  Skeleton,
  Empty,
} from "@/components/app/ui";

export const Route = createFileRoute("/_app/jobs/$jobId")({
  head: ({ params }) =>
    appHead(`Job ${params.jobId}`, `Execution details and output for job ${params.jobId}.`)(),
  component: JobDetail,
});

function formatDuration(startedAt: string | null, finishedAt: string | null): string {
  if (!startedAt || !finishedAt) return "—";
  const seconds = Math.max(0, Math.round((Date.parse(finishedAt) - Date.parse(startedAt)) / 1000));
  return `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, "0")}s`;
}

function JobDetail() {
  const { jobId } = Route.useParams();
  const { data: job, isLoading, error } = useQuery(jobQuery(jobId));
  if (isLoading)
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-40" />
      </div>
    );
  if (error)
    return (
      <p className="text-sm text-destructive" role="alert">
        {error.message}
      </p>
    );
  if (!job) return <Empty text={`Job ${jobId} was not found.`} />;

  const facts = [
    ["Job name", job.name],
    ["Return code", job.return_code === null ? "—" : String(job.return_code).padStart(4, "0")],
    ["Created", new Date(job.created_at).toLocaleString()],
    ["Started", job.started_at ? new Date(job.started_at).toLocaleString() : "—"],
    ["Finished", job.finished_at ? new Date(job.finished_at).toLocaleString() : "—"],
    ["Duration", formatDuration(job.started_at, job.finished_at)],
  ];

  return (
    <div>
      <Link
        to="/jobs"
        className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> All jobs
      </Link>
      <PageHeader
        title={job.name}
        subtitle={`Job ID · ${job.id}`}
        actions={<StatusBadge s={displayJobStatus(job.status)} />}
      />
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
        {facts.map(([label, value]) => (
          <div key={label} className="clay min-w-0 p-4">
            <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
              {label}
            </p>
            <p className="mt-1 truncate font-mono text-sm font-medium">{value}</p>
          </div>
        ))}
      </div>
      <div className="mt-6 grid gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">
          <section>
            <SectionTitle>Step execution</SectionTitle>
            {job.steps.length ? (
              <Table head={["Step", "Program", "Return code", "Executor", "Started", "Status"]}>
                {job.steps.map((step) => (
                  <tr key={step.id}>
                    <td className={`${td} font-mono text-xs`}>{step.name}</td>
                    <td className={`${td} font-mono text-xs`}>{step.program}</td>
                    <td className={`${td} font-mono text-xs`}>
                      {step.return_code === null ? "—" : String(step.return_code).padStart(4, "0")}
                    </td>
                    <td className={`${td} font-mono text-xs`}>{step.executor ?? "—"}</td>
                    <td className={`${td} font-mono text-xs`}>
                      {step.started_at ? new Date(step.started_at).toLocaleString() : "—"}
                    </td>
                    <td className={td}>
                      <StatusBadge s={displayJobStatus(step.status)} />
                    </td>
                  </tr>
                ))}
              </Table>
            ) : (
              <Empty text="No execution steps were recorded." />
            )}
          </section>
          <section>
            <SectionTitle>Submitted JCL</SectionTitle>
            <pre className="max-h-96 overflow-auto rounded-xl border border-border bg-navy p-4 font-mono text-xs leading-relaxed text-primary-foreground/90">
              {job.jcl}
            </pre>
          </section>
          <section>
            <SectionTitle>Execution output</SectionTitle>
            <pre className="max-h-96 overflow-auto rounded-xl border border-border bg-navy p-4 font-mono text-xs leading-relaxed text-primary-foreground/90">
              {job.stdout || job.stderr
                ? [job.stdout, job.stderr && `STDERR:\n${job.stderr}`].filter(Boolean).join("\n")
                : "No output recorded yet."}
            </pre>
          </section>
        </div>
        <aside>
          <SectionTitle>Execution engine</SectionTitle>
          <div className="flat-panel p-4 text-sm">
            <p className="text-muted-foreground">
              Each JCL step is executed in order by the backend queue. Step output and return codes
              are persisted in SQLite.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
