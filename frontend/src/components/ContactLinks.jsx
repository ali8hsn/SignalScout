const LABELS = { github: 'GitHub', linkedin: 'LinkedIn', x: 'X', email: 'Email', site: 'Site' };

export default function ContactLinks({ links, className = '' }) {
  const entries = Object.entries(links || {});
  if (!entries.length) return null;
  return (
    <div className={`flex flex-wrap gap-x-4 gap-y-1 font-mono text-[11px] ${className}`}>
      {entries.map(([key, url]) => (
        <a
          key={key}
          href={url}
          target="_blank"
          rel="noreferrer"
          className="text-olive hover:text-olive-dark underline-offset-2 hover:underline"
        >
          {LABELS[key] || key} →
        </a>
      ))}
    </div>
  );
}
