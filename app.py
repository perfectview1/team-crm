from __future__ import annotations

import os
from functools import wraps
from typing import Optional

from flask import Flask, g, jsonify, redirect, render_template_string, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.environ["DATABASE_URL"]
SECRET_KEY = os.environ.get("TEAM_CRM_SECRET", "change-this-secret-key")
PORT = int(os.environ.get("PORT", "5000"))

APP_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Team CRM</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 text-slate-900">
  <div class="max-w-7xl mx-auto p-6 space-y-6">
    <div class="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div>
        <h1 class="text-3xl font-bold">Team CRM</h1>
        <p class="text-slate-600 mt-1">Shared CRM for your team, accessible from anywhere.</p>
        <p class="text-sm text-slate-500 mt-2">Signed in as <span id="currentUser"></span></p>
      </div>
      <div class="flex gap-3">
        <button id="logoutBtn" class="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm">Log out</button>
      </div>
    </div>

    <div id="notice" class="hidden rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm"></div>

    <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
      <div class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div class="text-xs uppercase tracking-wide text-slate-500">Contacts</div>
        <div id="metricTotal" class="mt-2 text-2xl font-semibold">0</div>
      </div>
      <div class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div class="text-xs uppercase tracking-wide text-slate-500">Active deals</div>
        <div id="metricActive" class="mt-2 text-2xl font-semibold">0</div>
      </div>
      <div class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div class="text-xs uppercase tracking-wide text-slate-500">Pipeline</div>
        <div id="metricPipeline" class="mt-2 text-2xl font-semibold">$0</div>
      </div>
      <div class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div class="text-xs uppercase tracking-wide text-slate-500">Won</div>
        <div id="metricWon" class="mt-2 text-2xl font-semibold">$0</div>
      </div>
    </div>

    <div class="grid gap-6 xl:grid-cols-[1.2fr_0.9fr]">
      <div class="space-y-6">
        <div class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div class="flex flex-col gap-3 md:flex-row">
            <input id="searchInput" class="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" placeholder="Search by name, company, or email">
            <select id="stageFilter" class="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm md:max-w-48">
              <option value="All">All</option>
              <option value="Lead">Lead</option>
              <option value="Qualified">Qualified</option>
              <option value="Proposal">Proposal</option>
              <option value="Won">Won</option>
              <option value="Lost">Lost</option>
            </select>
          </div>
        </div>

        <div class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div class="mb-4 flex items-center justify-between">
            <h2 class="text-lg font-semibold">Contacts</h2>
            <span id="resultCount" class="text-sm text-slate-500">0 shown</span>
          </div>
          <div id="contactList" class="space-y-3"></div>
        </div>
      </div>

      <div class="space-y-6">
        <div class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 class="mb-4 text-lg font-semibold">Contact details</h2>
          <div id="contactDetails" class="text-sm text-slate-500">Select a contact</div>
        </div>

        <form id="contactForm" class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm space-y-4">
          <div>
            <h2 id="formTitle" class="text-lg font-semibold">Add new contact</h2>
            <p class="mt-1 text-sm text-slate-500">Changes are shared with the whole team.</p>
          </div>

          <input id="contactId" type="hidden">

          <div class="grid gap-3 md:grid-cols-2">
            <input id="name" class="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" placeholder="Full name" required>
            <input id="company" class="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" placeholder="Company" required>
            <input id="email" type="email" class="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" placeholder="Email" required>
            <select id="stage" class="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm">
              <option>Lead</option>
              <option>Qualified</option>
              <option>Proposal</option>
              <option>Won</option>
              <option>Lost</option>
            </select>
            <input id="value" type="number" class="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" placeholder="Deal value">
            <input id="last_contact" type="date" class="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm">
          </div>

          <textarea id="notes" class="min-h-24 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" placeholder="Notes"></textarea>

          <div class="flex gap-3">
            <button class="rounded-2xl bg-slate-900 px-4 py-2.5 text-sm font-medium text-white" type="submit">Save contact</button>
            <button id="cancelEdit" class="rounded-2xl border border-slate-300 px-4 py-2.5 text-sm bg-white hidden" type="button">Cancel</button>
          </div>
        </form>
      </div>
    </div>
  </div>

