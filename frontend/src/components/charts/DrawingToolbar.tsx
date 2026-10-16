import { useEffect, useRef, useState } from 'react';
import type { Chart, OverlayCreate, OverlayMode } from 'klinecharts';
import {
  Activity, Circle, Crosshair, Eye, EyeOff, Hexagon, Lock, LockOpen, Magnet, Minus, MoveDiagonal,
  MoveRight, MoveUpRight, PencilLine, RotateCcw, Rows3, Ruler, SeparatorVertical, Slash,
  SlidersHorizontal, Smile, Brush, Square, Tag, Trash2, Triangle, Type, Waypoints, ZoomIn, ZoomOut,
  type LucideIcon,
} from 'lucide-react';
import './drawingOverlays';

// TradingView-style left toolbar: grouped drawing tools with flyouts, then view/drawing toggles.
// Every drawing shares one group id so lock / hide / remove-all never touch other overlays.
const GROUP = 'drawings';
const DEFAULT_BAR_SPACE = 10;

type Tool = { id: string; label: string; overlay: string; icon: LucideIcon; extendData?: string };
type Group = { id: string; title: string; tools: Tool[] };

const GROUPS: Group[] = [
  { id: 'lines', title: 'Lines', tools: [
    { id: 'seg',   label: 'Trend line',      overlay: 'segment',                icon: Slash },
    { id: 'ray',   label: 'Ray',             overlay: 'rayLine',                icon: MoveUpRight },
    { id: 'ext',   label: 'Extended line',   overlay: 'straightLine',           icon: MoveDiagonal },
    { id: 'hor',   label: 'Horizontal line', overlay: 'horizontalStraightLine', icon: Minus },
    { id: 'hray',  label: 'Horizontal ray',  overlay: 'horizontalRayLine',      icon: MoveRight },
    { id: 'vert',  label: 'Vertical line',   overlay: 'verticalStraightLine',   icon: SeparatorVertical },
    { id: 'price', label: 'Price line',      overlay: 'priceLine',              icon: Tag },
  ] },
  { id: 'channels', title: 'Channels', tools: [
    { id: 'chan',  label: 'Parallel channel', overlay: 'parallelStraightLine', icon: Rows3 },
    { id: 'pchan', label: 'Price channel',    overlay: 'priceChannelLine',     icon: Rows3 },
  ] },
  { id: 'patterns', title: 'Patterns', tools: [
    { id: 'xabcd',   label: 'XABCD pattern',      overlay: 'xabcdPattern',      icon: Waypoints },
    { id: 'abcd',    label: 'ABCD pattern',       overlay: 'abcdPattern',       icon: Waypoints },
    { id: 'impulse', label: 'Elliott impulse wave',    overlay: 'elliottImpulse',    icon: Activity },
    { id: 'correct', label: 'Elliott correction wave', overlay: 'elliottCorrection', icon: Activity },
  ] },
  { id: 'fib', title: 'Fibonacci', tools: [
    { id: 'fib',    label: 'Fib retracement',              overlay: 'fibonacciLine', icon: SlidersHorizontal },
    { id: 'fibext', label: 'Trend-based Fib extension',    overlay: 'fibExtension',  icon: SlidersHorizontal },
  ] },
  { id: 'brush', title: 'Brush & shapes', tools: [
    { id: 'brush', label: 'Brush',     overlay: 'brush',         icon: Brush },
    { id: 'rect',  label: 'Rectangle', overlay: 'rectShape',     icon: Square },
    { id: 'circ',  label: 'Circle',    overlay: 'circleShape',   icon: Circle },
    { id: 'tri',   label: 'Triangle',  overlay: 'triangleShape', icon: Triangle },
  ] },
  { id: 'text', title: 'Text', tools: [
    { id: 'text', label: 'Text', overlay: 'textLabel', icon: Type },
  ] },
];

