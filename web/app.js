const q = (sel) => document.querySelector(sel);
const tabs = document.querySelectorAll('.tab');
const panels = document.querySelectorAll('.tab-panel');

for (const t of tabs) {
  t.addEventListener('click', () => {
    tabs.forEach(x => x.classList.remove('active'));
    panels.forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    q('#' + t.dataset.tab).classList.add('active');
    if (t.dataset.tab === 'admin') {
      loadDocs();
      loadLogs();
    }
  });
}

function addChat(role, text, extra = '') {
  const log = q('#chatLog');
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  div.innerHTML = `<strong>${role === 'user' ? 'You' : 'Assistant'}:</strong> ${text}${extra ? `<div class="small">${extra}</div>` : ''}`;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

async function askQuestion() {
  const query = q('#query').value.trim();
  if (!query) return;
  const role = q('#role').value;
  q('#query').value = '';
  addChat('user', query, `Role: ${role}`);

  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({query, role})
  });
  const data = await res.json();
  const citations = (data.citations || []).map(c => `${c.source_title} (${c.section}, ${c.last_updated})`).join(' | ');
  addChat('bot', data.answer, `Confidence: ${data.confidence}; Citations: ${citations || 'none'}`);
}

q('#askBtn').addEventListener('click', askQuestion);
q('#query').addEventListener('keydown', (e) => { if (e.key === 'Enter') askQuestion(); });

async function loadDocs() {
  const res = await fetch('/api/admin/docs');
  const data = await res.json();
  const list = q('#docsList');
  list.innerHTML = '';
  for (const doc of data.documents) {
    const el = document.createElement('div');
    el.className = 'item';
    el.innerHTML = `<strong>${doc.title}</strong><br><span class="small">${doc.department} • ${doc.access.join(', ')} • ${doc.updated_at}</span><p>${doc.content}</p>`;
    const edit = document.createElement('button');
    edit.className = 'inline-btn';
    edit.textContent = 'Edit';
    edit.onclick = () => {
      q('#docId').value = doc.id;
      q('#docTitle').value = doc.title;
      q('#docDept').value = doc.department;
      q('#docAccess').value = doc.access.join(',');
      q('#docContent').value = doc.content;
    };
    el.appendChild(edit);
    list.appendChild(el);
  }
}

async function loadLogs() {
  const res = await fetch('/api/admin/logs');
  const data = await res.json();
  const list = q('#logsList');
  list.innerHTML = '';
  for (const log of data.logs.slice().reverse()) {
    const el = document.createElement('div');
    el.className = 'item';
    el.innerHTML = `<div><strong>${log.query}</strong></div><div class="small">${log.timestamp} • role=${log.role} • confidence=${log.confidence}</div>`;
    list.appendChild(el);
  }
}

q('#docForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const payload = {
    id: q('#docId').value || undefined,
    title: q('#docTitle').value.trim(),
    department: q('#docDept').value.trim(),
    access: q('#docAccess').value.split(',').map(x => x.trim()).filter(Boolean),
    content: q('#docContent').value.trim()
  };
  await fetch('/api/admin/docs', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  e.target.reset();
  q('#docId').value = '';
  loadDocs();
});

addChat('bot', 'Welcome! Ask about pricing, onboarding, policy, or research updates.');
