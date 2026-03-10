import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const client = axios.create({ baseURL: API });

export const api = {
  backendUrl: BACKEND_URL,
  getProfile: () => client.get("/profile").then((res) => res.data),
  uploadCv: (formData) =>
    client
      .post("/profile/upload-cv", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((res) => res.data),
  getPreferences: () => client.get("/preferences").then((res) => res.data),
  updatePreferences: (payload) =>
    client.put("/preferences", payload).then((res) => res.data),
  getSettings: () => client.get("/settings").then((res) => res.data),
  updateSettings: (payload) => client.put("/settings", payload).then((res) => res.data),
  discoverJobs: () => client.post("/jobs/discover").then((res) => res.data),
  clearJobsCache: () => client.post("/jobs/clear-cache").then((res) => res.data),
  getJobs: (params) => client.get("/jobs", { params }).then((res) => res.data),
  getJobDetail: (jobId) => client.get(`/jobs/${jobId}`).then((res) => res.data),
  generateDocuments: (jobId) =>
    client.post(`/jobs/${jobId}/generate-documents`).then((res) => res.data),
  queueApplication: (jobId) =>
    client.post(`/applications/queue/${jobId}`).then((res) => res.data),
  runAutoApply: () => client.post("/auto-apply/run").then((res) => res.data),
  getApplications: () => client.get("/applications").then((res) => res.data),
  getApplicationDetail: (applicationId) =>
    client.get(`/applications/detail/${applicationId}`).then((res) => res.data),
  getApplicationsKanban: () => client.get("/applications/kanban").then((res) => res.data),
  updateApplicationStatus: (applicationId, status) =>
    client
      .patch(`/applications/${applicationId}/status`, { status })
      .then((res) => res.data),
  generateFollowupDraft: (applicationId) =>
    client.post(`/applications/detail/${applicationId}/followup/generate`).then((res) => res.data),
  sendFollowupDraft: (applicationId) =>
    client.post(`/applications/detail/${applicationId}/followup/send`).then((res) => res.data),
  getDashboardMetrics: () => client.get("/dashboard/metrics").then((res) => res.data),
  getGmailStatus: () => client.get("/gmail/status").then((res) => res.data),
  getGmailOAuthStart: (returnUrl) =>
    client.get("/gmail/oauth/start", { params: { return_url: returnUrl } }).then((res) => res.data),
  pollGmailInbox: () => client.post("/gmail/poll").then((res) => res.data),
};