const EMOJIS = ['🚀', '📈', '📉', '🔥', '⚠️', '✅', '❌', '⭐', '💰', '🎯', '👀', '🐂', '🐻', '👍', '👎', '🙂'];
const EMOJI_GROUP = 'emoji';
const MEASURE: Tool = { id: 'measure', label: 'Measure (price & date range)', overlay: 'measureRange', icon: Ruler };

const MAGNET_LABELS: Record<Exclude<OverlayMode, 'normal'>, string> = {
  weak_magnet: 'Weak magnet', strong_magnet: 'Strong magnet',
};

interface Props {
  getChart: () => Chart | null;
}

export default function DrawingToolbar({ getChart }: Props) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState<string | null>(null);         // tool id, null = cursor
  const [choice, setChoice] = useState<Record<string, string>>({});  // group id -> last tool used
  const [open, setOpen] = useState<string | null>(null);             // group whose flyout is open
  const [emoji, setEmoji] = useState(EMOJIS[0]);
  const [magnet, setMagnet] = useState<OverlayMode>('normal');
  const [lastMagnet, setLastMagnet] = useState<Exclude<OverlayMode, 'normal'>>('weak_magnet');
  const [stay, setStay] = useState(false);
  const [locked, setLocked] = useState(false);
  const [hidden, setHidden] = useState(false);

  // Overlay callbacks are created once per drawing, so they read the live settings through a ref.
  const live = useRef({ magnet, stay, locked });
  live.current = { magnet, stay, locked };
  const pending = useRef<string | null>(null);    // drawing that has not been finished yet
  const selected = useRef<string | null>(null);

  const cancelPending = () => {
    if (pending.current) getChart()?.removeOverlay({ id: pending.current });
    pending.current = null;
  };

  const editText = (id: string, current: string) => {
    const text = window.prompt('Text', current)?.trim();
    if (text === undefined) return false;          // cancelled
    if (!text) { getChart()?.removeOverlay({ id }); return false; }
    getChart()?.overrideOverlay({ id, extendData: text });
    return true;
  };

  const finish = (tool: Tool, id: string) => {
    pending.current = null;
    const chart = getChart();
    if (!chart) return;
    // Deferred so the chart finishes its own mouse-up handling before a prompt or a new drawing starts.
    setTimeout(() => {
      if (tool.overlay === 'textLabel' && !editText(id, '')) chart.removeOverlay({ id });
      if (live.current.locked) chart.overrideOverlay({ id, lock: true });
      if (live.current.stay) start(tool);
      else setActive(null);
    }, 0);
  };

  const start = (tool: Tool) => {
    const chart = getChart();
    if (!chart) return;
    cancelPending();
    if (hidden) { chart.overrideOverlay({ groupId: GROUP, visible: true }); setHidden(false); }
    const create: OverlayCreate = {
      name: tool.overlay,
      groupId: GROUP,
      mode: live.current.magnet,
      extendData: tool.extendData,
      onDrawEnd: ({ overlay }) => finish(tool, overlay.id),
      onSelected: ({ overlay }) => { selected.current = overlay.id; },
      onDeselected: ({ overlay }) => { if (selected.current === overlay.id) selected.current = null; },
      onRemoved: ({ overlay }) => { if (selected.current === overlay.id) selected.current = null; },
      onDoubleClick: tool.overlay === 'textLabel'
        ? ({ overlay }) => { editText(overlay.id, String(overlay.extendData ?? '')); }
        : null,
    };
    pending.current = chart.createOverlay(create) as string | null;
    setActive(tool.id);
  };

  const cursor = () => { cancelPending(); setActive(null); setOpen(null); };

  const pick = (group: string, tool: Tool) => {
    setChoice((c) => ({ ...c, [group]: tool.id }));
    setOpen(null);
    start(tool);
  };

  // Escape cancels the drawing in progress, Delete removes the selected drawing.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName))) return;
      if (e.key === 'Escape') { cancelPending(); setActive(null); setOpen(null); }
      if ((e.key === 'Delete' || e.key === 'Backspace') && selected.current) {
        getChart()?.removeOverlay({ id: selected.current });
        selected.current = null;
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Close an open flyout on any click outside the toolbar.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => { if (!rootRef.current?.contains(e.target as Node)) setOpen(null); };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open]);

  const applyMagnet = (mode: OverlayMode) => {
    setMagnet(mode);
    if (mode !== 'normal') setLastMagnet(mode);
    getChart()?.overrideOverlay({ groupId: GROUP, mode });
    setOpen(null);
  };

  const toggleLock = () => {
    getChart()?.overrideOverlay({ groupId: GROUP, lock: !locked });
    setLocked(!locked);
  };

  const toggleHidden = () => {
    getChart()?.overrideOverlay({ groupId: GROUP, visible: hidden });
    setHidden(!hidden);
  };

  const removeAll = () => {
    const chart = getChart();
    if (!chart) return;
    cancelPending();
    setActive(null);
    if (chart.getOverlays({ groupId: GROUP }).length && window.confirm('Remove all drawings from the chart?')) {
      chart.removeOverlay({ groupId: GROUP });
    }
  };

  const zoom = (scale: number | 'reset') => {
    const chart = getChart();
    if (!chart) return;
    if (scale === 'reset') { chart.setBarSpace(DEFAULT_BAR_SPACE); chart.scrollToRealTime(); }
    else chart.zoomAtCoordinate(scale);
  };

  const btn = (on: boolean, toggle = false) =>
    `flex h-9 w-9 items-center justify-center rounded-lg transition-colors ${
      on ? (toggle ? 'bg-accent/15 text-accent-light' : 'bg-accent/10 text-accent-light ring-1 ring-inset ring-accent/60')
        : 'text-text-secondary hover:bg-blue-500/10 hover:text-text-primary'}`;

  // Small corner arrow that opens a group's flyout, like TradingView.
  const flyoutToggle = (id: string) => (
    <button type="button" aria-label="More tools" aria-expanded={open === id}
      onClick={(e) => { e.stopPropagation(); setOpen((o) => (o === id ? null : id)); }}
      className="absolute bottom-0 right-0 flex h-3 w-3 items-end justify-end text-text-secondary opacity-60 hover:opacity-100">
      <svg viewBox="0 0 6 6" className="h-1.5 w-1.5 fill-current"><path d="M6 0v6H0z" /></svg>
    </button>
  );

  const flyout = (id: string, children: React.ReactNode, wide = false) => open === id && (
    <div role="menu" className={`absolute left-full top-0 z-30 ml-1 rounded-lg border border-border bg-bg-card p-1 shadow-lg ${wide ? 'w-[184px]' : 'min-w-[200px]'}`}>
      {children}
    </div>
  );

  const item = (on: boolean, Icon: LucideIcon, text: string, onClick: () => void, key?: string) => (
    <button key={key ?? text} type="button" role="menuitem" onClick={onClick}
      className={`flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs ${on ? 'bg-accent text-white' : 'text-text-primary hover:bg-blue-500/10'}`}>
      <Icon size={14} className="shrink-0" /> {text}
    </button>
  );

  const divider = <span className="my-1.5 h-px w-6 self-center bg-bg-border" />;

  return (
    <div ref={rootRef} className="flex flex-col items-center gap-1 border-r border-bg-border bg-bg-primary px-1.5 py-2">
      <button type="button" title="Cursor (Esc)" onClick={cursor} className={btn(active === null)}>
        <Crosshair size={17} />
      </button>

      {GROUPS.map((g) => {
        const current = g.tools.find((t) => t.id === choice[g.id]) ?? g.tools[0];
        const groupActive = g.tools.some((t) => t.id === active);
        const shown = groupActive ? g.tools.find((t) => t.id === active)! : current;
        const Icon = shown.icon;
        return (
          <div key={g.id} className="relative">
            <button type="button" title={shown.label} onClick={() => pick(g.id, shown)} className={btn(groupActive)}>
              <Icon size={17} />
            </button>
            {g.tools.length > 1 && flyoutToggle(g.id)}
            {flyout(g.id, (
              <>
                <p className="px-2 pb-1 pt-1 text-[11px] font-semibold text-text-secondary">{g.title}</p>
                {g.tools.map((t) => item(active === t.id, t.icon, t.label, () => pick(g.id, t), t.id))}
              </>
            ))}
          </div>
        );
      })}

      {/* Emoji: the button places the last emoji picked; the flyout chooses another. */}
      <div className="relative">
        <button type="button" title={`Emoji ${emoji}`}
          onClick={() => start({ id: EMOJI_GROUP, label: 'Emoji', overlay: 'emojiMark', icon: Smile, extendData: emoji })}
          className={btn(active === EMOJI_GROUP)}>
          <Smile size={17} />
        </button>
        {flyoutToggle(EMOJI_GROUP)}
        {flyout(EMOJI_GROUP, (
          <div className="grid grid-cols-6 gap-0.5">
            {EMOJIS.map((e) => (
              <button key={e} type="button" title={e}
                onClick={() => { setEmoji(e); setOpen(null); start({ id: EMOJI_GROUP, label: 'Emoji', overlay: 'emojiMark', icon: Smile, extendData: e }); }}
                className={`flex h-7 w-7 items-center justify-center rounded text-base hover:bg-blue-500/10 ${e === emoji ? 'bg-bg-elevated' : ''}`}>
                {e}
              </button>
            ))}
          </div>
        ), true)}
      </div>

      <button type="button" title={MEASURE.label} onClick={() => start(MEASURE)} className={btn(active === MEASURE.id)}>
        <Ruler size={17} />
      </button>

      <div className="relative">
        <button type="button" title="Zoom in" onClick={() => zoom(1.25)} className={btn(false)}>
          <ZoomIn size={17} />
        </button>
        {flyoutToggle('zoom')}
        {flyout('zoom', (
          <>
            {item(false, ZoomIn, 'Zoom in', () => zoom(1.25))}
            {item(false, ZoomOut, 'Zoom out', () => zoom(0.8))}
            {item(false, RotateCcw, 'Reset view', () => { zoom('reset'); setOpen(null); })}
          </>
        ))}
      </div>

      {divider}

      <div className="relative">
        <button type="button" title={magnet === 'normal' ? 'Magnet: off' : MAGNET_LABELS[magnet]}
          onClick={() => applyMagnet(magnet === 'normal' ? lastMagnet : 'normal')}
          className={btn(magnet !== 'normal', true)}>
          <Magnet size={17} />
        </button>
        {flyoutToggle('magnet')}
        {flyout('magnet', (
          <>
            {item(magnet === 'weak_magnet', Magnet, 'Weak magnet', () => applyMagnet('weak_magnet'))}
            {item(magnet === 'strong_magnet', Magnet, 'Strong magnet', () => applyMagnet('strong_magnet'))}
            {item(magnet === 'normal', Hexagon, 'Magnet off', () => applyMagnet('normal'))}
          </>
        ))}
      </div>

      <button type="button" title="Stay in drawing mode" aria-pressed={stay}
        onClick={() => setStay((s) => !s)} className={btn(stay, true)}>
        <PencilLine size={17} />
      </button>

      <button type="button" title={locked ? 'Unlock all drawings' : 'Lock all drawings'} aria-pressed={locked}
        onClick={toggleLock} className={btn(locked, true)}>
        {locked ? <Lock size={17} /> : <LockOpen size={17} />}
      </button>

      <button type="button" title={hidden ? 'Show all drawings' : 'Hide all drawings'} aria-pressed={hidden}
        onClick={toggleHidden} className={btn(hidden, true)}>
        {hidden ? <EyeOff size={17} /> : <Eye size={17} />}
      </button>

      {divider}

      <button type="button" title="Remove all drawings (Delete removes the selected one)" onClick={removeAll} className={btn(false)}>
        <Trash2 size={17} />
      </button>
    </div>
  );
}
