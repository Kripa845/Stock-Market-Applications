import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';

export default function Layout() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-bg-primary">
      <div className="flex flex-1 overflow-hidden">
        <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(c => !c)} />
        <div className="flex flex-col flex-1 overflow-hidden">
          <Header />
          <main className="flex-1 overflow-y-auto p-6">
            <Outlet />
          </main>
          <footer className="border-t border-bg-border px-6 py-2 text-[11px] text-text-muted">
            Data from ShareSansar, ShareHub and NEPSE (unofficial sources), for personal research only.
          </footer>
        </div>
      </div>
    </div>
  );
}
