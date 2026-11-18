import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { appHead } from "@/lib/head";
import {
  addVsamCustomer,
  createDataset,
  deleteVsamCustomer,
  datasetQuery,
  datasetsQuery,
  replaceDatasetRecords,
  updateVsamCustomer,
  vsamCustomersQuery,
  type Dataset,
} from "@/lib/api";
import { Empty, PageHeader, Table, TableSkeleton, td } from "@/components/app/ui";

export const Route = createFileRoute("/_app/datasets")({
  head: appHead("Datasets", "SQLite-backed datasets used by batch jobs."),
  component: DatasetsPage,
});

function DatasetRecords({ dataset }: { dataset: Dataset }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [recordsText, setRecordsText] = useState("");
  const { data, isLoading, error } = useQuery({ ...datasetQuery(dataset.name), enabled: open });
  const update = useMutation({
    mutationFn: (records: string) =>
      replaceDatasetRecords(dataset.name, records ? records.split(/\r?\n/) : []),
    onSuccess: async (updated) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["datasets", dataset.name] }),
        queryClient.invalidateQueries({ queryKey: ["datasets"] }),
      ]);
      setRecordsText(updated.records.join("\n"));
    },
  });

  useEffect(() => {
    if (data) setRecordsText(data.records.join("\n"));
  }, [data]);

  return (
    <details className="mt-1" onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary className="cursor-pointer text-xs text-ai hover:underline">View records</summary>
      {open && (
        <div className="mt-2 max-w-xl rounded-lg border border-border bg-background p-3">
          {isLoading ? (
            <p className="text-xs text-muted-foreground">Loading records…</p>
          ) : error ? (
            <p className="text-xs text-destructive" role="alert">
              {error.message}
            </p>
          ) : data ? (
            <form
              onSubmit={(event: FormEvent<HTMLFormElement>) => {
                event.preventDefault();
                update.mutate(recordsText);
              }}
            >
              <label className="grid gap-1 text-xs font-medium">
                Records (one per line)
                <textarea
                  value={recordsText}
                  onChange={(event) => setRecordsText(event.target.value)}
                  className="max-h-48 min-h-20 overflow-auto rounded-lg border border-border bg-card p-2 font-mono text-xs"
                />
              </label>
              {update.error && (
                <p className="mt-2 text-xs text-destructive" role="alert">
                  {update.error.message}
                </p>
              )}
              <button
                type="submit"
                disabled={update.isPending}
                className="mt-2 rounded-lg border border-border px-2.5 py-1 text-xs font-medium hover:bg-muted disabled:opacity-50"
              >
                {update.isPending ? "Saving…" : "Replace records"}
              </button>
            </form>
          ) : null}
        </div>
      )}
    </details>
  );
}

function DatasetsPage() {
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useQuery(datasetsQuery());
  const [name, setName] = useState("");
  const [organization, setOrganization] = useState("SEQUENTIAL");
  const [recordsText, setRecordsText] = useState("");
  const creation = useMutation({
    mutationFn: () =>
      createDataset(name.trim(), organization, recordsText ? recordsText.split(/\r?\n/) : []),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["datasets"] });
      setName("");
      setRecordsText("");
    },
  });

  function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    creation.mutate();
  }

  return (
    <div>
      <PageHeader
        title="Datasets"
        subtitle="SQLite batch datasets and GnuCOBOL indexed VSAM customer records"
      />
      <VsamCustomers />
      <details className="mb-5 rounded-xl border border-border bg-card p-4">
        <summary className="cursor-pointer text-sm font-medium">Create dataset</summary>
        <form onSubmit={handleCreate} className="mt-4 grid gap-3 md:grid-cols-2">
          <label className="grid gap-1 text-xs font-medium">
            Dataset name
            <input
              required
              maxLength={44}
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="NP.BATCH.INPUT"
              className="h-9 rounded-lg border border-border bg-background px-3 font-mono text-sm"
            />
          </label>
          <label className="grid gap-1 text-xs font-medium">
            Organization
            <input
              required
              maxLength={32}
              value={organization}
              onChange={(event) => setOrganization(event.target.value)}
              className="h-9 rounded-lg border border-border bg-background px-3 font-mono text-sm"
            />
          </label>
          <label className="grid gap-1 text-xs font-medium md:col-span-2">
            Initial records (one per line)
            <textarea
              value={recordsText}
              onChange={(event) => setRecordsText(event.target.value)}
              className="min-h-24 rounded-lg border border-border bg-background p-3 font-mono text-xs"
            />
          </label>
          {creation.error && (
            <p className="text-sm text-destructive md:col-span-2" role="alert">
              {creation.error.message}
            </p>
          )}
          <div className="md:col-span-2">
            <button
              type="submit"
              disabled={creation.isPending || !name.trim()}
              className="rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
            >
              {creation.isPending ? "Creating…" : "Create dataset"}
            </button>
          </div>
        </form>
      </details>
      {error && (
        <p className="mb-4 text-sm text-destructive" role="alert">
          {error.message}
        </p>
      )}
      {isLoading ? (
        <TableSkeleton />
      ) : !data?.length ? (
        <Empty text="No datasets have been created yet." />
      ) : (
        <Table head={["Dataset", "Organization", "Records", "Created", "Last updated"]}>
          {data.map((dataset) => (
            <tr key={dataset.name} className="align-top hover:bg-surface">
              <td className={`${td} font-mono text-xs font-medium text-navy`}>
                {dataset.name}
                <DatasetRecords dataset={dataset} />
              </td>
              <td className={td}>{dataset.organization}</td>
              <td className={`${td} font-mono text-xs`}>{dataset.record_count.toLocaleString()}</td>
              <td className={`${td} font-mono text-xs`}>
                {new Date(dataset.created_at).toLocaleString()}
              </td>
              <td className={`${td} font-mono text-xs`}>
                {new Date(dataset.updated_at).toLocaleString()}
              </td>
            </tr>
          ))}
        </Table>
      )}
    </div>
  );
}

