// VidForge AI — HyperFrame motion-graphics engine (Remotion-powered).
// A "hyper frame" is a dense, data-driven visual card: animated number grids,
// kinetic typography walls, chart dashboards, comparison matrices and full
// bento-style scenes that render at any resolution with true alpha.
// Everything here is prop-driven JSON so the Python engine / MCP agent can
// compose cinematic frames without touching code.
import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
  Easing,
} from "remotion";
import { FONT, hexA, Backdrop, Scene } from "./kit";

type HFProps = {
  layout?: string; // hero | grid | statwall | chartdash | compare | quote | bento
  title?: string;
  subtitle?: string;
  accent?: string;
  accent2?: string;
  textColor?: string;
  items?: HFItem[];
  scene?: Scene;
};

type HFItem = {
  type?: string; // stat | text | bar | line | chip | image | list | big
  label?: string;
  value?: number | string;
  unit?: string;
  suffix?: string;
  color?: string;
  data?: number[];
  labels?: string[];
  span?: number; // grid columns this tile occupies (1..4)
  rows?: number; // grid rows this tile occupies (1..3)
};

const fmtNum = (v: number, decimals = 0) =>
  v.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });

// ------------------------------------------------------------------ tiles
const StatTile: React.FC<{
  item: HFItem;
  delay: number;
  accent: string;
  W: number;
  H: number;
}> = ({ item, delay, accent, W, H }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({
    frame: frame - delay,
    fps,
    config: { damping: 14, stiffness: 120 },
  });
  const num = Number(item.value ?? 0);
  const shown = interpolate(pop, [0, 1], [0, num], {
    easing: Easing.out(Easing.cubic),
  });
  const fs = Math.round(H * 0.085);
  return (
    <div
      style={{
        opacity: pop,
        transform: `translateY(${(1 - pop) * 40}px) scale(${0.9 + pop * 0.1})`,
        background: "rgba(255,255,255,0.06)",
        border: `1px solid ${hexA(accent, 0.35)}`,
        borderRadius: H * 0.02,
        padding: `${H * 0.028}px ${W * 0.02}px`,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        fontFamily: FONT,
        boxSizing: "border-box",
        height: "100%",
      }}
    >
      <div
        style={{
          fontSize: fs,
          fontWeight: 800,
          color: item.color || "#ffffff",
          lineHeight: 1,
          fontVariantNumeric: "tabular-nums",
          textShadow: `0 0 ${H * 0.03}px ${hexA(accent, 0.5)}`,
        }}
      >
        {fmtNum(shown, Number.isInteger(num) ? 0 : 1)}
        {item.suffix || ""}
      </div>
      <div
        style={{
          marginTop: H * 0.012,
          fontSize: Math.round(H * 0.026),
          letterSpacing: H * 0.002,
          textTransform: "uppercase",
          color: hexA(item.color || accent, 0.9),
          fontWeight: 700,
        }}
      >
        {item.label || ""}
      </div>
    </div>
  );
};

