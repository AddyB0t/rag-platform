import { useEffect, useRef, useState } from "react";
import { api, ROLE_TOKENS } from "./api.js";

const MODES = {
  hybrid_rerank: "Hybrid + rerank",
  hybrid: "Hybrid (no rerank)",
  dense: "Dense only",
};

export default function App() {
  const [role, setRole] = useState("employee");
  const [tab, setTab] = useState("chat");

  useEffect(() => {
    if (tab === "admin" && role !== "admin") setTab("chat");
  }, [role, tab]);

  return (
    <div className="app">
      <header>
        <h1>Enterprise Knowledge Assistant</h1>
        <nav>
          <button className={tab === "chat" ? "active" : ""} onClick={() => setTab("chat")}>
            Chat
          </button>
          <button
            className={tab === "admin" ? "active" : ""}
            disabled={role !== "admin"}
            title={role !== "admin" ? "Switch to the admin role" : ""}
            onClick={() => setTab("admin")}
          >
            Admin
          </button>
        </nav>
        <label className="role">
          Role
          <select value={role} onChange={(e) => setRole(e.target.value)}>
            {Object.keys(ROLE_TOKENS).map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        </label>
      </header>
      {tab === "chat" ? <Chat role={role} /> : <Admin role={role} />}
    </div>
  );
}

function Chat({ role }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [mode, setMode] = useState("hybrid_rerank");
  const [busy, setBusy] = useState(false);
  const [source, setSource] = useState(null);
  const endRef = useRef(null);

  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), [messages]);

  async function send(e) {
    e.preventDefault();
    const q = input.trim();
    if (!q || busy) return;
    setInput("");
    setMessages((m) => [...m, { who: "user", text: q, role }]);
    setBusy(true);
    try {
      const res = await api.chat(role, q, mode);
      setMessages((m) => [...m, { who: "bot", ...res }]);
    } catch (err) {
      setMessages((m) => [...m, { who: "bot", error: err.message }]);
    } finally {
      setBusy(false);
    }
  }

  async function rate(i, rating) {
    const msg = messages[i];
    const comment = rating === -1 ? window.prompt("What was wrong? (optional)") || "" : "";
    await api.feedback(role, msg.request_id, rating, comment);
    setMessages((m) => m.map((x, j) => (j === i ? { ...x, rated: rating } : x)));
  }

  return (
    <main className="chat">
      <section className="messages">
        {messages.length === 0 && (
          <p className="hint">
            Ask about SEC 10-K filings (finance), arXiv papers (research), HR policies (hr), or
            Wikipedia topics (everyone). Switch roles to see access control at work.
          </p>
        )}
        {messages.map((m, i) =>
          m.who === "user" ? (
            <div key={i} className="msg user">
              <span className="tag">{m.role}</span> {m.text}
            </div>
          ) : (
            <div key={i} className={`msg bot ${m.idk ? "idk" : ""}`}>
              {m.error ? (
                <span className="error">Error: {m.error}</span>
              ) : (
                <>
                  <Answer text={m.answer} citations={m.citations} onCite={setSource} />
                  <div className="meta">
                    {m.citations?.map((c) => (
                      <button key={c.n} className="chip" onClick={() => setSource(c)}>
                        [{c.n}] {c.title}
                        {c.page ? ` p.${c.page}` : ""}
                      </button>
                    ))}
                  </div>
                  <div className="footer">
                    <span>
                      {MODES[m.mode]} · {m.latency_ms?.total} ms
                      {m.top_rerank_score != null && ` · top score ${m.top_rerank_score.toFixed(2)}`}
                    </span>
                    <span className="rate">
                      <button disabled={m.rated} className={m.rated === 1 ? "on" : ""} onClick={() => rate(i, 1)}>
                        👍
                      </button>
                      <button disabled={m.rated} className={m.rated === -1 ? "on" : ""} onClick={() => rate(i, -1)}>
                        👎
                      </button>
                    </span>
                  </div>
                </>
              )}
            </div>
          ),
        )}
        {busy && <div className="msg bot thinking">Searching documents…</div>}
        <div ref={endRef} />
      </section>
      <form className="composer" onSubmit={send}>
        <select value={mode} onChange={(e) => setMode(e.target.value)}>
          {Object.entries(MODES).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask a question…" />
        <button disabled={busy || !input.trim()}>Send</button>
      </form>
      {source && <SourcePanel source={source} onClose={() => setSource(null)} />}
    </main>
  );
}

function Answer({ text, citations, onCite }) {
  const byN = Object.fromEntries((citations || []).map((c) => [c.n, c]));
  const parts = text.split(/(\[\d+\])/g);
  return (
    <p className="answer">
      {parts.map((p, i) => {
        const m = p.match(/^\[(\d+)\]$/);
        if (m && byN[m[1]])
          return (
            <button key={i} className="cite" onClick={() => onCite(byN[m[1]])}>
              {m[1]}
            </button>
          );
        return <span key={i}>{p}</span>;
      })}
    </p>
  );
}

function SourcePanel({ source, onClose }) {
  return (
    <aside className="source">
      <div className="source-head">
        <strong>
          [{source.n}] {source.title}
        </strong>
        <button onClick={onClose}>✕</button>
      </div>
      <p className="where">
        {source.source} · {source.section}
        {source.page ? ` · page ${source.page}` : ""}
      </p>
      {source.url && (
        <a href={source.url} target="_blank" rel="noreferrer">
          Open original
        </a>
      )}
      <pre>{source.snippet}</pre>
    </aside>
  );
}

function Admin({ role }) {
  const [data, setData] = useState(null);
  const [file, setFile] = useState(null);
  const [roles, setRoles] = useState("all");
  const [title, setTitle] = useState("");
  const [status, setStatus] = useState("");

  const load = () => api.docs(role).then(setData).catch((e) => setStatus(e.message));
  useEffect(() => {
    load();
  }, [role]);

  async function upload(e) {
    e.preventDefault();
    if (!file) return;
    setStatus("Indexing…");
    try {
      const res = await api.upload(role, file, roles, title);
      setStatus(`Indexed "${res.title}": ${res.chunks} chunks, roles ${res.allowed_roles.join(", ")}`);
      setFile(null);
      setTitle("");
      e.target.reset();
      load();
    } catch (err) {
      setStatus(`Failed: ${err.message}`);
    }
  }

  return (
    <main className="admin">
      <section className="card">
        <h2>Upload a document</h2>
        <form onSubmit={upload}>
          <input type="file" accept=".pdf,.docx,.html,.htm,.txt,.md" onChange={(e) => setFile(e.target.files[0])} />
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title (optional)" />
          <input value={roles} onChange={(e) => setRoles(e.target.value)} placeholder="Allowed roles, e.g. finance,hr or all" />
          <button disabled={!file}>Upload & index</button>
        </form>
        {status && <p className="status">{status}</p>}
      </section>
      {data && (
        <section className="card">
          <h2>Index stats</h2>
          <p>
            {data.stats.documents} documents · {data.stats.chunks} chunks ·{" "}
            {Object.entries(data.stats.chunks_by_source)
              .map(([k, v]) => `${k}: ${v}`)
              .join(" · ")}
          </p>
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Source</th>
                <th>Allowed roles</th>
                <th>Chunks</th>
              </tr>
            </thead>
            <tbody>
              {data.documents.map((d) => (
                <tr key={d.doc_id}>
                  <td>{d.title}</td>
                  <td>{d.source}</td>
                  <td>{d.allowed_roles.join(", ")}</td>
                  <td>{d.chunks}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </main>
  );
}
