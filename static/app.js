document.addEventListener('DOMContentLoaded', () => {
    
    // --- Global State ---
    let authToken = localStorage.getItem('gateway_token') || null;

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
    const kbForm = document.getElementById('kb-form');

    // --- Initialization ---
    if (authToken) {
        // Optimistically show dashboard, fetch logs will fail if invalid
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
        fetchLogs();
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
            // Remove active from all
            navButtons.forEach(b => b.classList.remove('active'));
            contentSections.forEach(s => s.classList.remove('active'));
            
            // Set active
            btn.classList.add('active');
            const targetId = btn.getAttribute('data-target');
            document.getElementById(targetId).classList.add('active');
            
            if(targetId === 'logs-section') {
                fetchLogs();
            }
        });
    });

    // --- Authentication ---
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const token = tokenInput.value.trim();
        if (!token) return;

        authToken = token;
        // Test token validity by hitting the protected logs endpoint
        try {
            const resp = await fetch('/api/logs', {
                headers: { 'Authorization': `Bearer ${authToken}` }
            });
            if (resp.ok) {
                localStorage.setItem('gateway_token', authToken);
                showToast('Authenticated successfully', true);
                showDashboard();
            } else {
                handleLogout(); // clear invalid state
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

    // --- Fetch Logs ---
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

            data.forEach(log => {
                const tr = document.createElement('tr');
                
                // Format date safely
                const dateRaw = new Date(log.timestamp);
                const timeStr = isNaN(dateRaw) ? "Invalid Date" : dateRaw.toISOString().replace('T', ' ').substring(0, 19);

                // Format Status Code Badge
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
            });
        } catch (err) {
            console.error(err);
            showToast('Failed to fetch audit logs');
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

});
