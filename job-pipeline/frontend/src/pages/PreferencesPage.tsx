import { useState, useEffect } from 'react'
import { usePreferences, useSavePreferences } from '@/hooks/usePreferences'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { TopBar } from '@/components/TopBar'
import { Loader2, Check, X } from 'lucide-react'
import type { UserPreferences } from '@/types'

const ROLE_FAMILIES = [
  { id: 'forward-deployed-swe', label: 'Forward Deployed Engineering', desc: 'Customer-facing technical roles' },
  { id: 'ai-startup', label: 'AI / ML Engineering', desc: 'Machine learning & AI product roles' },
  { id: 'motorsport', label: 'Motorsport & Simulation', desc: 'Racing, simulation, dynamics' },
  { id: 'solutions-architect', label: 'Solutions Architecture', desc: 'Pre-sales & technical design' },
  { id: 'robotics', label: 'Robotics & Embedded Systems', desc: 'Robot/firmware/real-time systems' },
  { id: 'general-swe', label: 'General Software Engineering', desc: 'Full-stack & backend roles' },
] as const

const CURRENCIES = ['USD', 'GBP', 'EUR', 'AUD', 'CAD']
const COUNTRIES = ['us', 'uk', 'de', 'fr', 'au', 'ca']

const DEFAULT_PREFS: UserPreferences = {
  search_terms: [],
  role_families: [],
  location: '',
  country_indeed: 'uk',
  results_wanted: 50,
  hours_old: 72,
  salary_floor: 0,
  currency: 'GBP',
  excluded_title_keywords: [],
  excluded_desc_keywords: [],
}

function ChipInput({
  label,
  value,
  onChange,
}: {
  label: string
  value: string[]
  onChange: (v: string[]) => void
}) {
  const [input, setInput] = useState('')

  const add = () => {
    const trimmed = input.trim()
    if (trimmed && !value.includes(trimmed)) {
      onChange([...value, trimmed])
    }
    setInput('')
  }

  const remove = (chip: string) => onChange(value.filter((c) => c !== chip))

  return (
    <div className="space-y-2">
      <label className="text-xs text-text-secondary uppercase tracking-wider">{label}</label>
      <div className="flex gap-2">
        <input
          className="flex-1 bg-bg-elevated border border-border-default rounded px-3 py-1.5 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-border"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), add())}
          placeholder="Type and press Enter"
        />
        <Button variant="outline" size="sm" onClick={add} className="text-xs">
          Add
        </Button>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {value.map((chip) => (
          <Badge
            key={chip}
            variant="secondary"
            className="bg-bg-elevated text-text-secondary border-border-default gap-1 pr-1"
          >
            {chip}
            <button onClick={() => remove(chip)} className="hover:text-text-primary">
              <X className="h-3 w-3" />
            </button>
          </Badge>
        ))}
      </div>
    </div>
  )
}

