import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";

export default function JobsPage() {
  const [jobs, setJobs] = useState([]);
  const [minScore, setMinScore] = useState(0);
  const [source, setSource] = useState("");
  const [loading, setLoading] = useState(false);

  const loadJobs = async () => {
    const result = await api.getJobs({ min_score: Number(minScore) || 0, source: source || undefined });
    setJobs(result);
  };

  useEffect(() => {
    loadJobs();
  }, []);

  const discoverJobs = async () => {
    try {
      setLoading(true);
      const result = await api.discoverJobs();
      toast.success(`Discovery complete: ${result.deduped} unique jobs fetched.`);
      await loadJobs();
    } catch {
      toast.error("Could not fetch jobs right now.");
    } finally {
      setLoading(false);
    }
  };

  const queueJob = async (jobId) => {
    try {
      await api.queueApplication(jobId);
      toast.success("Job queued for auto-apply.");
    } catch {
      toast.error("Failed to queue this job.");
    }
  };

  return (
    <div className="space-y-6" data-testid="jobs-page">
      <div className="flex flex-wrap items-end justify-between gap-3" data-testid="jobs-header-row">
        <div>
          <h2 className="text-4xl font-semibold text-white sm:text-5xl" data-testid="jobs-heading">
            Jobs Feed
          </h2>
          <p className="mt-2 text-sm text-slate-400" data-testid="jobs-subheading">
            Remotive + Adzuna aggregation with AutoApply scoring.
          </p>
        </div>
        <Button onClick={discoverJobs} disabled={loading} data-testid="jobs-discover-button">
          {loading ? "Discovering..." : "Discover Jobs Now"}
        </Button>
      </div>

      <Card className="border-white/10 bg-white/[0.04]" data-testid="jobs-filters-card">
        <CardHeader>
          <CardTitle data-testid="jobs-filters-title">Filters</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
          <Input
            type="number"
            value={minScore}
            onChange={(e) => setMinScore(e.target.value)}
            placeholder="Minimum score"
            data-testid="jobs-min-score-input"
          />
          <Input
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder="Source (remotive / adzuna)"
            data-testid="jobs-source-input"
          />
          <Button onClick={loadJobs} data-testid="jobs-apply-filters-button">
            Apply Filters
          </Button>
        </CardContent>
      </Card>

      <div className="grid gap-4" data-testid="jobs-list">
        {jobs.length === 0 && (
          <Card className="border-white/10 bg-white/[0.04]" data-testid="jobs-empty-state">
            <CardContent className="p-6 text-sm text-slate-400">
              No jobs loaded yet. Run discovery and complete profile preferences to get personalized results.
            </CardContent>
          </Card>
        )}

        {jobs.map((job) => (
          <Card
            key={job.id}
            className="border-white/10 bg-white/[0.03] transition-transform hover:-translate-y-1"
            data-testid={`job-card-${job.id}`}
          >
            <CardContent className="flex flex-wrap items-start justify-between gap-4 p-6">
              <div className="max-w-3xl space-y-2">
                <p className="font-mono text-xs uppercase tracking-[0.2em] text-blue-300" data-testid={`job-source-${job.id}`}>
                  {job.source}
                </p>
                <h3 className="text-xl font-semibold text-white" data-testid={`job-title-${job.id}`}>
                  {job.title}
                </h3>
                <p className="text-sm text-slate-300" data-testid={`job-company-${job.id}`}>
                  {job.company} · {job.location}
                </p>
                <p className="line-clamp-3 text-sm text-slate-400" data-testid={`job-description-${job.id}`}>
                  {job.description?.replace(/<[^>]*>/g, " ")}
                </p>
              </div>

              <div className="flex min-w-52 flex-col gap-2" data-testid={`job-actions-${job.id}`}>
                <p className="rounded-lg bg-blue-500/20 px-3 py-2 text-center font-mono text-sm text-blue-200" data-testid={`job-score-${job.id}`}>
                  Match: {job.match_score}%
                </p>
                <Button asChild data-testid={`job-view-button-${job.id}`}>
                  <Link to={`/jobs/${job.id}`}>Open Job Detail</Link>
                </Button>
                <Button variant="outline" onClick={() => queueJob(job.id)} data-testid={`job-queue-button-${job.id}`}>
                  Queue Auto-Apply
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
