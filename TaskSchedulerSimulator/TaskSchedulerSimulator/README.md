# Task Scheduler Simulator

A Python 3, standard-library-only simulator for periodic real-time tasks.

## Features

- CSV task input: period, execution time, deadline, offset
- Rate Monotonic (RM)
- Earliest Deadline First (EDF)
- Preemptive and non-preemptive modes
- Deadline miss counting
- CPU utilization
- RM Liu & Layland bound
- EDF utilization test
- Hyperperiod calculation
- Gantt-style text timeline
- Context-switch overhead
- Critical-utilization search
- RM vs EDF comparison

## Requirements

Python 3.9+ recommended. No external packages are required.

## Project layout

```text
task_scheduler_sim/
├── scheduler.py
├── input/
│   ├── tasks_moderate.csv
│   ├── tasks_overloaded.csv
│   └── tasks_harmonic.csv
├── output/
│   └── results.txt
└── README.md
```

## CSV format

```csv
name,period,execution,deadline,offset
T1,10,3,10,0
T2,15,4,15,0
```

`deadline` defaults to `period` and `offset` defaults to `0` if omitted.

## Run

From the project folder:

```bash
python scheduler.py input/tasks_moderate.csv
```

RM preemptive is the default.

### EDF

```bash
python scheduler.py input/tasks_moderate.csv --policy EDF
```

### Non-preemptive RM

```bash
python scheduler.py input/tasks_moderate.csv --mode nonpreemptive
```

### Non-preemptive EDF

```bash
python scheduler.py input/tasks_moderate.csv --policy EDF --mode nonpreemptive
```

### Context-switch overhead

```bash
python scheduler.py input/tasks_moderate.csv --cs 1
```

### Compare RM and EDF

```bash
python scheduler.py input/tasks_moderate.csv --compare
```

### Find critical utilization

```bash
python scheduler.py input/tasks_moderate.csv --find-critical-utilization
```

With context switching:

```bash
python scheduler.py input/tasks_moderate.csv --cs 1 --find-critical-utilization
```

### Test an overloaded set

```bash
python scheduler.py input/tasks_overloaded.csv --policy EDF
```

### Test a harmonic set

```bash
python scheduler.py input/tasks_harmonic.csv --policy RM
```

## Concepts demonstrated

- Foreground/background behavior through static RM priorities
- Dynamic priorities under EDF
- Preemption
- Non-preemptive blocking
- Context switching
- Periodic task/job release
- Deadlines and deadline misses
- Utilization bounds
- Hyperperiod-based simulation

## Important interpretation

The RM Liu & Layland bound is a sufficient, not necessary, condition. A task set above the bound may still be schedulable.

For EDF, `U <= 1` is necessary and sufficient for the classic implicit-deadline case (`deadline == period`). For arbitrary deadlines, the simulator reports the limitation and relies on simulation for the concrete result.

## Suggested demonstration

1. Run the moderate task set with RM.
2. Run the same set with EDF.
3. Switch to non-preemptive mode.
4. Add context-switch overhead.
5. Run the critical-utilization search.
6. Try the overloaded task set.
7. Try the harmonic task set to demonstrate RM can succeed above its generic bound.


## GUI application

The project also includes a Tkinter desktop GUI.

Run:

```bash
python gui.py
```

The GUI provides:
- CSV file browser and task table
- RM / EDF policy selection
- Preemptive / non-preemptive kernel selection
- Context-switch overhead input
- Automatic or custom simulation duration
- Full simulation results
- RM vs EDF comparison
- Critical-utilization search
- Scrollable text Gantt timeline

Tkinter is included with most standard Python installations, so no external package is required.
