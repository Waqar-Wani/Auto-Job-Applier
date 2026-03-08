import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

const STATUSES = [
  "Discovered",
  "Tailoring",
  "Applied",
  "Under Review",
  "Interview Scheduled",
  "Offer Received",
  "Rejected",
  "Withdrawn",
];

export default function ApplicationsPage() {
  const [kanban, setKanban] = useState({});
  const [error, setError] = useState("");

  const loadKanban = async () => {
    try {
      setError("");
      const result = await api.getApplicationsKanban();
      setKanban(result);
    } catch {
      setError("Could not load application pipeline.");
    }
  };

  useEffect(() => {
    loadKanban();
  }, []);

  const updateStatus = async (applicationId, status) => {
    try {
      await api.updateApplicationStatus(applicationId, status);
      await loadKanban();
      toast.success("Application status updated.");
    } catch {
      toast.error("Could not update status.");
    }
  };

  const onDrop = async (event, nextStatus) => {
    event.preventDefault();
    const appId = event.dataTransfer.getData("application_id");
    if (appId) await updateStatus(appId, nextStatus);
  };

  return (
    <div className="space-y-6" data-testid="applications-page">
      <h2 className="text-4xl font-semibold text-white sm:text-5xl" data-testid="applications-heading">
        Application Pipeline
      </h2>

      {error && (
        <Card className="border-red-500/40 bg-red-500/10" data-testid="applications-error-state">
          <CardContent className="p-4 text-sm text-red-200">{error}</CardContent>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-4" data-testid="kanban-board-grid">
        {STATUSES.map((status) => (
          <Card
            key={status}
            className="min-h-64 border-white/10 bg-white/[0.04]"
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => onDrop(event, status)}
            data-testid={`kanban-column-${status.toLowerCase().replace(/\s+/g, "-")}`}
          >
            <CardHeader>
              <CardTitle className="text-base" data-testid={`kanban-column-title-${status.toLowerCase().replace(/\s+/g, "-")}`}>
                {status}
              </CardTitle>
            </CardHeader>
            <CardContent className="max-h-[55vh] space-y-3 overflow-y-auto pr-1" data-testid={`kanban-column-content-${status.toLowerCase().replace(/\s+/g, "-")}`}>
              {(kanban[status] || []).map((item) => (
                <div
                  key={item.id}
                  draggable
                  onDragStart={(event) => event.dataTransfer.setData("application_id", item.id)}
                  className="space-y-2 rounded-lg border border-white/10 bg-black/25 p-3"
                  data-testid={`kanban-card-${item.id}`}
                >
                  <p className="text-sm font-medium text-white" data-testid={`kanban-card-title-${item.id}`}>
                    {item.job_title}
                  </p>
                  <p className="text-xs text-slate-400" data-testid={`kanban-card-company-${item.id}`}>
                    {item.company}
                  </p>
                  <select
                    className="w-full rounded-md border border-white/20 bg-black/50 px-2 py-1 text-xs text-slate-100"
                    value={item.status}
                    onChange={(e) => updateStatus(item.id, e.target.value)}
                    data-testid={`kanban-card-status-select-${item.id}`}
                  >
                    {STATUSES.map((statusOption) => (
                      <option key={statusOption} value={statusOption}>
                        {statusOption}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
