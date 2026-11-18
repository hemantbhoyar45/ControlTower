import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { appHead } from "@/lib/head";
import { failuresQuery } from "@/lib/api";
import { Empty, PageHeader, Table, TableSkeleton, td } from "@/components/app/ui";

export const Route = createFileRoute("/_app/failures")({
  head: appHead("Failures", "Persisted failed batch jobs, return codes, and spool diagnostics."),
  component: FailuresPage,
});

function FailuresPage() {
  const { data, isLoading, error } = useQuery(failuresQuery());
  return (
    <div>
      <PageHeader title="Failures" subtitle="Failed jobs and their persisted COBOL diagnostics" />
      {error && (
        <p className="mb-4 text-sm text-destructive" role="alert">
          {error.message}
        </p>
      )}
      {isLoading ? (
        <TableSkeleton />
      ) : !data?.length ? (
        <Empty text="No failed batch jobs have been recorded." />
      ) : (
        <Table head={["Job", "Severity", "Return code", "Failure output", "Detected"]}>
          {data.map((failure) => (
            <tr key={failure.id} className="align-top hover:bg-surface">
              <td className={td}>
                <Link
                  to="/jobs/$jobId"
                  params={{ jobId: failure.job }}
                  className="font-mono font-medium text-navy hover:underline"
                >
                  {failure.job}
                </Link>
              </td>
              <td className={td}>
                <span className="rounded-full bg-destructive/10 px-2 py-0.5 text-xs font-medium text-destructive">
                  Failed
                </span>
              </td>
              <td className={`${td} font-mono text-xs text-destructive`}>{failure.code}</td>
              <td className="max-w-xl whitespace-pre-wrap px-4 py-2.5 text-xs">{failure.type}</td>
              <td className={`${td} font-mono text-xs`}>
                {new Date(failure.time).toLocaleString()}
              </td>
            </tr>
          ))}
        </Table>
      )}
    </div>
  );
}
