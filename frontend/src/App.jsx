import { useState } from 'react';
import Backtest from './pages/Backtest.jsx';
import Digest from './pages/Digest.jsx';
import Discover from './pages/Discover.jsx';

const TABS = ['Discover', 'Backtest', 'Digest'];

export default function App() {
  const [tab, setTab] = useState('Discover');

  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-cream/95 sticky top-0 z-10 backdrop-blur">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-end justify-between">
          <div>
            <h1 className="font-display text-3xl leading-none">Signal Scout</h1>
            <p className="label-mono mt-1.5">exceptional people, before breakout</p>
          </div>
          <nav className="flex gap-1">
            {TABS.map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-4 py-1.5 font-mono text-xs tracking-wide border rounded-sm transition-colors ${
                  tab === t
                    ? 'bg-olive text-cream border-olive'
                    : 'border-line text-ink-soft hover:border-olive hover:text-olive'
                }`}
              >
                {t.toUpperCase()}
              </button>
            ))}
          </nav>
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-6 py-8">
        {tab === 'Discover' && <Discover />}
        {tab === 'Backtest' && <Backtest />}
        {tab === 'Digest' && <Digest />}
      </main>
    </div>
  );
}
