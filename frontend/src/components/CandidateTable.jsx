import { useMemo, useState } from 'react';

const COLUMNS = [
  { key: 'score', label: 'Score' },
  { key: 'name', label: 'Name' },
  { key: 'school', label: 'School' },
  { key: 'area', label: 'Area' },
  { key: 'region', label: 'Location' },
  { key: 'github_followers', label: 'Followers' },
  { key: 'connection_count', label: 'Connections' },
  { key: 'signal_count', label: 'Signals' },
];

const UNKNOWN_FOLLOWER_CAP = 1000;

export default function CandidateTable({ candidates, onSelect, highlightIds }) {
  const highlight = highlightIds instanceof Set ? highlightIds : new Set(highlightIds || []);
  const [sortKey, setSortKey] = useState('score');
  const [sortDesc, setSortDesc] = useState(true);
  const [areaFilter, setAreaFilter] = useState('All');
  const [unknownsOnly, setUnknownsOnly] = useState(true);

  const areas = useMemo(
    () => ['All', ...new Set(candidates.map((c) => c.area).filter(Boolean))],
    [candidates],
  );

  const rows = useMemo(() => {
    let filtered = areaFilter === 'All' ? candidates : candidates.filter((c) => c.area === areaFilter);
    if (unknownsOnly) {
      filtered = filtered.filter(
        (c) => c.github_followers == null || c.github_followers <= UNKNOWN_FOLLOWER_CAP,
      );
    }
    return [...filtered].sort((a, b) => {
      const av = a[sortKey] ?? '';
      const bv = b[sortKey] ?? '';
      const cmp = typeof av === 'number' ? av - bv : String(av).localeCompare(String(bv));
      return sortDesc ? -cmp : cmp;
    });
  }, [candidates, sortKey, sortDesc, areaFilter, unknownsOnly]);

  const toggleSort = (key) => {
    if (key === sortKey) setSortDesc(!sortDesc);
    else {
      setSortKey(key);
      setSortDesc(true);
    }
  };

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <span className="label-mono">area</span>
        <select
          value={areaFilter}
          onChange={(e) => setAreaFilter(e.target.value)}
          className="bg-card border border-line rounded-sm font-mono text-xs px-3 py-1.5 text-ink-soft"
        >
          {areas.map((a) => <option key={a}>{a}</option>)}
        </select>
        <label className="flex items-center gap-1.5 label-mono cursor-pointer select-none">
          <input
            type="checkbox"
            checked={unknownsOnly}
            onChange={(e) => setUnknownsOnly(e.target.checked)}
            className="accent-olive"
          />
          unknowns only
        </label>
        <span className="label-mono ml-auto">{rows.length} candidates</span>
      </div>
      <div className="bg-card border border-line rounded-md overflow-hidden">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-line">
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  onClick={() => toggleSort(col.key)}
                  className="text-left px-4 py-2.5 label-mono cursor-pointer select-none hover:text-olive"
                >
                  {col.label}
                  {sortKey === col.key && <span className="ml-1 text-olive">{sortDesc ? '↓' : '↑'}</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr
                key={c.id}
                onClick={() => onSelect(c)}
                className={`border-b border-line-soft last:border-0 hover:bg-cream cursor-pointer ${
                  highlight.has(c.id) ? 'bg-olive/10' : ''
                }`}
              >
                <td className="px-4 py-2.5 font-mono text-olive">{Math.round(c.score)}</td>
                <td className="px-4 py-2.5 font-display text-[15px]">
                  {c.name}
                  {highlight.has(c.id) && (
                    <span className="ml-2 font-mono text-[9px] tracking-widest text-olive align-middle">NEW</span>
                  )}
                </td>
                <td className="px-4 py-2.5 text-ink-soft">{c.school || '—'}</td>
                <td className="px-4 py-2.5 text-ink-soft">{c.area || '—'}</td>
                <td className="px-4 py-2.5 text-ink-soft">{c.region || c.current_location || '—'}</td>
                <td className="px-4 py-2.5 font-mono">
                  {c.github_followers == null ? '—' : c.github_followers.toLocaleString()}
                </td>
                <td className="px-4 py-2.5 font-mono">{c.connection_count}</td>
                <td className="px-4 py-2.5 font-mono">{c.signal_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
