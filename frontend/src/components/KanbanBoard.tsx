import { useMemo, useState } from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useDroppable,
  useDraggable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { EyeOff, MapPin } from "lucide-react";
import { PIPELINE, type Job, type PipelineStatus } from "../lib/types";
import { STATUS_STYLES, initials } from "../lib/ui";

function MatchBadge({ job }: { job: Job }) {
  const pct = job.llm_match_pct ?? job.match_pct;
  if (pct == null) return null;
  const color =
    pct >= 75 ? "bg-emerald-100 text-emerald-700" : pct >= 40 ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-500";
  return <span className={`rounded-md px-1.5 py-0.5 text-[11px] font-semibold ${color}`}>{Math.round(pct)}%</span>;
}

function JobCard({
  job,
  onOpen,
  onIgnore,
  dragging,
}: {
  job: Job;
  onOpen: (j: Job) => void;
  onIgnore: (j: Job) => void;
  dragging?: boolean;
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: job.job_key,
    data: { job },
  });
  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      onClick={() => onOpen(job)}
      className={`group cursor-pointer rounded-lg border border-slate-200 bg-white p-3 shadow-sm transition hover:shadow-md ${
        isDragging && !dragging ? "opacity-30" : ""
      }`}
    >
      <div className="flex items-start gap-2">
        <div className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-slate-100 text-xs font-bold text-slate-600">
          {initials(job.company)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold leading-tight">
            {job.title || "Untitled role"}
          </div>
          <div className="truncate text-xs text-slate-500">
            {job.company || "Unknown company"}
          </div>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onIgnore(job);
          }}
          title="Skip this job"
          className="opacity-0 transition group-hover:opacity-100"
        >
          <EyeOff size={15} className="text-slate-400 hover:text-rose-500" />
        </button>
      </div>
      <div className="mt-2 flex items-center justify-between">
        <span className="flex items-center gap-1 truncate text-[11px] text-slate-400">
          {job.location && <MapPin size={12} />}
          {job.work_mode || job.location || ""}
        </span>
        <MatchBadge job={job} />
      </div>
      {job.salary && (
        <div className="mt-1 truncate text-[11px] font-medium text-emerald-600">
          {job.salary}
        </div>
      )}
    </div>
  );
}

function Column({
  status,
  jobs,
  onOpen,
  onIgnore,
}: {
  status: PipelineStatus;
  jobs: Job[];
  onOpen: (j: Job) => void;
  onIgnore: (j: Job) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: status });
  const style = STATUS_STYLES[status];
  return (
    <div className="flex w-72 shrink-0 flex-col">
      <div className="mb-2 flex items-center justify-between px-1">
        <div className="flex items-center gap-2">
          <span className={`h-2.5 w-2.5 rounded-full ${style.dot}`} />
          <span className="text-sm font-semibold">{status}</span>
          <span className="text-xs text-slate-400">{jobs.length}</span>
        </div>
      </div>
      <div
        ref={setNodeRef}
        className={`thin-scroll flex max-h-[calc(100vh-19rem)] flex-1 flex-col gap-2 overflow-y-auto rounded-xl border-2 border-dashed p-2 transition ${
          isOver ? "border-indigo-300 bg-indigo-50/50" : "border-slate-200 bg-slate-100/40"
        }`}
      >
        {jobs.length === 0 && (
          <div className="grid h-24 place-items-center text-xs text-slate-400">
            Drop jobs here
          </div>
        )}
        {jobs.map((job) => (
          <JobCard key={job.job_key} job={job} onOpen={onOpen} onIgnore={onIgnore} />
        ))}
      </div>
    </div>
  );
}

export function KanbanBoard({
  jobs,
  onOpen,
  onIgnore,
  onMove,
}: {
  jobs: Job[];
  onOpen: (j: Job) => void;
  onIgnore: (j: Job) => void;
  onMove: (jobKey: string, status: PipelineStatus) => void;
}) {
  const [active, setActive] = useState<Job | null>(null);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } })
  );

  const byStatus = useMemo(() => {
    const map = Object.fromEntries(PIPELINE.map((s) => [s, [] as Job[]])) as Record<
      PipelineStatus,
      Job[]
    >;
    for (const j of jobs) map[j.status]?.push(j);
    return map;
  }, [jobs]);

  function handleStart(e: DragStartEvent) {
    setActive((e.active.data.current as { job: Job })?.job ?? null);
  }
  function handleEnd(e: DragEndEvent) {
    setActive(null);
    const over = e.over?.id as PipelineStatus | undefined;
    const job = (e.active.data.current as { job: Job })?.job;
    if (over && job && job.status !== over) onMove(job.job_key, over);
  }

  return (
    <DndContext sensors={sensors} onDragStart={handleStart} onDragEnd={handleEnd}>
      <div className="flex gap-4 overflow-x-auto pb-2">
        {PIPELINE.map((status) => (
          <Column
            key={status}
            status={status}
            jobs={byStatus[status]}
            onOpen={onOpen}
            onIgnore={onIgnore}
          />
        ))}
      </div>
      <DragOverlay>
        {active && (
          <div className="w-72 rotate-2">
            <JobCard job={active} onOpen={() => {}} onIgnore={() => {}} dragging />
          </div>
        )}
      </DragOverlay>
    </DndContext>
  );
}