<script>
const ACTIVE_STAGES = new Set(['Lead', 'Qualified', 'Proposal']);
let contacts = [];
let selectedId = null;

function money(value) { return `$${Number(value || 0).toLocaleString()}`; }
function todayString() { return new Date().toISOString().slice(0, 10); }

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function showNotice(message, isError = false) {
  const el = document.getElementById('notice');
  if (!message) {
    el.classList.add('hidden');
    el.textContent = '';
    return;
  }
  el.className = `rounded-xl border px-4 py-3 text-sm ${isError ? 'border-red-200 bg-red-50 text-red-700' : 'border-slate-200 bg-white text-slate-700'}`;
  el.textContent = message;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Request failed');
  return data;
}

function filteredContacts() {
  const query = document.getElementById('searchInput').value.trim().toLowerCase();
  const stage = document.getElementById('stageFilter').value;
  return contacts.filter((contact) => {
    const haystack = `${contact.name || ''} ${contact.company || ''} ${contact.email || ''}`.toLowerCase();
    return (!query || haystack.includes(query)) && (stage === 'All' || contact.stage === stage);
  });
}

function renderMetrics() {
  const pipeline = contacts.filter(c => c.stage !== 'Won' && c.stage !== 'Lost').reduce((sum, c) => sum + Number(c.value || 0), 0);
  const won = contacts.filter(c => c.stage === 'Won').reduce((sum, c) => sum + Number(c.value || 0), 0);
  const active = contacts.filter(c => ACTIVE_STAGES.has(c.stage)).length;
  document.getElementById('metricTotal').textContent = contacts.length;
  document.getElementById('metricActive').textContent = active;
  document.getElementById('metricPipeline').textContent = money(pipeline);
  document.getElementById('metricWon').textContent = money(won);
}

function renderList() {
  const list = document.getElementById('contactList');
  const rows = filteredContacts();
  document.getElementById('resultCount').textContent = `${rows.length} shown`;
  if (!rows.some(c => c.id === selectedId)) selectedId = rows[0]?.id ?? null;
  list.innerHTML = '';
  if (!rows.length) {
    list.innerHTML = '<div class="rounded-2xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">No contacts match your search.</div>';
    return;
  }
  rows.forEach((contact) => {
    const selected = contact.id === selectedId;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `w-full rounded-2xl border p-4 text-left transition ${selected ? 'border-slate-900 bg-slate-900 text-white' : 'border-slate-200 bg-white hover:border-slate-300'}`;
    button.innerHTML = `
      <div class="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <div class="font-semibold">${escapeHtml(contact.name)}</div>
          <div class="text-sm ${selected ? 'text-slate-300' : 'text-slate-500'}">${escapeHtml(contact.company)} · ${escapeHtml(contact.email)}</div>
        </div>
        <div class="flex items-center gap-3 text-sm">
          <span class="rounded-full px-3 py-1 ${selected ? 'bg-white/10 text-white' : 'bg-slate-100 text-slate-700'}">${escapeHtml(contact.stage)}</span>
          <span class="${selected ? 'text-slate-200' : 'text-slate-600'}">${money(contact.value)}</span>
        </div>
      </div>`;
    button.onclick = () => { selectedId = contact.id; renderAll(); };
    list.appendChild(button);
  });
}

