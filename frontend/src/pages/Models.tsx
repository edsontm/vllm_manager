import { useState, useMemo } from "react"
import { useNavigate } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { modelsApi, type HFModelInfo, type LocalModelInfo } from "@/api/modelsApi"
import { HardDrive, Cpu } from "lucide-react"

// ── types ──────────────────────────────────────────────────────────────────────
type HubSort = "popularity" | "vram_asc" | "vram_desc"
type LocalSort = "name" | "vram_asc" | "vram_desc" | "size"
type VramCeiling = 8 | 16 | 24 | 40 | 80 | null

const VRAM_CEILINGS: { label: string; value: VramCeiling }[] = [
  { label: "Any", value: null },
  { label: "8 GB", value: 8 },
  { label: "16 GB", value: 16 },
  { label: "24 GB", value: 24 },
  { label: "40 GB", value: 40 },
  { label: "80 GB", value: 80 },
]

// ── shared controls ────────────────────────────────────────────────────────────
function PillGroup<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { label: string; value: T }[]
  value: T
  onChange: (v: T) => void
}) {
  return (
    <div className="flex gap-1">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={`px-3 py-1 rounded text-xs transition-colors font-sans font-[700] ${
            value === o.value
              ? "bg-indigo-600 text-white"
              : "text-gray-400 hover:text-white bg-gray-800 hover:bg-gray-700"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

function VramFilter({ value, onChange }: { value: VramCeiling; onChange: (v: VramCeiling) => void }) {
  return (
    <div className="flex items-center gap-2">
      <span className="font-sans font-[200] text-[11px] uppercase tracking-widest text-gray-500">Max VRAM</span>
      <div className="flex gap-1">
        {VRAM_CEILINGS.map((c) => (
          <button
            key={String(c.value)}
            onClick={() => onChange(c.value)}
            className={`px-2 py-1 rounded text-xs transition-colors font-mono font-[600] ${
              value === c.value
                ? "bg-amber-700 text-amber-100"
                : "text-gray-500 hover:text-amber-300 bg-gray-800 hover:bg-gray-700"
            }`}
          >
            {c.label}
          </button>
        ))}
      </div>
    </div>
  )
}

function vramChip(gb: number | null) {
  if (gb === null) return null
  return (
    <span className="inline-flex items-center gap-1 bg-amber-950 text-amber-400 font-mono font-[600] text-xs px-2 py-0.5 rounded">
      <Cpu size={10} />
      ~{gb} GB VRAM
    </span>
  )
}

function slugify(modelId: string): string {
  const tail = modelId.split("/").at(-1) ?? modelId
  return tail.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "").slice(0, 48)
}

function displayName(modelId: string): string {
  const tail = modelId.split("/").at(-1) ?? modelId
  return tail.replace(/[-_]/g, " ").replace(/\w/g, (c: string) => c.toUpperCase())
}

function ModelCard({ model }: { model: HFModelInfo }) {
  const navigate = useNavigate()
  const handlePrefill = () => {
    navigate("/instances", {
      state: { prefill: { model_id: model.model_id, slug: slugify(model.model_id), display_name: displayName(model.model_id) } },
    })
  }
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-2">
      <div>
        <p className="font-mono font-[300] text-xs text-gray-500">{model.author ? `${model.author}/` : ""}</p>
        <button onClick={handlePrefill} className="font-heading font-[800] text-sm text-white hover:text-indigo-300 underline-offset-2 hover:underline text-left transition-colors" title="Click to prefill a new instance with this model">
          {model.model_id.split("/").at(-1)}
        </button>
      </div>
      <p className="font-mono font-[300] text-xs text-indigo-400">{model.pipeline_tag ?? "—"}</p>
      <div className="flex flex-wrap gap-2 items-center mt-1">
        <span className="font-mono font-[600] text-xs text-gray-500">↓ {model.downloads.toLocaleString()}</span>
        <span className="font-mono font-[600] text-xs text-gray-500">♡ {model.likes.toLocaleString()}</span>
        {vramChip(model.vram_required_gb)}
      </div>
    </div>
  )
}

function LocalCard({ model }: { model: LocalModelInfo }) {
  const navigate = useNavigate()
  const handlePrefill = () => {
    navigate("/instances", {
      state: { prefill: { model_id: model.model_id, slug: slugify(model.model_id), display_name: displayName(model.model_id) } },
    })
  }
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex items-center gap-4">
      <HardDrive size={20} className="text-gray-500 shrink-0" />
      <div className="flex-1 min-w-0 space-y-1">
        <button onClick={handlePrefill} className="font-heading font-[800] text-sm text-white hover:text-indigo-300 underline-offset-2 hover:underline text-left transition-colors block truncate max-w-full" title="Click to prefill a new instance with this model">
          {model.model_id}
        </button>
        <div className="flex flex-wrap gap-2 items-center">
          <span className="font-mono font-[300] text-xs text-gray-500">{model.size_gb.toFixed(1)} GB disk</span>
          {vramChip(model.vram_required_gb)}
        </div>
      </div>
    </div>
  )
}

export default function Models() {
  const [search, setSearch] = useState("")
  const [activeTab, setActiveTab] = useState<"hub" | "local">("hub")

  // Hub tab controls
  const [hubSort, setHubSort] = useState<HubSort>("popularity")

  const handleHubVramClick = () => {
    setHubSort((prev) =>
      prev === "vram_asc" ? "vram_desc" : prev === "vram_desc" ? "vram_asc" : "vram_asc"
    )
  }
  const [hubVramCeiling, setHubVramCeiling] = useState<VramCeiling>(null)

  // Local tab controls
  const [localSort, setLocalSort] = useState<LocalSort>("name")
  const [localVramCeiling, setLocalVramCeiling] = useState<VramCeiling>(null)

  const { data: hubModels = [], isLoading: loadingHub } = useQuery({
    queryKey: ["models-hub", search, hubSort],
    queryFn: () =>
      modelsApi.available(search, 50, hubSort === "popularity" ? "downloads" : "downloads"),
    enabled: activeTab === "hub",
  })

  const { data: localModels = [], isLoading: loadingLocal } = useQuery({
    queryKey: ["models-local"],
    queryFn: modelsApi.local,
    enabled: activeTab === "local",
  })

  // Hub: client-side sort by VRAM then filter by ceiling
  const processedHub = useMemo(() => {
    let list = [...hubModels]
    if (hubSort === "vram_asc" || hubSort === "vram_desc") {
      const dir = hubSort === "vram_asc" ? 1 : -1
      list.sort((a, b) => {
        if (a.vram_required_gb === null && b.vram_required_gb === null) return 0
        if (a.vram_required_gb === null) return dir   // nulls last for ↑, first for ↓
        if (b.vram_required_gb === null) return -dir
        return dir * (a.vram_required_gb - b.vram_required_gb)
      })
    }
    if (hubVramCeiling !== null) {
      list = list.filter((m) => m.vram_required_gb === null || m.vram_required_gb <= hubVramCeiling)
    }
    return list
  }, [hubModels, hubSort, hubVramCeiling])

  // Local: client-side sort + filter
  const processedLocal = useMemo(() => {
    let list = [...localModels]
    if (localSort === "name") list.sort((a, b) => a.model_id.localeCompare(b.model_id))
    else if (localSort === "vram_asc") list.sort((a, b) => (a.vram_required_gb ?? Infinity) - (b.vram_required_gb ?? Infinity))
    else if (localSort === "vram_desc") list.sort((a, b) => (b.vram_required_gb ?? -Infinity) - (a.vram_required_gb ?? -Infinity))
    else if (localSort === "size") list.sort((a, b) => a.size_gb - b.size_gb)
    if (localVramCeiling !== null) {
      list = list.filter((m) => m.vram_required_gb === null || m.vram_required_gb <= localVramCeiling)
    }
    return list
  }, [localModels, localSort, localVramCeiling])

  const handleSearchChange = (v: string) => {
    setSearch(v)
    setHubSort("popularity")
    setHubVramCeiling(null)
  }

  const hubVramActive = hubSort === "vram_asc" || hubSort === "vram_desc"

  return (
    <div className="p-8">
      <h1 className="font-heading font-[900] text-5xl text-white mb-6">Models</h1>

      {/* Tab switcher */}
      <div className="flex gap-4 mb-6">
        <button
          onClick={() => setActiveTab("hub")}
          className={`text-sm font-sans font-[700] px-4 py-2 rounded-lg transition-colors ${activeTab === "hub" ? "bg-indigo-600 text-white" : "text-gray-400 hover:text-white"}`}
        >
          HuggingFace Hub
        </button>
        <button
          onClick={() => setActiveTab("local")}
          className={`text-sm font-sans font-[700] px-4 py-2 rounded-lg transition-colors ${activeTab === "local" ? "bg-indigo-600 text-white" : "text-gray-400 hover:text-white"}`}
        >
          Local Cache
        </button>
      </div>

      <p className="text-xs font-sans font-[200] text-gray-500 mb-5">
        Click a model name to prefill a new instance configuration.
      </p>

      {/* ── HF Hub tab ── */}
      {activeTab === "hub" && (
        <>
          <div className="flex flex-wrap gap-3 items-end mb-5">
            <input
              value={search}
              onChange={(e) => handleSearchChange(e.target.value)}
              placeholder="Search HuggingFace hub…"
              className="w-full max-w-md bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white font-mono font-[300] text-sm focus:outline-none focus:border-indigo-500"
            />
          </div>
          <div className="flex flex-wrap gap-4 items-center mb-5">
            <div className="flex items-center gap-2">
              <span className="font-sans font-[200] text-[11px] uppercase tracking-widest text-gray-500">Sort</span>
              <div className="flex gap-1">
                <button
                  onClick={() => setHubSort("popularity")}
                  className={`px-3 py-1 rounded text-xs font-sans font-[700] transition-colors ${
                    hubSort === "popularity"
                      ? "bg-indigo-600 text-white"
                      : "text-gray-400 hover:text-white bg-gray-800 hover:bg-gray-700"
                  }`}
                >
                  Popularity
                </button>
                <button
                  onClick={handleHubVramClick}
                  className={`px-3 py-1 rounded text-xs font-mono font-[600] transition-colors ${
                    hubVramActive
                      ? "bg-indigo-600 text-white"
                      : "text-gray-400 hover:text-white bg-gray-800 hover:bg-gray-700"
                  }`}
                  title={hubVramActive ? "Click to reverse VRAM order" : "Sort by VRAM"}
                >
                  {hubSort === "vram_desc" ? "VRAM ↓" : "VRAM ↑"}
                </button>
              </div>
            </div>
            <VramFilter value={hubVramCeiling} onChange={setHubVramCeiling} />
          </div>

          {loadingHub ? (
            <p className="text-gray-500 font-sans font-[200]">Searching…</p>
          ) : processedHub.length === 0 ? (
            <p className="text-gray-500 font-sans font-[200]">No models match the current filters.</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {processedHub.map((m) => <ModelCard key={m.model_id} model={m} />)}
            </div>
          )}
        </>
      )}

      {/* ── Local Cache tab ── */}
      {activeTab === "local" && (
        <>
          {!loadingLocal && localModels.length > 0 && (
            <div className="flex flex-wrap gap-4 items-center mb-5">
              <div className="flex items-center gap-2">
                <span className="font-sans font-[200] text-[11px] uppercase tracking-widest text-gray-500">Sort</span>
                <PillGroup<LocalSort>
                  options={[
                    { label: "Name", value: "name" },
                    { label: "VRAM ↑", value: "vram_asc" },
                    { label: "VRAM ↓", value: "vram_desc" },
                    { label: "Size ↑", value: "size" },
                  ]}
                  value={localSort}
                  onChange={setLocalSort}
                />
              </div>
              <VramFilter value={localVramCeiling} onChange={setLocalVramCeiling} />
            </div>
          )}

          {loadingLocal ? (
            <p className="text-gray-500 font-sans font-[200]">Loading…</p>
          ) : localModels.length === 0 ? (
            <p className="text-gray-500 font-sans font-[200]">No locally cached models found.</p>
          ) : processedLocal.length === 0 ? (
            <p className="text-gray-500 font-sans font-[200]">No models match the current filters.</p>
          ) : (
            <div className="space-y-3">
              {processedLocal.map((m) => <LocalCard key={m.model_id} model={m} />)}
            </div>
          )}
        </>
      )}
    </div>
  )
}
