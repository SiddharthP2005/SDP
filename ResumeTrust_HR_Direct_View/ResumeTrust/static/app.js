/**
 * ResumeTrust Frontend (fixed)
 */

const API = "";
let token = localStorage.getItem("rt_token") || null;
let currentUser = null;

// ---------- Helpers ----------
function toast(msg, type = "info") {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.className = `toast ${type}`;
  setTimeout(() => el.classList.add("hidden"), 3500);
}

async function api(method, path, body = null) {
  // Always read the latest token from localStorage
  token = localStorage.getItem("rt_token") || null;

  const opts = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (token) {
    opts.headers["Authorization"] = "Bearer " + token;
  }
  if (body) opts.body = JSON.stringify(body);

  const res = await fetch(API + path, opts);

  // Auto logout on 401
  if (res.status === 401 && path !== "/api/login") {
    logout();
    throw new Error("Session expired. Please login again.");
  }

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || ("HTTP " + res.status));
  }
  return data;
}

function statusClass(s) {
  return "status status-" + s;
}

// ---------- Auth ----------
async function doLogin() {
  const email = document.getElementById("login-email").value.trim();
  const password = document.getElementById("login-password").value;
  if (!email || !password) {
    toast("Enter email and password", "error");
    return;
  }
  try {
    const data = await api("POST", "/api/login", { email, password });
    token = data.token;
    currentUser = data.user;
    localStorage.setItem("rt_token", token);
    localStorage.setItem("rt_user", JSON.stringify(currentUser));
    showMain();
    toast("Welcome, " + currentUser.full_name + "!", "success");
  } catch (e) {
    toast(e.message, "error");
  }
}

function logout() {
  token = null;
  currentUser = null;
  localStorage.removeItem("rt_token");
  localStorage.removeItem("rt_user");
  document.getElementById("main-screen").classList.add("hidden");
  document.getElementById("login-screen").classList.remove("hidden");
  // Clear content
  const content = document.getElementById("content");
  if (content) content.innerHTML = "";
}

function showMain() {
  document.getElementById("login-screen").classList.add("hidden");
  document.getElementById("main-screen").classList.remove("hidden");
  document.getElementById("user-badge").textContent =
    currentUser.full_name + " (" + currentUser.role + ")";
  buildNav();
  const defaultTab = currentUser.role === "hr" ? "resumes" :
                     currentUser.role === "placement" ? "resumes" : "my-resume";
  switchTab(defaultTab);
}

function buildNav() {
  const nav = document.getElementById("nav-tabs");
  const role = currentUser.role;
  let tabs = [];

  if (role === "student") {
    tabs = [
      { id: "my-resume", label: "My Resume" },
      { id: "drives", label: "Placement Drives" },
      { id: "academics", label: "Academic Record" },
    ];
  } else if (role === "placement") {
    tabs = [
      { id: "resumes", label: "All Resumes" },
      { id: "drives", label: "Placement Drives" },
      { id: "academics", label: "Academic Records" },
      { id: "audit", label: "Audit Log" },
    ];
  } else if (role === "hr") {
    tabs = [
      { id: "resumes", label: "Student Resumes" },
      { id: "drives", label: "Placement Drives" },
    ];
  }

  nav.innerHTML = tabs.map(function(t) {
    return '<div class="nav-tab" data-tab="' + t.id + '" onclick="switchTab(\'' + t.id + '\')">' + t.label + '</div>';
  }).join("");
}

function switchTab(tabId) {
  document.querySelectorAll(".nav-tab").forEach(function(el) {
    el.classList.toggle("active", el.dataset.tab === tabId);
  });
  const content = document.getElementById("content");
  content.innerHTML = '<div class="empty">Loading…</div>';

  const loaders = {
    "my-resume": loadMyResume,
    "resumes": loadResumes,
    "requests": loadRequests,
    "drives": loadDrives,
    "academics": loadAcademics,
    "audit": loadAudit,
  };
  if (loaders[tabId]) loaders[tabId]();
}

