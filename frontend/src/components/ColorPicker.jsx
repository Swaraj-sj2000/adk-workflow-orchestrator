/**
 * Color picker popover — hue strip + 2D saturation/brightness square.
 * Internally uses HSV (easy to render with CSS gradients), converts to HSL for output.
 * Brightness floor = 0.42 (prevents very dark results).
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';

const MIN_V = 0.42;   // floor on HSV value — blocks very dark choices

const PRESETS = [
  { label: 'Sage',     h: 155, s: 0.44, v: 0.49 },
  { label: 'Ocean',    h: 200, s: 0.82, v: 0.53 },
  { label: 'Sunset',   h: 16,  s: 0.77, v: 0.79 },
  { label: 'Violet',   h: 268, s: 0.60, v: 0.72 },
  { label: 'Rose',     h: 340, s: 0.65, v: 0.80 },
  { label: 'Amber',    h: 38,  s: 0.88, v: 0.90 },
  { label: 'Sky',      h: 196, s: 0.70, v: 0.85 },
  { label: 'Coral',    h: 8,   s: 0.68, v: 0.88 },
];

/* ── HSV ↔ HSL helpers ─────────────────────────────────────────────────────── */

function hsvToHsl(h, s, v) {
  const l = v * (1 - s / 2);
  const sHsl = (l === 0 || l === 1) ? 0 : (v - l) / Math.min(l, 1 - l);
  return { h, s: sHsl, l };
}

function hslToCss(h, sHsl, l) {
  return `hsl(${Math.round(h)}, ${Math.round(sHsl * 100)}%, ${Math.round(l * 100)}%)`;
}

function darken(h, sHsl, l, amount = 0.12) {
  return hslToCss(h, sHsl, Math.max(l - amount, 0.25));
}

function hsvToAccent(h, s, v) {
  const { s: sHsl, l } = hsvToHsl(h, s, v);
  return {
    accent:       hslToCss(h, sHsl, l),
    accentStrong: darken(h, sHsl, l),
  };
}

/* ── Drag helper ───────────────────────────────────────────────────────────── */

function useDrag(onMove) {
  const ref = useRef(null);

  const handleMouseDown = useCallback((e) => {
    e.preventDefault();
    const rect = ref.current.getBoundingClientRect();

    const move = (ev) => {
      const x = Math.max(0, Math.min(1, (ev.clientX - rect.left) / rect.width));
      const y = Math.max(0, Math.min(1, (ev.clientY - rect.top) / rect.height));
      onMove(x, y);
    };
    const up = () => { window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up); };
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
    move(e);
  }, [onMove]);

  return { ref, onMouseDown: handleMouseDown };
}

function useHueDrag(onHue) {
  const ref = useRef(null);

  const handleMouseDown = useCallback((e) => {
    e.preventDefault();
    const rect = ref.current.getBoundingClientRect();
    const move = (ev) => {
      const x = Math.max(0, Math.min(1, (ev.clientX - rect.left) / rect.width));
      onHue(Math.round(x * 360));
    };
    const up = () => { window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up); };
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
    move(e);
  }, [onHue]);

  return { ref, onMouseDown: handleMouseDown };
}

/* ── Main component ─────────────────────────────────────────────────────────── */

