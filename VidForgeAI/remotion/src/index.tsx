// VidForge AI — Remotion root: registers all MG compositions.
// Each composition reads JSON props (via --props / inputProps) so the
// Python engine can drive them data-driven from timelines & MCP tools.
import React from "react";
import { Composition } from "remotion";
import {
  LowerThird,
  StatCounter,
  KineticTitle,
  BarChart,
  QuoteCard,
  SubscribeBumper,
  CalloutArrow,
  ProgressRing,
  MapPing,
  CompareSplit,
  ForgeScene,
} from "./kit";
import { HyperFrame, HyperTicker } from "./hyperframe";

const fps = 30;

export const VidForgeRoot: React.FC = () => (
  <>
    <Composition id="LowerThird" component={LowerThird} durationInFrames={90} fps={fps} width={1920} height={1080} />
    <Composition id="StatCounter" component={StatCounter} durationInFrames={90} fps={fps} width={1920} height={1080} />
    <Composition id="KineticTitle" component={KineticTitle} durationInFrames={120} fps={fps} width={1920} height={1080} />
    <Composition id="BarChart" component={BarChart} durationInFrames={120} fps={fps} width={1920} height={1080} />
    <Composition id="QuoteCard" component={QuoteCard} durationInFrames={150} fps={fps} width={1920} height={1080} />
    <Composition id="SubscribeBumper" component={SubscribeBumper} durationInFrames={90} fps={fps} width={1920} height={1080} />
    <Composition id="CalloutArrow" component={CalloutArrow} durationInFrames={90} fps={fps} width={1920} height={1080} />
    <Composition id="ProgressRing" component={ProgressRing} durationInFrames={100} fps={fps} width={1920} height={1080} />
    <Composition id="MapPing" component={MapPing} durationInFrames={100} fps={fps} width={1920} height={1080} />
    <Composition id="CompareSplit" component={CompareSplit} durationInFrames={100} fps={fps} width={1920} height={1080} />
    <Composition id="HyperFrame" component={HyperFrame} durationInFrames={180} fps={fps} width={1920} height={1080} defaultProps={{layout:"statwall",title:"Your Title",items:[{type:"stat",label:"Views",value:1240,suffix:"M"}]}} calculateMetadata={({props}) => {const p:any = props; return {...p, durationInFrames: Math.max(1, Number(p.durationInFrames) || 180)};}} />
    <Composition id="HyperTicker" component={HyperTicker} durationInFrames={150} fps={fps} width={1920} height={1080} defaultProps={{lines:["Fact one","Fact two"]}} calculateMetadata={({props}) => {const p:any = props; return {...p, durationInFrames: Math.max(1, Number(p.durationInFrames) || 150)};}} />
    <Composition id="ForgeScene" component={ForgeScene} durationInFrames={600} fps={fps} width={1920} height={1080} />
  </>
);

registerRootSafe(VidForgeRoot);

function registerRootSafe(C: React.FC) {
  // lazy import to keep this file valid even if registerRoot signature changes
  // eslint-disable-next-line
  const r = require("remotion");
  if (r && r.registerRoot) r.registerRoot(C);
}

export default VidForgeRoot;
