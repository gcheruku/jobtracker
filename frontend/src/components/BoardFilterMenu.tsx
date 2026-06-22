import { useRef, useState } from "react";
import { createPortal } from "react-dom";
import { SlidersHorizontal, X } from "lucide-react";
import type { BoardFilters } from "../lib/types";
import { countActiveFilters } from "../lib/filters";

const WORK_MODES = ["Remote", "Hybrid", "On-site"];

function Segmented<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { v: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex rounded-lg border border-slate-200 p-0.5">
      {options.map((o) => (
        <button
          key={o.v}
          onClick={() => onChange(o.v)}
          className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
            value === o.v ? "bg-indigo-600 text-white" : "text-slate-500 hover:text-slate-800"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="border-t border-slate-100 px-4 py-3 first:border-t-0">
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
        {label}
      </div>
      {children}
    </div>
  );
}

/** Filters button (with active count badge) + the filter popup. */
export function BoardFilterMenu({
  value,
  onChange,
}: {
  value: BoardFilters;
  onChange: (f: BoardFilters) => void;
}) {
  const [open, setOpen] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);
  const count = countActiveFilters(value);

  return (
    <>
      <button
        ref={btnRef}
        onClick={() => setOpen(true)}
        className={`flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-medium transition ${
          count > 0
            ? "border-indigo-300 bg-indigo-50 text-indigo-700"
            : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
        }`}
      >
        <SlidersHorizontal size={15} />
        <span className="hidden sm:inline">Filters</span>
        {count > 0 && (
          <span className="grid h-5 min-w-5 place-items-center rounded-full bg-indigo-600 px-1 text-[11px] font-semibold text-white">
            {count}
          </span>
        )}
      </button>

      {open && (
        <FilterPopup
          value={value}
          onChange={onChange}
          onClose={() => setOpen(false)}
          anchor={btnRef.current?.getBoundingClientRect() ?? null}
        />
      )}
    </>
  );
}

function FilterPopup({
  value,
  onChange,
  onClose,
  anchor,
}: {
  value: BoardFilters;
  onChange: (f: BoardFilters) => void;
  onClose: () => void;
  anchor: DOMRect | null;
}) {
  // Desktop anchors a dropdown under the button; mobile is a bottom sheet.
  // Rendered via a portal to escape the top bar's backdrop-filter, which would
  // otherwise trap our `position: fixed` element inside the header.
  const isDesktop =
    typeof window !== "undefined" && window.matchMedia("(min-width: 640px)").matches;
  const desktopStyle =
    isDesktop && anchor
      ? {
          top: anchor.bottom + 8,
          right: Math.max(8, window.innerWidth - anchor.right),
        }
      : undefined;
  // Local draft; committed on Apply. (Mounted only while open, so it seeds
  // fresh from `value` each time.)
  const [wmOp, setWmOp] = useState<"is" | "isNot">(value.workMode?.op ?? "is");
  const [wmVal, setWmVal] = useState(value.workMode?.value ?? "");
  const [salOp, setSalOp] = useState<"gte" | "lte">(value.salary?.op ?? "gte");
  const [salVal, setSalVal] = useState(value.salary ? String(value.salary.value) : "");
  const [matchOp, setMatchOp] = useState<"gte" | "lte">(value.match?.op ?? "gte");
  const [matchVal, setMatchVal] = useState(value.match ? String(value.match.value) : "");
  const [distOp, setDistOp] = useState<"gte" | "lte">(value.distance?.op ?? "lte");
  const [distVal, setDistVal] = useState(value.distance ? String(value.distance.value) : "");

  function apply() {
    const next: BoardFilters = {};
    if (wmVal) next.workMode = { op: wmOp, value: wmVal };
    if (salVal.trim()) next.salary = { op: salOp, value: Number(salVal) };
    if (matchVal.trim()) next.match = { op: matchOp, value: Number(matchVal) };
    if (distVal.trim()) next.distance = { op: distOp, value: Number(distVal) };
    onChange(next);
    onClose();
  }
  function reset() {
    onChange({});
    onClose();
  }

  return createPortal(
    <>
      <div
        onClick={onClose}
        className="fixed inset-0 z-40 bg-slate-900/30 sm:bg-transparent"
      />
      {/* Bottom sheet on mobile; dropdown panel anchored to the button on desktop. */}
      <div
        style={desktopStyle}
        className={
          isDesktop
            ? "fixed z-50 max-h-[80vh] w-80 overflow-y-auto rounded-xl border border-slate-200 bg-white shadow-2xl"
            : "fixed inset-x-0 bottom-0 z-50 max-h-[85vh] overflow-y-auto rounded-t-2xl border border-slate-200 bg-white shadow-2xl"
        }
      >
        <div className="flex items-center justify-between px-4 py-3">
          <h3 className="text-sm font-semibold">Filters</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700">
            <X size={18} />
          </button>
        </div>

        <Field label="Work mode">
          <div className="flex flex-wrap items-center gap-2">
            <Segmented
              options={[
                { v: "is", label: "is" },
                { v: "isNot", label: "is not" },
              ]}
              value={wmOp}
              onChange={setWmOp}
            />
            <select
              value={wmVal}
              onChange={(e) => setWmVal(e.target.value)}
              className="flex-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-sm text-slate-600 outline-none focus:border-indigo-400"
            >
              <option value="">Any</option>
              {WORK_MODES.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
        </Field>

        <Field label="Salary (yearly)">
          <div className="flex items-center gap-2">
            <Segmented
              options={[
                { v: "gte", label: "≥" },
                { v: "lte", label: "≤" },
              ]}
              value={salOp}
              onChange={setSalOp}
            />
            <div className="relative flex-1">
              <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-sm text-slate-400">
                $
              </span>
              <input
                type="number"
                inputMode="numeric"
                value={salVal}
                onChange={(e) => setSalVal(e.target.value)}
                placeholder="150000"
                className="w-full rounded-lg border border-slate-200 bg-white py-1.5 pl-6 pr-2.5 text-sm outline-none focus:border-indigo-400"
              />
            </div>
          </div>
        </Field>

        <Field label="Match score">
          <div className="flex items-center gap-2">
            <Segmented
              options={[
                { v: "gte", label: "≥" },
                { v: "lte", label: "≤" },
              ]}
              value={matchOp}
              onChange={setMatchOp}
            />
            <div className="relative flex-1">
              <input
                type="number"
                inputMode="numeric"
                min={0}
                max={100}
                value={matchVal}
                onChange={(e) => setMatchVal(e.target.value)}
                placeholder="60"
                className="w-full rounded-lg border border-slate-200 bg-white py-1.5 pl-2.5 pr-7 text-sm outline-none focus:border-indigo-400"
              />
              <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-sm text-slate-400">
                %
              </span>
            </div>
          </div>
        </Field>

        <Field label="Distance">
          <div className="flex items-center gap-2">
            <Segmented
              options={[
                { v: "lte", label: "≤" },
                { v: "gte", label: "≥" },
              ]}
              value={distOp}
              onChange={setDistOp}
            />
            <div className="relative flex-1">
              <input
                type="number"
                inputMode="numeric"
                min={0}
                value={distVal}
                onChange={(e) => setDistVal(e.target.value)}
                placeholder="30"
                className="w-full rounded-lg border border-slate-200 bg-white py-1.5 pl-2.5 pr-10 text-sm outline-none focus:border-indigo-400"
              />
              <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-sm text-slate-400">
                mi
              </span>
            </div>
          </div>
          <p className="mt-1.5 text-[11px] text-slate-400">
            Remote/unknown-location jobs are hidden while this is set.
          </p>
        </Field>

        <div className="sticky bottom-0 flex gap-2 border-t border-slate-100 bg-white px-4 py-3">
          <button
            onClick={reset}
            className="flex-1 rounded-lg border border-slate-200 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
          >
            Reset
          </button>
          <button
            onClick={apply}
            className="flex-1 rounded-lg bg-indigo-600 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
          >
            Apply
          </button>
        </div>
      </div>
    </>,
    document.body
  );
}

const OP_LABEL: Record<string, string> = { is: "is", isNot: "is not", gte: "≥", lte: "≤" };

/** Removable chips summarizing the active filters. */
export function BoardFilterChips({
  value,
  onChange,
}: {
  value: BoardFilters;
  onChange: (f: BoardFilters) => void;
}) {
  const chips: { key: keyof BoardFilters; label: string }[] = [];
  if (value.workMode)
    chips.push({ key: "workMode", label: `Work mode ${OP_LABEL[value.workMode.op]} ${value.workMode.value}` });
  if (value.salary)
    chips.push({ key: "salary", label: `Salary ${OP_LABEL[value.salary.op]} $${value.salary.value.toLocaleString()}` });
  if (value.match)
    chips.push({ key: "match", label: `Match ${OP_LABEL[value.match.op]} ${value.match.value}%` });
  if (value.distance)
    chips.push({ key: "distance", label: `Distance ${OP_LABEL[value.distance.op]} ${value.distance.value} mi` });

  if (chips.length === 0) return null;

  const remove = (key: keyof BoardFilters) => {
    const next = { ...value };
    delete next[key];
    onChange(next);
  };

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {chips.map((c) => (
        <span
          key={c.key}
          className="inline-flex items-center gap-1 rounded-full bg-indigo-50 py-1 pl-2.5 pr-1 text-xs font-medium text-indigo-700"
        >
          {c.label}
          <button
            onClick={() => remove(c.key)}
            className="grid h-4 w-4 place-items-center rounded-full hover:bg-indigo-200"
          >
            <X size={11} />
          </button>
        </span>
      ))}
      <button
        onClick={() => onChange({})}
        className="ml-1 text-xs text-slate-500 hover:text-slate-800"
      >
        Clear all
      </button>
    </div>
  );
}
