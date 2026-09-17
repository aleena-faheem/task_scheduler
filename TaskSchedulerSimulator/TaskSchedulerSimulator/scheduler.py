#!/usr/bin/env python3
"""
Task Scheduler Simulator
Supports:
- Periodic tasks loaded from CSV
- Rate Monotonic (RM) and Earliest Deadline First (EDF)
- Preemptive and non-preemptive scheduling
- Deadline miss counting
- CPU utilization and schedulability bounds
- Text Gantt timeline
- Optional context-switch overhead
- Critical-utilization search by execution-time scaling
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class Task:
    name: str
    period: int
    execution: int
    deadline: int
    offset: int = 0


@dataclass
class Job:
    task: Task
    release_time: int
    absolute_deadline: int
    remaining: int
    start_time: Optional[int] = None
    finish_time: Optional[int] = None
    missed: bool = False
    instance: int = 0

    @property
    def label(self) -> str:
        return f"{self.task.name}[{self.instance}]"


@dataclass
class ExecutionEvent:
    start: int
    end: int
    label: str


@dataclass
class SimulationResult:
    policy: str
    mode: str
    duration: int
    timeline: List[str]
    events: List[ExecutionEvent]
    jobs: List[Job]
    deadline_misses: int
    context_switches: int
    context_time: int
    idle_time: int

    @property
    def schedulable(self) -> bool:
        return self.deadline_misses == 0


def gcd(a: int, b: int) -> int:
    return math.gcd(a, b)


def lcm(a: int, b: int) -> int:
    return abs(a * b) // gcd(a, b)


def hyperperiod(tasks: List[Task]) -> int:
    return math.lcm(*(t.period for t in tasks))


def utilization(tasks: List[Task]) -> float:
    return sum(t.execution / t.period for t in tasks)


def rm_bound(n: int) -> float:
    if n <= 0:
        return 0.0
    return n * (2 ** (1 / n) - 1)


def edf_bound(tasks: List[Task]) -> Tuple[float, bool]:
    # U <= 1 is necessary and sufficient for implicit-deadline tasks.
    implicit = all(t.deadline == t.period for t in tasks)
    return 1.0, implicit


def load_tasks(path: str) -> List[Task]:
    tasks: List[Task] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"name", "period", "execution"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError("CSV must contain: name, period, execution; deadline and offset are optional.")

        seen = set()
        for line_no, row in enumerate(reader, start=2):
            try:
                name = row["name"].strip()
                period = int(float(row["period"]))
                execution = int(float(row["execution"]))
                deadline_raw = (row.get("deadline") or "").strip()
                offset_raw = (row.get("offset") or "").strip()
                deadline = int(float(deadline_raw)) if deadline_raw else period
                offset = int(float(offset_raw)) if offset_raw else 0
            except (ValueError, TypeError):
                raise ValueError(f"Invalid numeric value on CSV line {line_no}.")

            if not name:
                raise ValueError(f"Empty task name on CSV line {line_no}.")
            if name in seen:
                raise ValueError(f"Duplicate task name: {name}.")
            if period <= 0 or execution <= 0 or deadline <= 0 or offset < 0:
                raise ValueError(f"Invalid values for {name}: all times must be positive; offset cannot be negative.")
            if execution > period:
                raise ValueError(f"Task {name}: execution time cannot exceed its period.")

            seen.add(name)
            tasks.append(Task(name, period, execution, deadline, offset))

    if not tasks:
        raise ValueError("CSV contains no tasks.")
    return tasks


def release_jobs(tasks: List[Task], time: int, jobs: List[Job], counters: dict) -> None:
    for task in tasks:
        if time < task.offset:
            continue
        if (time - task.offset) % task.period == 0:
            counters[task.name] = counters.get(task.name, 0) + 1
            inst = counters[task.name]
            jobs.append(
                Job(
                    task=task,
                    release_time=time,
                    absolute_deadline=time + task.deadline,
                    remaining=task.execution,
                    instance=inst,
                )
            )


def priority_key(job: Job, policy: str):
    if policy == "RM":
        return (job.task.period, job.task.name, job.release_time, job.instance)
    if policy == "EDF":
        return (job.absolute_deadline, job.task.name, job.release_time, job.instance)
    raise ValueError("Unknown policy")


def choose_job(ready: List[Job], policy: str) -> Optional[Job]:
    if not ready:
        return None
    return min(ready, key=lambda j: priority_key(j, policy))


def add_event(events: List[ExecutionEvent], start: int, end: int, label: str) -> None:
    if end <= start:
        return
    if events and events[-1].end == start and events[-1].label == label:
        events[-1].end = end
    else:
        events.append(ExecutionEvent(start, end, label))


def simulate(
    tasks: List[Task],
    policy: str = "RM",
    mode: str = "preemptive",
    duration: Optional[int] = None,
    cs_overhead: int = 0,
) -> SimulationResult:
    if cs_overhead < 0:
        raise ValueError("Context-switch overhead cannot be negative.")
    if policy not in ("RM", "EDF"):
        raise ValueError("Policy must be RM or EDF.")
    if mode not in ("preemptive", "nonpreemptive"):
        raise ValueError("Mode must be preemptive or nonpreemptive.")

    hp = hyperperiod(tasks)
    duration = duration if duration is not None else hp + max(t.deadline for t in tasks)

    ready: List[Job] = []
    all_jobs: List[Job] = []
    counters = {}
    events: List[ExecutionEvent] = []
    timeline: List[str] = []

    cpu_job: Optional[Job] = None
    cpu_task: Optional[str] = None
    pending_job: Optional[Job] = None
    cs_remaining = 0

    misses = 0
    switches = 0
    context_time = 0
    idle_time = 0

    for time in range(duration):
        release_jobs(tasks, time, all_jobs, counters)
        ready.extend(
            j for j in all_jobs
            if j.release_time == time and j.remaining > 0 and j not in ready and j is not cpu_job
        )

        # Mark every unfinished overdue job exactly once.
        for job in all_jobs:
            if job.remaining > 0 and not job.missed and time >= job.absolute_deadline:
                job.missed = True
                misses += 1

        # Continue an existing context switch.
        if cs_remaining > 0:
            add_event(events, time, time + 1, "CS")
            timeline.append("CS")
            cs_remaining -= 1
            context_time += 1
            if cs_remaining == 0 and pending_job is not None:
                cpu_job = pending_job
                pending_job = None
                cpu_task = cpu_job.task.name
                if cpu_job.start_time is None:
                    cpu_job.start_time = time + 1
            continue

        # Remove completed jobs from ready.
        ready = [j for j in ready if j.remaining > 0]

        candidate = None
        if mode == "nonpreemptive" and cpu_job is not None and cpu_job.remaining > 0:
            candidate = cpu_job
        else:
            candidate = choose_job(ready, policy)

        if candidate is None:
            idle_time += 1
            add_event(events, time, time + 1, "IDLE")
            timeline.append("IDLE")
            cpu_job = None
            # Same-task continuation after idle is not a switch.
            if cpu_task is not None:
                cpu_task = None
            continue

        # If candidate changes task, charge context-switch overhead.
        if cpu_job is not None and cpu_job.remaining > 0 and candidate.task.name != cpu_job.task.name:
            if cs_overhead > 0:
                pending_job = candidate
                switches += 1
                cs_remaining = cs_overhead
                add_event(events, time, time + 1, "CS")
                timeline.append("CS")
                context_time += 1
                cpu_job = None
                cpu_task = None
                cs_remaining -= 1
                continue
            switches += 1

        if cpu_job is None and cpu_task is not None and candidate.task.name != cpu_task:
            if cs_overhead > 0:
                pending_job = candidate
                switches += 1
                cs_remaining = cs_overhead
                add_event(events, time, time + 1, "CS")
                timeline.append("CS")
                context_time += 1
                cpu_task = None
                cs_remaining -= 1
                continue

        cpu_job = candidate
        cpu_task = candidate.task.name
        if candidate.start_time is None:
            candidate.start_time = time

        candidate.remaining -= 1
        add_event(events, time, time + 1, candidate.label)
        timeline.append(candidate.label)

        if candidate.remaining == 0:
            candidate.finish_time = time + 1
            ready = [j for j in ready if j is not candidate]
            # Keep task context loaded until another task or idle is selected.
            if mode == "nonpreemptive":
                cpu_job = None
        elif mode == "preemptive":
            # Re-evaluate next tick.
            pass

    return SimulationResult(
        policy=policy,
        mode=mode,
        duration=duration,
        timeline=timeline,
        events=events,
        jobs=all_jobs,
        deadline_misses=misses,
        context_switches=switches,
        context_time=context_time,
        idle_time=idle_time,
    )


def render_gantt(result: SimulationResult, dense_limit: int = 180) -> str:
    lines = ["GANTT CHART", "-" * 72]
    lines.append("  ".join(f"[{e.start},{e.end}) {e.label}" for e in result.events))
    if result.duration <= dense_limit:
        lines.append("")
        lines.append("TICK TIMELINE")
        lines.append("-" * 72)
        lines.append(" ".join(result.timeline))
    else:
        lines.append("")
        lines.append(f"(Dense timeline suppressed because duration={result.duration} > {dense_limit} ticks.)")
    return "\n".join(lines)


def report(tasks: List[Task], result: SimulationResult, cs_overhead: int) -> str:
    u = utilization(tasks)
    hp = hyperperiod(tasks)
    rm_b = rm_bound(len(tasks))
    edf_b, implicit = edf_bound(tasks)

    lines = [
        "=" * 72,
        "TASK SCHEDULER SIMULATOR",
        "=" * 72,
        f"Policy              : {result.policy}",
        f"Kernel mode         : {result.mode}",
        f"Simulation duration : {result.duration}",
        f"Hyperperiod         : {hp}",
        "",
        "TASK SET",
        "-" * 72,
        f"{'Task':<10}{'Period':>10}{'Execution':>12}{'Deadline':>12}{'Offset':>10}",
    ]
    for t in tasks:
        lines.append(f"{t.name:<10}{t.period:>10}{t.execution:>12}{t.deadline:>12}{t.offset:>10}")

    lines += [
        "",
        "UTILIZATION",
        "-" * 72,
        f"CPU utilization     : {u * 100:.2f}%",
        f"RM bound            : {rm_b * 100:.2f}%",
        f"EDF bound           : {edf_b * 100:.2f}%",
    ]

    if result.policy == "RM":
        lines.append(f"RM utilization test : {'PASS' if u <= rm_b else 'ABOVE SUFFICIENT BOUND'}")
    else:
        if implicit:
            lines.append("EDF utilization test: " + ("PASS" if u <= 1 else "FAIL"))
        else:
            lines.append("EDF note            : D != T for at least one task; U<=1 is only a necessary test.")

    lines += [
        "",
        "DEADLINES",
        "-" * 72,
    ]

    miss_by_task = {}
    for j in result.jobs:
        miss_by_task[j.task.name] = miss_by_task.get(j.task.name, 0) + int(j.missed)
    for t in tasks:
        lines.append(f"{t.name:<10}: {miss_by_task.get(t.name, 0)} miss(es)")

    lines += [
        f"Total deadline misses: {result.deadline_misses}",
        "",
        "CPU STATISTICS",
        "-" * 72,
        f"Idle ticks          : {result.idle_time}",
        f"Context switches    : {result.context_switches}",
        f"Context overhead    : {cs_overhead} tick(s) per switch",
        f"Context CPU time    : {result.context_time} tick(s)",
        "",
        render_gantt(result),
        "",
        f"FINAL RESULT        : {'SCHEDULABLE' if result.schedulable else 'NOT SCHEDULABLE'}",
        "=" * 72,
    ]
    return "\n".join(lines)


def compare(tasks: List[Task], mode: str, cs: int, duration: Optional[int]) -> str:
    results = [simulate(tasks, p, mode, duration, cs) for p in ("RM", "EDF")]
    u = utilization(tasks)
    lines = [
        "RM vs EDF COMPARISON",
        "-" * 72,
        f"{'Metric':<24}{'RM':>18}{'EDF':>18}",
        "-" * 72,
        f"{'Utilization':<24}{u*100:>17.2f}%{u*100:>17.2f}%",
        f"{'Deadline misses':<24}{results[0].deadline_misses:>18}{results[1].deadline_misses:>18}",
        f"{'Context switches':<24}{results[0].context_switches:>18}{results[1].context_switches:>18}",
        f"{'Idle ticks':<24}{results[0].idle_time:>18}{results[1].idle_time:>18}",
        f"{'Result':<24}{('PASS' if results[0].schedulable else 'FAIL'):>18}{('PASS' if results[1].schedulable else 'FAIL'):>18}",
        "-" * 72,
    ]
    return "\n".join(lines)


def scale_tasks(tasks: List[Task], factor: float, resolution: int = 20) -> List[Task]:
    scaled = []
    for t in tasks:
        scaled.append(
            Task(
                t.name,
                t.period * resolution,
                max(1, round(t.execution * factor * resolution)),
                t.deadline * resolution,
                t.offset * resolution,
            )
        )
    return scaled


def find_critical_utilization(
    tasks: List[Task],
    policy: str,
    mode: str,
    cs: int = 0,
    scale_max: float = 3.0,
    resolution: int = 20,
) -> str:
    def sched(factor: float) -> bool:
        scaled = scale_tasks(tasks, factor, resolution)
        r = simulate(scaled, policy, mode, cs_overhead=cs * resolution)
        return r.schedulable

    if not sched(1.0):
        return "Task set is already unschedulable at the original execution times (factor=1.0)."

    if sched(scale_max):
        return f"Task set remains schedulable through factor={scale_max:.2f}; increase --scale-max to search farther."

    lo, hi = 1.0, scale_max
    for _ in range(25):
        mid = (lo + hi) / 2
        if sched(mid):
            lo = mid
        else:
            hi = mid

    threshold_factor = lo
    threshold_u = utilization(tasks) * threshold_factor
    return (
        "CRITICAL UTILIZATION SEARCH\n"
        + "-" * 72 + "\n"
        f"Policy                  : {policy}\n"
        f"Kernel mode             : {mode}\n"
        f"Context-switch overhead : {cs} tick(s)\n"
        f"Highest observed safe factor ≈ {threshold_factor:.5f}\n"
        f"Highest observed safe U     ≈ {threshold_u*100:.2f}%\n"
        f"First failing factor is just above {threshold_factor:.5f}\n"
    )


def main():
    parser = argparse.ArgumentParser(description="Periodic real-time task scheduler simulator.")
    parser.add_argument("file", nargs="?", default="input/tasks_moderate.csv", help="CSV task file")
    parser.add_argument("--policy", choices=["RM", "EDF"], default="RM")
    parser.add_argument("--mode", choices=["preemptive", "nonpreemptive"], default="preemptive")
    parser.add_argument("--cs", type=int, default=0, help="Context-switch overhead in ticks")
    parser.add_argument("--duration", type=int, default=None, help="Simulation duration in ticks")
    parser.add_argument("--compare", action="store_true", help="Compare RM and EDF")
    parser.add_argument("--find-critical-utilization", action="store_true")
    parser.add_argument("--scale-max", type=float, default=3.0)
    args = parser.parse_args()

    tasks = load_tasks(args.file)

    if args.compare:
        print(compare(tasks, args.mode, args.cs, args.duration))
        return

    if args.find_critical_utilization:
        print(find_critical_utilization(tasks, args.policy, args.mode, args.cs, args.scale_max))
        return

    result = simulate(tasks, args.policy, args.mode, args.duration, args.cs)
    output = report(tasks, result, args.cs)
    print(output)

    Path("output").mkdir(exist_ok=True)
    with open("output/results.txt", "w", encoding="utf-8") as f:
        f.write(output)


if __name__ == "__main__":
    main()
