import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";

export default function JobDetailPage() {
  const { jobId } = useParams();
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadDetail = async () => {
    const data = await api.getJobDetail(jobId);
    setDetail(data);
  };

  useEffect(() => {
    loadDetail();
  }, [jobId]);

  const generateDocs = async () => {
    try {
      setLoading(true);
      await api.generateDocuments(jobId);
      await loadDetail();
      toast.success("Tailored resume and cover letter generated.");
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Could not generate documents.");
    } finally {
      setLoading(false);
    }
  };

  const queueAndRun = async () => {
    try {
      await api.queueApplication(jobId);
      await api.runAutoApply();
      toast.success("Application queued and auto-apply processor triggered.");
      await loadDetail();
    } catch {
      toast.error("Auto-apply failed for this job.");
    }
  };

  const job = detail?.job;
  const doc = detail?.latest_document;
  const resumeDownload = doc
    ? `${api.backendUrl}/api/documents/${doc.id}/download/resume`
    : "#";
  const coverDownload = doc
    ? `${api.backendUrl}/api/documents/${doc.id}/download/cover`
    : "#";

  return (
    <div className="space-y-6" data-testid="job-detail-page">
      {!job && (
        <Card className="border-white/10 bg-white/[0.03]" data-testid="job-detail-loading-card">
          <CardContent className="p-6 text-sm text-slate-400">Loading job detail...</CardContent>
        </Card>
      )}

      {job && (
        <>
          <section className="space-y-2" data-testid="job-detail-header">
            <p className="font-mono text-xs tracking-[0.2em] text-blue-300" data-testid="job-detail-source">
              {job.source}
            </p>
            <h2 className="text-4xl font-semibold text-white sm:text-5xl" data-testid="job-detail-title">
              {job.title}
            </h2>
            <p className="text-sm text-slate-300" data-testid="job-detail-company-location">
              {job.company} · {job.location}
            </p>
            <p className="font-mono text-sm text-blue-300" data-testid="job-detail-score">
              Match Score: {job.match_score}%
            </p>
          </section>

          <Card className="border-white/10 bg-white/[0.04]" data-testid="job-detail-actions-card">
            <CardContent className="flex flex-wrap gap-3 p-6">
              <Button onClick={generateDocs} disabled={loading} data-testid="job-detail-generate-docs-button">
                {loading ? "Generating..." : "Generate Tailored Docs"}
              </Button>
              <Button variant="outline" onClick={queueAndRun} data-testid="job-detail-queue-run-button">
                Queue and Run Auto-Apply
              </Button>
              <a
                href={resumeDownload}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center rounded-md border border-blue-300/30 px-4 py-2 text-sm text-blue-200 hover:bg-blue-500/20"
                data-testid="job-detail-download-resume-link"
              >
                Download Resume PDF
              </a>
              <a
                href={coverDownload}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center rounded-md border border-blue-300/30 px-4 py-2 text-sm text-blue-200 hover:bg-blue-500/20"
                data-testid="job-detail-download-cover-link"
              >
                Download Cover Letter PDF
              </a>
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2" data-testid="job-detail-preview-grid">
            <Card className="border-white/10 bg-white/[0.03]" data-testid="job-detail-resume-preview-card">
              <CardHeader>
                <CardTitle data-testid="job-detail-resume-preview-title">Tailored Resume Preview</CardTitle>
              </CardHeader>
              <CardContent>
                <Textarea
                  className="min-h-[420px]"
                  value={doc?.tailored_resume_text || "Generate documents to see resume preview."}
                  readOnly
                  data-testid="job-detail-resume-preview-text"
                />
              </CardContent>
            </Card>

            <Card className="border-white/10 bg-white/[0.03]" data-testid="job-detail-cover-preview-card">
              <CardHeader>
                <CardTitle data-testid="job-detail-cover-preview-title">Cover Letter Preview</CardTitle>
              </CardHeader>
              <CardContent>
                <Textarea
                  className="min-h-[420px]"
                  value={doc?.cover_letter_text || "Generate documents to see cover letter preview."}
                  readOnly
                  data-testid="job-detail-cover-preview-text"
                />
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
