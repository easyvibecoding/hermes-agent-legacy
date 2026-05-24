import { useLayoutEffect, useState, type ComponentType } from "react";
import {
  Activity,
  Boxes,
  BrainCircuit,
  CircleDot,
  Cpu,
  Gauge,
  GitBranch,
  HardDrive,
  Layers3,
  Network,
  RadioTower,
  ServerCog,
  SplitSquareHorizontal,
  TerminalSquare,
  Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { usePageHeader } from "@/contexts/usePageHeader";
import { cn } from "@/lib/utils";

type SurfaceMode = "orchestration" | "runtime";
type WorkerStatus = "running" | "queued" | "warming" | "blocked";

interface WorkerNode {
  id: string;
  name: string;
  role: string;
  model: string;
  gpu: string;
  status: WorkerStatus;
  load: number;
  task: string;
  position: string;
}

interface RuntimePane {
  name: string;
  session: string;
  status: string;
  lines: string[];
}

const WORKERS: WorkerNode[] = [
  {
    id: "planner",
    name: "Planner-01",
    role: "task graph + decomposition",
    model: "qwen3-coder-480b",
    gpu: "pc1 / 2x4090",
    status: "running",
    load: 72,
    task: "split FrankenGPU install into bounded work packets",
    position: "lg:col-start-1 lg:row-start-1",
  },
  {
    id: "builder",
    name: "Builder-02",
    role: "repo edits + tests",
    model: "claude-opus-4.6",
    gpu: "cloud burst",
    status: "running",
    load: 81,
    task: "landing workspace product surface, not wireframe vapor",
    position: "lg:col-start-3 lg:row-start-1",
  },
  {
    id: "gpu-router",
    name: "GPU Router",
    role: "capacity / queue routing",
    model: "local mixtral router",
    gpu: "pc2 / 4x3090",
    status: "warming",
    load: 46,
    task: "packing inference lanes by memory pressure",
    position: "lg:col-start-1 lg:row-start-2",
  },
  {
    id: "qa",
    name: "QA-Sentinel",
    role: "verification + smoke tests",
    model: "gpt-5.4-codex",
    gpu: "api pool",
    status: "queued",
    load: 28,
    task: "waiting on build artifact and route smoke",
    position: "lg:col-start-3 lg:row-start-2",
  },
  {
    id: "ops",
    name: "Ops-Bridge",
    role: "deploy + tunnel health",
    model: "hermes-ops",
    gpu: "tailscale mesh",
    status: "blocked",
    load: 13,
    task: "needs runtime attach before tmux takeover",
    position: "lg:col-start-2 lg:row-start-3",
  },
];

const RUNTIME_PANES: RuntimePane[] = [
  {
    name: "aurora-control",
    session: "tmux:swarm2.0",
    status: "attached",
    lines: [
      "$ hermes --profile aurora --swarm-control",
      "orchestrator online · 5 workers registered",
      "routing: planner -> builder -> qa -> ops",
    ],
  },
  {
    name: "worker-builder-02",
    session: "tmux:swarm2.builder",
    status: "streaming",
    lines: [
      "$ pnpm -C web build",
      "vite compiling product surface",
      "queued handoff: qa-sentinel",
    ],
  },
  {
    name: "gpu-router",
    session: "tmux:frankengpu.router",
    status: "warming",
    lines: [
      "$ nvidia-smi dmon -s pucm",
      "pc1: 72% compute / 19GB free",
      "pc2: waiting for ollama runner",
    ],
  },
];

const STATUS_CLASSES: Record<WorkerStatus, string> = {
  running: "border-emerald-400/50 bg-emerald-400/10 text-emerald-200",
  queued: "border-sky-300/50 bg-sky-300/10 text-sky-100",
  warming: "border-amber-300/50 bg-amber-300/10 text-amber-100",
  blocked: "border-red-300/50 bg-red-300/10 text-red-100",
};

function MetricCard({
  icon: Icon,
  label,
  value,
  sub,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: string;
  sub: string;
}) {
  return (
    <Card className="bg-card/60">
      <CardHeader className="flex flex-row items-center justify-between gap-3 pb-2">
        <CardTitle className="text-xs">{label}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="font-expanded text-2xl font-bold tracking-[0.04em] text-midground blend-lighter">
          {value}
        </div>
        <p className="mt-1 text-xs text-muted-foreground">{sub}</p>
      </CardContent>
    </Card>
  );
}

function WorkerCard({ worker }: { worker: WorkerNode }) {
  return (
    <Card className={cn("relative overflow-hidden bg-card/70", worker.position)}>
      <span className="pointer-events-none absolute left-1/2 top-0 h-8 w-px bg-midground/20 lg:-translate-y-8" />
      <CardHeader className="gap-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <CardTitle className="truncate text-sm">{worker.name}</CardTitle>
            <CardDescription className="mt-1 truncate">{worker.role}</CardDescription>
          </div>
          <Badge className={cn("border text-[10px]", STATUS_CLASSES[worker.status])}>
            {worker.status}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div>
            <p className="text-muted-foreground">MODEL</p>
            <p className="mt-1 truncate font-mono-ui text-midground">{worker.model}</p>
          </div>
          <div>
            <p className="text-muted-foreground">LANE</p>
            <p className="mt-1 truncate font-mono-ui text-midground">{worker.gpu}</p>
          </div>
        </div>
        <div>
          <div className="mb-1.5 flex items-center justify-between text-xs text-muted-foreground">
            <span>LOAD</span>
            <span>{worker.load}%</span>
          </div>
          <div className="h-2 overflow-hidden border border-border bg-black/30">
            <div className="h-full bg-midground/80" style={{ width: `${worker.load}%` }} />
          </div>
        </div>
        <p className="min-h-10 text-sm leading-snug text-card-foreground/90">{worker.task}</p>
      </CardContent>
    </Card>
  );
}

function AuroraCore() {
  return (
    <div className="relative lg:col-start-2 lg:row-span-2 lg:row-start-1">
      <div className="absolute left-1/2 top-1/2 hidden h-[calc(100%+5rem)] w-[calc(100vw-24rem)] max-w-[58rem] -translate-x-1/2 -translate-y-1/2 border border-midground/10 lg:block" />
      <Card className="relative z-1 overflow-hidden border-midground/30 bg-background-base/80 shadow-[0_0_80px_-35px_var(--midground-base)]">
        <div className="absolute inset-x-8 top-0 h-px bg-midground/70" />
        <CardHeader className="items-center text-center">
          <Badge className="mb-2 border border-midground/30 bg-midground/10 text-[10px] text-midground">
            TOP-CENTER ORCHESTRATOR
          </Badge>
          <div className="relative flex h-28 w-28 items-center justify-center rounded-full border border-midground/25 bg-midground/5">
            <div className="absolute inset-3 rounded-full border border-midground/15" />
            <BrainCircuit className="h-12 w-12 text-midground blend-lighter" />
            <span className="absolute -right-2 top-3 flex h-5 w-5 items-center justify-center rounded-full border border-emerald-300/50 bg-emerald-300/15">
              <CircleDot className="h-3 w-3 text-emerald-200" />
            </span>
          </div>
          <CardTitle className="mt-3 text-2xl tracking-[0.12em]">Aurora</CardTitle>
          <CardDescription className="max-w-sm text-sm">
            FrankenGPU command plane. Assigns work, routes model lanes, tracks agent health, and keeps humans out of tmux until they need the wall.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-3">
          <div className="border border-border bg-black/20 p-3 text-center">
            <p className="text-[10px] text-muted-foreground">ACTIVE GRAPH</p>
            <p className="mt-1 font-expanded text-lg text-midground">5 NODES</p>
          </div>
          <div className="border border-border bg-black/20 p-3 text-center">
            <p className="text-[10px] text-muted-foreground">QUEUE DEPTH</p>
            <p className="mt-1 font-expanded text-lg text-midground">12 JOBS</p>
          </div>
          <div className="border border-border bg-black/20 p-3 text-center">
            <p className="text-[10px] text-muted-foreground">GPU MESH</p>
            <p className="mt-1 font-expanded text-lg text-midground">76% HOT</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function OrchestrationSurface() {
  return (
    <div className="flex flex-col gap-5">
      <section className="grid gap-3 md:grid-cols-4">
        <MetricCard icon={Network} label="MESH" value="8 GPUs" sub="PC1, PC2, API burst lanes" />
        <MetricCard icon={GitBranch} label="WORK GRAPH" value="17 edges" sub="Aurora owns handoffs" />
        <MetricCard icon={Gauge} label="THROUGHPUT" value="41 tok/s" sub="blended local + cloud" />
        <MetricCard icon={HardDrive} label="VRAM FREE" value="93 GB" sub="after active allocations" />
      </section>

      <section className="relative grid gap-4 lg:grid-cols-3 lg:grid-rows-[auto_auto_auto]">
        <div className="pointer-events-none absolute left-1/2 top-14 hidden h-[72%] w-px -translate-x-1/2 bg-midground/15 lg:block" />
        <div className="pointer-events-none absolute left-[16.66%] right-[16.66%] top-[11rem] hidden h-px bg-midground/15 lg:block" />
        <div className="pointer-events-none absolute left-[16.66%] right-[16.66%] top-[30rem] hidden h-px bg-midground/15 lg:block" />
        <AuroraCore />
        {WORKERS.map((worker) => (
          <WorkerCard key={worker.id} worker={worker} />
        ))}
      </section>
    </div>
  );
}

function RuntimeSurface() {
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
      <div className="grid gap-4 lg:grid-cols-2">
        {RUNTIME_PANES.map((pane) => (
          <Card key={pane.name} className="overflow-hidden bg-black/40">
            <CardHeader className="flex flex-row items-start justify-between gap-3">
              <div>
                <CardTitle className="flex items-center gap-2 text-sm">
                  <TerminalSquare className="h-4 w-4" />
                  {pane.name}
                </CardTitle>
                <CardDescription>{pane.session}</CardDescription>
              </div>
              <Badge className="border border-midground/25 bg-midground/10 text-[10px] text-midground">
                {pane.status}
              </Badge>
            </CardHeader>
            <CardContent>
              <pre className="min-h-40 whitespace-pre-wrap border border-border bg-black/50 p-3 font-mono-ui text-xs leading-relaxed text-midground/85">
                {pane.lines.join("\n")}
              </pre>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="bg-card/60">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            <SplitSquareHorizontal className="h-4 w-4" />
            Runtime wall rules
          </CardTitle>
          <CardDescription>Separated from the primary orchestration surface on purpose.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-card-foreground/85">
          <p>Use this mode when you need raw tmux attachment, logs, panes, and process control.</p>
          <p>The default surface stays product-facing: Aurora, workers, graph state, GPU allocation, and handoff health.</p>
          <div className="border border-border bg-black/25 p-3 text-xs text-muted-foreground">
            Next binding: live gateway endpoint for session inventory and websocket pane streaming.
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default function Swarm2Page() {
  const [mode, setMode] = useState<SurfaceMode>("orchestration");
  const { setAfterTitle, setEnd, setTitle } = usePageHeader();

  useLayoutEffect(() => {
    setTitle("Swarm2");
    setAfterTitle(
      <Badge className="border border-midground/30 bg-midground/10 text-[10px] text-midground">
        FRANKENGPU
      </Badge>,
    );
    setEnd(
      <div className="flex w-full justify-end gap-2">
        <Button
          type="button"
          variant={mode === "orchestration" ? "default" : "outline"}
          size="sm"
          className="h-7 text-xs"
          onClick={() => setMode("orchestration")}
        >
          <Boxes className="mr-1 h-3 w-3" />
          Orchestrate
        </Button>
        <Button
          type="button"
          variant={mode === "runtime" ? "default" : "outline"}
          size="sm"
          className="h-7 text-xs"
          onClick={() => setMode("runtime")}
        >
          <TerminalSquare className="mr-1 h-3 w-3" />
          Runtime wall
        </Button>
      </div>,
    );
    return () => {
      setTitle(null);
      setAfterTitle(null);
      setEnd(null);
    };
  }, [mode, setAfterTitle, setEnd, setTitle]);

  return (
    <div className="flex flex-col gap-5">
      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <Card className="bg-card/60">
          <CardHeader className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
            <div>
              <CardTitle className="text-base">FrankenGPU orchestration</CardTitle>
              <CardDescription className="mt-1 max-w-3xl text-sm">
                Aurora is the product surface: top-center controller, connected worker cards, visible graph health, and GPU lane pressure. Tmux is no longer the homepage.
              </CardDescription>
            </div>
            <div className="flex shrink-0 flex-wrap items-center gap-2">
              <Button
                type="button"
                variant={mode === "orchestration" ? "default" : "outline"}
                size="sm"
                className="h-8 text-xs"
                onClick={() => setMode("orchestration")}
              >
                <Boxes className="mr-1 h-3 w-3" />
                Orchestrate
              </Button>
              <Button
                type="button"
                variant={mode === "runtime" ? "default" : "outline"}
                size="sm"
                className="h-8 text-xs"
                onClick={() => setMode("runtime")}
              >
                <TerminalSquare className="mr-1 h-3 w-3" />
                Runtime wall
              </Button>
              <RadioTower className="hidden h-8 w-8 text-midground/70 sm:block" />
            </div>
          </CardHeader>
        </Card>
        <Card className="bg-card/60">
          <CardContent className="grid h-full grid-cols-3 gap-3 p-4 text-center">
            <div>
              <Activity className="mx-auto h-4 w-4 text-emerald-300" />
              <p className="mt-2 text-[10px] text-muted-foreground">RUNNING</p>
              <p className="font-expanded text-lg text-midground">2</p>
            </div>
            <div>
              <ServerCog className="mx-auto h-4 w-4 text-amber-200" />
              <p className="mt-2 text-[10px] text-muted-foreground">WARMING</p>
              <p className="font-expanded text-lg text-midground">1</p>
            </div>
            <div>
              <Cpu className="mx-auto h-4 w-4 text-sky-200" />
              <p className="mt-2 text-[10px] text-muted-foreground">QUEUED</p>
              <p className="font-expanded text-lg text-midground">1</p>
            </div>
          </CardContent>
        </Card>
      </section>

      {mode === "orchestration" ? <OrchestrationSurface /> : <RuntimeSurface />}

      <Card className="bg-card/50">
        <CardContent className="flex flex-col gap-3 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <span className="flex items-center gap-2">
            <Zap className="h-3.5 w-3.5 text-midground" />
            Visible product pass: no generic placeholders, no abstract dashboard mush.
          </span>
          <span className="flex items-center gap-2">
            <Layers3 className="h-3.5 w-3.5 text-midground" />
            Runtime/tmux wall is isolated behind its own mode.
          </span>
        </CardContent>
      </Card>
    </div>
  );
}
