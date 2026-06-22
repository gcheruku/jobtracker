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
import { ChevronDown, ExternalLink, EyeOff, MapPin } from "lucide-react";
import { BOARD_STATUSES, type Job, type PipelineStatus } from "../lib/types";
import { STATUS_STYLES, initials } from "../lib/ui";
import { MatchBadge } from "./MatchBadge";
import { SourceTag } from "./SourceTag";

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
        <div className="flex shrink-0 items-center gap-1.5">
          {job.url && (
            <a
              href={job.url}
              target="_blank"
              rel="noreferrer"
              onClick={(e) => e.stopPropagation()}
              onPointerDown={(e) => e.stopPropagation()}
              title="Open job posting"
              className="opacity-100 transition md:opacity-0 md:group-hover:opacity-100"
            >
              <ExternalLink size={15} className="text-slate-400 hover:text-indigo-600" />
            </a>
          )}
          <button
            onClick={(e) => {
              e.stopPropagation();
              onIgnore(job);
            }}
            onPointerDown={(e) => e.stopPropagation()}
            title="Skip this job"
            className="opacity-100 transition md:opacity-0 md:group-hover:opacity-100"
          >
            <EyeOff size={15} className="text-slate-400 hover:text-rose-500" />
          </button>
        </div>
      </div>
      <div className="mt-2 flex items-center justify-between gap-1">
        <span className="flex items-center gap-1 truncate text-[11px] text-slate-400">
          {job.location && <MapPin size={12} />}
          {job.work_mode || job.location || ""}
        </span>
        <span className="flex shrink-0 items-center gap-1.5">
          <SourceTag source={job.source} />
          <MatchBadge job={job} />
        </span>
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
  widthClass = "w-72 shrink-0",
  hideHeader = false,
}: {
  status: PipelineStatus;
  jobs: Job[];
  onOpen: (j: Job) => void;
  onIgnore: (j: Job) => void;
  widthClass?: string;
  hideHeader?: boolean;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: status });
  const style = STATUS_STYLES[status];
  return (
    <div className={`flex flex-col ${widthClass}`}>
      {!hideHeader && (
        <div className="mb-2 flex items-center justify-between px-1">
          <div className="flex items-center gap-2">
            <span className={`h-2.5 w-2.5 rounded-full ${style.dot}`} />
            <span className="text-sm font-semibold">{status}</span>
            <span className="text-xs text-slate-400">{jobs.length}</span>
          </div>
        </div>
      )}
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
  // Mobile shows one column at a time; default to "Saved".
  const [mobileStatus, setMobileStatus] = useState<PipelineStatus>("Saved");
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } })
  );

  const byStatus = useMemo(() => {
    const map = Object.fromEntries(
      BOARD_STATUSES.map((s) => [s, [] as Job[]])
    ) as Record<PipelineStatus, Job[]>;
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

  const dotStyle = STATUS_STYLES[mobileStatus];

  return (
    <DndContext sensors={sensors} onDragStart={handleStart} onDragEnd={handleEnd}>
      {/* Mobile: one column at a time, chosen via dropdown */}
      <div className="md:hidden">
        <div className="relative mb-3">
          <span
            className={`pointer-events-none absolute left-3 top-1/2 h-2.5 w-2.5 -translate-y-1/2 rounded-full ${dotStyle.dot}`}
          />
          <select
            value={mobileStatus}
            onChange={(e) => setMobileStatus(e.target.value as PipelineStatus)}
            className="w-full cursor-pointer appearance-none rounded-lg border border-slate-200 bg-white py-2.5 pl-7 pr-8 text-sm font-semibold text-slate-700 outline-none focus:border-indigo-400"
          >
            {BOARD_STATUSES.map((s) => (
              <option key={s} value={s}>
                {s} ({byStatus[s].length})
              </option>
            ))}
          </select>
          <ChevronDown
            size={16}
            className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400"
          />
        </div>
        <Column
          status={mobileStatus}
          jobs={byStatus[mobileStatus]}
          onOpen={onOpen}
          onIgnore={onIgnore}
          widthClass="w-full"
          hideHeader
        />
      </div>

      {/* Desktop: all columns side by side */}
      <div className="hidden gap-4 overflow-x-auto pb-2 md:flex">
        {BOARD_STATUSES.map((status) => (
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
