// VidForge AI — Remotion Motion Graphics Kit
// Professional, data-driven compositions. All graphics render on a
// TRANSPARENT background so VidForge overlays them via FFmpeg (alpha),
// or composites a "scene" backdrop for full-frame cards.
import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
  Sequence,
  Easing,
} from "remotion";

import { HyperFrame, HyperTicker } from "./hyperframe";

export const FONT =
  "'Inter','Segoe UI',system-ui,-apple-system,'Helvetica Neue',Arial,sans-serif";

export const hexA = (hex: string, a: number) => {
  const n = Math.round(Math.max(0, Math.min(1, a)) * 255)
    .toString(16)
    .padStart(2, "0");
  return (hex || "#ffffff") + n;
};

export type Scene = {
  kind?: "transparent" | "solid" | "gradient";
  bg?: string; // solid color when kind=solid
  from?: string; // gradient top
  to?: string; // gradient bottom
};

type BaseProps = {
  W?: number;
  H?: number;
  accent?: string;
  text?: string;
  sub?: string;
  scene?: Scene;
};

export const Backdrop: React.FC<{ scene?: Scene }> = ({ scene }) => {
  const s = scene || { kind: "transparent" as const };
  if (s.kind === "solid")
    return <AbsoluteFill style={{ backgroundColor: s.bg || "#0b0e14" }} />;
  if (s.kind === "gradient")
    return (
      <AbsoluteFill
        style={{
          background: `linear-gradient(160deg, ${s.from || "#101423"}, ${
            s.to || "#05070c"
          })`,
        }}
      />
    );
  return null;
};

// ------------------------------------------------------------------ Lower Third
export const LowerThird: React.FC<
  BaseProps & { role?: string; position?: "left" | "center" }