const BarTile: React.FC<{ item: HFItem; delay: number; accent: string; W: number; H: number }> = ({
  item,
  delay,
  accent,
  W,
  H,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const grow = spring({ frame: frame - delay, fps, config: { damping: 18, stiffness: 90 } });
  const data = item.data && item.data.length ? item.data : [1];
  const max = Math.max(...data.map((d) => Math.abs(d)), 0.0001);
  return (
    <div
      style={{
        opacity: grow,
        background: "rgba(255,255,255,0.05)",
        border: `1px solid ${hexA(accent, 0.25)}`,
        borderRadius: H * 0.02,
        padding: H * 0.024,
        display: "flex",
        flexDirection: "column",
        fontFamily: FONT,
        boxSizing: "border-box",
        height: "100%",
      }}
    >
      {item.label ? (
        <div
          style={{
            color: "#fff",
            fontWeight: 800,
            fontSize: Math.round(H * 0.03),
            marginBottom: H * 0.016,
          }}
        >
          {item.label}
        </div>
      ) : null}
      <div style={{ flex: 1, display: "flex", alignItems: "flex-end", gap: W * 0.008 }}>
        {data.map((d, i) => {
          const h = interpolate(grow, [0, 1], [0, (Math.abs(d) / max) * 100]);
          return (
            <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", height: "100%", justifyContent: "flex-end" }}>
              <div
                style={{
                  height: `${h}%`,
                  background: `linear-gradient(180deg, ${item.color || accent}, ${hexA(item.color || accent, 0.35)})`,
                  borderRadius: H * 0.006,
                }}
              />
              {item.labels?.[i] ? (
                <div style={{ fontSize: Math.round(H * 0.018), color: hexA("#ffffff", 0.6), textAlign: "center", marginTop: 4 }}>
                  {item.labels[i]}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
};

const TextTile: React.FC<{ item: HFItem; delay: number; accent: string; W: number; H: number }> = ({
  item,
  delay,
  accent,
  W,
  H,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - delay, fps, config: { damping: 20, stiffness: 100 } });
  const words = String(item.value ?? item.label ?? "").split(" ");
  return (
    <div
      style={{
        opacity: s,
        transform: `translateX(${(1 - s) * -30}px)`,
        fontFamily: FONT,
        color: "#fff",
        fontSize: Math.round(H * (item.type === "big" ? 0.06 : 0.034)),
        fontWeight: item.type === "big" ? 900 : 600,
        lineHeight: 1.25,
        padding: H * 0.02,
        borderLeft: `6px solid ${item.color || accent}`,
        boxSizing: "border-box",
        height: "100%",
      }}
    >
      {words.map((w, i) => (
        <span key={i} style={{ marginRight: H * 0.01 }}>{w}</span>
      ))}
    </div>
  );
};

const ChipTile: React.FC<{ item: HFItem; delay: number; accent: string; W: number; H: number }> = ({
  item,
  delay,
  accent,
  W,
  H,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - delay, fps, config: { damping: 12, stiffness: 160 } });
  return (
    <div
      style={{
        opacity: s,
        transform: `scale(${s})`,
        alignSelf: "flex-start",
        background: hexA(item.color || accent, 0.16),
        border: `1px solid ${item.color || accent}`,
        color: item.color || accent,
        borderRadius: 999,
        padding: `${H * 0.012}px ${H * 0.028}px`,
        fontFamily: FONT,
        fontWeight: 800,
        fontSize: Math.round(H * 0.026),
        width: "fit-content",
        margin: H * 0.012,
      }}
    >
      {item.label}
    </div>
  );
};

const ListTile: React.FC<{ item: HFItem; delay: number; accent: string; W: number; H: number }> = ({
  item,
  delay,
  accent,
  W,
  H,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const rows = (item.labels && item.labels.length ? item.labels : [String(item.value ?? "")]).filter(Boolean);
  return (
    <div style={{ fontFamily: FONT, padding: H * 0.018, height: "100%", boxSizing: "border-box" }}>
      {item.label ? (
        <div style={{ color: accent, fontWeight: 900, fontSize: Math.round(H * 0.03), marginBottom: H * 0.012, textTransform: "uppercase", letterSpacing: 2 }}>
          {item.label}
        </div>
      ) : null}
      {rows.map((r, i) => {
        const s = spring({ frame: frame - delay - i * 5, fps, config: { damping: 20, stiffness: 110 } });
        return (
          <div
            key={i}
            style={{
              opacity: s,
              transform: `translateY(${(1 - s) * 16}px)`,
              color: "#eef2f7",
              fontSize: Math.round(H * 0.028),
              padding: `${H * 0.008}px 0`,
              borderBottom: `1px solid ${hexA("#ffffff", 0.08)}`,
              display: "flex",
              gap: H * 0.014,
              alignItems: "center",
            }}
          >
            <span style={{ color: accent, fontWeight: 900 }}>▸</span>
            {r}
          </div>
        );
      })}
    </div>
  );
};

const ImageTile: React.FC<{ item: HFItem; delay: number; accent: string; W: number; H: number }> = ({
  item,
  delay,
  accent,
  W,
  H,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - delay, fps, config: { damping: 16, stiffness: 90 } });
  const zoom = interpolate(frame, [delay, delay + 90], [1.0, 1.12], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  if (!item.value) return null;
  return (
    <div
      style={{
        opacity: s,
        borderRadius: H * 0.02,
        overflow: "hidden",
        border: `1px solid ${hexA(accent, 0.4)}`,
        height: "100%",
        position: "relative",
      }}
    >
      <img
        src={String(item.value)}
        style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${zoom})` }}
      />
      {item.label ? (
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            bottom: 0,
            padding: H * 0.016,
            background: "linear-gradient(transparent, rgba(0,0,0,0.75))",
            color: "#fff",
            fontFamily: FONT,
            fontWeight: 800,
            fontSize: Math.round(H * 0.028),
          }}
        >
          {item.label}
        </div>
      ) : null}
    </div>
  );
};

const Tile: React.FC<{ item: HFItem; index: number; accent: string; W: number; H: number }> = ({
  item,
  index,
  accent,
  W,
  H,
}) => {
  const delay = 6 + index * 4;
  const t = (item.type || "stat").toLowerCase();
  switch (t) {
    case "bar":
      return <BarTile item={item} delay={delay} accent={accent} W={W} H={H} />;
    case "text":
    case "big":
      return <TextTile item={item} delay={delay} accent={accent} W={W} H={H} />;
    case "chip":
      return <ChipTile item={item} delay={delay} accent={accent} W={W} H={H} />;
    case "list":
      return <ListTile item={item} delay={delay} accent={accent} W={W} H={H} />;
    case "image":
      return <ImageTile item={item} delay={delay} accent={accent} W={W} H={H} />;
    default:
      return <StatTile item={item} delay={delay} accent={accent} W={W} H={H} />;
  }
};

// ------------------------------------------------------------------ header
const Header: React.FC<{ p: HFProps; W: number; H: number }> = ({ p, W, H }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame, fps, config: { damping: 16, stiffness: 110 } });
  const glow = 0.5 + 0.5 * Math.sin(frame / 8);
  if (!p.title) return null;
  return (
    <div
      style={{
        fontFamily: FONT,
        padding: `${H * 0.04}px ${W * 0.045}px ${H * 0.01}px`,
        opacity: s,
        transform: `translateY(${(1 - s) * -40}px)`,
      }}
    >
      <div
        style={{
          fontSize: Math.round(H * 0.062),
          fontWeight: 900,
          color: "#ffffff",
          letterSpacing: -H * 0.001,
          textShadow: `0 0 ${H * (0.02 + 0.02 * glow)}px ${hexA(p.accent || "#00d9ff", 0.6)}`,
        }}
      >
        {p.title}
      </div>
      {p.subtitle ? (
        <div style={{ fontSize: Math.round(H * 0.028), color: hexA(p.textColor || "#cfe3ff", 0.85), marginTop: H * 0.008 }}>
          {p.subtitle}
        </div>
      ) : null}
      <div
        style={{
          marginTop: H * 0.014,
          height: Math.max(3, H * 0.006),
          width: interpolate(s, [0, 1], [0, W * 0.3]),
          background: `linear-gradient(90deg, ${p.accent || "#00d9ff"}, ${p.accent2 || "#ff3d68"})`,
          borderRadius: 99,
        }}
      />
    </div>
  );
};

// ------------------------------------------------------------------ layouts
const GridLayout: React.FC<{ p: HFProps; W: number; H: number }> = ({ p, W, H }) => {
  const items = p.items || [];
  const cols = p.layout === "grid" ? 2 : p.layout === "statwall" ? 3 : p.layout === "bento" ? 4 : 3;
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: `repeat(${cols}, 1fr)`,
        gap: H * 0.018,
        padding: `${H * 0.02}px ${W * 0.045}px ${H * 0.04}px`,
        flex: 1,
        alignContent: "stretch",
      }}
    >
      {items.map((it, i) => (
        <div
          key={i}
          style={{
            gridColumn: `span ${Math.min(it.span || 1, cols)}`,
            gridRow: `span ${it.rows || 1}`,
            minHeight: 0,
          }}
        >
          <Tile item={it} index={i} accent={p.accent || "#00d9ff"} W={W} H={H} />
        </div>
      ))}
    </div>
  );
};

const HeroLayout: React.FC<{ p: HFProps; W: number; H: number }> = ({ p, W, H }) => {
  const items = p.items || [];
  const main = items[0];
  const rest = items.slice(1);
  return (
    <div style={{ display: "flex", flex: 1, gap: H * 0.02, padding: `${H * 0.02}px ${W * 0.045}px ${H * 0.04}px` }}>
      <div style={{ flex: 2, minHeight: 0 }}>
        {main ? <Tile item={main} index={0} accent={p.accent || "#00d9ff"} W={W} H={H} /> : null}
      </div>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: H * 0.018 }}>
        {rest.map((it, i) => (
          <div key={i} style={{ flex: 1, minHeight: 0 }}>
            <Tile item={it} index={i + 1} accent={p.accent || "#00d9ff"} W={W} H={H} />
          </div>
        ))}
      </div>
    </div>
  );
};

const CompareLayout: React.FC<{ p: HFProps; W: number; H: number }> = ({ p, W, H }) => {
  const items = p.items || [];
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const wipe = spring({ frame: frame - 8, fps, config: { damping: 20, stiffness: 80 } });
  return (
    <div style={{ display: "flex", flex: 1, position: "relative", padding: `${H * 0.02}px ${W * 0.045}px ${H * 0.04}px`, gap: H * 0.02 }}>
      {[0, 1].map((side) => (
        <div key={side} style={{ flex: 1, display: "flex", flexDirection: "column", gap: H * 0.016 }}>
          {(side === 0 ? items.filter((_, i) => i % 2 === 0) : items.filter((_, i) => i % 2 === 1)).map((it, i) => (
            <div key={i} style={{ flex: 1, minHeight: 0 }}>
              <Tile item={it} index={side * 3 + i} accent={side === 0 ? "#3fb6ff" : "#ff3d68"} W={W} H={H} />
            </div>
          ))}
        </div>
      ))}
      <div
        style={{
          position: "absolute",
          top: H * 0.02,
          bottom: H * 0.04,
          left: `${interpolate(wipe, [0, 1], [0, 50])}%`,
          width: 4,
          background: "linear-gradient(180deg,#fff,#888)",
          transform: "translateX(-50%)",
          borderRadius: 99,
          boxShadow: "0 0 24px rgba(255,255,255,.6)",
        }}
      />
    </div>
  );
};

// ------------------------------------------------------------------ main
export const HyperFrame: React.FC<HFProps> = (props) => {
  const { width: W, height: H } = useVideoConfig();
  const p = props;
  const layout = (p.layout || "grid").toLowerCase();
  return (
    <AbsoluteFill style={{ backgroundColor: "transparent", fontFamily: FONT }}>
      <Backdrop scene={p.scene} />
      {/* subtle animated grid backdrop for tech feel */}
      <GridLines accent={p.accent || "#00d9ff"} />
      <Header p={p} W={W} H={H} />
      {layout === "hero" ? (
        <HeroLayout p={p} W={W} H={H} />
      ) : layout === "compare" ? (
        <CompareLayout p={p} W={W} H={H} />
      ) : (
        <GridLayout p={p} W={W} H={H} />
      )}
    </AbsoluteFill>
  );
};

const GridLines: React.FC<{ accent: string }> = ({ accent }) => {
  const frame = useCurrentFrame();
  const off = (frame * 0.6) % 80;
  return (
    <AbsoluteFill
      style={{
        opacity: 0.1,
        backgroundImage: `linear-gradient(${hexA(accent, 0.6)} 1px, transparent 1px), linear-gradient(90deg, ${hexA(accent, 0.6)} 1px, transparent 1px)`,
        backgroundSize: "80px 80px",
        backgroundPosition: `0 ${off}px`,
      }}
    />
  );
};

// ------------------------------------------------------------------ ticker
export const HyperTicker: React.FC<{
  lines?: string[];
  accent?: string;
  speed?: number;
  scene?: Scene;
}> = ({ lines = [], accent = "#ffd23c", speed = 2, scene }) => {
  const frame = useCurrentFrame();
  const { fps, height: H, width: W } = useVideoConfig();
  const items = lines.length ? lines : ["VidForge AI"];
  const rowH = H * 0.09;
  const shift = ((frame / fps) * speed * rowH) % (rowH * items.length);
  return (
    <AbsoluteFill style={{ backgroundColor: "transparent" }}>
      <Backdrop scene={scene} />
      <div style={{ position: "absolute", inset: 0, overflow: "hidden" }}>
        {items.concat(items).map((l, i) => (
          <div
            key={i}
            style={{
              height: rowH,
              display: "flex",
              alignItems: "center",
              transform: `translateY(${-shift + i * rowH}px)`,
              fontFamily: FONT,
              fontWeight: 900,
              fontSize: Math.round(rowH * 0.52),
              color: i % 2 ? "#ffffff" : accent,
              whiteSpace: "nowrap",
              padding: `0 ${W * 0.05}px`,
            }}
          >
            <span style={{ color: accent, marginRight: 24 }}>●</span>
            {l}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};
