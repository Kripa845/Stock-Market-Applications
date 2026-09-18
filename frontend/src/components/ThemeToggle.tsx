import { Sun, Moon } from 'lucide-react';
import { useTheme } from '../hooks/useTheme';

export default function ThemeToggle() {
  const [theme, toggle] = useTheme();

  return (
    <button
      onClick={toggle}
      className="flex items-center justify-center w-9 h-9 rounded-lg border border-bg-border text-text-muted hover:text-text-primary hover:bg-bg-elevated transition-colors"
      aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
      title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
    >
      {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}
