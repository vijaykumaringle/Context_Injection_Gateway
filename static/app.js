document.addEventListener('DOMContentLoaded', () => {
    
    // --- Global State ---
    let authToken = localStorage.getItem('gateway_token') || null;
    let usageChartInstance = null;

    // --- DOM Elements ---
    const loginScreen = document.getElementById('login-screen');
    const dashboard = document.getElementById('dashboard');
    const loginForm = document.getElementById('login-form');
    const tokenInput = document.getElementById('token-input');
    const logoutBtn = document.getElementById('logout-btn');
    const navButtons = document.querySelectorAll('.nav-btn[data-target]');
    const contentSections = document.querySelectorAll('.content-section');
    const toast = document.getElementById('toast');
    const logsTbody = document.querySelector('#logs-table tbody');
    const identitiesTbody = document.querySelector('#identities-table tbody');
    const apikeysTbody = document.querySelector('#apikeys-table tbody');
    const kbForm = document.getElementById('kb-form');
    const apikeysForm = document.getElementById('apikeys-form');

    // --- Initialization ---
    if (authToken) {
        showDashboard();
    }

    // --- UI Logic ---
    function showToast(message, isSuccess = false) {
        toast.textContent = message;
        toast.className = isSuccess ? 'show success' : 'show';
        
        setTimeout(() => {
            toast.className = '';
        }, 3000);
    }

    function showDashboard() {
        loginScreen.style.display = 'none';
        dashboard.style.display = 'flex';
        initChart();
        fetchLogs();
        fetchIdentities();
        fetchKeys();
    }

    function handleLogout() {
        localStorage.removeItem('gateway_token');
        authToken = null;
        dashboard.style.display = 'none';
        loginScreen.style.display = 'block';
        tokenInput.value = '';
    }

    // --- Tab Switching ---
    navButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            navButtons.forEach(b => b.classList.remove('active'));
            contentSections.forEach(s => s.classList.remove('active'));
            
            btn.classList.add('active');
            const targetId = btn.getAttribute('data-target');
            document.getElementById(targetId).classList.add('active');
            
            if(targetId === 'logs-section' || targetId === 'analytics-section') {
                fetchLogs();
            }
            if(targetId === 'identities-section') {
                fetchIdentities();
            }
            if(targetId === 'apikeys-section') {
                fetchKeys();
            }
        });
    });

    // --- Authentication ---
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const token = tokenInput.value.trim();
        if (!token) return;

        authToken = token;
        try {
            const resp = await fetch('/api/logs', {
                headers: { 'Authorization': `Bearer ${authToken}` }
            });
            if (resp.ok) {
                localStorage.setItem('gateway_token', authToken);
                showToast('Authenticated successfully', true);
                showDashboard();
            } else {
                handleLogout();
                if (resp.status === 403) {
                    showToast('Access Denied: Admins Only');
                } else {
                    showToast('Invalid Token Signature');
                }
            }
        } catch (err) {
            showToast('Network error connecting to Gateway');
        }
    });

    logoutBtn.addEventListener('click', handleLogout);

    // --- Chart Initialization ---
    function initChart() {
        const ctx = document.getElementById('usageChart').getContext('2d');
        if (usageChartInstance) {
            usageChartInstance.destroy();
        }
        usageChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Input Tokens',
                    data: [],
                    borderColor: '#38bdf8',
                    backgroundColor: 'rgba(56, 189, 248, 0.1)',
                    fill: true,
                    tension: 0.4
                }, {
                    label: 'Output Tokens',
                    data: [],
                    borderColor: '#c084fc',
                    backgroundColor: 'rgba(192, 132, 252, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: '#f8fafc' } }
                },
                scales: {
                    x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148, 163, 184, 0.1)' } },
                    y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148, 163, 184, 0.1)' }, beginAtZero: true }
                }
            }
        });
    }

    // --- Fetch Logs & Update Analytics ---
    async function fetchLogs() {
        if (!authToken) return;
        try {
            const resp = await fetch('/api/logs', {
                headers: { 'Authorization': `Bearer ${authToken}` }
            });
            
            if (resp.status === 401 || resp.status === 403) {
                handleLogout();
                showToast('Session expired or unauthorized');
                return;
            }

            const data = await resp.json();
            
            logsTbody.innerHTML = '';
            
            if (data.length === 0) {
                logsTbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-secondary);">No audit logs captured yet.</td></tr>`;
                return;
            }

            let totalTokens = 0;
            let totalLatency = 0;
            const chartLabels = [];
            const inputData = [];
            const outputData = [];

            // Sort data chronological for chart
            const chartData = [...data].reverse();

            data.forEach(log => {
                const tr = document.createElement('tr');
                const dateRaw = new Date(log.timestamp);
                const timeStr = isNaN(dateRaw) ? "Invalid Date" : dateRaw.toISOString().replace('T', ' ').substring(0, 19);

                const isError = log.status_code >= 400;
                const badgeClass = isError ? 'status-badge status-error' : 'status-badge status-success';

                tr.innerHTML = `
                    <td>${timeStr}</td>
                    <td><span style="color: var(--accent-blue);">${log.role}</span></td>
                    <td style="font-family: monospace; color: var(--text-secondary);">${log.user_pseudo_id}</td>
                    <td><span style="opacity: 0.7">${log.input_tokens} →</span> ${log.output_tokens}</td>
                    <td><span class="${badgeClass}">${log.status_code}</span></td>
                `;
                logsTbody.appendChild(tr);

                totalTokens += log.input_tokens + log.output_tokens;
                totalLatency += log.duration_ms;
            });

            chartData.forEach(log => {
                const d = new Date(log.timestamp);
                chartLabels.push(d.getHours() + ':' + String(d.getMinutes()).padStart(2, '0'));
                inputData.push(log.input_tokens);
                outputData.push(log.output_tokens);
            });

            // Update stats
            document.getElementById('stat-req-count').innerText = data.length;
            document.getElementById('stat-token-count').innerText = totalTokens.toLocaleString();
            document.getElementById('stat-avg-latency').innerText = Math.round(totalLatency / data.length) + 'ms';

            // Update chart
            if (usageChartInstance) {
                usageChartInstance.data.labels = chartLabels;
                usageChartInstance.data.datasets[0].data = inputData;
                usageChartInstance.data.datasets[1].data = outputData;
                usageChartInstance.update();
            }
        } catch (err) {
            console.error(err);
            showToast('Failed to fetch audit logs');
        }
    }

    // --- Fetch Identities ---
    async function fetchIdentities() {
        if (!authToken) return;
        try {
            const resp = await fetch('/api/users', {
                headers: { 'Authorization': `Bearer ${authToken}` }
            });
            if (resp.ok) {
                const data = await resp.json();
                identitiesTbody.innerHTML = '';
                if (data.length === 0) {
                    identitiesTbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-secondary);">No identities resolved yet.</td></tr>`;
                    return;
                }
                data.forEach(user => {
                    const tr = document.createElement('tr');
                    const dateRaw = new Date(user.created_at);
                    const timeStr = isNaN(dateRaw) ? "Invalid Date" : dateRaw.toISOString().replace('T', ' ').substring(0, 10);
                    tr.innerHTML = `
                        <td>${user.user_id}</td>
                        <td style="font-family: monospace; color: var(--accent-purple);">${user.user_pseudo_id}</td>
                        <td>${user.role}</td>
                        <td>${timeStr}</td>
                    `;
                    identitiesTbody.appendChild(tr);
                });
            }
        } catch (err) {
            console.error(err);
            showToast('Failed to fetch identities');
        }
    }

    // --- Inject Knowledge Base (RAG) ---
    kbForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const payload = {
            doc_id: document.getElementById('kb-doc-id').value,
            role: document.getElementById('kb-role').value,
            topic: document.getElementById('kb-topic').value,
            document: document.getElementById('kb-content').value
        };

        try {
            const resp = await fetch('/api/documents', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify(payload)
            });

            if (resp.ok) {
                showToast('Vector successfully injected into ChromaDB!', true);
                kbForm.reset();
            } else {
                showToast(`Failed to inject: ${resp.status}`);
            }
        } catch (err) {
            showToast('Network error injecting vector');
        }
    });

    // --- API Keys Management ---
    async function fetchKeys() {
        if (!authToken) return;
        try {
            const resp = await fetch('/api/keys', {
                headers: { 'Authorization': `Bearer ${authToken}` }
            });
            if (resp.ok) {
                const data = await resp.json();
                apikeysTbody.innerHTML = '';
                if (data.length === 0) {
                    apikeysTbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-secondary);">No API keys generated yet.</td></tr>`;
                    return;
                }
                data.forEach(key => {
                    const tr = document.createElement('tr');
                    const statusHtml = key.is_revoked ? `<span class="status-badge status-error">Revoked</span>` : `<span class="status-badge status-success">Active</span>`;
                    const actionHtml = key.is_revoked ? `` : `<button onclick="window.revokeKey(${key.id})" style="padding: 0.25rem 0.5rem; background: var(--accent-red);">Revoke</button>`;
                    
                    tr.innerHTML = `
                        <td>${key.user_id}</td>
                        <td style="font-family: monospace; color: var(--text-secondary);">${key.prefix}...</td>
                        <td><span style="color: var(--accent-blue);">${key.tier}</span></td>
                        <td>${statusHtml}</td>
                        <td>${actionHtml}</td>
                    `;
                    apikeysTbody.appendChild(tr);
                });
            }
        } catch (err) {
            console.error(err);
            showToast('Failed to fetch API keys');
        }
    }

    if (apikeysForm) {
        apikeysForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const payload = {
                user_id: document.getElementById('apikey-user').value,
                tier: document.getElementById('apikey-tier').value
            };
            try {
                const resp = await fetch('/api/keys', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
                    body: JSON.stringify(payload)
                });
                if (resp.ok) {
                    const data = await resp.json();
                    alert(`API Key Generated: ${data.raw_key}\n\nPlease copy this now. It will not be shown again.`);
                    showToast('API Key generated successfully', true);
                    apikeysForm.reset();
                    fetchKeys();
                } else {
                    showToast(`Failed to generate key: ${resp.status}`);
                }
            } catch (err) {
                showToast('Network error generating key');
            }
        });
    }

    window.revokeKey = async function(id) {
        if(!confirm("Are you sure you want to revoke this API key?")) return;
        try {
            const resp = await fetch(`/api/keys/${id}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${authToken}` }
            });
            if (resp.ok) {
                showToast('Key revoked successfully', true);
                fetchKeys();
            }
        } catch (err) {
            showToast('Network error revoking key');
        }
    };

});
