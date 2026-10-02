import { useEffect, useRef } from 'react';

// Dotted "landscape" band under the landing hero: two overlapping hills of fine dots, blue on the
// left and magenta on the right. Drawn once (a still image, no animation); redrawn only on resize.

const LAYERS = [
  { peak: 0.3, spread: 0.2, height: 0.62, rgb: [59, 91, 246] },   // blue, left
  { peak: 0.66, spread: 0.24, height: 0.82, rgb: [192, 38, 211] }, // magenta, right
];

export default function ParticleWave({ className = '' }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;
    let width = 0, height = 0, dpr = 1;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = rect.width;
      height = rect.height;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
    };

    const draw = (time: number) => {
      const t = time / 1000;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, width, height);
      ctx.globalCompositeOperation = 'lighter';
      const rows = 22;
      const spacing = width < 640 ? 6 : 5;
      for (const layer of LAYERS) {
        const [r, g, b] = layer.rgb;
        // One colour per layer; per-dot fading uses globalAlpha (a number) instead of a new colour string.
        ctx.fillStyle = `rgb(${r},${g},${b})`;
        for (let j = 0; j < rows; j++) {
          const depth = j / rows;                       // 0 = ridge line, 1 = far back
          for (let x = 0; x <= width; x += spacing) {
            const fx = x / width;
            const hill = Math.exp(-((fx - layer.peak) ** 2) / (2 * layer.spread ** 2));
            const swell = Math.sin(fx * 9 + j * 0.45 + t * 0.35) * 0.06 + Math.sin(fx * 23 - t * 0.5) * 0.02;
            const y = height - (hill * layer.height + swell + 0.12) * height * (1 - depth * 0.55);
            const edge = Math.min(1, fx * 6, (1 - fx) * 6);
            const alpha = hill * (1 - depth) * edge * 0.55;
            if (alpha < 0.02) continue;
            ctx.globalAlpha = alpha;
            ctx.fillRect(x, y, 1.2, 1.2);
          }
        }
      }
      ctx.globalAlpha = 1;
    };

    const resizeObserver = new ResizeObserver(() => { resize(); draw(0); });
    resizeObserver.observe(canvas);
    return () => resizeObserver.disconnect();
  }, []);

  return <canvas ref={canvasRef} className={className} aria-hidden />;
}
