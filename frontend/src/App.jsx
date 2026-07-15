import { useEffect } from 'react';
import { api } from './api/client.js';
import Discover from './pages/Discover.jsx';

export default function App() {
  useEffect(() => {
    api.pageView({
      path: '/discover',
      referrer: document.referrer || null,
    }).catch(() => {
      // Analytics must never affect the product experience.
    });
  }, []);

  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-cream/95 sticky top-0 z-10 backdrop-blur">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-4 flex flex-col sm:flex-row sm:items-end gap-4 justify-between">
          <div>
            <h1 className="font-display text-3xl leading-none">Signal Scout</h1>
            <p className="text-xs sm:text-sm text-ink-soft mt-1.5">
              Finding exceptional people before the world knows their names
            </p>
          </div>
          <p className="label-mono text-olive">Reviewed public signals</p>
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-8">
        <Discover coryMode />
      </main>
    </div>
  );
}
