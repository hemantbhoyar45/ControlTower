import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { appHead } from "@/lib/head";
import { reportJobsQuery, reportSummaryQuery } from "@/lib/api";
import { Empty, PageHeader, SectionTitle, Skeleton, Table, td } from "@/components/app/ui";

export const Route = createFileRoute("/_app/reports")({
  head: appHead("Reports", "Batch execution success rate, job volume and processing time."),
  component: ReportsPage,
});

const axis = {
  tick: { fontSize: 11, fill: "var(--muted-foreground)" },
  axisLine: false,
  tickLine: false,
};

function formatDuration(seconds: number): string {
  if (!seconds) return "—";
  const minutes = Math.floor(seconds / 60);
  const remainder = Math.round(seconds % 60);
  return minutes ? `${minutes}m ${remainder}s` : `${remainder}s`;
}

function ReportsPage() {
  const { data: report, isLoading, error } = useQuery(reportSummaryQuery());
  const { data: cobolReports, error: cobolReportsError } = useQuery(reportJobsQuery());
  return (
    <div>
      <PageHeader title="Reports" subtitle="Aggregated from persisted backend job history" />
      {error && (
        <p className="mb-4 text-sm text-destructive" role="alert">
          {error.message}
        </p>
      )}
      {cobolReportsError && (
        <p className="mb-4 text-sm text-destructive" role="alert">
          {cobolReportsError.message}
        </p>
      )}
      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-24" />
          ))}
        </div>
      ) : report ? (
        <>
          <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-3">
            {[
              ["Success rate", `${report.success_rate}%`],
              ["Jobs submitted", report.total_jobs.toLocaleString()],
              ["Failed jobs", report.failed_jobs.toLocaleString()],
              ["Cancelled jobs", report.cancelled_jobs.toLocaleString()],
              ["Active jobs", report.active_jobs.toLocaleString()],
              ["Completed jobs", report.completed_jobs.toLocaleString()],
              ["Avg runtime", formatDuration(report.avg_duration_seconds)],
            ].map(([label, value]) => (
              <div key={label} className="clay p-4">
                <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                  {label}
                </p>
                <p className="mt-1 text-2xl font-semibold text-navy">{value}</p>
              </div>
            ))}
          </div>
          {report.daily.length ? (
            <div className="grid gap-6 lg:grid-cols-2">
              <section>
                <SectionTitle>Daily success rate (%)</SectionTitle>
                <div className="flat-panel h-72 p-4">
                  <ResponsiveContainer>
                    <LineChart data={report.daily} margin={{ left: -20, right: 8, top: 8 }}>
                      <CartesianGrid
                        strokeDasharray="3 3"
                        stroke="var(--border)"
                        vertical={false}
                      />
                      <XAxis dataKey="date" {...axis} />
                      <YAxis domain={[0, 100]} {...axis} />
                      <Tooltip contentStyle={{ borderRadius: 12, fontSize: 12 }} />
                      <Line
                        dataKey="success_rate"
                        name="Success rate"
                        stroke="var(--success)"
                        strokeWidth={2.5}
                        dot={{ r: 3 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </section>
              <section>
                <SectionTitle>Daily job volume</SectionTitle>
                <div className="flat-panel h-72 p-4">
                  <ResponsiveContainer>
                    <BarChart data={report.daily} margin={{ left: -20, right: 8, top: 8 }}>
                      <CartesianGrid
                        strokeDasharray="3 3"
                        stroke="var(--border)"
                        vertical={false}
                      />
                      <XAxis dataKey="date" {...axis} />
                      <YAxis allowDecimals={false} {...axis} />
                      <Tooltip contentStyle={{ borderRadius: 12, fontSize: 12 }} />
                      <Bar
                        dataKey="jobs"
                        name="Jobs submitted"
                        fill="var(--navy)"
                        radius={[6, 6, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </section>
            </div>
          ) : (
            <Empty text="No jobs have been submitted in the last seven days." />
          )}
          <section className="mt-8">
            <SectionTitle>COBOL-generated reports</SectionTitle>
            {cobolReports?.length ? (
              <Table head={["Job", "Status", "Return code", "Generated output"]}>
                {cobolReports.map((job) => (
                  <tr key={job.id} className="align-top">
                    <td className={`${td} font-mono text-xs font-medium`}>{job.name}</td>
                    <td className={`${td} capitalize`}>{job.status}</td>
                    <td className={`${td} font-mono text-xs`}>{job.return_code ?? "—"}</td>
                    <td className="max-w-2xl whitespace-pre-wrap px-4 py-2.5 font-mono text-xs">
                      {job.stdout || job.stderr || "Report job is still running."}
                    </td>
                  </tr>
                ))}
              </Table>
            ) : (
              <Empty text="Submit a JCL job with EXEC PGM=REPORT to generate a COBOL report." />
            )}
          </section>
        </>
      ) : !error ? (
        <Empty text="Report data is unavailable." />
      ) : null}
    </div>
  );
}