export default function ColorPicker({ onAccentChange, onClose, currentAccent }) {
  const [hue, setHue] = useState(155);
  const [sat, setSat] = useState(0.44);  // HSV saturation
  const [val, setVal] = useState(0.49);  // HSV value (brightness), clamped ≥ MIN_V

  // Initialise from currentAccent if provided
  useEffect(() => {
    if (currentAccent) {
      setHue(currentAccent.h);
      setSat(currentAccent.s);
      setVal(currentAccent.v);
    }
  }, []);

  const safeVal = Math.max(val, MIN_V);

  const { accent, accentStrong } = hsvToAccent(hue, sat, safeVal);

  const emit = useCallback((h, s, v) => {
    const sv = Math.max(v, MIN_V);
    const { s: sHsl, l } = hsvToHsl(h, s, sv);
    const { accent: a, accentStrong: as_ } = hsvToAccent(h, s, sv);
    onAccentChange({ h, s, v: sv, sHsl, l, accent: a, accentStrong: as_ });
  }, [onAccentChange]);

  // 2D square drag
  const onSquareMove = useCallback((x, y) => {
    const newSat = x;
    // Y=0 → top → v=1; Y=1 → bottom → v=MIN_V
    const newVal = 1 - y * (1 - MIN_V);
    setSat(newSat);
    setVal(newVal);
    emit(hue, newSat, newVal);
  }, [hue, emit]);

  const squareDrag = useDrag(onSquareMove);

  // Hue strip drag
  const onHueMove = useCallback((h) => {
    setHue(h);
    emit(h, sat, safeVal);
  }, [sat, safeVal, emit]);

  const hueDrag = useHueDrag(onHueMove);

  const handlePreset = (p) => {
    setHue(p.h);
    setSat(p.s);
    setVal(p.v);
    emit(p.h, p.s, p.v);
  };

  // Click outside to close
  const panelRef = useRef(null);
  useEffect(() => {
    const handler = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target)) onClose();
    };
    setTimeout(() => window.addEventListener('mousedown', handler), 0);
    return () => window.removeEventListener('mousedown', handler);
  }, [onClose]);

  // 2D square handle position
  const handleX = `${Math.round(sat * 100)}%`;
  const handleY = `${Math.round((1 - (safeVal - MIN_V) / (1 - MIN_V)) * 100)}%`;

  return (
    <div ref={panelRef} style={panel}>

      {/* Preset swatches */}
      <div style={{ marginBottom: 14 }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Quick presets</div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {PRESETS.map((p) => {
            const { accent: pa } = hsvToAccent(p.h, p.s, p.v);
            return (
              <button
                key={p.label}
                title={p.label}
                onClick={() => handlePreset(p)}
                style={{
                  width: 26, height: 26, borderRadius: '50%',
                  background: pa, border: `2px solid ${hue === p.h && Math.abs(sat - p.s) < 0.05 ? 'var(--text-primary)' : 'transparent'}`,
                  cursor: 'pointer', transition: 'transform 0.1s',
                  boxShadow: '0 1px 4px rgba(0,0,0,0.2)',
                }}
              />
            );
          })}
        </div>
      </div>

      {/* 2D saturation / brightness square */}
      <div style={{ marginBottom: 10 }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Colour</div>
        <div
          {...squareDrag}
          style={{
            width: '100%', height: 160, borderRadius: 10, position: 'relative',
            cursor: 'crosshair', userSelect: 'none',
            background: `
              linear-gradient(to bottom, transparent 0%, rgba(0,0,0,${1 - MIN_V}) 100%),
              linear-gradient(to right, rgba(255,255,255,1) 0%, rgba(255,255,255,0) 100%),
              hsl(${hue}, 100%, 50%)
            `,
            boxShadow: 'inset 0 0 0 1px rgba(0,0,0,0.12)',
          }}
          onClick={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            onSquareMove(
              Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width)),
              Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height)),
            );
          }}
        >
          {/* Handle */}
          <div style={{
            position: 'absolute',
            left: handleX, top: handleY,
            transform: 'translate(-50%, -50%)',
            width: 16, height: 16, borderRadius: '50%',
            border: '2.5px solid #fff',
            boxShadow: '0 0 0 1px rgba(0,0,0,0.35), 0 2px 6px rgba(0,0,0,0.25)',
            background: accent,
            pointerEvents: 'none',
          }} />
        </div>
      </div>

      {/* Hue rainbow strip */}
      <div style={{ marginBottom: 14 }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Hue</div>
        <div
          {...hueDrag}
          style={{
            width: '100%', height: 18, borderRadius: 9, position: 'relative',
            cursor: 'ew-resize', userSelect: 'none',
            background: 'linear-gradient(to right, hsl(0,100%,50%), hsl(30,100%,50%), hsl(60,100%,50%), hsl(90,100%,50%), hsl(120,100%,50%), hsl(150,100%,50%), hsl(180,100%,50%), hsl(210,100%,50%), hsl(240,100%,50%), hsl(270,100%,50%), hsl(300,100%,50%), hsl(330,100%,50%), hsl(360,100%,50%))',
            boxShadow: 'inset 0 0 0 1px rgba(0,0,0,0.12)',
          }}
          onClick={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const x = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
            onHueMove(Math.round(x * 360));
          }}
        >
          {/* Hue handle */}
          <div style={{
            position: 'absolute',
            left: `${(hue / 360) * 100}%`,
            top: '50%',
            transform: 'translate(-50%, -50%)',
            width: 20, height: 20, borderRadius: '50%',
            border: '2.5px solid #fff',
            background: `hsl(${hue}, 100%, 50%)`,
            boxShadow: '0 0 0 1px rgba(0,0,0,0.3), 0 2px 6px rgba(0,0,0,0.2)',
            pointerEvents: 'none',
          }} />
        </div>
      </div>

      {/* Preview + info */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{
          width: 40, height: 40, borderRadius: 10, background: accent, flexShrink: 0,
          boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
        }} />
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)' }}>{accent}</div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>Hue {Math.round(hue)}° · Sat {Math.round(sat * 100)}% · Brightness {Math.round(safeVal * 100)}%</div>
        </div>
        <button
          onClick={() => { handlePreset(PRESETS[0]); }}
          style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-secondary)', background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline', whiteSpace: 'nowrap' }}
        >
          Reset
        </button>
      </div>

      {/* Dark warning if approaching limit */}
      {safeVal <= MIN_V + 0.02 && (
        <div style={{ marginTop: 10, fontSize: 11, color: '#e6a817', fontWeight: 600 }}>
          ⚠ Brightness floored — very dark colors are blocked
        </div>
      )}
    </div>
  );
}

const panel = {
  position: 'absolute',
  top: 'calc(100% + 10px)',
  right: 0,
  width: 300,
  background: 'var(--surface-card)',
  border: '1px solid var(--border-soft)',
  borderRadius: 16,
  padding: '18px 18px 16px',
  boxShadow: '0 16px 50px rgba(0,0,0,0.22)',
  zIndex: 9999,
};