// ---------- Student: My Resume ----------
async function loadMyResume() {
  const content = document.getElementById("content");
  try {
    const data = await api("GET", "/api/resumes");
    const resumes = data.resumes || [];
    let html = '<h2 class="page-title">Submit Resume to Placement Cell</h2>' +
      '<p class="page-sub">Choose your demo PDF. It is encrypted in this browser before it is uploaded. Placement Cell performs the verification decryption; HR can view or download the decrypted PDF immediately after Placement Cell verifies and forwards it.</p>' +
      '<div class="card upload-panel"><div class="card-title">1. Upload your resume</div>' +
      '<div class="form-group" style="margin-top:14px"><label>Resume PDF</label><input type="file" id="resume-file" accept="application/pdf,.pdf" /></div>' +
      '<button class="btn btn-primary" style="width:auto" onclick="encryptAndUploadResume()">🔐 Encrypt & Submit to Placement Cell</button>' +
      '<p class="card-meta" style="margin-top:10px">Encryption: AES-256-GCM (one-time key) · Key protection: RSA-OAEP / SHA-256 · Integrity: SHA-256</p><p class="card-meta">Demo PDFs are available in the extracted <code>demo_resumes</code> folder.</p></div>' +
      '<div class="info-box"><strong>Live security flow:</strong> Student selects PDF → browser calculates SHA-256 → browser encrypts PDF with AES-256-GCM → AES key is wrapped using Placement Cell RSA public key → encrypted file is stored → Placement Cell unwraps key and decrypts → SHA-256 is checked → verified file is forwarded to Company HR.</div>';

    if (!resumes.length) {
      html += '<div class="card empty">No resume submitted yet. Upload a PDF to start the workflow.</div>';
    }
    resumes.forEach(function(r) {
      html += '<div class="card"><div class="card-header"><div><div class="card-title">' + escapeHtml(r.original_filename) + '</div>' +
        '<div class="card-meta">Submitted: ' + new Date(r.uploaded_at).toLocaleString() + '</div></div>' +
        '<span class="status ' + (r.forwarded_to_hr ? 'status-granted' : r.integrity_verified ? 'status-verified' : 'status-pending') + '">' +
        (r.forwarded_to_hr ? 'Forwarded to HR' : r.verified_by_placement ? 'Reviewed by Placement' : r.integrity_verified ? 'Integrity checked' : 'Awaiting Placement Cell') + '</span></div>' +
        '<div class="workflow"><div class="workflow-step done"><b>1</b><span>Student encryption</span><small>AES-256-GCM</small></div>' +
        '<div class="workflow-step ' + (r.decrypted_by_placement ? 'done' : '') + '"><b>2</b><span>Placement decryption</span><small>' + (r.decrypted_by_placement ? 'Completed' : 'Pending') + '</small></div>' +
        '<div class="workflow-step ' + (r.integrity_verified ? 'done' : '') + '"><b>3</b><span>SHA-256 check</span><small>' + (r.integrity_verified ? 'Matched' : 'Pending') + '</small></div>' +
        '<div class="workflow-step ' + (r.forwarded_to_hr ? 'done' : '') + '"><b>4</b><span>Company HR</span><small>' + (r.forwarded_to_hr ? 'Forwarded' : 'Not sent') + '</small></div></div>' +
        '<div style="margin-top:12px"><span class="crypto-badge">🔒 ' + escapeHtml(r.encryption_method || 'AES-256-GCM') + '</span> ' +
        '<span class="crypto-badge">SHA-256 ' + String(r.sha256_hash || '').slice(0, 18) + '…</span></div>' +
        (r.verification_notes ? '<p class="card-meta" style="margin-top:10px">Placement note: ' + escapeHtml(r.verification_notes) + '</p>' : '') +
        '<div class="card-meta" style="margin-top:10px">Keep your original PDF locally. The server stores only the encrypted copy.</div></div>';
    });
    content.innerHTML = html;
  } catch (e) { content.innerHTML = '<div class="empty">' + escapeHtml(e.message) + '</div>'; }
}

