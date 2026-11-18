import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { appHead } from "@/lib/head";
import { cancelJob, jobsQuery, retryJob } from "@/lib/api";
import { Empty, PageHeader, Table, TableSkeleton, td } from "@/components/app/ui";

export const Route = createFileRoute("/_app/recovery")({
  head: appHead("Recovery", "Retry failed workloads or cancel jobs in the controlled queue."),
  component: RecoveryPage,
});

function RecoveryPage() {
  const queryClient = useQueryClient();
  const { data: jobs, isLoading, error } = useQuery(jobsQuery());
  const recovery = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "retry" | "cancel" }) =>
      action === "retry" ? retryJob(id) : cancelJob(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["jobs"] });
      await queryClient.invalidateQueries({ queryKey: ["reports"] });
    },
  });
  const actionable = (jobs ?? []).filter((job) =>
    ["failed", "queued", "running"].includes(job.status),
  );

  return (
    <div>
      <PageHeader
        title="Recovery"
        subtitle="Retry failed persisted jobs or cancel queued/running work in the JES2-inspired queue."
      />
      {error && (
        <p className="mb-4 text-sm text-destructive" role="alert">
          {error.message}
        </p>
      )}
      {recovery.error && (
        <p className="mb-4 text-sm text-destructive" role="alert">
          {recovery.error.message}
        </p>
      )}
      {isLoading ? (
        <TableSkeleton />
      ) : !actionable.length ? (
        <Empty text="No failed or active jobs require recovery." />
      ) : (
        <Table head={["Job", "Status", "Return code", "Execution steps", "Recovery action"]}>
          {actionable.map((job) => (
            <tr key={job.id} className="align-top">
              <td className={`${td} font-mono text-xs font-medium text-navy`}>{job.name}</td>
              <td className={`${td} capitalize`}>{job.status}</td>
              <td className={`${td} font-mono text-xs`}>{job.return_code ?? "—"}</td>
              <td className={`${td} font-mono text-xs`}>
                {job.steps.map((step) => `${step.name}:${step.status}`).join(", ")}
              </td>
              <td className={td}>
                <div className="flex flex-wrap gap-2">
                  {job.status === "failed" && (
                    <button
                      type="button"
                      disabled={recovery.isPending}
                      onClick={() => recovery.mutate({ id: job.id, action: "retry" })}
                      className="rounded border border-border px-2.5 py-1 text-xs font-medium hover:bg-muted disabled:opacity-50"
                    >
                      Retry
                    </button>
                  )}
                  {(job.status === "queued" || job.status === "running") && (
                    <button
                      type="button"
                      disabled={recovery.isPending}
                      onClick={() => recovery.mutate({ id: job.id, action: "cancel" })}
                      className="rounded border border-destructive/30 px-2.5 py-1 text-xs font-medium text-destructive hover:bg-destructive/5 disabled:opacity-50"
                    >
                      Cancel
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </Table>
      )}
    </div>
  );
}
