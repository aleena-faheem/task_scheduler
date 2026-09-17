import csv
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from scheduler import load_tasks, simulate, utilization, rm_bound, edf_bound, hyperperiod, compare, find_critical_utilization


class SchedulerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Task Scheduler Simulator")
        self.geometry("1180x760")
        self.minsize(1000, 650)

        self.file_var = tk.StringVar(value="input/tasks_moderate.csv")
        self.policy_var = tk.StringVar(value="RM")
        self.mode_var = tk.StringVar(value="preemptive")
        self.cs_var = tk.StringVar(value="0")
        self.duration_var = tk.StringVar(value="")
        self.tasks = []

        self._build_style()
        self._build_ui()
        self.load_file()

    def _build_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"))
        style.configure("Section.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("Treeview", rowheight=28, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

    def _build_ui(self):
        header = ttk.Frame(self, padding=(18, 14))
        header.pack(fill="x")
        ttk.Label(header, text="Task Scheduler Simulator", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="RM • EDF • Preemptive • Non-preemptive",
                  font=("Segoe UI", 10)).pack(side="right", pady=8)

        controls = ttk.LabelFrame(self, text="Simulation Controls", padding=12)
        controls.pack(fill="x", padx=18, pady=(0, 10))

        ttk.Label(controls, text="Task file:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(controls, textvariable=self.file_var, width=48).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(controls, text="Browse", command=self.browse).grid(row=0, column=2, padx=5)
        ttk.Button(controls, text="Load Tasks", command=self.load_file).grid(row=0, column=3, padx=5)

        ttk.Label(controls, text="Policy:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        ttk.Combobox(controls, textvariable=self.policy_var, values=["RM", "EDF"],
                     state="readonly", width=15).grid(row=1, column=1, sticky="w", padx=5)

        ttk.Label(controls, text="Kernel mode:").grid(row=1, column=2, sticky="w", padx=5)
        ttk.Combobox(controls, textvariable=self.mode_var,
                     values=["preemptive", "nonpreemptive"], state="readonly", width=18).grid(row=1, column=3, sticky="w")

        ttk.Label(controls, text="Context switch (ticks):").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(controls, textvariable=self.cs_var, width=18).grid(row=2, column=1, sticky="w", padx=5)

        ttk.Label(controls, text="Duration (blank = auto):").grid(row=2, column=2, sticky="w", padx=5)
        ttk.Entry(controls, textvariable=self.duration_var, width=18).grid(row=2, column=3, sticky="w")

        buttons = ttk.Frame(controls)
        buttons.grid(row=3, column=0, columnspan=4, sticky="w", pady=(10, 0))
        ttk.Button(buttons, text="Run Simulation", style="Accent.TButton",
                   command=self.run_simulation).pack(side="left", padx=4)
        ttk.Button(buttons, text="Compare RM vs EDF", command=self.run_compare).pack(side="left", padx=4)
        ttk.Button(buttons, text="Find Critical Utilization", command=self.run_critical).pack(side="left", padx=4)

        content = ttk.Panedwindow(self, orient="vertical")
        content.pack(fill="both", expand=True, padx=18, pady=8)

        upper = ttk.Frame(content, padding=4)
        lower = ttk.Frame(content, padding=4)
        content.add(upper, weight=1)
        content.add(lower, weight=2)

        task_frame = ttk.LabelFrame(upper, text="Task Set", padding=8)
        task_frame.pack(fill="both", expand=True)

        cols = ("name", "period", "execution", "deadline", "offset")
        self.tree = ttk.Treeview(task_frame, columns=cols, show="headings", height=7)
        headings = {"name": "Task", "period": "Period", "execution": "Execution",
                    "deadline": "Deadline", "offset": "Offset"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, anchor="center", width=120)
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(task_frame, orient="vertical", command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)

        result_frame = ttk.LabelFrame(lower, text="Results", padding=8)
        result_frame.pack(fill="both", expand=True)
        self.result = tk.Text(result_frame, wrap="none", font=("Consolas", 10),
                              padx=10, pady=10)
        self.result.pack(side="left", fill="both", expand=True)
        ysb = ttk.Scrollbar(result_frame, orient="vertical", command=self.result.yview)
        ysb.pack(side="right", fill="y")
        xsb = ttk.Scrollbar(result_frame, orient="horizontal", command=self.result.xview)
        xsb.pack(side="bottom", fill="x")
        self.result.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)

        self.status = ttk.Label(self, text="Ready", relief="sunken", anchor="w", padding=5)
        self.status.pack(fill="x", side="bottom")

    def browse(self):
        path = filedialog.askopenfilename(
            title="Select task CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if path:
            self.file_var.set(path)
            self.load_file()

    def load_file(self):
        try:
            self.tasks = load_tasks(self.file_var.get())
            for item in self.tree.get_children():
                self.tree.delete(item)
            for t in self.tasks:
                self.tree.insert("", "end", values=(t.name, t.period, t.execution, t.deadline, t.offset))
            u = utilization(self.tasks)
            self.status.config(text=f"Loaded {len(self.tasks)} tasks • U={u*100:.2f}% • Hyperperiod={hyperperiod(self.tasks)}")
        except Exception as e:
            self.tasks = []
            self.status.config(text="Load failed")
            messagebox.showerror("Input Error", str(e))

    def _params(self):
        if not self.tasks:
            raise ValueError("Load a valid task file first.")
        cs = int(self.cs_var.get() or 0)
        duration = int(self.duration_var.get()) if self.duration_var.get().strip() else None
        if cs < 0:
            raise ValueError("Context-switch overhead cannot be negative.")
        return cs, duration

    def _show(self, text):
        self.result.delete("1.0", "end")
        self.result.insert("1.0", text)
        self.result.see("1.0")

    def run_simulation(self):
        try:
            cs, duration = self._params()
            r = simulate(self.tasks, self.policy_var.get(), self.mode_var.get(), duration, cs)
            u = utilization(self.tasks)
            rb = rm_bound(len(self.tasks))
            eb, implicit = edf_bound(self.tasks)
            lines = [
                "=" * 92,
                "TASK SCHEDULER SIMULATOR — GUI RESULT",
                "=" * 92,
                f"Policy              : {r.policy}",
                f"Kernel mode         : {r.mode}",
                f"Simulation duration : {r.duration}",
                f"Hyperperiod         : {hyperperiod(self.tasks)}",
                "",
                f"CPU utilization     : {u*100:.2f}%",
                f"RM bound            : {rb*100:.2f}%",
                f"EDF bound           : {eb*100:.2f}%",
            ]
            if r.policy == "RM":
                lines.append(f"RM utilization test : {'PASS' if u <= rb else 'ABOVE SUFFICIENT BOUND'}")
            else:
                lines.append(f"EDF implicit deadline test: {'PASS' if u <= 1 else 'FAIL'}" if implicit
                             else "EDF note             : arbitrary deadline set; simulation is the concrete test.")

            lines += [
                "",
                "DEADLINE MISSES",
                "-" * 92
            ]
            per = {}
            for j in r.jobs:
                per[j.task.name] = per.get(j.task.name, 0) + int(j.missed)
            for t in self.tasks:
                lines.append(f"{t.name:<10}: {per.get(t.name, 0)}")
            lines += [
                f"Total misses        : {r.deadline_misses}",
                "",
                "CPU STATISTICS",
                "-" * 92,
                f"Idle ticks          : {r.idle_time}",
                f"Context switches    : {r.context_switches}",
                f"Context CPU ticks   : {r.context_time}",
                "",
                "GANTT TIMELINE",
                "-" * 92,
                "  ".join(f"[{e.start},{e.end}) {e.label}" for e in r.events),
                "",
                f"FINAL RESULT        : {'SCHEDULABLE' if r.schedulable else 'NOT SCHEDULABLE'}",
                "=" * 92
            ]
            self._show("\n".join(lines))
            self.status.config(text=f"Simulation complete • {r.policy} • {r.mode} • {'SCHEDULABLE' if r.schedulable else 'DEADLINE MISSES'}")
        except Exception as e:
            messagebox.showerror("Simulation Error", str(e))

    def run_compare(self):
        try:
            cs, duration = self._params()
            self._show(compare(self.tasks, self.mode_var.get(), cs, duration))
            self.status.config(text="RM vs EDF comparison complete")
        except Exception as e:
            messagebox.showerror("Comparison Error", str(e))

    def run_critical(self):
        try:
            cs, _ = self._params()
            text = find_critical_utilization(self.tasks, self.policy_var.get(),
                                             self.mode_var.get(), cs=cs)
            self._show(text)
            self.status.config(text="Critical-utilization search complete")
        except Exception as e:
            messagebox.showerror("Analysis Error", str(e))


if __name__ == "__main__":
    app = SchedulerGUI()
    app.mainloop()