function VsamCustomers() {
  const queryClient = useQueryClient();
  const { data: customers, isLoading, error } = useQuery(vsamCustomersQuery());
  const [customerId, setCustomerId] = useState("");
  const [customerName, setCustomerName] = useState("");
  const [editedNames, setEditedNames] = useState<Record<string, string>>({});
  const add = useMutation({
    mutationFn: addVsamCustomer,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["vsam", "customers"] });
      setCustomerId("");
      setCustomerName("");
    },
  });
  const update = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => updateVsamCustomer(id, name),
    onSuccess: async (customer) => {
      await queryClient.invalidateQueries({ queryKey: ["vsam", "customers"] });
      setEditedNames((current) => ({ ...current, [customer.customer_id]: customer.name }));
    },
  });
  const remove = useMutation({
    mutationFn: deleteVsamCustomer,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["vsam", "customers"] }),
  });

  return (
    <section className="console-panel mb-6 p-4 sm:p-5">
      <div className="mb-4">
        <h2 className="text-sm font-semibold">VSAM KSDS · GnuCOBOL indexed file</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Customer records are stored in the COBOL indexed file, not SQLite.
        </p>
      </div>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          add.mutate({ customer_id: customerId.trim(), name: customerName.trim() });
        }}
        className="mb-4 flex flex-wrap items-end gap-3"
      >
        <label className="grid gap-1 text-xs font-medium">
          Customer ID
          <input
            required
            maxLength={8}
            pattern="[A-Za-z0-9]+"
            value={customerId}
            onChange={(event) => setCustomerId(event.target.value)}
            className="h-9 w-36 rounded-lg border border-border bg-background px-3 font-mono text-sm"
          />
        </label>
        <label className="grid gap-1 text-xs font-medium">
          Name
          <input
            required
            maxLength={40}
            value={customerName}
            onChange={(event) => setCustomerName(event.target.value)}
            className="h-9 w-56 rounded-lg border border-border bg-background px-3 text-sm"
          />
        </label>
        <button
          type="submit"
          disabled={add.isPending}
          className="h-9 rounded-lg bg-primary px-3 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          {add.isPending ? "Adding…" : "Insert customer"}
        </button>
      </form>
      {(error || add.error || update.error || remove.error) && (
        <p className="mb-3 text-sm text-destructive" role="alert">
          {(error || add.error || update.error || remove.error)?.message}
        </p>
      )}
      {isLoading ? (
        <p className="text-sm text-muted-foreground">Reading indexed customer file…</p>
      ) : customers?.length ? (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-[10px] uppercase text-muted-foreground">
              <tr>
                <th className="py-2 pr-3">Customer ID</th>
                <th className="py-2 pr-3">Name</th>
                <th className="py-2">Operations</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {customers.map((customer) => (
                <tr key={customer.customer_id}>
                  <td className="py-2 pr-3 font-mono text-xs">{customer.customer_id}</td>
                  <td className="py-2 pr-3">
                    <input
                      aria-label={`Update ${customer.customer_id} name`}
                      maxLength={40}
                      value={editedNames[customer.customer_id] ?? customer.name}
                      onChange={(event) =>
                        setEditedNames((current) => ({
                          ...current,
                          [customer.customer_id]: event.target.value,
                        }))
                      }
                      className="h-8 rounded border border-border bg-background px-2 text-sm"
                    />
                  </td>
                  <td className="py-2">
                    <div className="flex gap-2">
                      <button
                        type="button"
                        disabled={update.isPending}
                        onClick={() =>
                          update.mutate({
                            id: customer.customer_id,
                            name: (editedNames[customer.customer_id] ?? customer.name).trim(),
                          })
                        }
                        className="text-xs font-medium text-ai hover:underline disabled:opacity-50"
                      >
                        Update
                      </button>
                      <button
                        type="button"
                        disabled={remove.isPending}
                        onClick={() => remove.mutate(customer.customer_id)}
                        className="text-xs font-medium text-destructive hover:underline disabled:opacity-50"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty text="No indexed customer records are available." />
      )}
    </section>
  );
}
