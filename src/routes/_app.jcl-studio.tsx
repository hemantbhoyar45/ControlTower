import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { appHead } from "@/lib/head";
import { jobQuery, submitJob, validateJcl } from "@/lib/api";
import { Empty, PageHeader, SectionTitle, StatusBadge } from "@/components/app/ui";

export const Route = createFileRoute("/_app/jcl-studio")({
  head: appHead("JCL Studio", "Validate, submit, and monitor controlled JCL batch jobs."),
  component: JclStudioPage,
});

const starterJcl = `//GREETCHK JOB (ACCT),'SAMPLE'
//HELLO EXEC PGM=GREET
//SYSOUT DD SYSOUT=*`;

function JclStudioPage() {
  const queryClient = useQueryClient();
  const [content, setContent] = useState(starterJcl);
  const [validatedContent, setValidatedContent] = useState("");
  const [jobId, setJobId] = useState("");
  const validation = useMutation({
    mutationFn: validateJcl,
    onSuccess: (_, source) => setValidatedContent(source),
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

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isValidated) submission.mutate(content);
  }

  return (
    <div>
      <PageHeader
        title="JCL Studio"
        subtitle="Validate the supported JOB / EXEC / DD subset, then submit it to the controlled queue."
      />
      <div className="grid gap-6 xl:grid-cols-2">
        <form onSubmit={handleSubmit} className="console-panel space-y-4 p-4 sm:p-5">
          <label htmlFor="jcl-source" className="text-sm font-semibold">
            JCL source
          </label>
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
            className="min-h-[22rem] w-full rounded-lg border border-border bg-navy p-4 font-mono text-xs leading-relaxed text-primary-foreground"
          />
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => validation.mutate(content)}
              disabled={validation.isPending || !content.trim()}
              className="rounded-lg border border-border px-3 py-2 text-sm font-medium hover:bg-muted disabled:opacity-50"
            >
              {validation.isPending ? "Validating…" : "Validate JCL"}
            </button>
            <button
              type="submit"
              disabled={!isValidated || submission.isPending}
              className="rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
            >
              {submission.isPending ? "Submitting…" : "Submit batch job"}
            </button>
          </div>
          {validation.error && (
            <p className="text-sm text-destructive" role="alert">
              {validation.error.message}
            </p>
          )}
          {submission.error && (
            <p className="text-sm text-destructive" role="alert">
              {submission.error.message}
            </p>
          )}
        </form>

        <div className="space-y-5">
          <section>
            <SectionTitle>Validation</SectionTitle>
            <div className="console-panel min-h-32 p-4">
              {validation.data && isValidated ? (
                <>
                  <p className="text-sm text-success">
                    {validation.data.job_name} is valid · {validation.data.steps.length} step(s)
                  </p>
                  <ul className="mt-3 space-y-2 font-mono text-xs">
                    {validation.data.steps.map((step) => (
                      <li key={step.name}>
                        <span className="font-semibold">{step.name}</span> → {step.program}
                        {step.datasets.map((dd) => (
                          <span key={dd.name} className="block pl-4 text-muted-foreground">
                            DD {dd.name}
                            {dd.dataset ? ` DSN=${dd.dataset}` : ""}
                            {dd.inline_data.length
                              ? ` · ${dd.inline_data.length} inline record(s)`
                              : ""}
                          </span>
                        ))}
                      </li>
                    ))}
                  </ul>
                </>
              ) : (
                <Empty text="Validate the editor contents to inspect parsed JOB, EXEC and DD statements." />
              )}
            </div>
          </section>

          <section>
            <SectionTitle>Execution status and spool</SectionTitle>
            <div className="console-panel min-h-56 p-4">
              {execution.error && (
                <p className="text-sm text-destructive" role="alert">
                  {execution.error.message}
                </p>
              )}
              {execution.data ? (
                <>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <StatusBadge
                      s={execution.data.status === "queued" ? "waiting" : execution.data.status}
                    />
                    <Link
                      to="/jobs/$jobId"
                      params={{ jobId: execution.data.id }}
                      className="text-xs text-ai hover:underline"
                    >
                      Open job details
                    </Link>
                  </div>
                  <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap rounded-lg bg-navy p-3 font-mono text-xs text-primary-foreground">
                    {execution.data.stdout ||
                      execution.data.stderr ||
                      "Waiting for COBOL execution output…"}
                  </pre>
                </>
              ) : jobId ? (
                <p className="text-sm text-muted-foreground">Loading job spool…</p>
              ) : (
                <Empty text="Submit a validated job to follow queue status and persisted output here." />
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
