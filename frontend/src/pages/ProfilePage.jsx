import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";

const toCsv = (list) => (Array.isArray(list) ? list.join(", ") : "");
const fromCsv = (value) =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

export default function ProfilePage() {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState("");
  const [preferences, setPreferences] = useState({
    target_job_titles: "",
    preferred_industries: "",
    location_preferences: "",
    salary_min: 0,
    salary_max: 250000,
    remote_mode: "remote",
    blacklisted_companies: [],
    company_size_preference: "any",
    application_frequency: "moderate",
    auto_apply_enabled: false,
  });

  const loadData = async () => {
    try {
      setError("");
      const [profileRes, preferenceRes] = await Promise.all([api.getProfile(), api.getPreferences()]);
      setProfile(profileRes);
      setPreferences({
        ...preferenceRes,
        target_job_titles: toCsv(preferenceRes.target_job_titles),
        preferred_industries: toCsv(preferenceRes.preferred_industries),
        location_preferences: toCsv(preferenceRes.location_preferences),
      });
    } catch {
      setError("Could not load your profile right now.");
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleUpload = async () => {
    if (!file) {
      toast.error("Please select a PDF or DOCX file.");
      return;
    }
    const formData = new FormData();
    formData.append("file", file);

    try {
      setUploading(true);
      const response = await api.uploadCv(formData);
      setProfile(response);
      toast.success("CV uploaded and parsed successfully.");
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Upload failed.");
    } finally {
      setUploading(false);
    }
  };

  const handlePreferencesSave = async () => {
    try {
      const payload = {
        ...preferences,
        target_job_titles: fromCsv(preferences.target_job_titles || ""),
        preferred_industries: fromCsv(preferences.preferred_industries || ""),
        location_preferences: fromCsv(preferences.location_preferences || ""),
        salary_min: Number(preferences.salary_min) || 0,
        salary_max: Number(preferences.salary_max) || 250000,
        blacklisted_companies: preferences.blacklisted_companies || [],
        company_size_preference: preferences.company_size_preference || "any",
        application_frequency: preferences.application_frequency || "moderate",
        auto_apply_enabled: preferences.auto_apply_enabled || false,
      };
      const updated = await api.updatePreferences(payload);
      setPreferences({
        ...updated,
        target_job_titles: toCsv(updated.target_job_titles),
        preferred_industries: toCsv(updated.preferred_industries),
        location_preferences: toCsv(updated.location_preferences),
      });
      toast.success("Preferences updated.");
    } catch {
      toast.error("Could not save preferences.");
    }
  };

  return (
    <div className="space-y-6" data-testid="profile-page">
      <h2 className="text-4xl font-semibold text-white sm:text-5xl" data-testid="profile-heading">
        Profile & CV Intelligence
      </h2>

      {error && (
        <Card className="border-red-500/40 bg-red-500/10" data-testid="profile-error-state">
          <CardContent className="p-4 text-sm text-red-200">{error}</CardContent>
        </Card>
      )}

      <Card className="border-white/10 bg-white/[0.04]" data-testid="cv-upload-card">
        <CardHeader>
          <CardTitle data-testid="cv-upload-title">Upload Resume (PDF / DOCX)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Input
            type="file"
            accept=".pdf,.docx"
            onChange={(event) => setFile(event.target.files?.[0] || null)}
            data-testid="cv-file-input"
          />
          <Button onClick={handleUpload} disabled={uploading} data-testid="cv-upload-button">
            {uploading ? "Parsing CV..." : "Upload and Parse CV"}
          </Button>

          <div className="rounded-lg border border-white/10 bg-black/30 p-4" data-testid="parsed-summary-box">
            <p className="text-sm text-slate-400" data-testid="parsed-file-name">
              Uploaded file: {profile?.filename || "No resume uploaded yet"}
            </p>
            <p className="mt-2 text-sm text-slate-300" data-testid="parsed-skills-preview">
              Parsed skills: {(profile?.parsed?.skills_technical || []).slice(0, 10).join(", ") || "—"}
            </p>
            <Textarea
              className="mt-3 min-h-36"
              value={profile?.parsed?.summary || ""}
              readOnly
              data-testid="parsed-summary-text"
            />
          </div>
        </CardContent>
      </Card>

      <Card className="border-white/10 bg-white/[0.04]" data-testid="preferences-card">
        <CardHeader>
          <CardTitle data-testid="preferences-title">Job Preferences</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <Input
            value={preferences.target_job_titles || ""}
            onChange={(e) => setPreferences((s) => ({ ...s, target_job_titles: e.target.value }))}
            placeholder="Target titles (comma-separated)"
            data-testid="preferences-target-titles-input"
          />
          <Input
            value={preferences.preferred_industries || ""}
            onChange={(e) => setPreferences((s) => ({ ...s, preferred_industries: e.target.value }))}
            placeholder="Preferred industries"
            data-testid="preferences-industries-input"
          />
          <Input
            value={preferences.location_preferences || ""}
            onChange={(e) => setPreferences((s) => ({ ...s, location_preferences: e.target.value }))}
            placeholder="Locations"
            data-testid="preferences-locations-input"
          />
          <Input
            value={preferences.remote_mode || "remote"}
            onChange={(e) => setPreferences((s) => ({ ...s, remote_mode: e.target.value }))}
            placeholder="remote / hybrid / onsite / any"
            data-testid="preferences-remote-mode-input"
          />
          <Input
            type="number"
            value={preferences.salary_min || 0}
            onChange={(e) => setPreferences((s) => ({ ...s, salary_min: e.target.value }))}
            placeholder="Minimum salary"
            data-testid="preferences-salary-min-input"
          />
          <Input
            type="number"
            value={preferences.salary_max || 0}
            onChange={(e) => setPreferences((s) => ({ ...s, salary_max: e.target.value }))}
            placeholder="Maximum salary"
            data-testid="preferences-salary-max-input"
          />
          <div className="md:col-span-2">
            <Button onClick={handlePreferencesSave} data-testid="preferences-save-button">
              Save Preferences
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