export function PreferencesPage() {
  const { data, isLoading } = usePreferences()
  const save = useSavePreferences()
  const [prefs, setPrefs] = useState<UserPreferences>(DEFAULT_PREFS)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (data) setPrefs(data)
  }, [data])

  const toggleRoleFamily = (id: string) => {
    setPrefs((p) => ({
      ...p,
      role_families: p.role_families.includes(id)
        ? p.role_families.filter((r) => r !== id)
        : [...p.role_families, id],
    }))
  }

  const handleSave = () => {
    save.mutate(prefs, {
      onSuccess: () => {
        setSaved(true)
        setTimeout(() => setSaved(false), 2000)
      },
    })
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-bg-base">
        <Loader2 className="h-5 w-5 animate-spin text-text-muted" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-bg-base text-text-primary">
      <TopBar
        plan={undefined}
        isLoading={false}
        acceptedCount={0}
        totalSlots={0}
        onGenerateCV={() => undefined}
        isGenerating={false}
        menuOnly
      />

      <main className="max-w-2xl mx-auto px-6 py-10 space-y-10">

        {/* Target Roles */}
        <section className="space-y-4">
          <div>
            <h2 className="text-sm font-semibold text-text-primary">Target Roles</h2>
            <p className="text-xs text-text-muted mt-0.5">Select all role families to include in job searches.</p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {ROLE_FAMILIES.map((rf) => {
              const active = prefs.role_families.includes(rf.id)
              return (
                <button
                  key={rf.id}
                  onClick={() => toggleRoleFamily(rf.id)}
                  className={`text-left rounded-lg border p-3 transition-colors ${
                    active
                      ? 'border-accent-border bg-accent-subtle text-accent-color'
                      : 'border-border-default bg-bg-elevated text-text-secondary hover:border-border-muted'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-xs font-medium leading-snug">{rf.label}</span>
                    {active && <Check className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />}
                  </div>
                  <p className="text-[11px] text-text-muted mt-1">{rf.desc}</p>
                </button>
              )
            })}
          </div>
        </section>

        {/* Search Terms */}
        <section className="space-y-4">
          <div>
            <h2 className="text-sm font-semibold text-text-primary">Search Terms</h2>
            <p className="text-xs text-text-muted mt-0.5">Additional job title keywords to search for.</p>
          </div>
          <ChipInput
            label="Keywords"
            value={prefs.search_terms}
            onChange={(v) => setPrefs((p) => ({ ...p, search_terms: v }))}
          />
        </section>

        {/* Location & Country */}
        <section className="space-y-4">
          <h2 className="text-sm font-semibold text-text-primary">Location</h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs text-text-secondary uppercase tracking-wider">City / Region</label>
              <input
                className="w-full bg-bg-elevated border border-border-default rounded px-3 py-1.5 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-border"
                value={prefs.location}
                onChange={(e) => setPrefs((p) => ({ ...p, location: e.target.value }))}
                placeholder="London"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs text-text-secondary uppercase tracking-wider">Indeed Country</label>
              <select
                className="w-full bg-bg-elevated border border-border-default rounded px-3 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent-border"
                value={prefs.country_indeed}
                onChange={(e) => setPrefs((p) => ({ ...p, country_indeed: e.target.value }))}
              >
                {COUNTRIES.map((c) => (
                  <option key={c} value={c}>{c.toUpperCase()}</option>
                ))}
              </select>
            </div>
          </div>
        </section>

        {/* Search Settings */}
        <section className="space-y-4">
          <h2 className="text-sm font-semibold text-text-primary">Search Settings</h2>
          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs text-text-secondary uppercase tracking-wider">Max results</label>
              <input
                type="number"
                min={1}
                max={200}
                className="w-full bg-bg-elevated border border-border-default rounded px-3 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent-border"
                value={prefs.results_wanted}
                onChange={(e) => setPrefs((p) => ({ ...p, results_wanted: Number(e.target.value) }))}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs text-text-secondary uppercase tracking-wider">Max age (hrs)</label>
              <input
                type="number"
                min={1}
                max={720}
                className="w-full bg-bg-elevated border border-border-default rounded px-3 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent-border"
                value={prefs.hours_old}
                onChange={(e) => setPrefs((p) => ({ ...p, hours_old: Number(e.target.value) }))}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs text-text-secondary uppercase tracking-wider">Salary floor</label>
              <div className="flex gap-1">
                <input
                  type="number"
                  min={0}
                  className="flex-1 bg-bg-elevated border border-border-default rounded px-3 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent-border"
                  value={prefs.salary_floor}
                  onChange={(e) => setPrefs((p) => ({ ...p, salary_floor: Number(e.target.value) }))}
                />
                <select
                  className="bg-bg-elevated border border-border-default rounded px-2 py-1.5 text-xs text-text-primary focus:outline-none focus:border-accent-border"
                  value={prefs.currency}
                  onChange={(e) => setPrefs((p) => ({ ...p, currency: e.target.value }))}
                >
                  {CURRENCIES.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        </section>

        {/* Exclusions */}
        <section className="space-y-4">
          <div>
            <h2 className="text-sm font-semibold text-text-primary">Exclusion Filters</h2>
            <p className="text-xs text-text-muted mt-0.5">Jobs with these keywords in titles or descriptions will be hidden.</p>
          </div>
          <ChipInput
            label="Excluded title keywords"
            value={prefs.excluded_title_keywords}
            onChange={(v) => setPrefs((p) => ({ ...p, excluded_title_keywords: v }))}
          />
          <ChipInput
            label="Excluded description keywords"
            value={prefs.excluded_desc_keywords}
            onChange={(v) => setPrefs((p) => ({ ...p, excluded_desc_keywords: v }))}
          />
        </section>

        {/* Save */}
        <div className="flex items-center gap-3 pt-2">
          <Button
            onClick={handleSave}
            disabled={save.isPending}
            className="bg-accent-color hover:bg-accent-hover text-white"
          >
            {save.isPending ? (
              <>
                <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                Saving…
              </>
            ) : saved ? (
              <>
                <Check className="mr-2 h-3.5 w-3.5" />
                Saved
              </>
            ) : (
              'Save Preferences'
            )}
          </Button>
          {save.isError && (
            <span className="text-xs text-red-400">Failed to save — check backend.</span>
          )}
        </div>
      </main>
    </div>
  )
}
