import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { appHead } from "@/lib/head";
import { inspectJcl, jobQuery, submitJob, validateJcl, type Job } from "@/lib/api";
import { Empty, PageHeader, SectionTitle, StatusBadge } from "@/components/app/ui";
import {
  CheckCircle2,
  AlertTriangle,
  AlertOctagon,
  ShieldAlert,
  Terminal,
  Play,
  RotateCcw,
  FileCode,
  Clock,
  Cpu,
  Info,
} from "lucide-react";

export const Route = createFileRoute("/_app/jcl-studio")({
  head: appHead("JCL Studio", "Validate, classify, and execute controlled JCL batch jobs."),
  component: JclStudioPage,
});

interface JclDemoScenario {
  id: string;
  title: string;
  tag: string;
  expectedRc: string;
  classification: "SUCCESS" | "WARNING" | "CRITICAL ERROR" | "ADVANCED CRITICAL ERROR";
  badgeBg: string;
  badgeBorder: string;
  badgeText: string;
  summary: string;
  program: string;
  jcl: string;
}

const DEMO_SCENARIOS: JclDemoScenario[] = [
  {
    id: "success",
    title: "Demo 1 · Valid Transaction",
    tag: "SUCCESS",
    expectedRc: "RC 0000",
    classification: "SUCCESS",
    badgeBg: "bg-emerald-500/10",
    badgeBorder: "border-emerald-500/30",
    badgeText: "text-emerald-700 dark:text-emerald-400",
    summary: "Reads valid transaction record, verifies account balance, updates ledger, and exits with RC 0000.",
    program: "TRNSUCC",
    jcl: `//TRNSUCC  JOB (ACCT),'TXN PROCESS - SUCCESS'
//STEP001  EXEC PGM=TRNSUCC
//SYSIN    DD *
TXN-902100
/*
//SYSOUT   DD SYSOUT=*`,
  },
  {
    id: "warning",
    title: "Demo 2 · Policy Warning",
    tag: "WARNING",
    expectedRc: "RC 0004",
    classification: "WARNING",
    badgeBg: "bg-amber-500/10",
    badgeBorder: "border-amber-500/30",
    badgeText: "text-amber-700 dark:text-amber-400",
    summary: "Detects transaction exceeding daily soft limit, logs audit exception, continues processing, and exits with RC 0004.",
    program: "TRNWARN",
    jcl: `//TRNWARN  JOB (ACCT),'TXN PROCESS - WARNING'
//STEP001  EXEC PGM=TRNWARN
//SYSIN    DD *
TXN-902104
/*
//SYSOUT   DD SYSOUT=*`,
  },
  {
    id: "critical",
    title: "Demo 3 · Invalid Account",
    tag: "CRITICAL ERROR",
    expectedRc: "RC 0008",
    classification: "CRITICAL ERROR",
    badgeBg: "bg-rose-500/10",
    badgeBorder: "border-rose-500/30",
    badgeText: "text-rose-700 dark:text-rose-400",
    summary: "Account identifier not found in master ledger; transaction posting rejected with controlled failure RC 0008.",
    program: "TRNERR",
    jcl: `//TRNERR   JOB (ACCT),'TXN PROCESS - CRITICAL'
//STEP001  EXEC PGM=TRNERR
//SYSIN    DD *
TXN-902108
/*
//SYSOUT   DD SYSOUT=*`,
  },
  {
    id: "adv-critical",
    title: "Demo 4 · Subsystem Abend",
    tag: "ADVANCED CRITICAL ERROR",
    expectedRc: "RC 0012",
    classification: "ADVANCED CRITICAL ERROR",
    badgeBg: "bg-purple-500/10",
    badgeBorder: "border-purple-500/30",
    badgeText: "text-purple-700 dark:text-purple-400",
    summary: "Simulated journal commit integrity failure & VSAM corruption abend requiring emergency manual recovery RC 0012.",
    program: "TRNCRIT",
    jcl: `//TRNCRIT  JOB (ACCT),'TXN PROCESS - ADV CRIT'
//STEP001  EXEC PGM=TRNCRIT
//SYSIN    DD *
TXN-902112
/*
//SYSOUT   DD SYSOUT=*`,
  },
];

