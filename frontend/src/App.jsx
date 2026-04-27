import { useCallback, useEffect, useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const MERCHANT_TOKEN = import.meta.env.VITE_MERCHANT_API_KEY || "demo-token-alpha";

function formatInr(paise) {
  const n = Number(paise || 0);
  return (n / 100).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

async function apiFetch(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${MERCHANT_TOKEN}`,
    ...(options.headers || {}),
  };
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const text = await res.text();
  let body = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = { detail: text };
  }
  return { ok: res.ok, status: res.status, body };
}

export default function App() {
  const [balance, setBalance] = useState(null);
  const [credits, setCredits] = useState([]);
  const [payouts, setPayouts] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [amountRupees, setAmountRupees] = useState("");
  const [bankAccountId, setBankAccountId] = useState("demo-bank-account");

  const load = useCallback(async () => {
    setError("");
    const [b, c, p] = await Promise.all([
      apiFetch("/api/v1/balance/"),
      apiFetch("/api/v1/credits/"),
      apiFetch("/api/v1/payouts/"),
    ]);
    if (!b.ok) {
      setError(b.body?.detail || `Balance failed (${b.status})`);
      return;
    }
    if (!c.ok) {
      setError(c.body?.detail || `Credits failed (${c.status})`);
      return;
    }
    if (!p.ok) {
      setError(p.body?.detail || `Payouts failed (${p.status})`);
      return;
    }
    setBalance(b.body);
    setCredits(c.body);
    setPayouts(p.body);
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [load]);

  const onSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    const rupees = Number(amountRupees);
    if (!Number.isFinite(rupees) || rupees <= 0) {
      setError("Enter a positive amount in rupees.");
      setBusy(false);
      return;
    }
    const amountPaise = Math.round(rupees * 100);
    const idem = crypto.randomUUID();
    const res = await apiFetch("/api/v1/payouts/", {
      method: "POST",
      headers: { "Idempotency-Key": idem },
      body: JSON.stringify({ amount_paise: amountPaise, bank_account_id: bankAccountId }),
    });
    setBusy(false);
    if (!res.ok) {
      setError(res.body?.detail || res.body?.code || `Request failed (${res.status})`);
      return;
    }
    setAmountRupees("");
    await load();
  };

  const heldLine = useMemo(() => {
    if (!balance) return null;
    return (
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
          <div className="text-xs uppercase tracking-wide text-slate-400">Available</div>
          <div className="mt-1 text-2xl font-semibold">₹{formatInr(balance.available_paise)}</div>
          <div className="mt-1 text-xs text-slate-500">{balance.available_paise} paise</div>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
          <div className="text-xs uppercase tracking-wide text-slate-400">Held</div>
          <div className="mt-1 text-2xl font-semibold">₹{formatInr(balance.held_paise)}</div>
          <div className="mt-1 text-xs text-slate-500">{balance.held_paise} paise</div>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
          <div className="text-xs uppercase tracking-wide text-slate-400">Credits (total in)</div>
          <div className="mt-1 text-2xl font-semibold">₹{formatInr(balance.credits_paise)}</div>
          <div className="mt-1 text-xs text-slate-500">Outstanding pipeline: {balance.outstanding_paise} paise</div>
        </div>
      </div>
    );
  }, [balance]);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">Merchant payout dashboard</h1>
        <p className="mt-2 text-sm text-slate-400">
          Uses <span className="font-mono text-slate-200">VITE_API_BASE_URL</span> and{" "}
          <span className="font-mono text-slate-200">VITE_MERCHANT_API_KEY</span> (Bearer on every request).
        </p>
      </header>

      {error ? (
        <div className="mb-6 rounded-md border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-200">
          {String(error)}
        </div>
      ) : null}

      {heldLine}

      <div className="mt-8 grid gap-8 lg:grid-cols-2">
        <section className="rounded-lg border border-slate-800 bg-slate-900/30 p-5">
          <h2 className="text-lg font-medium">Request payout</h2>
          <form className="mt-4 space-y-4" onSubmit={onSubmit}>
            <label className="block text-sm text-slate-300">
              Amount (INR)
              <input
                className="mt-1 w-full rounded-md border border-slate-800 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-slate-600"
                value={amountRupees}
                onChange={(e) => setAmountRupees(e.target.value)}
                inputMode="decimal"
                placeholder="e.g. 1500.50"
              />
            </label>
            <label className="block text-sm text-slate-300">
              Bank account id
              <input
                className="mt-1 w-full rounded-md border border-slate-800 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-slate-600"
                value={bankAccountId}
                onChange={(e) => setBankAccountId(e.target.value)}
              />
            </label>
            <button
              disabled={busy}
              className="w-full rounded-md bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
              type="submit"
            >
              {busy ? "Submitting…" : "Submit payout"}
            </button>
          </form>
        </section>

        <section className="rounded-lg border border-slate-800 bg-slate-900/30 p-5">
          <h2 className="text-lg font-medium">Recent credits (money in)</h2>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase text-slate-400">
                <tr>
                  <th className="py-2">When</th>
                  <th className="py-2">Amount</th>
                  <th className="py-2">Note</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {credits.map((c) => (
                  <tr key={c.id} className="text-slate-200">
                    <td className="py-2 font-mono text-xs text-slate-400">{c.created_at}</td>
                    <td className="py-2">₹{formatInr(c.amount_paise)}</td>
                    <td className="py-2 text-slate-300">{c.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <section className="mt-8 rounded-lg border border-slate-800 bg-slate-900/30 p-5">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-medium">Payout history (debits / withdrawals)</h2>
          <button
            type="button"
            className="rounded-md border border-slate-700 px-3 py-1 text-xs text-slate-200 hover:bg-slate-900"
            onClick={() => load()}
          >
            Refresh now
          </button>
        </div>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-slate-400">
              <tr>
                <th className="py-2">ID</th>
                <th className="py-2">Amount</th>
                <th className="py-2">Status</th>
                <th className="py-2">Bank</th>
                <th className="py-2">Attempts</th>
                <th className="py-2">Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {payouts.map((p) => (
                <tr key={p.id} className="text-slate-200">
                  <td className="py-2 font-mono text-xs">{p.id}</td>
                  <td className="py-2">₹{formatInr(p.amount_paise)}</td>
                  <td className="py-2">
                    <span className="rounded-full bg-slate-800 px-2 py-0.5 text-xs font-medium text-slate-100">
                      {p.status}
                    </span>
                  </td>
                  <td className="py-2 font-mono text-xs text-slate-400">{p.bank_account_id}</td>
                  <td className="py-2">{p.attempt_count}</td>
                  <td className="py-2 font-mono text-xs text-slate-400">{p.updated_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