function renderDetails() {
  const details = document.getElementById('contactDetails');
  const contact = contacts.find(c => c.id === selectedId);
  if (!contact) {
    details.textContent = 'Select a contact';
    return;
  }
  details.innerHTML = `
    <div class="space-y-4">
      <div><div class="text-2xl font-bold">${escapeHtml(contact.name)}</div><div class="text-sm text-slate-500">${escapeHtml(contact.company)}</div></div>
      <div class="grid grid-cols-2 gap-3 text-sm">
        <div class="rounded-xl bg-slate-100 p-3"><div class="text-slate-500">Email</div><div class="mt-1 font-medium break-all">${escapeHtml(contact.email)}</div></div>
        <div class="rounded-xl bg-slate-100 p-3"><div class="text-slate-500">Deal value</div><div class="mt-1 font-medium">${money(contact.value)}</div></div>
        <div class="rounded-xl bg-slate-100 p-3"><div class="text-slate-500">Stage</div><div class="mt-1 font-medium">${escapeHtml(contact.stage)}</div></div>
        <div class="rounded-xl bg-slate-100 p-3"><div class="text-slate-500">Last contact</div><div class="mt-1 font-medium">${escapeHtml(contact.last_contact || '-')}</div></div>
      </div>
      <div><div class="mb-2 text-sm font-medium">Notes</div><div class="rounded-xl border border-slate-200 p-4 text-sm text-slate-700">${escapeHtml(contact.notes || 'No notes yet.')}</div></div>
      <div class="flex flex-wrap gap-2">
        ${['Lead','Qualified','Proposal','Won','Lost'].map((stage) => `<button type="button" class="stageBtn rounded-xl px-3 py-2 text-sm ${contact.stage === stage ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700'}" data-stage="${stage}">${stage}</button>`).join('')}
      </div>
      <div class="flex gap-3">
        <button id="editBtn" type="button" class="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm">Edit</button>
        <button id="deleteBtn" type="button" class="rounded-xl border border-red-200 bg-white px-4 py-2 text-sm text-red-600">Delete</button>
      </div>
    </div>`;

  details.querySelectorAll('.stageBtn').forEach((btn) => {
    btn.addEventListener('click', async () => {
      await api(`/api/contacts/${contact.id}`, { method: 'PUT', body: JSON.stringify({ stage: btn.dataset.stage }) });
      await loadContacts();
      showNotice('Stage updated.');
    });
  });

  document.getElementById('editBtn').onclick = () => {
    document.getElementById('contactId').value = contact.id;
    document.getElementById('name').value = contact.name || '';
    document.getElementById('company').value = contact.company || '';
    document.getElementById('email').value = contact.email || '';
    document.getElementById('stage').value = contact.stage || 'Lead';
    document.getElementById('value').value = contact.value || '';
    document.getElementById('last_contact').value = contact.last_contact || todayString();
    document.getElementById('notes').value = contact.notes || '';
    document.getElementById('formTitle').textContent = 'Edit contact';
    document.getElementById('cancelEdit').classList.remove('hidden');
  };

  document.getElementById('deleteBtn').onclick = async () => {
    if (!confirm(`Delete ${contact.name}?`)) return;
    await api(`/api/contacts/${contact.id}`, { method: 'DELETE' });
    await loadContacts();
    showNotice('Deleted successfully.');
  };
}

function renderAll() { renderMetrics(); renderList(); renderDetails(); }

function resetForm() {
  document.getElementById('contactId').value = '';
  document.getElementById('name').value = '';
  document.getElementById('company').value = '';
  document.getElementById('email').value = '';
  document.getElementById('stage').value = 'Lead';
  document.getElementById('value').value = '';
  document.getElementById('last_contact').value = todayString();
  document.getElementById('notes').value = '';
  document.getElementById('formTitle').textContent = 'Add new contact';
  document.getElementById('cancelEdit').classList.add('hidden');
}

async function loadContacts() {
  const data = await api('/api/contacts');
  contacts = data.contacts;
  document.getElementById('currentUser').textContent = data.user.name || data.user.username;
  if (!selectedId && contacts.length) selectedId = contacts[0].id;
  renderAll();
}

function runTests() {
  console.assert(money(12000) === '$12,000', 'money should format thousands');
  console.assert(escapeHtml('<b>x</b>') === '&lt;b&gt;x&lt;/b&gt;', 'escapeHtml should escape html');
}
runTests();