function formatDuration(startedAt?: string | null, finishedAt?: string | null): string {
  if (!startedAt || !finishedAt) return "—";
  try {
    const diff = (new Date(finishedAt).getTime() - new Date(startedAt).getTime()) / 1000;
    return `${Math.max(0, diff).toFixed(2)}s`;
  } catch {
    return "—";
  }
}

function getClassificationMeta(job: Job) {
  const rc = job.return_code;
  if (rc === 0) {
    return {
      classification: "SUCCESS",
      rcCode: "RC 0000",
      icon: CheckCircle2,
      bannerBg: "bg-emerald-500/10 border-emerald-500/30",
      badgeBg: "bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border-emerald-500/30",
      textClass: "text-emerald-700 dark:text-emerald-400",
      description: "JCL is valid. Execution completed normally with zero errors.",
    };
  }
  if (rc === 4) {
    return {
      classification: "WARNING",
      rcCode: "RC 0004",
      icon: AlertTriangle,
      bannerBg: "bg-amber-500/10 border-amber-500/30",
      badgeBg: "bg-amber-500/20 text-amber-700 dark:text-amber-300 border-amber-500/30",
      textClass: "text-amber-700 dark:text-amber-400",
      description: "JCL is valid. Completed with minor warning or policy exception (execution was not halted).",
    };
  }
  if (rc === 8) {
    return {
      classification: "CRITICAL ERROR",
      rcCode: "RC 0008",
      icon: AlertOctagon,
      bannerBg: "bg-rose-500/10 border-rose-500/30",
      badgeBg: "bg-rose-500/20 text-rose-700 dark:text-rose-300 border-rose-500/30",
      textClass: "text-rose-700 dark:text-rose-400",
      description: "Job execution encountered an error condition. Step failed and processing halted.",
    };
  }
  if (rc === 12) {
    return {
      classification: "ADVANCED CRITICAL ERROR",
      rcCode: "RC 0012",
      icon: ShieldAlert,
      bannerBg: "bg-purple-500/10 border-purple-500/30",
      badgeBg: "bg-purple-500/20 text-purple-700 dark:text-purple-300 border-purple-500/30",
      textClass: "text-purple-700 dark:text-purple-400",
      description: "Severe system-level execution failure. Manual disaster recovery or operator attention required.",
    };
  }
  if (rc === 130) {
    return {
      classification: "CANCELLED",
      rcCode: "RC 0130",
      icon: AlertTriangle,
      bannerBg: "bg-muted border-border",
      badgeBg: "bg-muted text-muted-foreground border-border",
      textClass: "text-muted-foreground",
      description: "Job was cancelled prior to or during execution.",
    };
  }
  if (rc !== null && rc > 0) {
    const isAdv = rc >= 12;
    const isCrit = rc >= 8;
    const code = `RC ${String(rc).padStart(4, "0")}`;
    return {
      classification: isAdv ? "ADVANCED CRITICAL ERROR" : isCrit ? "CRITICAL ERROR" : "WARNING",
      rcCode: code,
      icon: isAdv ? ShieldAlert : isCrit ? AlertOctagon : AlertTriangle,
      bannerBg: isAdv ? "bg-purple-500/10 border-purple-500/30" : isCrit ? "bg-rose-500/10 border-rose-500/30" : "bg-amber-500/10 border-amber-500/30",
      badgeBg: isAdv ? "bg-purple-500/20 text-purple-700 border-purple-500/30" : isCrit ? "bg-rose-500/20 text-rose-700 border-rose-500/30" : "bg-amber-500/20 text-amber-700 border-amber-500/30",
      textClass: isAdv ? "text-purple-700" : isCrit ? "text-rose-700" : "text-amber-700",
      description: `Job completed with code ${code}.`,
    };
  }
  if (job.status === "running") {
    return {
      classification: "IN EXECUTION",
      rcCode: "RC ----",
      icon: Cpu,
      bannerBg: "bg-info/10 border-info/30",
      badgeBg: "bg-info/20 text-info border-info/30",
      textClass: "text-info",
      description: "Job is currently executing in the JES2 processor.",
    };
  }
  return {
    classification: "QUEUED",
    rcCode: "RC ----",
    icon: Clock,
    bannerBg: "bg-muted/50 border-border",
    badgeBg: "bg-muted text-muted-foreground border-border",
    textClass: "text-muted-foreground",
    description: "Job is waiting in queue for JES2 worker dispatch.",
  };
}