function bytesToBase64(bytes) {
  let binary = ''; const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
  return btoa(binary);
}
function pemToArrayBuffer(pem) {
  const b64 = pem.replace(/-----BEGIN PUBLIC KEY-----|-----END PUBLIC KEY-----|\s/g, '');
  const raw = atob(b64); const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out.buffer;
}
function escapeHtml(value) {
  return String(value == null ? '' : value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
async function encryptAndUploadResume() {
  const input = document.getElementById('resume-file');
  const file = input && input.files && input.files[0];
  if (!file) { toast('Choose a PDF resume first', 'error'); return; }
  if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) { toast('Only PDF resumes are supported', 'error'); return; }
  if (file.size > 10 * 1024 * 1024) { toast('PDF must be 10 MB or smaller', 'error'); return; }
  try {
    toast('Encrypting resume in your browser…', 'info');
    const plain = await file.arrayBuffer();
    const digest = await crypto.subtle.digest('SHA-256', plain);
    const hash = Array.from(new Uint8Array(digest)).map(b => b.toString(16).padStart(2, '0')).join('');
    const aesKey = await crypto.subtle.generateKey({name:'AES-GCM', length:256}, true, ['encrypt']);
    const nonce = crypto.getRandomValues(new Uint8Array(12));
    const aad = new TextEncoder().encode('ResumeTrust-Student-Upload');
    const encrypted = await crypto.subtle.encrypt({name:'AES-GCM', iv:nonce, additionalData:aad, tagLength:128}, aesKey, plain);
    const rawAesKey = await crypto.subtle.exportKey('raw', aesKey);
    const keyInfo = await api('GET', '/api/crypto/public-key');
    const publicKey = await crypto.subtle.importKey('spki', pemToArrayBuffer(keyInfo.public_key),
      {name:'RSA-OAEP', hash:'SHA-256'}, false, ['encrypt']);
    const wrapped = await crypto.subtle.encrypt({name:'RSA-OAEP'}, publicKey, rawAesKey);
    const payload = {
      filename:file.name, content_base64:bytesToBase64(new Uint8Array(encrypted)),
      nonce:bytesToBase64(nonce), wrapped_key:bytesToBase64(new Uint8Array(wrapped)), sha256:hash
    };
    const result = await api('POST', '/api/resumes/upload', payload);
    toast('Encrypted and submitted. Placement Cell can now decrypt and verify it.', 'success');
    loadMyResume();
  } catch (e) { toast('Upload failed: ' + e.message, 'error'); }
}

// ---------- Resumes list (Placement / HR) ----------
async function loadResumes() {
  const content = document.getElementById("content");
  try {
    const data = await api("GET", "/api/resumes");
    const resumes = data.resumes || [];
    const isHR = currentUser.role === 'hr';
    let html = '<h2 class="page-title">' + (isHR ? 'Resumes Forwarded by Placement Cell' : 'Placement Cell Verification Desk') + '</h2>' +
      '<p class="page-sub">' + (isHR ? 'Only resumes verified and forwarded by Placement Cell appear here. Open the document or download the PDF directly.' : 'Decrypt each submission and verify its SHA-256 fingerprint. Then review the resume details against official Academic Records before forwarding to Company HR.') + '</p>';
    if (!resumes.length) html += '<div class="card empty">' + (isHR ? 'No verified resumes have been forwarded to HR yet.' : 'No student submissions found.') + '</div>';
    resumes.forEach(function(r) {
      html += '<div class="card"><div class="card-header"><div><div class="card-title">' + escapeHtml(r.full_name || 'Student') + '</div>' +
        '<div class="card-meta">' + escapeHtml(r.email || '') + (r.student_id ? ' · ' + escapeHtml(r.student_id) : '') + (r.college ? ' · ' + escapeHtml(r.college) : '') + '</div>' +
        '<div class="card-meta" style="margin-top:4px">' + escapeHtml(r.original_filename) + '</div></div>' +
        '<span class="status ' + (r.forwarded_to_hr ? 'status-granted' : r.integrity_verified ? 'status-verified' : 'status-pending') + '">' +
        (r.forwarded_to_hr ? 'Forwarded to HR' : r.integrity_verified ? 'Integrity verified' : 'Encrypted · Pending review') + '</span></div>' +
        '<div><span class="crypto-badge">🔐 ' + escapeHtml(r.encryption_method || 'AES-256-GCM') + '</span> <span class="crypto-badge">SHA-256 fingerprint</span></div>' +
        '<div class="workflow"><div class="workflow-step done"><b>1</b><span>Student encrypts</span><small>Browser-side</small></div>' +
        '<div class="workflow-step ' + (r.decrypted_by_placement ? 'done' : '') + '"><b>2</b><span>Placement decrypts</span><small>' + (r.decrypted_by_placement ? 'Done' : 'Waiting') + '</small></div>' +
        '<div class="workflow-step ' + (r.integrity_verified ? 'done' : '') + '"><b>3</b><span>Integrity check</span><small>' + (r.integrity_verified ? 'SHA-256 matched' : 'Waiting') + '</small></div>' +
        '<div class="workflow-step ' + (r.forwarded_to_hr ? 'done' : '') + '"><b>4</b><span>Forward to HR</span><small>' + (r.forwarded_to_hr ? 'Sent' : 'Waiting') + '</small></div></div>' +
        '<div class="card-meta" style="margin-top:10px">Fingerprint: <code>' + escapeHtml(r.sha256_hash || '') + '</code></div><div class="actions">';
      if (currentUser.role === 'placement' && !r.integrity_verified) html += '<button class="btn btn-success btn-sm" onclick="verifyResume(' + r.id + ')">🔓 Decrypt & Verify</button> ';
      if (currentUser.role === 'placement' && r.integrity_verified && !r.forwarded_to_hr) html += '<button class="btn btn-primary btn-sm" onclick="forwardResume(' + r.id + ')">Confirm Review & Forward to HR</button> ';
      if (currentUser.role === 'placement') html += '<button class="btn btn-outline btn-sm" onclick="viewResume(' + r.id + ')">View PDF</button> <button class="btn btn-outline btn-sm" onclick="downloadResume(' + r.id + ')">Download</button> ';
      if (currentUser.role === 'hr' && r.forwarded_to_hr) html += '<button class="btn btn-primary btn-sm" onclick="viewResume(' + r.id + ')">View Document</button> <button class="btn btn-outline btn-sm" onclick="downloadResume(' + r.id + ')">Download PDF</button>';
      html += '</div></div>';
    });
    content.innerHTML = html;
  } catch (e) { content.innerHTML = '<div class="empty">' + escapeHtml(e.message) + '</div>'; }
}

async function verifyResume(id) {
  try {
    const result = await api("POST", "/api/resumes/" + id + "/verify", {
      notes: "Placement Cell decrypted the student submission and confirmed SHA-256 integrity."
    });
    toast('Decryption successful · SHA-256 matched · ' + result.bytes_verified + ' bytes verified', 'success');
    loadResumes();
  } catch (e) { toast(e.message, "error"); }
}

async function forwardResume(id) {
  const confirmed = window.confirm('Have you reviewed this decrypted resume against the student’s official academic records? Only continue if the details have been checked.');
  if (!confirmed) return;
  try {
    const result = await api('POST', '/api/resumes/' + id + '/forward', {review_confirmed:true});
    toast(result.message || 'Forwarded to Company HR', 'success');
    loadResumes();
  } catch (e) { toast(e.message, 'error'); }
}

async function requestAccess(resumeId) {
  try {
    const data = await api("POST", "/api/access-requests", {
      resume_id: resumeId,
      notes: "Requesting resume for campus recruitment evaluation"
    });
    toast(data.message || "Access request submitted", "success");
    switchTab("requests");
  } catch (e) {
    toast(e.message, "error");
  }
}

async function viewResume(id) {
  try {
    const authToken = localStorage.getItem("rt_token") || null;
    const res = await fetch("/api/resumes/" + id + "/view", {
      headers: { Authorization: "Bearer " + authToken }
    });
    if (!res.ok) {
      const err = await res.json().catch(function() { return {}; });
      throw new Error(err.error || "Unable to open resume");
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    let viewer = document.getElementById("resume-viewer");
    if (!viewer) {
      viewer = document.createElement("div");
      viewer.id = "resume-viewer";
      viewer.className = "resume-viewer";
      viewer.innerHTML = '<div class="resume-viewer-panel"><div class="resume-viewer-toolbar"><strong>Resume PDF Viewer</strong><button class="btn btn-sm" onclick="closeResumeViewer()">Close ✕</button></div><iframe title="Student resume PDF" class="resume-pdf-frame"></iframe></div>';
      document.body.appendChild(viewer);
    }
    const frame = viewer.querySelector("iframe");
    if (frame.dataset.objectUrl) URL.revokeObjectURL(frame.dataset.objectUrl);
    frame.src = url;
    frame.dataset.objectUrl = url;
    viewer.classList.add("open");
    toast("Resume opened · SHA-256 integrity verified", "success");
  } catch (e) { toast(e.message, "error"); }
}

function closeResumeViewer() {
  const viewer = document.getElementById("resume-viewer");
  if (!viewer) return;
  const frame = viewer.querySelector("iframe");
  frame.src = "about:blank";
  if (frame.dataset.objectUrl) URL.revokeObjectURL(frame.dataset.objectUrl);
  viewer.remove();
}

async function downloadResume(id) {
  try {
    token = localStorage.getItem("rt_token") || null;
    const res = await fetch("/api/resumes/" + id + "/download", {
      headers: { Authorization: "Bearer " + token }
    });
    if (!res.ok) {
      const err = await res.json().catch(function() { return {}; });
      throw new Error(err.error || "Download failed");
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "resume_" + id + ".pdf";
    a.click();
    URL.revokeObjectURL(url);
    toast("Resume downloaded (integrity verified)", "success");
  } catch (e) {
    toast(e.message, "error");
  }
}

// ---------- Access Requests ----------
async function loadRequests() {
  const content = document.getElementById("content");
  try {
    const data = await api("GET", "/api/access-requests");
    const requests = data.requests || [];

    let html = '<h2 class="page-title">Access Requests</h2>' +
      '<p class="page-sub">Legacy access-request records. Resume access is now controlled by Placement Cell forwarding; HR does not need to request access.</p>';

    if (requests.length === 0) {
      html += '<div class="card empty">No access requests yet.</div>';
    } else {
      requests.forEach(function(r) {
        const canStudentConsent = currentUser.role === "student" && r.status === "pending";
        const canPlacementApprove = currentUser.role === "placement" &&
          (r.status === "pending" || r.status === "student_approved");
        const canReject = (currentUser.role === "student" || currentUser.role === "placement") &&
          ["granted", "rejected", "revoked"].indexOf(r.status) === -1;
        const canDownload = currentUser.role === "hr" && r.status === "granted";

        html += '<div class="card"><div class="card-header"><div>' +
          '<div class="card-title">' + (r.original_filename || 'Resume') + '</div>' +
          '<div class="card-meta">' +
          (r.student_name ? 'Student: ' + r.student_name : '') +
          (r.hr_name ? ' • HR: ' + r.hr_name : '') +
          (r.company ? ' (' + r.company + ')' : '') +
          '</div><div class="card-meta">Requested: ' + new Date(r.requested_at).toLocaleString() + '</div></div>' +
          '<span class="' + statusClass(r.status) + '">' + r.status.replace(/_/g, ' ') + '</span></div>' +
          '<div style="font-size:13px;color:#64748b">Student consent: ' + (r.student_consent ? '✓' : '—') +
          ' &nbsp;|&nbsp; Placement approval: ' + (r.placement_approval ? '✓' : '—') + '</div><div class="actions">';

        if (canStudentConsent) html += '<button class="btn btn-success btn-sm" onclick="studentConsent(' + r.id + ')">Give Consent</button> ';
        if (canPlacementApprove) html += '<button class="btn btn-success btn-sm" onclick="placementApprove(' + r.id + ')">Approve</button> ';
        if (canReject) html += '<button class="btn btn-danger btn-sm" onclick="rejectRequest(' + r.id + ')">Reject</button> ';
        if (canDownload) html += '<button class="btn btn-primary btn-sm" onclick="viewResume(' + r.resume_id + ')">View Resume</button> <button class="btn btn-outline btn-sm" onclick="downloadResume(' + r.resume_id + ')">Download PDF</button>';
        html += '</div></div>';
      });
    }
    content.innerHTML = html;
  } catch (e) {
    content.innerHTML = '<div class="empty">' + e.message + '</div>';
  }
}

async function studentConsent(id) {
  try {
    const data = await api("POST", "/api/access-requests/" + id + "/student-consent");
    toast("Consent given. Status: " + data.status, "success");
    loadRequests();
  } catch (e) {
    toast(e.message, "error");
  }
}

async function placementApprove(id) {
  try {
    const data = await api("POST", "/api/access-requests/" + id + "/placement-approve");
    toast("Approved. Status: " + data.status, "success");
    loadRequests();
  } catch (e) {
    toast(e.message, "error");
  }
}

async function rejectRequest(id) {
  try {
    await api("POST", "/api/access-requests/" + id + "/reject");
    toast("Request rejected", "success");
    loadRequests();
  } catch (e) {
    toast(e.message, "error");
  }
}

// ---------- Drives ----------
async function loadDrives() {
  const content = document.getElementById("content");
  try {
    const data = await api("GET", "/api/drives");
    const drives = data.drives || [];

    let html = '<h2 class="page-title">Placement Drives</h2>' +
      '<p class="page-sub">Current and upcoming campus recruitment drives.</p>';

    if (drives.length === 0) {
      html += '<div class="card empty">No drives available.</div>';
    } else {
      drives.forEach(function(d) {
        html += '<div class="card"><div class="card-header"><div>' +
          '<div class="card-title">' + d.title + '</div>' +
          '<div class="card-meta">' + d.company_name + ' • Deadline: ' + (d.deadline || 'N/A') + '</div></div>' +
          '<span class="status status-granted">' + d.status + '</span></div>' +
          '<p style="font-size:14px;margin-top:8px">' + (d.description || '') + '</p>' +
          (d.eligibility ? '<p style="font-size:13px;color:#64748b;margin-top:6px">Eligibility: ' + d.eligibility + '</p>' : '') +
          '</div>';
      });
    }
    content.innerHTML = html;
  } catch (e) {
    content.innerHTML = '<div class="empty">' + e.message + '</div>';
  }
}

// ---------- Academics ----------
async function loadAcademics() {
  const content = document.getElementById("content");
  try {
    const data = await api("GET", "/api/academic-records");
    const records = data.records || [];

    let html = '<h2 class="page-title">Academic Records</h2>' +
      '<p class="page-sub">Authorised academic information used by Placement Cell for resume verification.</p>';

    if (records.length === 0) {
      html += '<div class="card empty">No academic records found.</div>';
    } else {
      html += '<div class="card"><table class="table"><thead><tr>' +
        '<th>Student</th><th>10th %</th><th>12th %</th><th>CGPA</th><th>Degree</th><th>Branch</th><th>YOP</th>' +
        '</tr></thead><tbody>';
      records.forEach(function(r) {
        html += '<tr><td>' + (r.full_name || currentUser.full_name) +
          '<br><small style="color:#64748b">' + (r.email || '') + '</small></td>' +
          '<td>' + r.tenth_percentage + '</td><td>' + r.twelfth_percentage + '</td>' +
          '<td>' + r.degree_cgpa + '</td><td>' + r.degree_name + '</td>' +
          '<td>' + r.branch + '</td><td>' + r.year_of_passing + '</td></tr>';
      });
      html += '</tbody></table></div>';
    }
    content.innerHTML = html;
  } catch (e) {
    content.innerHTML = '<div class="empty">' + e.message + '</div>';
  }
}

// ---------- Audit Log ----------
async function loadAudit() {
  const content = document.getElementById("content");
  try {
    const data = await api("GET", "/api/audit-logs");
    const logs = data.logs || [];

    let html = '<h2 class="page-title">Audit Log</h2>' +
      '<p class="page-sub">HMAC-SHA256 protected activity log for security and compliance.</p>' +
      '<div class="card"><table class="table"><thead><tr>' +
      '<th>Time</th><th>Actor</th><th>Action</th><th>Resource</th><th>Details</th></tr></thead><tbody>';
    logs.forEach(function(l) {
      html += '<tr><td style="white-space:nowrap">' + new Date(l.created_at).toLocaleString() + '</td>' +
        '<td>' + (l.actor_id || '—') + '</td><td><code>' + l.action + '</code></td>' +
        '<td>' + (l.resource_type || '') + ' ' + (l.resource_id || '') + '</td>' +
        '<td style="max-width:240px;overflow:hidden;text-overflow:ellipsis">' + (l.details || '') + '</td></tr>';
    });
    html += '</tbody></table></div>';
    content.innerHTML = html;
  } catch (e) {
    content.innerHTML = '<div class="empty">' + e.message + '</div>';
  }
}

// ---------- Init ----------
document.addEventListener("DOMContentLoaded", function() {
  document.getElementById("login-password")?.addEventListener("keydown", function(e) {
    if (e.key === "Enter") doLogin();
  });

  token = localStorage.getItem("rt_token") || null;
  if (token) {
    currentUser = JSON.parse(localStorage.getItem("rt_user") || "null");
    if (currentUser) {
      api("GET", "/api/me").then(function(data) {
        currentUser = data.user;
        localStorage.setItem("rt_user", JSON.stringify(currentUser));
        showMain();
      }).catch(function() {
        logout();
      });
    } else {
      logout();
    }
  }
});