document.getElementById('searchInput').addEventListener('input', renderAll);
document.getElementById('stageFilter').addEventListener('change', renderAll);
document.getElementById('cancelEdit').addEventListener('click', resetForm);
document.getElementById('logoutBtn').addEventListener('click', async () => {
  await api('/logout', { method: 'POST' });
  window.location.href = '/login';
});
document.getElementById('contactForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const id = document.getElementById('contactId').value;
  const payload = {
    name: document.getElementById('name').value.trim(),
    company: document.getElementById('company').value.trim(),
    email: document.getElementById('email').value.trim(),
    stage: document.getElementById('stage').value,
    value: Number(document.getElementById('value').value || 0),
    last_contact: document.getElementById('last_contact').value || todayString(),
    notes: document.getElementById('notes').value.trim(),
  };
  if (id) {
    await api(`/api/contacts/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
    showNotice('Updated successfully.');
  } else {
    await api('/api/contacts', { method: 'POST', body: JSON.stringify(payload) });
    showNotice('Added successfully.');
  }
  resetForm();
  await loadContacts();
});

loadContacts().catch((error) => showNotice(error.message, true));
resetForm();
setInterval(() => { loadContacts().catch(() => {}); }, 10000);
</script>
</body>
</html>
"""

AUTH_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title }}</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="min-h-screen bg-slate-50 flex items-center justify-center p-6 text-slate-900">
  <div class="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-sm space-y-5">
    <div>
      <h1 class="text-2xl font-bold">{{ title }}</h1>
      <p class="mt-1 text-sm text-slate-600">Simple shared CRM for your team.</p>
    </div>
    {% if error %}
      <div class="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{{ error }}</div>
    {% endif %}
    <form method="post" class="space-y-3">
      {% if register %}
        <input name="name" class="w-full rounded-xl border border-slate-200 px-3 py-2" placeholder="Full name" required>
      {% endif %}
      <input name="username" class="w-full rounded-xl border border-slate-200 px-3 py-2" placeholder="Username" required>
      <input name="password" type="password" class="w-full rounded-xl border border-slate-200 px-3 py-2" placeholder="Password" required>
      <button class="w-full rounded-xl bg-slate-900 px-4 py-2.5 text-white" type="submit">{{ button_text }}</button>
    </form>
    <div class="text-sm text-slate-600">
      {% if register %}
        Already have an account? <a class="underline" href="{{ url_for('login') }}">Sign in</a>
      {% else %}
        Need an account? <a class="underline" href="{{ url_for('register') }}">Create one</a>
      {% endif %}
    </div>
  </div>
</body>
</html>
"""

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY


def get_db():
    if "db" not in g:
        g.db = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    return g.db


@app.teardown_appcontext
def close_db(_error: Optional[BaseException]) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                create table if not exists users (
                    id bigserial primary key,
                    name text not null,
                    username text not null unique,
                    password_hash text not null,
                    created_at timestamptz not null default now()
                );
                """
            )
            cur.execute(
                """
                create table if not exists contacts (
                    id bigserial primary key,
                    name text not null,
                    company text not null,
                    email text not null,
                    stage text not null default 'Lead',
                    value integer not null default 0,
                    last_contact date,
                    notes text,
                    created_by bigint references users(id),
                    created_at timestamptz not null default now(),
                    updated_at timestamptz not null default now()
                );
                """
            )
        conn.commit()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def current_user() -> Optional[dict]:
    user_id = session.get("user_id")
    if not user_id:
        return None
    with get_db().cursor() as cur:
        cur.execute("select id, name, username from users where id = %s", (user_id,))
        return cur.fetchone()


def contact_payload(data: dict, existing: Optional[dict] = None) -> dict:
    existing = existing or {}
    return {
        "name": str(data.get("name", existing.get("name", ""))).strip(),
        "company": str(data.get("company", existing.get("company", ""))).strip(),
        "email": str(data.get("email", existing.get("email", ""))).strip(),
        "stage": str(data.get("stage", existing.get("stage", "Lead"))).strip() or "Lead",
        "value": int(float(data.get("value", existing.get("value", 0)) or 0)),
        "last_contact": str(data.get("last_contact", existing.get("last_contact", ""))).strip() or None,
        "notes": str(data.get("notes", existing.get("notes", ""))).strip(),
    }


@app.get("/")
@login_required
def index():
    return render_template_string(APP_HTML)


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not username or not password:
            error = "All fields are required."
        else:
            with get_db().cursor() as cur:
                cur.execute("select id from users where username = %s", (username,))
                exists = cur.fetchone()
                if exists:
                    error = "That username already exists."
                else:
                    cur.execute(
                        "insert into users (name, username, password_hash) values (%s, %s, %s)",
                        (name, username, generate_password_hash(password)),
                    )
                    get_db().commit()
                    return redirect(url_for("login"))
    return render_template_string(AUTH_HTML, title="Create account", button_text="Create account", register=True, error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        with get_db().cursor() as cur:
            cur.execute("select * from users where username = %s", (username,))
            user = cur.fetchone()
        if not user or not check_password_hash(user["password_hash"], password):
            error = "Invalid username or password."
        else:
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("index"))
    return render_template_string(AUTH_HTML, title="Sign in", button_text="Sign in", register=False, error=error)


@app.post("/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/contacts")
@login_required
def list_contacts():
    user = current_user()
    with get_db().cursor() as cur:
        cur.execute(
            """
            select id, name, company, email, stage, value, last_contact, notes, created_at, updated_at
            from contacts
            order by created_at desc, id desc
            """
        )
        rows = cur.fetchall()
    return jsonify({"contacts": rows, "user": user})


@app.post("/api/contacts")
@login_required
def create_contact():
    payload = contact_payload(request.get_json(silent=True) or {})
    if not payload["name"] or not payload["company"] or not payload["email"]:
        return jsonify({"error": "Name, company, and email are required."}), 400
    with get_db().cursor() as cur:
        cur.execute(
            """
            insert into contacts (name, company, email, stage, value, last_contact, notes, created_by)
            values (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (payload["name"], payload["company"], payload["email"], payload["stage"], payload["value"], payload["last_contact"], payload["notes"], session["user_id"]),
        )
        get_db().commit()
    return jsonify({"ok": True})


@app.put("/api/contacts/<int:contact_id>")
@login_required
def update_contact(contact_id: int):
    with get_db().cursor() as cur:
        cur.execute("select * from contacts where id = %s", (contact_id,))
        existing = cur.fetchone()
        if not existing:
            return jsonify({"error": "Contact not found."}), 404
        payload = contact_payload(request.get_json(silent=True) or {}, existing)
        if not payload["name"] or not payload["company"] or not payload["email"]:
            return jsonify({"error": "Name, company, and email are required."}), 400
        cur.execute(
            """
            update contacts
            set name = %s, company = %s, email = %s, stage = %s, value = %s, last_contact = %s, notes = %s, updated_at = now()
            where id = %s
            """,
            (payload["name"], payload["company"], payload["email"], payload["stage"], payload["value"], payload["last_contact"], payload["notes"], contact_id),
        )
        get_db().commit()
    return jsonify({"ok": True})


@app.delete("/api/contacts/<int:contact_id>")
@login_required
def delete_contact(contact_id: int):
    with get_db().cursor() as cur:
        cur.execute("delete from contacts where id = %s", (contact_id,))
        get_db().commit()
    return jsonify({"ok": True})


def run_tests() -> None:
    assert contact_payload({"name": "A", "company": "B", "email": "c@test.com", "value": "12.5"})["value"] == 12
    assert contact_payload({"stage": "Won"})["stage"] == "Won"
    assert contact_payload({}, {"name": "Alice", "company": "Acme", "email": "a@a.com"})["name"] == "Alice"


if __name__ == "__main__":
    run_tests()
    init_db()
    app.run(host="0.0.0.0", port=PORT)
