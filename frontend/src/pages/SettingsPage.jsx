import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { api } from "@/lib/api";

export default function SettingsPage() {
  const [settings, setSettings] = useState(null);
  const [error, setError] = useState("");

  const loadSettings = async () => {
    try {
      setError("");
      const result = await api.getSettings();
      setSettings(result);
    } catch {
      setError("Could not load settings.");
    }
  };

  useEffect(() => {
    loadSettings();
  }, []);

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
          <Input
            value={settings.adzuna_app_id || ""}
            onChange={(e) => setSettings((s) => ({ ...s, adzuna_app_id: e.target.value }))}
            placeholder="Adzuna App ID"
            data-testid="settings-adzuna-app-id-input"
          />
          <Input
            value={settings.adzuna_app_key || ""}
            onChange={(e) => setSettings((s) => ({ ...s, adzuna_app_key: e.target.value }))}
            placeholder="Adzuna App Key"
            data-testid="settings-adzuna-app-key-input"
          />
          <Input
            value={settings.resend_api_key || ""}
            onChange={(e) => setSettings((s) => ({ ...s, resend_api_key: e.target.value }))}
            placeholder="Resend API Key"
            data-testid="settings-resend-api-key-input"
          />
          <Input
            value={settings.sender_email || ""}
            onChange={(e) => setSettings((s) => ({ ...s, sender_email: e.target.value }))}
            placeholder="Sender email"
            data-testid="settings-sender-email-input"
          />
        </CardContent>
      </Card>

      <Card className="border-white/10 bg-white/[0.04]" data-testid="settings-automation-card">
        <CardHeader>
          <CardTitle data-testid="settings-automation-title">Auto-Apply Rules</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <Input
            type="number"
            value={settings.score_threshold}
            onChange={(e) => setSettings((s) => ({ ...s, score_threshold: e.target.value }))}
            placeholder="Score threshold"
            data-testid="settings-score-threshold-input"
          />
          <Input
            type="number"
            value={settings.daily_application_limit}
            onChange={(e) => setSettings((s) => ({ ...s, daily_application_limit: e.target.value }))}
            placeholder="Daily application limit"
            data-testid="settings-daily-limit-input"
          />
          <Input
            type="number"
            value={settings.discovery_interval_hours}
            onChange={(e) => setSettings((s) => ({ ...s, discovery_interval_hours: e.target.value }))}
            placeholder="Discovery interval (hours)"
            data-testid="settings-discovery-interval-input"
          />
          <Input
            value={settings.resume_template}
            onChange={(e) => setSettings((s) => ({ ...s, resume_template: e.target.value }))}
            placeholder="Resume template (Modern/Classic/Minimal)"
            data-testid="settings-template-input"
          />

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
