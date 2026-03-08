import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
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
  const [selectedApplicationId, setSelectedApplicationId] = useState("");
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

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

  const loadDetail = async (applicationId) => {
    try {
      setDetailLoading(true);
      const result = await api.getApplicationDetail(applicationId);
      setDetail(result);
    } catch {
      toast.error("Could not load application detail.");
    } finally {
      setDetailLoading(false);
    }
  };

  const updateStatus = async (applicationId, status) => {
    try {
      await api.updateApplicationStatus(applicationId, status);
      await loadKanban();
      if (selectedApplicationId === applicationId) {
        await loadDetail(applicationId);
      }
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

  const generateFollowup = async () => {
    if (!selectedApplicationId) return;
    try {
      await api.generateFollowupDraft(selectedApplicationId);
      await loadDetail(selectedApplicationId);
      await loadKanban();
      toast.success("Follow-up draft generated.");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not generate follow-up draft.");
    }
  };

  const sendFollowup = async () => {
    if (!selectedApplicationId) return;
    try {
      await api.sendFollowupDraft(selectedApplicationId);
      await loadDetail(selectedApplicationId);
      await loadKanban();
      toast.success("Follow-up sent via Gmail.");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Follow-up send failed.");
    }
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
                  onClick={() => {
                    setSelectedApplicationId(item.id);
                    loadDetail(item.id);
                  }}
                  data-testid={`kanban-card-${item.id}`}
                >
                  <p className="text-sm font-medium text-white" data-testid={`kanban-card-title-${item.id}`}>
                    {item.job_title}
                  </p>
                  <p className="text-xs text-slate-400" data-testid={`kanban-card-company-${item.id}`}>
                    {item.company}
                  </p>
                  <p className="text-xs text-blue-200" data-testid={`kanban-card-email-summary-${item.id}`}>
                    {item.email_summary_note || "No recruiter response parsed yet."}
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

      <Card className="border-white/10 bg-white/[0.04]" data-testid="application-detail-card">
        <CardHeader>
          <CardTitle data-testid="application-detail-title">Application Detail</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {!selectedApplicationId && (
            <p className="text-sm text-slate-400" data-testid="application-detail-empty-state">
              Select an application card to view screenshot proof, email summary, and follow-up draft.
            </p>
          )}

          {selectedApplicationId && detailLoading && (
            <p className="text-sm text-slate-400" data-testid="application-detail-loading-state">
              Loading application detail...
            </p>
          )}

          {selectedApplicationId && detail?.application && !detailLoading && (
            <div className="space-y-4" data-testid="application-detail-content">
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-md border border-white/10 bg-black/20 p-3" data-testid="application-detail-meta-box">
                  <p className="text-sm text-white" data-testid="application-detail-job-title">
                    {detail.application.job_title}
                  </p>
                  <p className="text-xs text-slate-400" data-testid="application-detail-company">
                    {detail.application.company}
                  </p>
                  <p className="mt-1 text-xs text-blue-300" data-testid="application-detail-status">
                    {detail.application.status}
                  </p>
                  <p className="mt-2 text-xs text-slate-300" data-testid="application-detail-email-summary">
                    {detail.application.email_summary_note || "No email response summary yet."}
                  </p>
                </div>

                <div className="rounded-md border border-white/10 bg-black/20 p-3" data-testid="application-detail-followup-box">
                  <p className="text-xs text-slate-400" data-testid="application-detail-followup-subject-label">
                    Follow-up subject
                  </p>
                  <p className="text-sm text-white" data-testid="application-detail-followup-subject">
                    {detail.application.followup_draft_subject || "Not generated yet"}
                  </p>
                </div>
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <div data-testid="application-detail-screenshot-box">
                  <p className="mb-2 text-sm text-slate-300">Submission Screenshot</p>
                  {detail.proof_image_available ? (
                    <img
                      src={`${api.backendUrl}${detail.proof_image_url}`}
                      alt="Application proof"
                      className="max-h-[380px] w-full rounded-md border border-white/10 object-contain"
                      data-testid="application-detail-proof-image"
                    />
                  ) : (
                    <div
                      className="flex h-48 items-center justify-center rounded-md border border-dashed border-white/20 text-xs text-slate-500"
                      data-testid="application-detail-proof-empty"
                    >
                      No screenshot proof available yet.
                    </div>
                  )}
                </div>

                <div data-testid="application-detail-followup-draft-box">
                  <p className="mb-2 text-sm text-slate-300">Follow-up Draft (3-day no-response)</p>
                  <Textarea
                    value={detail.application.followup_draft_body || "No follow-up draft generated yet."}
                    readOnly
                    className="min-h-52"
                    data-testid="application-detail-followup-draft-text"
                  />
                  <div className="mt-3 flex flex-wrap gap-2" data-testid="application-detail-followup-actions">
                    <Button onClick={generateFollowup} variant="outline" data-testid="application-detail-generate-followup-button">
                      Generate Follow-up Draft
                    </Button>
                    <Button
                      onClick={sendFollowup}
                      disabled={Boolean(detail.application.followup_sent_at)}
                      data-testid="application-detail-send-followup-button"
                    >
                      {detail.application.followup_sent_at ? "Follow-up Already Sent" : "Send Follow-up via Gmail"}
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
