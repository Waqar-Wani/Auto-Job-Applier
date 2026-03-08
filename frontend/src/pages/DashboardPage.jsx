import { useEffect, useMemo, useRef, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

const COLORS = ["#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#a855f7", "#14b8a6"];

const AnimatedNumber = ({ value }) => {
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    let frame;
    const duration = 700;
    const start = performance.now();
    const from = Number(display) || 0;
    const to = Number(value) || 0;

    const animate = (now) => {
      const progress = Math.min((now - start) / duration, 1);
      const current = from + (to - from) * progress;
      setDisplay(current);
      if (progress < 1) frame = requestAnimationFrame(animate);
    };

    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [value]);

  return <span>{Math.round(display * 100) / 100}</span>;
};

const ChartFrame = ({ children, testId }) => {
  const frameRef = useRef(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    if (!frameRef.current || typeof ResizeObserver === "undefined") return undefined;

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const width = Math.max(0, Math.floor(entry.contentRect.width));
      const height = Math.max(0, Math.floor(entry.contentRect.height));
      setSize({ width, height });
    });

    observer.observe(frameRef.current);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={frameRef} className="h-72 w-full" data-testid={testId}>
      {size.width > 0 && size.height > 0 ? (
        children(size)
      ) : (
        <div className="flex h-full items-center justify-center text-xs text-slate-500" data-testid={`${testId}-loading`}>
          Loading chart...
        </div>
      )}
    </div>
  );
};

export default function DashboardPage() {
  const [metrics, setMetrics] = useState(null);
  const [applications, setApplications] = useState([]);
  const [error, setError] = useState("");

  const loadData = async () => {
    try {
      setError("");
      const [metricRes, appRes] = await Promise.all([api.getDashboardMetrics(), api.getApplications()]);
      setMetrics(metricRes);
      setApplications(appRes.slice(0, 8));
    } catch {
      setError("Dashboard data failed to load. Please refresh.");
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const kpis = metrics?.kpis || {};
  const sourceData = metrics?.source_breakdown || [];
  const statusData = metrics?.status_breakdown || [];
  const timelineData = metrics?.applications_over_time || [];

  const statCards = useMemo(
    () => [
      { label: "Total Applications Sent", value: kpis.total_applied ?? 0, testId: "kpi-total-applied" },
      { label: "Response Rate %", value: kpis.response_rate ?? 0, testId: "kpi-response-rate" },
      { label: "Interview Rate %", value: kpis.interview_rate ?? 0, testId: "kpi-interview-rate" },
      { label: "Active Applications", value: kpis.active_applications ?? 0, testId: "kpi-active-applications" },
      { label: "Avg AutoApply Score", value: kpis.avg_autoapply_score ?? 0, testId: "kpi-avg-score" },
      { label: "Applications Tracked", value: kpis.applications_total ?? 0, testId: "kpi-applications-tracked" },
    ],
    [kpis],
  );

  return (
    <div className="space-y-8" data-testid="dashboard-page">
      <section data-testid="dashboard-header-section">
        <h2 className="text-4xl font-semibold text-white sm:text-5xl" data-testid="dashboard-heading">
          Mission Dashboard
        </h2>
        <p className="mt-3 max-w-2xl text-sm text-slate-400 sm:text-base" data-testid="dashboard-subheading">
          Live funnel visibility across discovery, tailoring, and application automation.
        </p>
      </section>

      {error && (
        <Card className="border-red-500/40 bg-red-500/10" data-testid="dashboard-error-state">
          <CardContent className="p-4 text-sm text-red-200">{error}</CardContent>
        </Card>
      )}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" data-testid="dashboard-kpi-grid">
        {statCards.map((card) => (
          <Card
            key={card.testId}
            className="border-white/10 bg-white/[0.04] backdrop-blur-xl transition-transform hover:-translate-y-1"
            data-testid={`${card.testId}-card`}
          >
            <CardHeader>
              <CardTitle className="text-sm text-slate-300" data-testid={`${card.testId}-label`}>
                {card.label}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="font-mono text-3xl text-blue-300" data-testid={`${card.testId}-value`}>
                <AnimatedNumber value={card.value} />
              </p>
            </CardContent>
          </Card>
        ))}
      </section>

      <section className="grid gap-6 xl:grid-cols-2" data-testid="dashboard-charts-grid">
        <Card className="border-white/10 bg-white/[0.03]" data-testid="applications-over-time-card">
          <CardHeader>
            <CardTitle data-testid="applications-over-time-title">Applications Over Time</CardTitle>
          </CardHeader>
          <CardContent data-testid="applications-over-time-chart">
            <ChartFrame testId="applications-over-time-chart-frame">
              {({ width, height }) => (
                <LineChart width={width} height={height} data={timelineData}>
                <CartesianGrid stroke="rgba(255,255,255,0.1)" />
                <XAxis dataKey="date" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip />
                <Line type="monotone" dataKey="applications" stroke="#3b82f6" strokeWidth={2} dot={false} />
              </LineChart>
              )}
            </ChartFrame>
          </CardContent>
        </Card>

        <Card className="border-white/10 bg-white/[0.03]" data-testid="status-breakdown-card">
          <CardHeader>
            <CardTitle data-testid="status-breakdown-title">Application Status Breakdown</CardTitle>
          </CardHeader>
          <CardContent data-testid="status-breakdown-chart">
            <ChartFrame testId="status-breakdown-chart-frame">
              {({ width, height }) => (
                <PieChart width={width} height={height}>
                <Pie data={statusData} dataKey="count" nameKey="status" outerRadius={100}>
                  {statusData.map((entry, index) => (
                    <Cell key={entry.status} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
              )}
            </ChartFrame>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.4fr_1fr]" data-testid="dashboard-lower-grid">
        <Card className="border-white/10 bg-white/[0.03]" data-testid="source-breakdown-card">
          <CardHeader>
            <CardTitle data-testid="source-breakdown-title">Response Volume by Source</CardTitle>
          </CardHeader>
          <CardContent data-testid="source-breakdown-chart">
            <ChartFrame testId="source-breakdown-chart-frame">
              {({ width, height }) => (
                <BarChart width={width} height={height} data={sourceData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis dataKey="source" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip />
                <Bar dataKey="count" fill="#3b82f6" radius={[8, 8, 0, 0]} />
              </BarChart>
              )}
            </ChartFrame>
          </CardContent>
        </Card>

        <Card className="border-white/10 bg-white/[0.03]" data-testid="recent-activity-card">
          <CardHeader>
            <CardTitle data-testid="recent-activity-title">Recent Activity</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3" data-testid="recent-activity-list">
            {applications.length === 0 && (
              <p className="text-sm text-slate-400" data-testid="recent-activity-empty-state">
                No applications yet. Upload your CV and run discovery to start the automation flow.
              </p>
            )}
            {applications.map((application) => (
              <div
                key={application.id}
                className="rounded-lg border border-white/10 bg-black/20 p-3"
                data-testid={`recent-activity-item-${application.id}`}
              >
                <p className="text-sm font-medium text-white" data-testid={`recent-activity-title-${application.id}`}>
                  {application.job_title}
                </p>
                <p className="text-xs text-slate-400" data-testid={`recent-activity-company-${application.id}`}>
                  {application.company}
                </p>
                <p className="mt-1 font-mono text-xs text-blue-300" data-testid={`recent-activity-status-${application.id}`}>
                  {application.status}
                </p>
              </div>
            ))}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
