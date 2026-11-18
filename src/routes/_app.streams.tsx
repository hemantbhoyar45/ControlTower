import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { appHead } from "@/lib/head";
import { displayJobStatus, jobsQuery } from "@/lib/api";
import { Empty, PageHeader, StatusBadge, Table, TableSkeleton, td } from "@/components/app/ui";

export const Route = createFileRoute("/_app/streams")({
  head: appHead(
    "Batch Streams",
    "Live job steps and execution state from the controlled batch queue.",
  ),
  component: StreamsPage,
});

function StreamsPage() {
  const { data: jobs, isLoading, error } = useQuery(jobsQuery());
  const steps = (jobs ?? []).flatMap((job) => job.steps.map((step) => ({ job, step })));
  const running = (jobs ?? []).filter((job) => job.status === "running").length;
  const failed = (jobs ?? []).filter((job) => job.status === "failed").length;

  return (
    <div>
      <PageHeader
        title="Batch Streams"
        subtitle="Execution steps recorded by the JES2-inspired job queue"
      />
      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        {[
          ["Jobs", jobs?.length ?? "—"],
          ["Steps", steps.length],
          ["Running", running],
          ["Failed", failed],
        ].map(([label, value]) => (
          <div key={label} className="console-kpi p-4">
            <p className="text-[10px] uppercase text-muted-foreground">{label}</p>
            <p className="mt-1 font-mono text-2xl font-medium text-navy">{value}</p>
          </div>
        ))}
      </div>
      {error && (
        <p className="mb-4 text-sm text-destructive" role="alert">
          {error.message}
        </p>
      )}
      {isLoading ? (
        <TableSkeleton />
      ) : !steps.length ? (
        <Empty text="No JCL execution steps have been recorded yet." />
      ) : (
        <Table head={["Job", "Step", "Program", "Status", "Return code", "Started", "Finished"]}>
          {steps.map(({ job, step }) => (
            <tr key={step.id} className="hover:bg-surface">
              <td className={td}>
                <Link
                  to="/jobs/$jobId"
                  params={{ jobId: job.id }}
                  className="font-mono text-xs font-medium text-navy hover:underline"
                >
                  {job.name}
                </Link>
              </td>
              <td className={`${td} font-mono text-xs`}>{step.name}</td>
              <td className={`${td} font-mono text-xs`}>{step.program}</td>
              <td className={td}>
                <StatusBadge s={displayJobStatus(step.status)} />
              </td>
              <td className={`${td} font-mono text-xs`}>{step.return_code ?? "—"}</td>
              <td className={`${td} font-mono text-xs`}>
                {step.started_at ? new Date(step.started_at).toLocaleString() : "—"}
              </td>
              <td className={`${td} font-mono text-xs`}>
                {step.finished_at ? new Date(step.finished_at).toLocaleString() : "—"}
              </td>
            </tr>
          ))}
        </Table>
      )}
    </div>
  );
}
