"use client";

import {
  AlertCircle,
  Brain,
  Check,
  ChevronDown,
  CreditCard,
  Loader2,
  Plus,
  Trash2,
  TrendingUp,
  Users,
  X,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { useAuth } from "@/lib/auth";

// ─── Types ────────────────────────────────────────────────────────────────────

type ServiceType = "llm" | "tts" | "stt" | "realtime" | "embeddings";

interface SystemAIModel {
  id: number;
  provider: string;
  service_type: ServiceType;
  model_name: string;
  display_name: string;
  api_base_url: string | null;
  is_active: boolean;
  config_schema: Record<string, unknown>;
  extra_config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

interface BillingAccount {
  organization_id: number;
  credits_balance: number;
  currency: string;
  updated_at: string;
}

interface LedgerEntry {
  id: number;
  organization_id: number;
  entry_type: string;
  credits_delta: number;
  quantity: number | null;
  quantity_unit: string | null;
  rate: number | null;
  description: string | null;
  workflow_run_id: number | null;
  created_at: string;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

async function apiFetch(
  path: string,
  init?: RequestInit,
  token?: string | null
) {
  const res = await fetch(
    `${process.env.NEXT_PUBLIC_BACKEND_URL ?? ""}/api/v1${path}`,
    {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init?.headers ?? {}),
      },
    }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

const SERVICE_TYPES: ServiceType[] = [
  "llm",
  "tts",
  "stt",
  "realtime",
  "embeddings",
];

const SERVICE_TYPE_LABELS: Record<ServiceType, string> = {
  llm: "LLM",
  tts: "Text-to-Speech",
  stt: "Speech-to-Text",
  realtime: "Realtime",
  embeddings: "Embeddings",
};

const TYPE_COLORS: Record<ServiceType, string> = {
  llm: "bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300",
  tts: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  stt: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  realtime:
    "bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300",
  embeddings:
    "bg-pink-100 text-pink-800 dark:bg-pink-900/40 dark:text-pink-300",
};

// ─── Component ────────────────────────────────────────────────────────────────

export default function AdminDashboardPage() {
  const { getAccessToken } = useAuth();

  // Models state
  const [models, setModels] = useState<SystemAIModel[]>([]);
  const [modelsLoading, setModelsLoading] = useState(true);
  const [filterType, setFilterType] = useState<ServiceType | "all">("all");
  const [showAddModel, setShowAddModel] = useState(false);
  const [newModel, setNewModel] = useState({
    provider: "",
    service_type: "llm" as ServiceType,
    model_name: "",
    display_name: "",
    api_base_url: "",
    is_active: true,
  });
  const [addingModel, setAddingModel] = useState(false);

  // Billing state
  const [billingOrgId, setBillingOrgId] = useState("");
  const [billingAccount, setBillingAccount] = useState<BillingAccount | null>(null);
  const [ledger, setLedger] = useState<LedgerEntry[]>([]);
  const [billingLoading, setBillingLoading] = useState(false);
  const [grantAmount, setGrantAmount] = useState("");
  const [grantDesc, setGrantDesc] = useState("Admin credit grant");
  const [granting, setGranting] = useState(false);

  // ── Load models ─────────────────────────────────────────────────────────────
  const loadModels = useCallback(async () => {
    setModelsLoading(true);
    try {
      const token = await getAccessToken();
      const data: SystemAIModel[] = await apiFetch("/admin/models", {}, token);
      setModels(data);
    } catch (e: unknown) {
      toast.error(`Failed to load models: ${e instanceof Error ? e.message : e}`);
    } finally {
      setModelsLoading(false);
    }
  }, [getAccessToken]);

  useEffect(() => {
    loadModels();
  }, [loadModels]);

  // ── Add model ────────────────────────────────────────────────────────────────
  const handleAddModel = async () => {
    if (!newModel.provider || !newModel.model_name || !newModel.display_name) {
      toast.error("Provider, Model Name, and Display Name are required.");
      return;
    }
    setAddingModel(true);
    try {
      const token = await getAccessToken();
      await apiFetch(
        "/admin/models",
        {
          method: "POST",
          body: JSON.stringify({
            ...newModel,
            api_base_url: newModel.api_base_url || null,
          }),
        },
        token
      );
      toast.success(`Model "${newModel.display_name}" added to catalogue!`);
      setShowAddModel(false);
      setNewModel({
        provider: "",
        service_type: "llm",
        model_name: "",
        display_name: "",
        api_base_url: "",
        is_active: true,
      });
      loadModels();
    } catch (e: unknown) {
      toast.error(`Failed to add model: ${e instanceof Error ? e.message : e}`);
    } finally {
      setAddingModel(false);
    }
  };

  // ── Toggle model active ──────────────────────────────────────────────────────
  const toggleModel = async (model: SystemAIModel) => {
    try {
      const token = await getAccessToken();
      await apiFetch(
        `/admin/models/${model.id}`,
        { method: "PUT", body: JSON.stringify({ is_active: !model.is_active }) },
        token
      );
      toast.success(
        `Model "${model.display_name}" ${!model.is_active ? "activated" : "deactivated"}.`
      );
      loadModels();
    } catch (e: unknown) {
      toast.error(`Failed to update: ${e instanceof Error ? e.message : e}`);
    }
  };

  // ── Delete model ─────────────────────────────────────────────────────────────
  const deleteModel = async (model: SystemAIModel) => {
    if (!confirm(`Delete "${model.display_name}"? This cannot be undone.`)) return;
    try {
      const token = await getAccessToken();
      await apiFetch(`/admin/models/${model.id}`, { method: "DELETE" }, token);
      toast.success(`Model deleted.`);
      loadModels();
    } catch (e: unknown) {
      toast.error(`Failed to delete: ${e instanceof Error ? e.message : e}`);
    }
  };

  // ── Load billing ─────────────────────────────────────────────────────────────
  const loadBilling = async () => {
    const orgId = parseInt(billingOrgId);
    if (!orgId) return;
    setBillingLoading(true);
    try {
      const token = await getAccessToken();
      const [account, entries] = await Promise.all([
        apiFetch(`/admin/billing/${orgId}`, {}, token),
        apiFetch(`/admin/billing/${orgId}/ledger?limit=20`, {}, token),
      ]);
      setBillingAccount(account);
      setLedger(entries);
    } catch (e: unknown) {
      toast.error(`Failed to load billing: ${e instanceof Error ? e.message : e}`);
    } finally {
      setBillingLoading(false);
    }
  };

  // ── Grant credits ─────────────────────────────────────────────────────────────
  const handleGrant = async () => {
    const orgId = parseInt(billingOrgId);
    const amount = parseFloat(grantAmount);
    if (!orgId || !amount || amount <= 0) {
      toast.error("Enter a valid Org ID and amount.");
      return;
    }
    setGranting(true);
    try {
      const token = await getAccessToken();
      await apiFetch(
        "/admin/billing/grant",
        {
          method: "POST",
          body: JSON.stringify({
            organization_id: orgId,
            credits: amount,
            description: grantDesc,
          }),
        },
        token
      );
      toast.success(`Granted ₹${amount} to org ${orgId}`);
      setGrantAmount("");
      loadBilling();
    } catch (e: unknown) {
      toast.error(`Grant failed: ${e instanceof Error ? e.message : e}`);
    } finally {
      setGranting(false);
    }
  };

  const filtered =
    filterType === "all"
      ? models
      : models.filter((m) => m.service_type === filterType);

  // ── Render ───────────────────────────────────────────────────────────────────
  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 text-white p-6 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">
            Dailsmart Super Admin
          </h1>
          <p className="text-slate-400 mt-1 text-sm">
            Manage AI model catalogue · Billing · Organisations
          </p>
        </div>
        <div className="flex gap-3 text-xs text-slate-400 items-center">
          <span className="px-3 py-1 bg-indigo-900/50 border border-indigo-700 rounded-full">
            Platform fee: ₹0.89 / min (BYOK)
          </span>
          <span className="px-3 py-1 bg-purple-900/50 border border-purple-700 rounded-full">
            Dailsmart AI: ₹1.89 / min — billed per full minute (ceiling)
          </span>
        </div>
      </div>

      {/* ── Stats Bar ── */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Total Models", value: models.length, icon: Brain, color: "indigo" },
          { label: "Active Models", value: models.filter((m) => m.is_active).length, icon: Check, color: "green" },
          { label: "Inactive Models", value: models.filter((m) => !m.is_active).length, icon: AlertCircle, color: "amber" },
        ].map(({ label, value, icon: Icon, color }) => (
          <div
            key={label}
            className={`rounded-2xl border border-${color}-800/40 bg-${color}-900/20 p-5 flex items-center gap-4`}
          >
            <div className={`p-3 rounded-xl bg-${color}-800/30`}>
              <Icon className={`w-5 h-5 text-${color}-400`} />
            </div>
            <div>
              <div className="text-2xl font-bold">{value}</div>
              <div className="text-xs text-slate-400">{label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* ── AI Model Catalogue ── */}
      <section className="rounded-2xl border border-slate-700/50 bg-slate-800/50 backdrop-blur p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Brain className="w-5 h-5 text-indigo-400" />
            <h2 className="text-lg font-semibold">AI Model Catalogue</h2>
            <span className="text-xs text-slate-400 bg-slate-700 px-2 py-0.5 rounded-full">
              Reflects in all org dropdowns
            </span>
          </div>
          <button
            onClick={() => setShowAddModel(true)}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-xl text-sm font-medium transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add Model
          </button>
        </div>

        {/* Filters */}
        <div className="flex gap-2 flex-wrap">
          {(["all", ...SERVICE_TYPES] as const).map((t) => (
            <button
              key={t}
              onClick={() => setFilterType(t)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                filterType === t
                  ? "bg-indigo-600 text-white"
                  : "bg-slate-700 text-slate-300 hover:bg-slate-600"
              }`}
            >
              {t === "all" ? "All" : SERVICE_TYPE_LABELS[t]}
            </button>
          ))}
        </div>

        {/* Model list */}
        {modelsLoading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-indigo-400" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-12 text-slate-400">
            <Brain className="w-10 h-10 mx-auto mb-3 opacity-30" />
            <p className="text-sm">No models found. Add one to get started.</p>
          </div>
        ) : (
          <div className="overflow-auto rounded-xl border border-slate-700/50">
            <table className="w-full text-sm">
              <thead className="bg-slate-900/60">
                <tr className="text-slate-400 text-xs uppercase tracking-wide">
                  {["Provider", "Model Name", "Display Name", "Type", "API Base", "Status", "Actions"].map((h) => (
                    <th key={h} className="px-4 py-3 text-left font-medium">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/40">
                {filtered.map((m) => (
                  <tr key={m.id} className="hover:bg-slate-700/20 transition-colors">
                    <td className="px-4 py-3 font-medium text-white">{m.provider}</td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-300">{m.model_name}</td>
                    <td className="px-4 py-3 text-slate-200">{m.display_name}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${TYPE_COLORS[m.service_type]}`}>
                        {SERVICE_TYPE_LABELS[m.service_type]}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-400 text-xs truncate max-w-[160px]">
                      {m.api_base_url ?? "—"}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => toggleModel(m)}
                        className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                          m.is_active
                            ? "bg-emerald-900/50 text-emerald-400 hover:bg-emerald-800/50"
                            : "bg-slate-700 text-slate-400 hover:bg-slate-600"
                        }`}
                      >
                        {m.is_active ? "Active" : "Inactive"}
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => deleteModel(m)}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-900/20 transition-colors"
                        title="Delete model"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ── Add Model Modal ── */}
      {showAddModel && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg bg-slate-900 border border-slate-700 rounded-2xl p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">Add AI Model to Catalogue</h3>
              <button
                onClick={() => setShowAddModel(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3">
              {/* Provider */}
              <div className="space-y-1">
                <label className="text-xs text-slate-400">Provider *</label>
                <input
                  value={newModel.provider}
                  onChange={(e) => setNewModel((p) => ({ ...p, provider: e.target.value }))}
                  placeholder="openai, sarvam, custom..."
                  className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-indigo-500"
                />
              </div>
              {/* Service Type */}
              <div className="space-y-1">
                <label className="text-xs text-slate-400">Service Type *</label>
                <select
                  value={newModel.service_type}
                  onChange={(e) =>
                    setNewModel((p) => ({ ...p, service_type: e.target.value as ServiceType }))
                  }
                  className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-indigo-500"
                >
                  {SERVICE_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {SERVICE_TYPE_LABELS[t]}
                    </option>
                  ))}
                </select>
              </div>
              {/* Model Name */}
              <div className="space-y-1">
                <label className="text-xs text-slate-400">Model Name / ID *</label>
                <input
                  value={newModel.model_name}
                  onChange={(e) => setNewModel((p) => ({ ...p, model_name: e.target.value }))}
                  placeholder="gpt-4o, claude-3-5-sonnet..."
                  className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-indigo-500"
                />
              </div>
              {/* Display Name */}
              <div className="space-y-1">
                <label className="text-xs text-slate-400">Display Name *</label>
                <input
                  value={newModel.display_name}
                  onChange={(e) => setNewModel((p) => ({ ...p, display_name: e.target.value }))}
                  placeholder="GPT-4o (OpenAI)"
                  className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-indigo-500"
                />
              </div>
              {/* API Base URL */}
              <div className="col-span-2 space-y-1">
                <label className="text-xs text-slate-400">API Base URL (optional)</label>
                <input
                  value={newModel.api_base_url}
                  onChange={(e) => setNewModel((p) => ({ ...p, api_base_url: e.target.value }))}
                  placeholder="https://api.openai.com/v1"
                  className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-indigo-500"
                />
              </div>
              {/* Active toggle */}
              <div className="col-span-2 flex items-center gap-3">
                <label className="text-sm text-slate-300">Activate immediately</label>
                <button
                  onClick={() => setNewModel((p) => ({ ...p, is_active: !p.is_active }))}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    newModel.is_active ? "bg-indigo-600" : "bg-slate-600"
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      newModel.is_active ? "translate-x-6" : "translate-x-1"
                    }`}
                  />
                </button>
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => setShowAddModel(false)}
                className="px-4 py-2 rounded-xl text-sm text-slate-400 hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleAddModel}
                disabled={addingModel}
                className="flex items-center gap-2 px-5 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-xl text-sm font-medium disabled:opacity-50 transition-colors"
              >
                {addingModel ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Plus className="w-4 h-4" />
                )}
                Add Model
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Billing Management ── */}
      <section className="rounded-2xl border border-slate-700/50 bg-slate-800/50 backdrop-blur p-6 space-y-5">
        <div className="flex items-center gap-3">
          <CreditCard className="w-5 h-5 text-emerald-400" />
          <h2 className="text-lg font-semibold">Organisation Billing</h2>
        </div>

        {/* Billing rates reminder */}
        <div className="grid grid-cols-2 gap-3">
          {[
            {
              label: "BYOK Platform Fee",
              value: "₹0.89 / minute",
              desc: "Charged when org uses their own keys",
              color: "emerald",
            },
            {
              label: "Dailsmart AI Usage",
              value: "₹1.89 / minute",
              desc: "Ceiling billed — 61s = 2 min = ₹3.78 AI + ₹1.78 platform",
              color: "purple",
            },
          ].map(({ label, value, desc, color }) => (
            <div
              key={label}
              className={`rounded-xl border border-${color}-800/40 bg-${color}-900/20 p-4`}
            >
              <div className={`text-lg font-bold text-${color}-300`}>{value}</div>
              <div className="text-sm font-medium text-white mt-0.5">{label}</div>
              <div className="text-xs text-slate-400 mt-1">{desc}</div>
            </div>
          ))}
        </div>

        {/* Org lookup */}
        <div className="flex gap-3">
          <input
            value={billingOrgId}
            onChange={(e) => setBillingOrgId(e.target.value)}
            placeholder="Organisation ID (integer)"
            className="flex-1 bg-slate-800 border border-slate-600 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-emerald-500"
          />
          <button
            onClick={loadBilling}
            disabled={billingLoading}
            className="px-5 py-2.5 bg-slate-700 hover:bg-slate-600 rounded-xl text-sm font-medium flex items-center gap-2 transition-colors"
          >
            {billingLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <TrendingUp className="w-4 h-4" />}
            Load
          </button>
        </div>

        {billingAccount && (
          <div className="space-y-4">
            {/* Balance card */}
            <div className="flex items-center gap-6 p-4 rounded-xl bg-emerald-900/20 border border-emerald-800/40">
              <div>
                <div className="text-3xl font-bold text-emerald-300">
                  ₹{billingAccount.credits_balance.toFixed(2)}
                </div>
                <div className="text-xs text-slate-400 mt-0.5">
                  Credits balance · Org {billingAccount.organization_id}
                </div>
              </div>
              <div className="ml-auto flex gap-3">
                <input
                  value={grantAmount}
                  onChange={(e) => setGrantAmount(e.target.value)}
                  placeholder="Amount (₹)"
                  type="number"
                  min={0}
                  className="w-32 bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-emerald-500"
                />
                <input
                  value={grantDesc}
                  onChange={(e) => setGrantDesc(e.target.value)}
                  placeholder="Description"
                  className="w-40 bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-emerald-500"
                />
                <button
                  onClick={handleGrant}
                  disabled={granting}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors"
                >
                  {granting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                  Grant
                </button>
              </div>
            </div>

            {/* Ledger */}
            {ledger.length > 0 && (
              <div className="overflow-auto rounded-xl border border-slate-700/50">
                <table className="w-full text-sm">
                  <thead className="bg-slate-900/60">
                    <tr className="text-slate-400 text-xs uppercase tracking-wide">
                      {["Date", "Type", "Credits Delta", "Qty", "Rate", "Description"].map((h) => (
                        <th key={h} className="px-4 py-3 text-left font-medium">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-700/40">
                    {ledger.map((e) => (
                      <tr key={e.id} className="hover:bg-slate-700/20">
                        <td className="px-4 py-2.5 text-slate-400 text-xs">
                          {new Date(e.created_at).toLocaleString()}
                        </td>
                        <td className="px-4 py-2.5">
                          <span
                            className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                              e.entry_type === "grant" || e.entry_type === "topup"
                                ? "bg-emerald-900/50 text-emerald-400"
                                : "bg-red-900/40 text-red-400"
                            }`}
                          >
                            {e.entry_type}
                          </span>
                        </td>
                        <td
                          className={`px-4 py-2.5 font-mono font-medium ${
                            e.credits_delta >= 0 ? "text-emerald-400" : "text-red-400"
                          }`}
                        >
                          {e.credits_delta >= 0 ? "+" : ""}
                          {e.credits_delta.toFixed(4)}
                        </td>
                        <td className="px-4 py-2.5 text-slate-400">
                          {e.quantity != null
                            ? `${e.quantity.toFixed(2)} ${e.quantity_unit ?? ""}`
                            : "—"}
                        </td>
                        <td className="px-4 py-2.5 text-slate-400">
                          {e.rate != null ? `₹${e.rate}` : "—"}
                        </td>
                        <td className="px-4 py-2.5 text-slate-300">{e.description ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </section>
    </main>
  );
}