> = ({ text = "", role = "", accent = "#00d9ff", position = "left", scene }) => {
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();
  const enter = spring({ frame, fps, config: { damping: 200, stiffness: 180 } });
  const barW = interpolate(enter, [0, 1], [0, 1], {
    easing: Easing.out(Easing.cubic),
  });
  const txtA = interpolate(frame, [8, 22], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const align = position === "center" ? ("center" as const) : ("flex-start" as const);
  return (
    <AbsoluteFill style={{ backgroundColor: "transparent" }}>
      <Backdrop scene={scene} />
      <div
        style={{
          position: "absolute",
          left: position === "center" ? "10%" : "6%",
          right: position === "center" ? "10%" : undefined,
          bottom: height * 0.14,
          display: "flex",
          flexDirection: "column",
          alignItems: align,
          fontFamily: FONT,
        }}
      >
        <div
          style={{
            opacity: txtA,
            transform: `translateX(${(1 - enter) * -60}px)`,
            fontSize: height * 0.062,
            fontWeight: 800,
            color: "#ffffff",
            letterSpacing: -height * 0.001,
            textShadow: "0 2px 18px rgba(0,0,0,.55)",
          }}
        >
          {text}
        </div>
        {role ? (
          <div
            style={{
              opacity: txtA,
              marginTop: height * 0.008,
              fontSize: height * 0.032,
              fontWeight: 600,
              color: accent,
              textTransform: "uppercase",
              letterSpacing: height * 0.004,
            }}
          >
            {role}
          </div>
        ) : null}
        <div
          style={{
            marginTop: height * 0.018,
            height: height * 0.011,
            width: `${barW * 100}%`,
            maxWidth: "46vw",
            borderRadius: height * 0.011,
            background: `linear-gradient(90deg, ${accent}, ${hexA(accent, 0.15)})`,
          }}
        />
      </div>
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------ Stat Counter
export const StatCounter: React.FC<
  BaseProps & { value?: number; suffix?: string; prefix?: string }
> = ({ value = 100, suffix = "", prefix = "", accent = "#ffd23c", text = "", scene }) => {
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();
  const p = spring({ frame, fps, config: { damping: 200, stiffness: 110 } });
  const shown = interpolate(p, [0, 1], [0, value], {
    easing: Easing.out(Easing.quad),
  });
  const fmt = Math.abs(value) >= 100 ? Math.round(shown).toLocaleString() : shown.toFixed(1);
  const pop = interpolate(frame, [0, 6, 12], [0.7, 1.06, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill style={{ backgroundColor: "transparent", justifyContent: "center", alignItems: "center" }}>
      <Backdrop scene={scene} />
      <div style={{ fontFamily: FONT, textAlign: "center", transform: `scale(${pop})` }}>
        <div
          style={{
            fontSize: height * 0.22,
            fontWeight: 900,
            color: accent,
            lineHeight: 1,
            textShadow: `0 0 60px ${hexA(accent, 0.35)}`,
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {prefix}
          {fmt}
          {suffix}
        </div>
        {text ? (
          <div
            style={{
              marginTop: height * 0.02,
              fontSize: height * 0.042,
              fontWeight: 600,
              color: "#e8ecf4",
              opacity: interpolate(frame, [4, 18], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              }),
              textTransform: "uppercase",
              letterSpacing: height * 0.003,
            }}
          >
            {text}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------ Kinetic Title
export const KineticTitle: React.FC<BaseProps & { words?: string[] }> = ({
  words,
  text = "",
  sub = "",
  accent = "#ff3d68",
  scene,
}) => {
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();
  const list = (words && words.length ? words : (text || "").split(" ")).slice(0, 12);
  return (
    <AbsoluteFill style={{ backgroundColor: "transparent", justifyContent: "center", alignItems: "center" }}>
      <Backdrop scene={scene} />
      <div
        style={{
          fontFamily: FONT,
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          maxWidth: "84%",
          gap: height * 0.02,
        }}
      >
        {list.map((w, i) => {
          const s = spring({
            frame: frame - i * 4,
            fps,
            config: { damping: 14, stiffness: 170, mass: 0.7 },
          });
          return (
            <span
              key={i}
              style={{
                display: "inline-block",
                fontSize: height * 0.095,
                fontWeight: 900,
                color: i % 3 === 1 ? accent : "#ffffff",
                opacity: s,
                transform: `translateY(${(1 - s) * 90}px) rotate(${(1 - s) * -6}deg) scale(${0.6 + s * 0.4})`,
                textShadow: "0 4px 30px rgba(0,0,0,.5)",
              }}
            >
              {w}
            </span>
          );
        })}
      </div>
      {sub ? (
        <div
          style={{
            position: "absolute",
            bottom: height * 0.16,
            fontFamily: FONT,
            fontSize: height * 0.036,
            fontWeight: 600,
            color: "#aeb8cc",
            opacity: interpolate(frame, [18, 34], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            letterSpacing: height * 0.002,
          }}
        >
          {sub.toUpperCase()}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------ Bar Chart
export const BarChart: React.FC<
  BaseProps & { data?: number[]; labels?: string[]; title?: string }
> = ({ data = [], labels = [], title = "", accent = "#00d9ff", scene }) => {
  const frame = useCurrentFrame();
  const { fps, height, width } = useVideoConfig();
  const max = Math.max(...data.map((d) => Math.abs(d)), 1);
  const cols = ["#00d9ff", "#ff3d68", "#7de87d", "#ffc93c", "#c07dff", "#ff8c3d", "#50dcdc", "#f0f0f0"];
  const bw = (width * 0.7) / Math.max(1, data.length);
  return (
    <AbsoluteFill style={{ backgroundColor: "transparent" }}>
      <Backdrop scene={scene} />
      {title ? (
        <div
          style={{
            position: "absolute",
            top: height * 0.1,
            left: width * 0.15,
            fontFamily: FONT,
            fontSize: height * 0.045,
            fontWeight: 800,
            color: "#fff",
          }}
        >
          {title}
        </div>
      ) : null}
      <div
        style={{
          position: "absolute",
          bottom: height * 0.2,
          left: width * 0.15,
          display: "flex",
          alignItems: "flex-end",
          gap: bw * 0.3,
          height: height * 0.5,
        }}
      >
        {data.map((v, i) => {
          const g = spring({
            frame: frame - i * 5 - 5,
            fps,
            config: { damping: 200, stiffness: 120 },
          });
          const h = (Math.abs(v) / max) * height * 0.5 * g;
          return (
            <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
              <div
                style={{
                  width: bw * 0.7,
                  height: h,
                  borderRadius: height * 0.012,
                  background: `linear-gradient(180deg, ${cols[i % cols.length]}, ${hexA(cols[i % cols.length], 0.55)})`,
                  boxShadow: `0 0 24px ${hexA(cols[i % cols.length], 0.3)}`,
                }}
              />
              <div
                style={{
                  marginTop: height * 0.012,
                  fontFamily: FONT,
                  fontSize: height * 0.026,
                  color: "#cfd8e6",
                  opacity: g,
                  whiteSpace: "nowrap",
                }}
              >
                {labels[i] ?? ""}
              </div>
            </div>
          );
        })}
      </div>
      <div
        style={{
          position: "absolute",
          bottom: height * 0.185,
          left: width * 0.13,
          width: width * 0.74,
          height: 3,
          backgroundColor: hexA("#ffffff", 0.35),
        }}
      />
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------ Quote Card
export const QuoteCard: React.FC<BaseProps & { author?: string }> = ({
  text = "",
  author = "",
  accent = "#5aa2ff",
  scene = { kind: "gradient", from: "#131a2e", to: "#070a12" },
}) => {
  const frame = useCurrentFrame();
  const { fps, height, width } = useVideoConfig();
  const a = interpolate(frame, [0, 16], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const slide = spring({ frame, fps, config: { damping: 200, stiffness: 100 } });
  return (
    <AbsoluteFill style={{ backgroundColor: "transparent" }}>
      <Backdrop scene={scene} />
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: `0 ${width * 0.12}px`,
          fontFamily: FONT,
          opacity: a,
          transform: `translateY(${(1 - slide) * 40}px)`,
        }}
      >
        <div style={{ fontSize: height * 0.16, color: accent, lineHeight: 0.6 }}>&ldquo;</div>
        <div
          style={{
            fontSize: height * 0.052,
            fontWeight: 700,
            color: "#f2f5fa",
            lineHeight: 1.35,
            maxWidth: "76%",
          }}
        >
          {text}
        </div>
        {author ? (
          <div style={{ marginTop: height * 0.03, fontSize: height * 0.032, color: accent, fontWeight: 600 }}>
            — {author}
          </div>
        ) : null}
        <div
          style={{
            position: "absolute",
            left: width * 0.08,
            top: "18%",
            bottom: "18%",
            width: height * 0.008,
            borderRadius: 8,
            background: `linear-gradient(180deg, ${accent}, ${hexA(accent, 0.1)})`,
          }}
        />
      </div>
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------ Subscribe Bumper
export const SubscribeBumper: React.FC<BaseProps & { handle?: string }> = ({
  handle = "@vidforge",
  accent = "#e6202d",
  scene,
}) => {
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();
  const pop = spring({ frame, fps, config: { damping: 9, stiffness: 200, mass: 0.6 } });
  const bell = spring({ frame: frame - 12, fps, config: { damping: 6, stiffness: 240 } });
  const ring = interpolate(frame, [0, 30], [1.6, 1], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.back(2)),
  });
  return (
    <AbsoluteFill style={{ backgroundColor: "transparent", justifyContent: "center", alignItems: "center" }}>
      <Backdrop scene={scene} />
      <div style={{ position: "relative", transform: `scale(${pop * ring})` }}>
        <div
          style={{
            width: height * 0.18,
            height: height * 0.18,
            borderRadius: "50%",
            background: accent,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: `0 0 80px ${hexA(accent, 0.6)}`,
          }}
        >
          <svg width={height * 0.09} height={height * 0.09} viewBox="0 0 24 24" fill="#fff">
            <path d="M8 5v14l11-7z" />
          </svg>
        </div>
        <div
          style={{
            position: "absolute",
            top: -height * 0.16,
            left: "50%",
            transform: `translateX(-50%) scale(${bell}) rotate(${Math.sin(frame / 3) * 12 * bell}deg)`,
            fontSize: height * 0.09,
          }}
        >
          🔔
        </div>
      </div>
      <div
        style={{
          marginTop: height * 0.05,
          fontFamily: FONT,
          fontSize: height * 0.05,
          fontWeight: 800,
          color: "#fff",
          opacity: interpolate(frame, [10, 22], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        SUBSCRIBE {handle}
      </div>
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------ Callout Arrow
export const CalloutArrow: React.FC<
  BaseProps & { targetX?: number; targetY?: number }
> = ({ text = "Look here", accent = "#ffd23c", targetX = 0.62, targetY = 0.4, scene }) => {
  const frame = useCurrentFrame();
  const { fps, height, width } = useVideoConfig();
  const draw = interpolate(frame, [0, 18], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const bob = Math.sin(frame / 6) * 6;
  const tx = width * targetX;
  const ty = height * targetY;
  const sx = width * 0.28;
  const sy = height * 0.68;
  return (
    <AbsoluteFill style={{ backgroundColor: "transparent" }}>
      <Backdrop scene={scene} />
      <svg width="100%" height="100%" style={{ position: "absolute", inset: 0 }}>
        <path
          d={`M ${sx} ${sy} Q ${sx + 40} ${ty}, ${tx} ${ty}`}
          stroke={accent}
          strokeWidth={height * 0.008}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={1000}
          strokeDashoffset={1000 - 1000 * draw}
        />
        <polygon
          points={`${tx},${ty} ${tx - 26},${ty - 16} ${tx - 20},${ty + 18}`}
          fill={accent}
          opacity={draw}
        />
      </svg>
      <div
        style={{
          position: "absolute",
          left: sx - width * 0.02,
          top: sy + bob * 0.3,
          fontFamily: FONT,
          fontSize: height * 0.045,
          fontWeight: 800,
          color: accent,
          opacity: draw,
          transform: `translateY(${bob}px)`,
          textShadow: "0 2px 14px rgba(0,0,0,.6)",
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------ Progress Ring
export const ProgressRing: React.FC<BaseProps & { pct?: number }> = ({
  pct = 75,
  accent = "#7de87d",
  text = "",
  scene,
}) => {
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();
  const p = spring({ frame, fps, config: { damping: 200, stiffness: 90 } }) * (pct / 100);
  const R = height * 0.14;
  const C = 2 * Math.PI * R;
  return (
    <AbsoluteFill style={{ backgroundColor: "transparent", justifyContent: "center", alignItems: "center" }}>
      <Backdrop scene={scene} />
      <svg width={R * 2.6} height={R * 2.6}>
        <circle cx={R * 1.3} cy={R * 1.3} r={R} stroke={hexA("#ffffff", 0.15)} strokeWidth={R * 0.16} fill="none" />
        <circle
          cx={R * 1.3}
          cy={R * 1.3}
          r={R}
          stroke={accent}
          strokeWidth={R * 0.16}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={C}
          strokeDashoffset={C * (1 - p)}
          transform={`rotate(-90 ${R * 1.3} ${R * 1.3})`}
        />
        <text
          x="50%"
          y="54%"
          textAnchor="middle"
          fill="#fff"
          fontFamily={FONT}
          fontWeight={900}
          fontSize={R * 0.62}
        >
          {Math.round(p * 100)}%
        </text>
      </svg>
      {text ? (
        <div style={{ fontFamily: FONT, marginTop: height * 0.02, fontSize: height * 0.036, color: "#dfe6f2" }}>
          {text}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------ Map Ping
export const MapPing: React.FC<BaseProps & { place?: string }> = ({
  place = "Location",
  accent = "#ff3d68",
  scene = { kind: "gradient", from: "#0e1626", to: "#0a0f1a" },
}) => {
  const frame = useCurrentFrame();
  const { fps, height, width } = useVideoConfig();
  const drop = spring({ frame, fps, config: { damping: 12, stiffness: 160 } });
  const ripple = (frame % 40) / 40;
  return (
    <AbsoluteFill style={{ backgroundColor: "transparent" }}>
      <Backdrop scene={scene} />
      <div
        style={{
          position: "absolute",
          left: width / 2,
          top: height / 2,
          transform: `translate(-50%, ${-60 + (1 - drop) * -300}px)`,
          textAlign: "center",
        }}
      >
        <div style={{ position: "relative", width: 80, height: 80, margin: "0 auto" }}>
          <div
            style={{
              position: "absolute",
              inset: 0,
              borderRadius: "50%",
              border: `3px solid ${accent}`,
              opacity: 1 - ripple,
              transform: `scale(${0.4 + ripple * 1.6})`,
            }}
          />
          <div
            style={{
              width: 44,
              height: 44,
              margin: 18,
              borderRadius: "50% 50% 50% 0",
              background: accent,
              transform: "rotate(-45deg)",
              boxShadow: `0 0 40px ${hexA(accent, 0.7)}`,
            }}
          />
        </div>
        <div style={{ fontFamily: FONT, fontSize: height * 0.05, fontWeight: 800, color: "#fff", marginTop: 10 }}>
          {place}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------ Compare Split
export const CompareSplit: React.FC<
  BaseProps & { leftLabel?: string; rightLabel?: string }
> = ({ leftLabel = "Before", rightLabel = "After", accent = "#00d9ff", scene }) => {
  const frame = useCurrentFrame();
  const { fps, height, width } = useVideoConfig();
  const wipe = spring({ frame: frame - 6, fps, config: { damping: 200, stiffness: 90 } });
  const x = width * (0.2 + wipe * 0.6);
  return (
    <AbsoluteFill style={{ backgroundColor: "transparent" }}>
      <Backdrop scene={scene} />
      <div
        style={{
          position: "absolute",
          left: x - 3,
          top: height * 0.16,
          bottom: height * 0.16,
          width: 6,
          background: accent,
          boxShadow: `0 0 30px ${accent}`,
        }}
      />
      <div
        style={{
          position: "absolute",
          left: width * 0.08,
          top: height * 0.2,
          fontFamily: FONT,
          fontSize: height * 0.05,
          fontWeight: 800,
          color: "#cfd8e6",
        }}
      >
        {leftLabel}
      </div>
      <div
        style={{
          position: "absolute",
          right: width * 0.08,
          top: height * 0.2,
          fontFamily: FONT,
          fontSize: height * 0.05,
          fontWeight: 800,
          color: accent,
          opacity: wipe,
        }}
      >
        {rightLabel}
      </div>
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------ Full Scene
export const ForgeScene: React.FC<BaseProps & { items?: any[]; music?: boolean }> = ({
  items = [],
  scene,
}) => {
  const { height, width } = useVideoConfig();
  let cursor = 0;
  return (
    <AbsoluteFill style={{ backgroundColor: "transparent" }}>
      <Backdrop scene={scene} />
      {items.map((it: any, i: number) => {
        const dur = Math.max(1, Math.round((it.dur_s || 3) * 30));
        const from = cursor;
        cursor += dur;
        return (
          <Sequence key={i} from={from} durationInFrames={dur} layout="none" name={it.type}>
            <AbsoluteFill>{<OverlayItem item={it} W={width} H={height} />}</AbsoluteFill>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

const OverlayItem: React.FC<{ item: any; W: number; H: number }> = ({ item }) => {
  const t = (item.type || "").toLowerCase();
  const p = item.props || {};
  switch (t) {
    case "lowerthird":
      return <LowerThird {...p} />;
    case "statcounter":
      return <StatCounter {...p} />;
    case "kinetictitle":
      return <KineticTitle {...p} />;
    case "barchart":
      return <BarChart {...p} />;
    case "quotecard":
      return <QuoteCard {...p} />;
    case "subscribe":
      return <SubscribeBumper {...p} />;
    case "callout":
      return <CalloutArrow {...p} />;
    case "progressring":
      return <ProgressRing {...p} />;
    case "mappin":
      return <MapPing {...p} />;
    case "compare":
      return <CompareSplit {...p} />;
    case "hyperframe":
      return <HyperFrame {...p} />;
    case "hyperticker":
      return <HyperTicker {...p} />;
    default:
      return <KineticTitle text={p.text || item.type || "VidForge"} />;
  }
};