function JclStudioPage() {
  const queryClient = useQueryClient();
  const [content, setContent] = useState(DEMO_SCENARIOS[0]!.jcl);
  const [activeScenarioId, setActiveScenarioId] = useState<string>("success");
  const [validatedContent, setValidatedContent] = useState("");
  const [jobId, setJobId] = useState("");

  const validation = useMutation({
    mutationFn: validateJcl,
    onSuccess: (_, source) => {
      setValidatedContent(source);
    },
  });

  const inspection = useMutation({
    mutationFn: inspectJcl,
  });

  const submission = useMutation({
    mutationFn: submitJob,
    onSuccess: async (job) => {
      setJobId(job.id);
      await queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });

  const execution = useQuery({ ...jobQuery(jobId), enabled: Boolean(jobId) });
  const isValidated = Boolean(validation.data && validatedContent === content);

  function handleSelectScenario(scenario: JclDemoScenario) {
    setActiveScenarioId(scenario.id);
    setContent(scenario.jcl);
    setValidatedContent("");
    validation.reset();
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isValidated) {
      submission.mutate(content);
    }
  }

  const job = execution.data;
  const classificationMeta = job ? getClassificationMeta(job) : null;
  const programsInJob = job ? Array.from(new Set(job.steps.map((s) => s.program))).join(", ") : "";

  return (
    <div className="space-y-6">
      <PageHeader
        title="JCL Studio"
        subtitle="Validate JCL syntax, inspect statements, and classify batch jobs into project return-code categories."
      />

      {/* Demo Scenario Selectors */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <SectionTitle>Four Job Classification Scenarios</SectionTitle>
          <span className="text-xs text-muted-foreground">Select a scenario to populate the editor</span>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {DEMO_SCENARIOS.map((sc) => {
            const isSelected = activeScenarioId === sc.id;
            return (
              <button
                key={sc.id}
                type="button"
                onClick={() => handleSelectScenario(sc)}
                className={`flex flex-col justify-between rounded-lg border p-3.5 text-left transition ${
                  isSelected
                    ? "border-primary bg-primary/5 ring-1 ring-primary"
                    : "border-border bg-card hover:border-primary/40 hover:bg-muted/40"
                }`}
              >
                <div>
                  <div className="flex items-center justify-between gap-1">
                    <span className="font-mono text-xs font-bold text-navy dark:text-foreground">
                      {sc.expectedRc}
                    </span>
                    <span
                      className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase ${sc.badgeBg} ${sc.badgeBorder} ${sc.badgeText}`}
                    >
                      {sc.tag}
                    </span>
                  </div>
                  <h3 className="mt-1.5 text-xs font-semibold text-foreground">{sc.title}</h3>
                  <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-muted-foreground">
                    {sc.summary}
                  </p>
                </div>
                <div className="mt-3 flex items-center justify-between pt-2 text-[10px] text-muted-foreground border-t border-border/60">
                  <span className="font-mono">PGM={sc.program}</span>
                  <span className={isSelected ? "font-semibold text-primary" : "text-muted-foreground"}>
                    {isSelected ? "Active in Editor" : "Load Scenario"}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </section>

      {/* Main Grid: Editor & Validation / Results */}
      <div className="grid gap-6 xl:grid-cols-2">
        {/* Left Column: JCL Editor */}
        <form onSubmit={handleSubmit} className="console-panel space-y-4 p-4 sm:p-5">
          <div className="flex items-center justify-between">
            <label htmlFor="jcl-source" className="flex items-center gap-2 text-sm font-semibold">
              <FileCode className="h-4 w-4 text-primary" />
              <span>JCL Source Editor</span>
            </label>
            <span className="font-mono text-xs text-muted-foreground">
              {content.split("\n").length} lines · {content.length} bytes
            </span>
          </div>

          <div className="relative">
            <textarea
              id="jcl-source"
              required
              maxLength={1_000_000}
              spellCheck={false}
              value={content}
              onChange={(event) => {
                setContent(event.target.value);
                setValidatedContent("");
              }}
              className="min-h-[22rem] w-full rounded-lg border border-border bg-navy p-4 font-mono text-xs leading-relaxed text-primary-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              placeholder="//JOBNAME JOB (ACCT),'TITLE'..."
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => validation.mutate(content)}
                disabled={validation.isPending || !content.trim()}
                className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3.5 py-2 text-sm font-medium hover:bg-muted disabled:opacity-50"
              >
                <Terminal className="h-4 w-4" />
                <span>{validation.isPending ? "Validating JCL…" : "Validate JCL"}</span>
              </button>

              <button
                type="submit"
                disabled={!isValidated || submission.isPending}
                className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                <Play className="h-4 w-4 fill-current" />
                <span>{submission.isPending ? "Submitting to JES2…" : "Submit Batch Job"}</span>
              </button>
            </div>

            <button
              type="button"
              onClick={() => {
                const sc = DEMO_SCENARIOS.find((s) => s.id === activeScenarioId);
                const jcl = sc?.jcl ?? DEMO_SCENARIOS[0]!.jcl;
                setContent(jcl);
                setValidatedContent("");
                validation.reset();
              }}
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            >
              <RotateCcw className="h-3 w-3" />
              <span>Reset Template</span>
            </button>
          </div>

          {/* Validation Error Alert */}
          {validation.error && (
            <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
              <div className="flex items-start gap-2">
                <AlertOctagon className="h-4 w-4 shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold">Validation Rejected</p>
                  <p className="mt-0.5">{validation.error.message}</p>
                </div>
              </div>
            </div>
          )}

          {/* Submission Error Alert */}
          {submission.error && (
            <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
              <div className="flex items-start gap-2">
                <AlertOctagon className="h-4 w-4 shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold">Submission Failed</p>
                  <p className="mt-0.5">{submission.error.message}</p>
                </div>
              </div>
            </div>
          )}
        </form>

        {/* Right Column: Validation Diagnostics & Classification Result */}
        <div className="space-y-6">
          {/* Section 1: Validation Diagnostics */}
          <section>
            <SectionTitle>JCL Diagnostics & Structure</SectionTitle>
            <div className="console-panel min-h-36 p-4">
              {validation.data && isValidated ? (
                <div className="space-y-3">
                  <div className="flex items-center justify-between border-b border-border/60 pb-2.5">
                    <div className="flex items-center gap-2">
                      <span className="inline-flex items-center rounded border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-xs font-semibold text-emerald-700 dark:text-emerald-400">
                        ✓ VALID JCL
                      </span>
                      <span className="font-mono text-xs font-bold text-navy dark:text-foreground">
                        {validation.data.job_name}
                      </span>
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {validation.data.steps.length} step(s) configured
                    </span>
                  </div>

                  {validation.data.structure_summary && (
                    <p className="text-xs text-muted-foreground">
                      {validation.data.structure_summary}
                    </p>
                  )}

                  {/* Steps mapping */}
                  <div className="space-y-2 pt-1 font-mono text-xs">
                    {validation.data.steps.map((step) => (
                      <div key={step.name} className="rounded bg-muted/40 p-2.5 border border-border/50">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-foreground">
                            {step.name} <span className="font-normal text-muted-foreground">→</span> PGM={step.program}
                          </span>
                          <span className="text-[10px] text-muted-foreground">
                            {step.datasets.length} DD statement(s)
                          </span>
                        </div>
                        {step.datasets.map((dd) => (
                          <div key={dd.name} className="mt-1 pl-3 text-[11px] text-muted-foreground">
                            <span className="font-semibold text-foreground/80">DD {dd.name}</span>
                            {dd.dataset ? ` DSN=${dd.dataset}` : ""}
                            {dd.inline_data.length
                              ? ` · ${dd.inline_data.length} inline record(s)`
                              : ""}
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>

                  {/* Warnings if any */}
                  {validation.data.warnings && validation.data.warnings.length > 0 && (
                    <div className="rounded border border-amber-500/30 bg-amber-500/10 p-2 text-xs text-amber-700 dark:text-amber-400">
                      <p className="font-semibold">Validation Warnings:</p>
                      <ul className="list-disc pl-4 mt-1 space-y-0.5">
                        {validation.data.warnings.map((w, i) => (
                          <li key={i}>{w}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ) : validation.error ? (
                <div className="flex flex-col items-center justify-center p-4 text-center">
                  <AlertOctagon className="h-6 w-6 text-destructive mb-2" />
                  <p className="text-xs font-semibold text-destructive">JCL Structure Invalid</p>
                  <p className="text-xs text-muted-foreground mt-1 max-w-sm">
                    {validation.error.message}
                  </p>
                </div>
              ) : (
                <Empty text="Validate the editor contents to inspect parsed JOB, EXEC and DD statements." />
              )}
            </div>
          </section>

          {/* Section 2: Job Classification Result & Execution Spool */}
          <section>
            <SectionTitle>Job Classification & Spool Output</SectionTitle>
            <div className="console-panel min-h-60 p-4">
              {execution.error && (
                <p className="text-sm text-destructive" role="alert">
                  {execution.error.message}
                </p>
              )}

              {job ? (
                <div className="space-y-4">
                  {/* Classification Banner */}
                  {classificationMeta && (
                    <div
                      className={`rounded-lg border p-3.5 transition ${classificationMeta.bannerBg}`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2.5">
                          <classificationMeta.icon
                            className={`h-5 w-5 shrink-0 ${classificationMeta.textClass}`}
                          />
                          <div>
                            <div className="flex items-center gap-2">
                              <span
                                className={`rounded border px-2 py-0.5 font-mono text-xs font-bold uppercase tracking-wider ${classificationMeta.badgeBg}`}
                              >
                                {classificationMeta.classification}
                              </span>
                              <span className="font-mono text-xs font-bold text-foreground">
                                {classificationMeta.rcCode}
                              </span>
                            </div>
                            <p className="mt-1 text-xs text-muted-foreground">
                              {classificationMeta.description}
                            </p>
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          <StatusBadge s={job.status === "queued" ? "waiting" : job.status} />
                          <Link
                            to="/jobs/$jobId"
                            params={{ jobId: job.id }}
                            className="rounded border border-border bg-card px-2 py-1 text-xs text-ai hover:underline"
                          >
                            Full Job View →
                          </Link>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Metadata Summary Table */}
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 rounded-lg bg-muted/40 p-3 text-xs border border-border/50">
                    <div>
                      <span className="text-[10px] uppercase text-muted-foreground">Job Name</span>
                      <p className="font-mono font-bold text-foreground">{job.name}</p>
                    </div>
                    <div>
                      <span className="text-[10px] uppercase text-muted-foreground">Program(s)</span>
                      <p className="font-mono text-foreground">{programsInJob || "—"}</p>
                    </div>
                    <div>
                      <span className="text-[10px] uppercase text-muted-foreground">Duration</span>
                      <p className="font-mono text-foreground">{formatDuration(job.started_at, job.finished_at)}</p>
                    </div>
                    <div>
                      <span className="text-[10px] uppercase text-muted-foreground">Job ID</span>
                      <p className="font-mono text-[11px] text-muted-foreground truncate" title={job.id}>
                        {job.id.slice(0, 8)}…
                      </p>
                    </div>
                  </div>

                  {/* Execution Spool Output */}
                  <div>
                    <div className="mb-1.5 flex items-center justify-between">
                      <span className="text-[11px] font-semibold uppercase text-muted-foreground">
                        SYSOUT / Execution Spool
                      </span>
                      {job.finished_at && (
                        <span className="text-[10px] text-muted-foreground">
                          Finished {job.finished_at.slice(11, 19)} UTC
                        </span>
                      )}
                    </div>
                    <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-lg bg-navy p-3 font-mono text-xs text-primary-foreground leading-relaxed">
                      {job.stdout ||
                        job.stderr ||
                        (job.status === "running"
                          ? "Executing COBOL binary in JES2 queue…"
                          : "Waiting for COBOL execution output…")}
                    </pre>
                  </div>
                </div>
              ) : jobId ? (
                <div className="flex items-center justify-center py-10 text-xs text-muted-foreground">
                  <Cpu className="h-4 w-4 animate-spin mr-2" />
                  <span>Loading job execution and dispatching worker…</span>
                </div>
              ) : (
                <Empty text="Submit a validated job to follow queue status and inspect classified output here." />
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
