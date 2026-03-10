import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { api } from "@/lib/api";

export default function SettingsPage() {
  const location = useLocation();
  const [settings, setSettings] = useState(null);
  const [gmailStatus, setGmailStatus] = useState({ connected: false });
  const [error, setError] = useState("");

  const loadSettings = async () => {
    try {
      setError("");
      const [result, gmail] = await Promise.all([api.getSettings(), api.getGmailStatus()]);
      setSettings(result);
      setGmailStatus(gmail);
    } catch {
      setError("Could not load settings.");
    }
  };

  useEffect(() => {
    loadSettings();
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (params.get("gmail_connected") === "1") {
      toast.success("Gmail connected successfully.");
      loadSettings();
    }
    if (params.get("gmail_error")) {
      toast.error(`Gmail connect failed: ${params.get("gmail_error")}`);
    }
  }, [location.search]);

  const save = async () => {
    try {
      await api.updateSettings({
        ...settings,
        score_threshold: Number(settings.score_threshold) || 70,
        daily_application_limit: Number(settings.daily_application_limit) || 20,
        discovery_interval_hours: Number(settings.discovery_interval_hours) || 6,
      });
      toast.success("Settings updated.");
    } catch {
      toast.error("Could not save settings.");
    }
  };

  const runQueue = async () => {
    try {
      const result = await api.runAutoApply();
      toast.success(`Queue run complete. Processed: ${result.processed}`);
    } catch {
      toast.error("Queue run failed.");
    }
  };

  const connectGmail = async () => {
    try {
      const returnUrl = `${window.location.origin}/settings`;
      const result = await api.getGmailOAuthStart(returnUrl);
      window.location.href = result.auth_url;
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to start Gmail OAuth.");
    }
  };

  const pollInbox = async () => {
    try {
      const result = await api.pollGmailInbox();
      toast.success(
        `Inbox checked: ${result.gmail_poll.processed} messages, ${result.gmail_poll.applications_updated} status updates.`,
      );
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Gmail polling failed.");
    }
  };

  if (!settings) {
    return (
      <div className="space-y-2">
        {error && (
          <div className="text-sm text-red-300" data-testid="settings-error-state">
            {error}
          </div>
        )}
        <div className="text-sm text-slate-400" data-testid="settings-loading-state">
          Loading settings...
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="settings-page">
      <h2 className="text-4xl font-semibold text-white sm:text-5xl" data-testid="settings-heading">
        Automation Controls
      </h2>

      {error && (
        <Card className="border-red-500/40 bg-red-500/10" data-testid="settings-error-card">
          <CardContent className="p-4 text-sm text-red-200">{error}</CardContent>
        </Card>
      )}

      <Card className="border-white/10 bg-white/[0.04]" data-testid="settings-credentials-card">
        <CardHeader>
          <CardTitle data-testid="settings-credentials-title">API Credentials & Sources</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <p className="text-xs text-slate-400">Adzuna App ID</p>
            <Input
              value={settings.adzuna_app_id || ""}
              onChange={(e) => setSettings((s) => ({ ...s, adzuna_app_id: e.target.value }))}
              placeholder="Adzuna App ID"
              data-testid="settings-adzuna-app-id-input"
            />
          </div>
          <div className="space-y-2">
            <p className="text-xs text-slate-400">Adzuna App Key</p>
            <Input
              value={settings.adzuna_app_key || ""}
              onChange={(e) => setSettings((s) => ({ ...s, adzuna_app_key: e.target.value }))}
              placeholder="Adzuna App Key"
              data-testid="settings-adzuna-app-key-input"
            />
          </div>
          <div className="space-y-2">
            <p className="text-xs text-slate-400">Resend API Key</p>
            <Input
              value={settings.resend_api_key || ""}
              onChange={(e) => setSettings((s) => ({ ...s, resend_api_key: e.target.value }))}
              placeholder="Resend API Key"
              data-testid="settings-resend-api-key-input"
            />
          </div>
          <div className="space-y-2">
            <p className="text-xs text-slate-400">Sender Email</p>
            <Input
              value={settings.sender_email || ""}
              onChange={(e) => setSettings((s) => ({ ...s, sender_email: e.target.value }))}
              placeholder="Sender email"
              data-testid="settings-sender-email-input"
            />
          </div>
          <div className="space-y-2">
            <p className="text-xs text-slate-400">Google OAuth Client ID</p>
            <Input
              value={settings.google_client_id || ""}
              onChange={(e) => setSettings((s) => ({ ...s, google_client_id: e.target.value }))}
              placeholder="Google OAuth Client ID"
              data-testid="settings-google-client-id-input"
            />
          </div>
          <div className="space-y-2">
            <p className="text-xs text-slate-400">Google OAuth Client Secret</p>
            <Input
              value={settings.google_client_secret || ""}
              onChange={(e) => setSettings((s) => ({ ...s, google_client_secret: e.target.value }))}
              placeholder="Google OAuth Client Secret"
              data-testid="settings-google-client-secret-input"
            />
          </div>
          <p className="text-xs text-slate-500 md:col-span-2">
            Note: Save settings after updating keys. Rotate leaked keys immediately and avoid sharing screenshots with secrets.
          </p>
        </CardContent>
      </Card>

      <Card className="border-white/10 bg-white/[0.04]" data-testid="settings-gmail-card">
        <CardHeader>
          <CardTitle data-testid="settings-gmail-title">Gmail Integration</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-3">
          <p className="rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-300" data-testid="settings-gmail-status">
            Status: {gmailStatus.connected ? "Connected" : "Not connected"}
          </p>
          <Button onClick={connectGmail} variant="outline" data-testid="settings-gmail-connect-button">
            Connect Gmail OAuth
          </Button>
          <Button onClick={pollInbox} variant="outline" data-testid="settings-gmail-poll-button">
            Poll Inbox Now
          </Button>
          <p className="w-full text-xs text-slate-500">
            Note: OAuth must be connected with Gmail API enabled in Google Cloud. Polling reads recent inbox replies for status updates.
          </p>
        </CardContent>
      </Card>

      <Card className="border-white/10 bg-white/[0.04]" data-testid="settings-automation-card">
        <CardHeader>
          <CardTitle data-testid="settings-automation-title">Auto-Apply Rules</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <p className="text-xs text-slate-400">Score Threshold (%)</p>
            <Input
              type="number"
              value={settings.score_threshold}
              onChange={(e) => setSettings((s) => ({ ...s, score_threshold: e.target.value }))}
              placeholder="Score threshold"
              data-testid="settings-score-threshold-input"
            />
          </div>
          <div className="space-y-2">
            <p className="text-xs text-slate-400">Daily Application Limit</p>
            <Input
              type="number"
              value={settings.daily_application_limit}
              onChange={(e) => setSettings((s) => ({ ...s, daily_application_limit: e.target.value }))}
              placeholder="Daily application limit"
              data-testid="settings-daily-limit-input"
            />
          </div>
          <div className="space-y-2">
            <p className="text-xs text-slate-400">Discovery Interval (hours)</p>
            <Input
              type="number"
              value={settings.discovery_interval_hours}
              onChange={(e) => setSettings((s) => ({ ...s, discovery_interval_hours: e.target.value }))}
              placeholder="Discovery interval (hours)"
              data-testid="settings-discovery-interval-input"
            />
          </div>
          <div className="space-y-2">
            <p className="text-xs text-slate-400">Resume Template</p>
            <Input
              value={settings.resume_template}
              onChange={(e) => setSettings((s) => ({ ...s, resume_template: e.target.value }))}
              placeholder="Resume template (Modern/Classic/Minimal)"
              data-testid="settings-template-input"
            />
          </div>

          <div className="flex items-center justify-between rounded-lg border border-white/10 bg-black/20 px-3 py-2" data-testid="settings-auto-apply-toggle-row">
            <span className="text-sm text-slate-200" data-testid="settings-auto-apply-label">
              Enable Auto-Apply
            </span>
            <Switch
              checked={Boolean(settings.auto_apply_enabled)}
              onCheckedChange={(checked) => setSettings((s) => ({ ...s, auto_apply_enabled: checked }))}
              data-testid="settings-auto-apply-toggle"
            />
          </div>

          <div className="flex items-center justify-between rounded-lg border border-white/10 bg-black/20 px-3 py-2" data-testid="settings-business-hours-toggle-row">
            <span className="text-sm text-slate-200" data-testid="settings-business-hours-label">
              Business Hours Only
            </span>
            <Switch
              checked={Boolean(settings.business_hours_only)}
              onCheckedChange={(checked) => setSettings((s) => ({ ...s, business_hours_only: checked }))}
              data-testid="settings-business-hours-toggle"
            />
          </div>
          <p className="text-xs text-slate-500 md:col-span-2">
            Note: Use Business Hours Only if you want queued applications to run only during standard office hours.
          </p>
        </CardContent>
      </Card>

      <div className="flex flex-wrap gap-3" data-testid="settings-actions-row">
        <Button onClick={save} data-testid="settings-save-button">
          Save Settings
        </Button>
        <Button variant="outline" onClick={runQueue} data-testid="settings-run-queue-button">
          Run Auto-Apply Queue Now
        </Button>
      </div>
    </div>
  );
}
