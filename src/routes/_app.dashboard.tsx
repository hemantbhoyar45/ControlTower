import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, ArrowRight, ListChecks, Network, LifeBuoy } from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { appHead } from "@/lib/head";
import { displayJobStatus, jobsQuery, metricsQuery, reportSummaryQuery } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Empty, PageHeader, SectionTitle, StatusBadge, TableSkeleton } from "@/components/app/ui";

export const Route = createFileRoute("/_app/dashboard")({
  head: appHead(
    "Operations Dashboard",
    "Live overview of persisted batch jobs, execution status and recent activity.",
  ),
  component: Dashboard,
});

function Dashboard() {
  const queryClient = useQueryClient();
  const jobsQueryResult = useQuery(jobsQuery());
  const reportQueryResult = useQuery(reportSummaryQuery());
  const metricsQueryResult = useQuery(metricsQuery());
  const jobs = jobsQueryResult.data ?? [];
  const report = reportQueryResult.data;
  const metrics = metricsQueryResult.data;
  const priorityJobs = [...jobs]
    .sort((a, b) => {
      const priority = {
        failed: 0,
        running: 1,
        queued: 2,
        completed: 3,
        blocked: 4,
        cancelled: 5,
      };
      return (
        priority[a.status] - priority[b.status] ||
        b.created_at.localeCompare(a.created_at)
      );
    })
    .slice(0, 8);

  const refresh = () => {
    void Promise.all([
      queryClient.invalidateQueries({ queryKey: ["jobs"] }),
      queryClient.invalidateQueries({ queryKey: ["reports"] }),
      queryClient.invalidateQueries({ queryKey: ["metrics"] }),
    ]);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Operations Overview"
        subtitle="Live view of the FastAPI job queue and SQLite execution history"
        actions={
          <Button variant="outline" size="sm" onClick={refresh}>
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </Button>
        }
      />
      {(jobsQueryResult.error || reportQueryResult.error || metricsQueryResult.error) && (
        <p className="text-sm text-destructive" role="alert">
          {jobsQueryResult.error?.message ??
            reportQueryResult.error?.message ??
            metricsQueryResult.error?.message}
        </p>
      )}
      <section aria-label="Operations shortcuts" className="grid gap-4 md:grid-cols-3">
        {[
          {
            to: "/jobs",
            title: "Browse jobs",
            description: "Submit batch JCL, inspect execution steps and return codes.",
            icon: ListChecks,
            tone: "bg-icon-blue text-primary",
          },
          {
            to: "/dependencies",
            title: "Trace dependencies",
            description: "Explore the dependency map for the demonstration workload.",
            icon: Network,
            tone: "bg-icon-teal text-ai",
          },
          {
            to: "/recovery",
            title: "Review recovery",
            description: "Review the available recovery workflow.",
            icon: LifeBuoy,
            tone: "bg-icon-green text-success",
          },
        ].map((item) => (
          <Link
            key={item.to}
            to={item.to}
            className="reference-heading block p-5 transition hover:border-ring/40 hover:bg-surface"
          >
            <span className={`icon-tile ${item.tone}`}>
              <item.icon className="h-5 w-5" strokeWidth={1.7} />
            </span>
            <h2 className="mt-4 text-base font-semibold">{item.title}</h2>
            <p className="mt-1 min-h-10 text-sm leading-relaxed text-muted-foreground">
              {item.description}
            </p>
            <span className="mt-4 inline-flex items-center gap-1 text-sm text-primary">
              Open <ArrowRight className="h-3.5 w-3.5" />
            </span>
          </Link>
        ))}
      </section>
      <section aria-label="Batch summary">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {[
            ["Total jobs", report?.total_jobs ?? "—"],
            ["Active", metrics ? metrics.queued_jobs + metrics.running_jobs : "—"],
            ["Completed", report?.completed_jobs ?? "—"],
            ["Failed", report?.failed_jobs ?? "—"],
            ["Success rate", report ? `${report.success_rate}%` : "—"],
            ["Avg runtime", report ? `${Math.round(report.avg_duration_seconds)}s` : "—"],
            ["Queue depth", metrics?.queue_depth ?? "—"],
            ["Database", metrics ? `${(metrics.database_bytes / 1024).toFixed(1)} KB` : "—"],
          ].map(([label, value]) => (
            <div key={label} className="console-kpi p-4">
              <p className="text-[10px] uppercase text-muted-foreground">{label}</p>
              <p className="mt-1 font-mono text-2xl font-medium text-navy">{value}</p>
            </div>
          ))}
        </div>
      </section>
      {metrics && (
        <p className="text-xs text-muted-foreground">
          COBOL execution engine: <span className="font-mono">{metrics.executor}</span>
          {metrics.gnucobol_available
            ? " · GnuCOBOL compiler available"
            : " · GnuCOBOL unavailable; only the documented COBOL subset interpreter can run"}
        </p>
      )}
      <div className="grid gap-5 xl:grid-cols-2">
        <section className="min-w-0">
          <SectionTitle
            right={
              <Link to="/jobs" className="text-xs font-medium text-ai hover:underline">
                All jobs →
              </Link>
            }
          >
            Job queue · attention first
          </SectionTitle>
          {jobsQueryResult.isLoading ? (
            <TableSkeleton />
          ) : priorityJobs.length === 0 ? (
            <Empty text="No jobs have been submitted yet. Submit JCL from the Jobs page." />
          ) : (
            <div className="console-panel overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border bg-surface text-[11px] uppercase text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3 font-semibold">Job / program</th>
                    <th className="px-3 py-3 font-semibold">Status</th>
                    <th className="px-3 py-3 font-semibold">RC</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {priorityJobs.map((job) => (
                    <tr key={job.id} className="hover:bg-surface">
                      <td className="px-4 py-3">
                        <Link
                          to="/jobs/$jobId"
                          params={{ jobId: job.id }}
                          className="font-mono font-semibold text-navy hover:underline"
                        >
                          {job.name}
                        </Link>
                        <span className="block font-mono text-[11px] text-muted-foreground">
                          {job.steps.map((step) => step.program).join(", ") || "No steps"}
                        </span>
                      </td>
                      <td className="px-3 py-3">
                        <StatusBadge s={displayJobStatus(job.status)} />
                      </td>
                      <td className="px-3 py-3 font-mono text-xs">{job.return_code ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
        <section className="min-w-0">
          <SectionTitle>Seven-day execution activity</SectionTitle>
          <div className="console-panel h-72 p-4">
            {report?.daily.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={report.daily} margin={{ left: -20, right: 8, top: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                    axisLine={false}
                    tickLine={false}
                    allowDecimals={false}
                  />
                  <Tooltip
                    contentStyle={{
                      borderRadius: 6,
                      border: "1px solid var(--border)",
                      fontSize: 12,
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="completed"
                    name="Completed"
                    stroke="var(--success)"
                    fill="var(--success)"
                    fillOpacity={0.08}
                    strokeWidth={2}
                  />
                  <Area
                    type="monotone"
                    dataKey="failed"
                    name="Failed"
                    stroke="var(--destructive)"
                    fill="var(--destructive)"
                    fillOpacity={0.06}
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : reportQueryResult.isLoading ? (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                Loading report data…
              </div>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                No jobs in the last seven days.
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
