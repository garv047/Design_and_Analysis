"""
Maximum Gain Window PRO  -  longest path in a DAG, GUI for big CSV files
========================================================================

Run:   python max_gain_pro.py                 -> GUI
       python max_gain_pro.py data.csv        -> GUI, file opened at start
       python max_gain_pro.py --cli data.csv [max_trades] [fee]   -> table, no GUI
       python max_gain_pro.py --demo          -> self-tests, no GUI

CSV format: asset,date,price,status   (status = OK or HALTED; header optional,
column names such as symbol/close are also understood). Dates must sort
correctly as text (ISO format YYYY-MM-DD).

The DAG
-------
Node = (day, stage).  stage 0 = no shares, 1 = holding (trade 1),
2 = sold trade 1, 3 = holding (trade 2), 4 = sold trade 2 ...
All edges go from day d to d+1, so there are no loops (a DAG).
    WAIT : same stage,            weight 0
    BUY  : even stage -> stage+1, weight -price            (not on halted days)
    SELL : odd  stage -> stage+1, weight +price - fee      (not on halted days)
Best plan = longest path from node (0,0) to the last day.

For big files the graph is never stored as Python objects: solve_dag() walks
the same DAG implicitly (O(days x stages) time, compact arrays), and the GUI
draws any window of days straight from the DP table. The original explicit
graph code (build_graph / longest_path / find_best_trades) is kept as a
reference and is cross-checked against the fast solver in the self-test.
"""

import csv
import math
import os
import queue
import random
import statistics
import sys
import threading
import time
from array import array

NEG_INF = float("-inf")


# ======================================================================
# PART 1: DATA CLEANING   record = (asset, date, price, status)
# ======================================================================
def clean_records(records):
    """Remove bad rows and count every problem. Works on any iterable."""
    report = {"rows_read": 0, "missing_price": 0, "invalid_price": 0,
              "invalid_status": 0, "duplicates": 0, "rows_kept": 0}
    seen = set()
    by_asset = {}

    for asset, date, price, status in records:
        report["rows_read"] += 1

        if price is None or str(price).strip() == "":
            report["missing_price"] += 1
            continue
        try:
            price = float(price)
        except ValueError:
            report["invalid_price"] += 1
            continue
        if price != price or price in (float("inf"), float("-inf")) or price <= 0:
            report["invalid_price"] += 1          # nan, infinite, zero or negative
            continue
        if status not in ("OK", "HALTED"):
            report["invalid_status"] += 1
            continue
        if (asset, date) in seen:
            report["duplicates"] += 1             # keep the first one only
            continue

        seen.add((asset, date))
        by_asset.setdefault(asset, []).append((date, price, status == "OK"))
        report["rows_kept"] += 1

    for asset in by_asset:
        by_asset[asset].sort(key=lambda row: row[0])   # sort by date
    return by_asset, report


class Series:
    """One asset: parallel lists (fast for 200,000+ days)."""
    __slots__ = ("name", "dates", "prices", "ok")

    def __init__(self, name, rows):
        self.name = name
        self.dates = [r[0] for r in rows]
        self.prices = [r[1] for r in rows]
        self.ok = [r[2] for r in rows]

    def __len__(self):
        return len(self.prices)

    def days(self):
        return list(zip(self.dates, self.prices, self.ok))


def load_csv(path, emit=lambda *a, **k: None):
    """Stream a CSV file through clean_records. Returns (dict name->Series, report)."""
    t0 = time.perf_counter()
    stem = os.path.splitext(os.path.basename(path))[0]
    with open(path, newline="", encoding="utf-8-sig") as f:
        rd = csv.reader(f)
        first = next(rd, None)
        if first is None:
            return {}, clean_records([])[1]
        names = [c.strip().lower() for c in first]

        def find(options):
            for o in options:
                if o in names:
                    return names.index(o)
            return None
        a_i = find(("asset", "symbol", "ticker", "name"))
        d_i = find(("date", "day", "timestamp", "time"))
        p_i = find(("price", "close", "adj close", "adj_close"))
        s_i = find(("status", "state"))
        has_header = d_i is not None and p_i is not None
        if not has_header:                          # no header: asset,date,price,status
            a_i, d_i, p_i, s_i = 0, 1, 2, 3

        def cell(row, i, default=""):
            return row[i].strip() if i is not None and i < len(row) else default

        def rows():
            count = 0
            pending = [] if has_header else [first]
            for row in (r for chunk in (pending, rd) for r in chunk):
                if not row:
                    continue
                count += 1
                if count % 25000 == 0:
                    emit(None, f"Reading... {count:,} rows")
                status = cell(row, s_i, "OK").upper() or "OK"
                yield (cell(row, a_i, stem) or stem, cell(row, d_i), cell(row, p_i), status)

        by_asset, report = clean_records(rows())
    emit(None, "Sorting and indexing...")
    data = {name: Series(name, rows_) for name, rows_ in by_asset.items()}
    report["seconds"] = time.perf_counter() - t0
    report["file_mb"] = os.path.getsize(path) / 1e6
    return data, report


# ======================================================================
# PART 2: THE DAG ALGORITHM
# ======================================================================
# ---- 2a. reference version: explicit graph (small inputs, used for tests) ----
def build_graph(days, max_trades, fee):
    n = len(days)
    stages = 2 * max_trades + 1
    graph = [[] for _ in range((n + 1) * stages)]
    for d in range(n):
        price, tradable = days[d][1], days[d][2]
        for s in range(stages):
            here = d * stages + s
            graph[here].append(((d + 1) * stages + s, 0.0, "WAIT"))
            if not tradable or s == stages - 1:
                continue
            nxt = (d + 1) * stages + s + 1
            if s % 2 == 0:
                graph[here].append((nxt, -price, "BUY"))
            else:
                graph[here].append((nxt, price - fee, "SELL"))
    return graph, stages


def longest_path(graph, stats):
    best = [NEG_INF] * len(graph)
    parent = [None] * len(graph)
    best[0] = 0.0
    for u in range(len(graph)):
        if best[u] == NEG_INF:
            continue
        stats["nodes"] += 1
        for v, weight, action in graph[u]:
            stats["relaxations"] += 1
            if best[u] + weight > best[v]:
                best[v] = best[u] + weight
                parent[v] = (u, action)
    return best, parent


def find_best_trades(days, max_trades=1, fee=0.0):
    """Reference implementation on an explicit graph."""
    stats = {"nodes": 0, "relaxations": 0}
    if len(days) < 2:
        return {"profit": 0.0, "trades": [], "stats": stats}
    graph, stages = build_graph(days, max_trades, fee)
    best, parent = longest_path(graph, stats)
    n = len(days)
    end = None
    for s in range(0, stages, 2):
        node = n * stages + s
        if best[node] != NEG_INF and (end is None or best[node] > best[end]):
            end = node
    actions, node = [], end
    while parent[node] is not None:
        prev, action = parent[node]
        if action != "WAIT":
            actions.append((prev // stages, action))
        node = prev
    actions.reverse()
    trades = []
    for i in range(0, len(actions), 2):
        b, s = actions[i][0], actions[i + 1][0]
        trades.append({"buy_idx": b, "sell_idx": s, "buy_price": days[b][1],
                       "sell_price": days[s][1], "gain": days[s][1] - days[b][1] - fee})
    return {"profit": best[end], "trades": trades, "stats": stats}


# ---- 2b. fast version: same DAG, walked implicitly with compact arrays ----
def solve_dag(prices, ok, max_trades=1, fee=0.0, emit=None):
    """Longest path in the implicit DAG. Same tie-breaking as the reference.

    Returns the whole DP table (best, via) so the GUI can draw any window of
    the DAG, plus the optimal path (path_stage[d] = stage on the path at day d).
    """
    t0 = time.perf_counter()
    n = len(prices)
    S = 2 * max_trades + 1
    size = (n + 1) * S
    best = array("d", [NEG_INF]) * size
    via = array("b", bytes(size))                 # 1 = arrived by BUY/SELL, 0 = WAIT
    best[0] = 0.0
    relax = 0

    for d in range(n):
        base = d * S
        nb = base + S
        wb, ws = -prices[d], prices[d] - fee
        tradable = ok[d]
        # stage 0 can only wait
        if best[base] > best[nb]:
            best[nb] = best[base]
        for s in range(1, S):
            if tradable:                          # edge from (d, s-1): BUY if s odd, SELL if s even
                c = best[base + s - 1] + (wb if s & 1 else ws)
                if c > best[nb + s]:
                    best[nb + s] = c
                    via[nb + s] = 1
            c = best[base + s]                    # WAIT edge from (d, s)
            if c > best[nb + s]:
                best[nb + s] = c
                via[nb + s] = 0
        relax += S + (S - 1 if tradable else 0)
        if emit and d % 20000 == 0 and n > 50000:
            emit(d / n, f"Solving... day {d:,} of {n:,}")

    # finish in any "no shares" stage; ties -> fewer trades
    end_s = None
    for s in range(0, S, 2):
        if best[n * S + s] != NEG_INF and (end_s is None or best[n * S + s] > best[n * S + end_s]):
            end_s = s

    path_stage = array("b", bytes(n + 1))
    trades_raw, s = [], end_s
    path_stage[n] = s
    for d in range(n, 0, -1):
        if via[d * S + s] == 1:
            trades_raw.append((d - 1, s - 1))     # action taken on day d-1, from stage s-1
            s -= 1
        path_stage[d - 1] = s
    trades_raw.reverse()

    trades = []
    for i in range(0, len(trades_raw), 2):
        b, sl = trades_raw[i][0], trades_raw[i + 1][0]
        trades.append({"buy_idx": b, "sell_idx": sl, "buy_price": prices[b],
                       "sell_price": prices[sl], "holding_days": sl - b,
                       "gain": prices[sl] - prices[b] - fee})
    return {"profit": best[n * S + end_s] if n else 0.0, "trades": trades, "best": best,
            "via": via, "path_stage": path_stage, "S": S, "n": n, "k": max_trades, "fee": fee,
            "nodes": size, "relaxations": relax, "seconds": time.perf_counter() - t0}


# ======================================================================
# PART 3: BASELINES AND CHECKS
# ======================================================================
def brute_force_pairs(days, fee=0.0):
    best, comparisons = 0.0, 0
    for i in range(len(days)):
        if not days[i][2]:
            continue
        for j in range(i + 1, len(days)):
            if not days[j][2]:
                continue
            comparisons += 1
            best = max(best, days[j][1] - days[i][1] - fee)
    return best, comparisons


def exhaustive(days, max_trades, fee=0.0):
    """Try EVERY possible plan. Tiny inputs only; ground truth."""
    n = len(days)

    def solve(day, left):
        if left == 0 or day >= n:
            return 0.0
        best = solve(day + 1, left)
        if days[day][2]:
            for sell in range(day + 1, n):
                if days[sell][2]:
                    best = max(best, days[sell][1] - days[day][1] - fee + solve(sell + 1, left - 1))
        return best
    return solve(0, max_trades)


def linear_single_trade(prices, ok, fee=0.0):
    """Independent O(n) answer for ONE trade (running minimum). Works for any size."""
    lowest, best = None, 0.0
    for p, tradable in zip(prices, ok):
        if not tradable:
            continue
        if lowest is not None:
            best = max(best, p - lowest - fee)
        lowest = p if lowest is None else min(lowest, p)
    return best


def check_result(series, res):
    """Cheap sanity checks usable on every size. Returns 'OK' or a description."""
    tol = lambda a, b: math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
    if not tol(sum(t["gain"] for t in res["trades"]), res["profit"]):
        return "gains do not add up"
    if res["k"] == 1 and not tol(linear_single_trade(series.prices, series.ok, res["fee"]), res["profit"]):
        return "differs from O(n) scan"
    last = -1
    for t in res["trades"]:
        if not (last < t["buy_idx"] < t["sell_idx"]) or not series.ok[t["buy_idx"]] or not series.ok[t["sell_idx"]]:
            return "illegal trade"
        last = t["sell_idx"]
    return "OK"


# ======================================================================
# PART 4: HELPERS
# ======================================================================
def fnum(v):
    if v == 0:
        return "0"
    a = abs(v)
    return f"{v:.4g}" if (a >= 1e7 or a < 1e-3) else f"{v:,.2f}"


def make_days(prices, halted=()):
    return [(f"day{i}", float(p), i not in halted) for i, p in enumerate(prices)]


def random_series(name, n, rng, start=100.0):
    price, rows = start, []
    for i in range(n):
        price = max(0.01, price * (1 + rng.gauss(0.0003, 0.02)))
        rows.append((f"D{i + 1:07d}", round(price, 4), rng.random() > 0.01))
    return Series(name, rows)


def parse_price_text(text):
    """'10 12 9* 15' -> records. A trailing * or h marks a HALTED day."""
    tokens = [t for t in text.replace(",", " ").replace(";", " ").split() if t]
    width = max(4, len(str(len(tokens))))
    out = []
    for i, tok in enumerate(tokens):
        status = "OK"
        if tok[-1] in "*hH":
            status, tok = "HALTED", tok[:-1]
        out.append(("MANUAL", f"D{i + 1:0{width}d}", tok, status))
    return out


def median_time(fn, repeats=3):
    ts = []
    for _ in range(repeats):
        t = time.perf_counter()
        fn()
        ts.append(time.perf_counter() - t)
    return statistics.median(ts)


def run_self_test(cases=500, seed=42):
    """Fast solver vs explicit-graph version vs exhaustive search on random tiny inputs."""
    rng = random.Random(seed)
    wrong_profit = wrong_trades = 0
    for _ in range(cases):
        n = rng.randint(0, 9)
        days = make_days([rng.randint(1, 20) for _ in range(n)],
                         {i for i in range(n) if rng.random() < 0.15})
        k, fee = rng.randint(1, 3), rng.choice([0, 0.5, 1, 3])
        truth = exhaustive(days, k, fee)
        ref = find_best_trades(days, k, fee)
        if n < 2:
            continue
        fast = solve_dag([d[1] for d in days], [d[2] for d in days], k, fee)
        if abs(fast["profit"] - truth) > 1e-9 or abs(ref["profit"] - truth) > 1e-9:
            wrong_profit += 1
        if [(t["buy_idx"], t["sell_idx"]) for t in fast["trades"]] != \
           [(t["buy_idx"], t["sell_idx"]) for t in ref["trades"]]:
            wrong_trades += 1
    return wrong_profit, wrong_trades


def solve_all(data, k, fee, emit=lambda *a, **kw: None):
    rows = []
    names = list(data)
    for i, name in enumerate(names):
        s = data[name]
        emit(i / len(names), f"Solving {name} ({len(s):,} days)...")
        if len(s) < 2:
            rows.append((name, len(s), 0, 0.0, 0, 0.0, "n/a"))
            continue
        r = solve_dag(s.prices, s.ok, k, fee)
        rows.append((name, len(s), s.ok.count(False), r["profit"], len(r["trades"]),
                     r["seconds"] * 1000, check_result(s, r)))
    return rows


# ======================================================================
# PART 5: GUI
# ======================================================================
def launch_gui(start_file=None):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, simpledialog

    C = {"bg": "#f3f4f6", "panel": "#ffffff", "ink": "#111827", "muted": "#6b7280",
         "wait": "#c4c9d2", "buy": "#16a34a", "sell": "#dc2626", "path": "#2563eb",
         "node": "#e0e7ff", "dead": "#eceef2", "gold": "#fde68a", "halt": "#b91c1c",
         "grid": "#e5e7eb", "band": "#dbeafe", "accent": "#1d4ed8"}

    class App(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("Maximum Gain Window PRO - longest path in a DAG")
            self.geometry("1440x860")
            self.minsize(1100, 680)
            self.configure(bg=C["bg"])
            self.data, self.cur, self.res = {}, None, None
            self.cache = {}                         # (asset,k,fee) -> result row info
            self.q = queue.Queue()
            self.busy = False
            self.pending = False
            self.v0 = self.v1 = 0.0                 # chart view (day indices)
            self.drag = None
            self.dag_job = None
            self.anim = None
            self._style()
            self._build()
            self.after(50, self._poll)
            self.set_data({"SAMPLE": Series("SAMPLE", [(f"D{i + 1:04d}", float(p), True)
                                                      for i, p in enumerate([7, 1, 5, 3, 6, 4, 9, 2])])},
                          None, "built-in sample")
            if start_file:
                self.after(200, lambda: self.open_path(start_file))

        # --------------------------------------------------- look & layout
        def _style(self):
            st = ttk.Style(self)
            try:
                st.theme_use("clam")
            except tk.TclError:
                pass
            st.configure(".", background=C["bg"], foreground=C["ink"], font=("Segoe UI", 10))
            st.configure("TButton", padding=5)
            st.configure("Accent.TButton", background=C["accent"], foreground="white", font=("Segoe UI", 10, "bold"))
            st.map("Accent.TButton", background=[("active", "#1e40af")])
            st.configure("H.TLabel", font=("Segoe UI", 10, "bold"))
            st.configure("Treeview", rowheight=22, background=C["panel"], fieldbackground=C["panel"])
            st.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
            st.configure("TNotebook.Tab", padding=(12, 5))

        def _build(self):
            bottom = ttk.Frame(self, padding=(10, 2))
            bottom.pack(side="bottom", fill="x")
            self.status = tk.StringVar(value="Open a CSV file to begin.")
            ttk.Label(bottom, textvariable=self.status, foreground=C["muted"]).pack(side="left")
            self.prog = ttk.Progressbar(bottom, length=220, mode="determinate")
            self.prog.pack(side="right")

            pw = ttk.PanedWindow(self, orient="horizontal")
            pw.pack(fill="both", expand=True, padx=8, pady=8)
            left = ttk.Frame(pw, padding=4)
            right = ttk.Frame(pw, padding=0)
            pw.add(left, weight=0)
            pw.add(right, weight=1)

            top = ttk.Frame(left)
            top.pack(fill="x")
            ttk.Button(top, text="Open CSV...", style="Accent.TButton", command=self.open_dialog).pack(side="left")
            ttk.Button(top, text="Type prices", command=self.manual_dialog).pack(side="left", padx=4)
            ttk.Button(top, text="Random", command=self.random_dialog).pack(side="left")
            self.file_lbl = ttk.Label(left, text="", foreground=C["muted"], wraplength=360)
            self.file_lbl.pack(anchor="w", pady=(4, 6))

            ttk.Label(left, text="Assets", style="H.TLabel").pack(anchor="w")
            cols = ("asset", "days", "halted", "profit")
            self.atree = ttk.Treeview(left, columns=cols, show="headings", height=9, selectmode="browse")
            for c, w, t in (("asset", 110, "Asset"), ("days", 62, "Days"), ("halted", 58, "Halted"), ("profit", 100, "Profit")):
                self.atree.heading(c, text=t)
                self.atree.column(c, width=w, anchor="w" if c == "asset" else "e")
            self.atree.pack(fill="x", pady=(2, 8))
            self.atree.bind("<<TreeviewSelect>>", lambda e: self.on_select())

            box = ttk.Frame(left)
            box.pack(fill="x")
            ttk.Label(box, text="Max trades").grid(row=0, column=0, sticky="w")
            self.k_var = tk.IntVar(value=2)
            ttk.Spinbox(box, from_=1, to=6, width=4, textvariable=self.k_var).grid(row=0, column=1, padx=6)
            ttk.Label(box, text="Fee / trade").grid(row=0, column=2, sticky="w", padx=(8, 0))
            self.fee_var = tk.StringVar(value="0")
            ttk.Entry(box, width=8, textvariable=self.fee_var).grid(row=0, column=3, padx=6)
            self.log_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(box, text="Log price scale", variable=self.log_var,
                            command=self.draw_chart).grid(row=1, column=0, columnspan=4, sticky="w", pady=(6, 0))

            btns = ttk.Frame(left)
            btns.pack(fill="x", pady=8)
            ttk.Button(btns, text="Solve selected", style="Accent.TButton", command=self.solve).pack(side="left")
            ttk.Button(btns, text="Run ALL assets", command=self.run_all).pack(side="left", padx=4)

            ttk.Label(left, text="Result", style="H.TLabel").pack(anchor="w")
            self.out = tk.Text(left, width=44, height=14, wrap="word", relief="solid", bd=1, bg=C["panel"],
                               state="disabled", font=("Consolas", 10))
            self.out.pack(fill="both", expand=True, pady=(2, 0))

            self.nb = ttk.Notebook(right)
            self.nb.pack(fill="both", expand=True)

            # ---- price chart
            t1 = ttk.Frame(self.nb)
            self.nb.add(t1, text="Price chart")
            bar = ttk.Frame(t1, padding=(6, 4))
            bar.pack(fill="x")
            ttk.Button(bar, text="Reset zoom", command=self.reset_view).pack(side="left")
            ttk.Button(bar, text="Zoom to trade 1", command=lambda: self.zoom_trade(0)).pack(side="left", padx=4)
            ttk.Label(bar, text="wheel = zoom   drag = pan   double-click = open that spot in the DAG",
                      foreground=C["muted"]).pack(side="left", padx=10)
            self.chart = tk.Canvas(t1, bg=C["panel"], highlightthickness=0, cursor="crosshair")
            self.chart.pack(fill="both", expand=True)
            self.chart.bind("<Configure>", lambda e: self.draw_chart())
            self.chart.bind("<MouseWheel>", self.on_wheel)
            self.chart.bind("<Button-4>", lambda e: self.on_wheel(e, 1))
            self.chart.bind("<Button-5>", lambda e: self.on_wheel(e, -1))
            self.chart.bind("<ButtonPress-1>", self.on_press)
            self.chart.bind("<B1-Motion>", self.on_drag)
            self.chart.bind("<Motion>", self.on_move)
            self.chart.bind("<Double-Button-1>", self.on_dbl)

            # ---- DAG window
            t2 = ttk.Frame(self.nb)
            self.nb.add(t2, text="DAG window")
            bar = ttk.Frame(t2, padding=(6, 4))
            bar.pack(fill="x")
            ttk.Label(bar, text="Start day").pack(side="left")
            self.start_var = tk.IntVar(value=0)
            self.start_sc = ttk.Scale(bar, from_=0, to=1, orient="horizontal", length=320,
                                      command=lambda v: self.on_scale())
            self.start_sc.pack(side="left", padx=6)
            self.start_lbl = ttk.Label(bar, text="0", width=9)
            self.start_lbl.pack(side="left")
            ttk.Label(bar, text="Columns").pack(side="left", padx=(8, 2))
            self.win_var = tk.IntVar(value=12)
            ttk.Spinbox(bar, from_=4, to=30, width=4, textvariable=self.win_var,
                        command=self.schedule_dag).pack(side="left")
            ttk.Button(bar, text="<", width=3, command=lambda: self.shift(-1)).pack(side="left", padx=(10, 1))
            ttk.Button(bar, text=">", width=3, command=lambda: self.shift(1)).pack(side="left")
            ttk.Label(bar, text="Jump to").pack(side="left", padx=(10, 2))
            self.jump = ttk.Combobox(bar, state="readonly", width=24)
            self.jump.pack(side="left")
            self.jump.bind("<<ComboboxSelected>>", lambda e: self.do_jump())
            ttk.Button(bar, text="Animate", command=self.animate).pack(side="left", padx=8)
            frame = ttk.Frame(t2)
            frame.pack(fill="both", expand=True)
            self.dag = tk.Canvas(frame, bg=C["panel"], highlightthickness=0)
            hs = ttk.Scrollbar(frame, orient="horizontal", command=self.dag.xview)
            self.dag.configure(xscrollcommand=hs.set)
            hs.pack(side="bottom", fill="x")
            self.dag.pack(fill="both", expand=True)
            self.dag.bind("<Configure>", lambda e: self.schedule_dag())

            # ---- all assets
            t3 = ttk.Frame(self.nb)
            self.nb.add(t3, text="All assets")
            bar = ttk.Frame(t3, padding=(6, 4))
            bar.pack(fill="x")
            ttk.Button(bar, text="Run ALL assets", style="Accent.TButton", command=self.run_all).pack(side="left")
            ttk.Button(bar, text="Export table (CSV)", command=self.export_table).pack(side="left", padx=6)
            ttk.Label(bar, text="click a column header to sort, double-click a row to open it",
                      foreground=C["muted"]).pack(side="left", padx=8)
            cols = ("asset", "days", "halted", "profit", "trades", "avg", "ms", "check")
            heads = ("Asset", "Days", "Halted", "Max profit", "Trades", "Avg gain/trade", "Solve ms", "Check")
            self.rtree = ttk.Treeview(t3, columns=cols, show="headings")
            for c, h in zip(cols, heads):
                self.rtree.heading(c, text=h, command=lambda c=c: self.sort_table(c))
                self.rtree.column(c, width=110 if c != "asset" else 130, anchor="w" if c in ("asset", "check") else "e")
            self.rtree.pack(fill="both", expand=True, padx=6, pady=4)
            self.rtree.bind("<Double-1>", self.open_from_table)
            self.rows_raw = []
            self.sort_rev = {}

            # ---- cleaning report
            t4 = ttk.Frame(self.nb)
            self.nb.add(t4, text="Cleaning report")
            self.rep = tk.Text(t4, font=("Consolas", 10), relief="flat", bg=C["panel"], state="disabled")
            self.rep.pack(fill="both", expand=True, padx=6, pady=6)

            # ---- tests
            t5 = ttk.Frame(self.nb)
            self.nb.add(t5, text="Tests & speed")
            bar = ttk.Frame(t5, padding=6)
            bar.pack(fill="x")
            ttk.Button(bar, text="Correctness test", command=self.do_selftest).pack(side="left", padx=3)
            ttk.Button(bar, text="Speed: DAG vs brute force", command=self.do_speed).pack(side="left", padx=3)
            ttk.Button(bar, text="Stress: 200,000 days", command=self.do_stress).pack(side="left", padx=3)
            self.log = tk.Text(t5, font=("Consolas", 10), relief="flat", bg=C["panel"], state="disabled")
            self.log.pack(fill="both", expand=True, padx=6, pady=6)

        # --------------------------------------------------- background jobs
        def run_bg(self, work, done, text="Working..."):
            if self.busy:
                self.bell()
                self.status.set("Busy - please wait for the current job to finish.")
                return False
            self.busy = True
            self.status.set(text)
            self.prog.configure(mode="indeterminate")
            self.prog.start(12)

            def emit(frac=None, msg=None, log=None):
                self.q.put(("prog", frac, msg, log))

            def target():
                try:
                    self.q.put(("done", work(emit), done))
                except Exception as e:                       # report in the UI thread
                    self.q.put(("err", e, None))
            threading.Thread(target=target, daemon=True).start()
            return True

        def _poll(self):
            try:
                while True:
                    kind, a, b, *rest = self.q.get_nowait()
                    if kind == "prog":
                        if a is not None:
                            self.prog.stop()
                            self.prog.configure(mode="determinate", value=a * 100)
                        if b:
                            self.status.set(b)
                        if rest and rest[0]:
                            self._write(self.log, rest[0], True)
                    else:
                        self.busy = False
                        self.prog.stop()
                        self.prog.configure(mode="determinate", value=0)
                        if kind == "err":
                            self.status.set("Error")
                            messagebox.showerror("Error", f"{type(a).__name__}: {a}")
                        else:
                            b(a)
                        if self.pending and not self.busy:
                            self.pending = False
                            self.solve()
            except queue.Empty:
                pass
            self.after(50, self._poll)

        def _write(self, widget, text, append=False):
            widget.configure(state="normal")
            if not append:
                widget.delete("1.0", "end")
            widget.insert("end", text)
            widget.configure(state="disabled")
            widget.see("end")

        # --------------------------------------------------- loading data
        def open_dialog(self):
            p = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
            if p:
                self.open_path(p)

        def open_path(self, path):
            def work(emit):
                return load_csv(path, emit)

            def done(result):
                data, report = result
                if not data:
                    messagebox.showwarning("No usable rows", "Nothing valid was found in that file.")
                    return
                self.set_data(data, report, os.path.basename(path))
            self.run_bg(work, done, f"Loading {os.path.basename(path)}...")

        def set_data(self, data, report, source):
            self.data = data
            self.cache = {}
            self.rows_raw = []
            self.rtree.delete(*self.rtree.get_children())
            self.file_lbl.configure(text=f"{source}: {len(data)} asset(s), "
                                         f"{sum(len(s) for s in data.values()):,} valid rows")
            self.refresh_assets()
            if report:
                lines = [f"File: {source}   ({report['file_mb']:.1f} MB, loaded in {report['seconds']:.2f} s)", "",
                         f"rows read       : {report['rows_read']:,}",
                         f"rows kept       : {report['rows_kept']:,}",
                         f"missing price   : {report['missing_price']:,}",
                         f"invalid price   : {report['invalid_price']:,}   (not a number, nan/inf, zero or negative)",
                         f"invalid status  : {report['invalid_status']:,}",
                         f"duplicates      : {report['duplicates']:,}   (first one kept)", "",
                         f"{'asset':14s} {'days':>9s} {'halted':>8s} {'min price':>12s} {'max price':>12s}   first .. last date"]
                for name, s in data.items():
                    lines.append(f"{name:14s} {len(s):9,d} {s.ok.count(False):8,d} {fnum(min(s.prices)):>12s} "
                                 f"{fnum(max(s.prices)):>12s}   {s.dates[0]} .. {s.dates[-1]}")
                self._write(self.rep, "\n".join(lines))
            first = next(iter(data))
            self.atree.selection_set(first)

        def refresh_assets(self):
            self.atree.delete(*self.atree.get_children())
            k, fee = self.params(quiet=True)
            for name, s in self.data.items():
                prof = self.cache.get((name, k, fee))
                self.atree.insert("", "end", iid=name, values=(
                    name, f"{len(s):,}", f"{s.ok.count(False):,}", fnum(prof) if prof is not None else "-"))

        def add_series(self, s):
            self.data[s.name] = s
            self.refresh_assets()
            self.atree.selection_set(s.name)

        def manual_dialog(self):
            win = tk.Toplevel(self)
            win.title("Type prices")
            win.geometry("460x260")
            ttk.Label(win, text="Prices separated by space/comma. Add * after a halted day (e.g. 3*).").pack(anchor="w", padx=8, pady=6)
            box = tk.Text(win, height=8, wrap="word")
            box.pack(fill="both", expand=True, padx=8)
            box.insert("1.0", "7 1 5 3 6 4 9 2")

            def go():
                data, rep = clean_records(parse_price_text(box.get("1.0", "end")))
                if "MANUAL" not in data or len(data["MANUAL"]) < 2:
                    messagebox.showwarning("Need data", f"Need at least 2 valid prices.\nCleaning report: {rep}", parent=win)
                    return
                win.destroy()
                self.add_series(Series("MANUAL", data["MANUAL"]))
            ttk.Button(win, text="Add as asset MANUAL", style="Accent.TButton", command=go).pack(pady=8)

        def random_dialog(self):
            n = simpledialog.askinteger("Random series", "Number of days:", initialvalue=1000,
                                        minvalue=2, maxvalue=1000000, parent=self)
            if n:
                self.add_series(random_series(f"RANDOM_{n}", n, random.Random()))

        # --------------------------------------------------- solving
        def params(self, quiet=False):
            try:
                k, fee = int(self.k_var.get()), float(self.fee_var.get() or 0)
                if k < 1 or k > 6 or fee < 0:
                    raise ValueError
                return k, fee
            except (ValueError, tk.TclError):
                if not quiet:
                    messagebox.showerror("Bad input", "Max trades must be a whole number 1-6\nand fee must be a number >= 0.")
                return None, None

        def on_select(self):
            sel = self.atree.selection()
            if not sel or sel[0] not in self.data:
                return
            if self.busy:
                self.pending = True
                return
            self.solve()

        def solve(self):
            sel = self.atree.selection()
            if not sel:
                return
            k, fee = self.params()
            if k is None:
                return
            s = self.data[sel[0]]
            self.anim_stop()
            if len(s) < 2:
                self.cur, self.res = s, None
                self._write(self.out, "Need at least 2 valid days.")
                self.draw_all()
                return

            def work(emit):
                r = solve_dag(s.prices, s.ok, k, fee, emit)
                r["check"] = check_result(s, r)
                if k == 1 and len(s) <= 4000:
                    bf, _ = brute_force_pairs(s.days(), fee)
                    r["brute"] = bf
                return r

            def done(r):
                self.cur, self.res = s, r
                self.cache[(s.name, k, fee)] = r["profit"]
                self.atree.set(s.name, "profit", fnum(r["profit"]))
                self.show_result()
                self.log_var.set(max(s.prices) / min(s.prices) >= 50)
                self.reset_view()
                self.setup_dag()
                self.status.set(f"Solved {s.name}: {len(s):,} days in {r['seconds'] * 1000:.0f} ms")
            self.run_bg(work, done, f"Solving {s.name}...")

        def show_result(self):
            r, s = self.res, self.cur
            L = [f"Asset : {s.name}", f"Days  : {len(s):,}   (halted {s.ok.count(False):,})",
                 f"Trades: up to {r['k']}   Fee: {r['fee']:g}", "",
                 f"MAX PROFIT: {fnum(r['profit'])}", ""]
            if not r["trades"]:
                L.append("Best plan: do nothing\n(no trade makes money" + (" after fees)" if r["fee"] else ")"))
            for i, t in enumerate(r["trades"], 1):
                L += [f"Trade {i}",
                      f"  buy  {s.dates[t['buy_idx']]} @ {fnum(t['buy_price'])}",
                      f"  sell {s.dates[t['sell_idx']]} @ {fnum(t['sell_price'])}",
                      f"  gain {fnum(t['gain'])}  ({t['holding_days']:,} days)"]
            L += ["", f"DAG: {r['nodes']:,} nodes, {r['relaxations']:,} edges relaxed",
                  f"Time: {r['seconds'] * 1000:.1f} ms", f"Check: {r['check']}"]
            if "brute" in r:
                ok = abs(r["brute"] - r["profit"]) < 1e-9
                L.append(f"Brute force: {fnum(r['brute'])}  {'matches' if ok else 'MISMATCH'}")
            self._write(self.out, "\n".join(L))

        def run_all(self):
            k, fee = self.params()
            if k is None:
                return

            def done(rows):
                self.rows_raw = rows
                for name, n, h, profit, *_ in rows:
                    self.cache[(name, k, fee)] = profit
                self.refresh_assets()
                self.fill_table()
                self.nb.select(2)
                tot = sum(r[5] for r in rows)
                self.status.set(f"Solved {len(rows)} assets in {tot / 1000:.2f} s (k={k}, fee={fee:g})")
            self.run_bg(lambda emit: solve_all(self.data, k, fee, emit), done, "Solving all assets...")

        def fill_table(self):
            self.rtree.delete(*self.rtree.get_children())
            for name, n, h, profit, trades, ms, chk in self.rows_raw:
                avg = profit / trades if trades else 0.0
                self.rtree.insert("", "end", iid=name, values=(name, f"{n:,}", f"{h:,}", fnum(profit), trades,
                                                               fnum(avg), f"{ms:.1f}", chk))

        def sort_table(self, col):
            idx = {"asset": 0, "days": 1, "halted": 2, "profit": 3, "trades": 4, "avg": None, "ms": 5, "check": 6}[col]
            rev = self.sort_rev[col] = not self.sort_rev.get(col, True)
            if idx is None:
                self.rows_raw.sort(key=lambda r: (r[3] / r[4]) if r[4] else 0.0, reverse=rev)
            else:
                self.rows_raw.sort(key=lambda r: r[idx], reverse=rev)
            self.fill_table()

        def open_from_table(self, _e):
            sel = self.rtree.selection()
            if sel and sel[0] in self.data:
                self.atree.selection_set(sel[0])
                self.nb.select(0)

        def export_table(self):
            if not self.rows_raw:
                messagebox.showinfo("Nothing to export", "Press 'Run ALL assets' first.")
                return
            p = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
            if p:
                with open(p, "w", newline="") as f:
                    w = csv.writer(f)
                    w.writerow(["asset", "days", "halted", "max_profit", "trades", "solve_ms", "check"])
                    w.writerows(self.rows_raw)
                self.status.set(f"Saved {p}")

        def draw_all(self):
            self.draw_chart()
            self.setup_dag()

        # --------------------------------------------------- price chart
        def reset_view(self):
            n = len(self.cur) if self.cur else 1
            self.v0, self.v1 = 0.0, float(max(1, n - 1))
            self.draw_chart()

        def zoom_trade(self, i):
            if not self.res or i >= len(self.res["trades"]):
                return
            t = self.res["trades"][i]
            pad = max(5, (t["sell_idx"] - t["buy_idx"]) * 0.3)
            self.v0, self.v1 = max(0, t["buy_idx"] - pad), min(len(self.cur) - 1, t["sell_idx"] + pad)
            self.draw_chart()

        def _geo(self):
            W, H = max(self.chart.winfo_width(), 300), max(self.chart.winfo_height(), 240)
            return W, H, 74, 20, 36, 44            # W, H, L, R, T, B

        def draw_chart(self):
            cv = self.chart
            cv.delete("all")
            s, r = self.cur, self.res
            if s is None or len(s) < 2 or r is None:
                return
            W, H, L, Rr, T, B = self._geo()
            n, pw = len(s), W - L - Rr
            v0, v1 = self.v0, self.v1
            i0, i1 = max(0, int(v0)), min(n - 1, int(v1) + 1)
            span = max(v1 - v0, 1e-9)
            vis = i1 - i0 + 1
            P = s.prices
            lo, hi = min(P[i0:i1 + 1]), max(P[i0:i1 + 1])
            logs = self.log_var.get()
            f = (lambda v: math.log10(v)) if logs else (lambda v: v)
            flo, fhi = f(lo), f(hi)
            if fhi - flo < 1e-12:
                flo, fhi = flo - 1, fhi + 1
            X = lambda i: L + (i - v0) / span * pw
            Y = lambda p: T + (H - T - B) * (1 - (f(p) - flo) / (fhi - flo))

            for g in range(5):                                      # y grid
                fv = flo + (fhi - flo) * g / 4
                val = 10 ** fv if logs else fv
                y = T + (H - T - B) * (1 - g / 4)
                cv.create_line(L, y, W - Rr, y, fill=C["grid"])
                cv.create_text(L - 6, y, anchor="e", text=fnum(val), fill=C["muted"], font=("Segoe UI", 9))
            for g in range(6):                                      # x labels
                idx = int(v0 + span * g / 5)
                idx = min(max(idx, 0), n - 1)
                cv.create_text(X(idx), H - B + 14, text=s.dates[idx], fill=C["muted"], font=("Segoe UI", 8))

            for t in r["trades"]:                                   # holding bands
                a, b = max(X(t["buy_idx"]), L), min(X(t["sell_idx"]), W - Rr)
                if b > a:
                    cv.create_rectangle(a, T, b, H - B, fill=C["band"], outline="")

            if vis <= pw * 1.5:                                     # draw every point
                pts = [c for i in range(i0, i1 + 1) for c in (X(i), Y(P[i]))]
                if len(pts) >= 4:
                    cv.create_line(*pts, fill=C["ink"], width=2)
                for i in range(i0, i1 + 1):
                    if not s.ok[i]:
                        cv.create_oval(X(i) - 3, Y(P[i]) - 3, X(i) + 3, Y(P[i]) + 3, fill=C["panel"],
                                       outline=C["halt"], width=2)
                    elif vis <= 150:
                        cv.create_oval(X(i) - 2, Y(P[i]) - 2, X(i) + 2, Y(P[i]) + 2, fill=C["ink"], outline="")
            else:                                                   # min/max envelope per pixel column
                step = vis / pw
                for px in range(int(pw)):
                    a = i0 + int(px * step)
                    b = max(a + 1, i0 + int((px + 1) * step))
                    seg = P[a:b + 1]
                    x = L + px
                    cv.create_line(x, Y(min(seg)), x, Y(max(seg)) - 1, fill=C["ink"])
                    if vis <= pw * 4 and False in s.ok[a:b]:
                        cv.create_line(x, H - B - 6, x, H - B, fill=C["halt"])

            for i, t in enumerate(r["trades"], 1):
                for idx, price, up, tag, col in ((t["buy_idx"], t["buy_price"], True, f"BUY {i}", C["buy"]),
                                                 (t["sell_idx"], t["sell_price"], False, f"SELL {i}", C["sell"])):
                    if v0 <= idx <= v1:
                        x, y = X(idx), Y(price)
                        if up:
                            cv.create_polygon(x, y - 4, x - 8, y + 10, x + 8, y + 10, fill=col, outline="")
                            cv.create_text(x, min(y + 22, H - B - 14), text=tag, fill=col, font=("Segoe UI", 9, "bold"))
                        else:
                            cv.create_polygon(x, y + 4, x - 8, y - 10, x + 8, y - 10, fill=col, outline="")
                            cv.create_text(x, max(y - 22, T + 14), text=tag, fill=col, font=("Segoe UI", 9, "bold"))
            cv.create_text(L, 14, anchor="w", font=("Segoe UI", 11, "bold"),
                           text=f"{s.name}  |  {n:,} days  |  max profit {fnum(r['profit'])}  |  showing days {i0 + 1:,}-{i1 + 1:,}")
            cv.create_text(W - Rr, H - 8, anchor="e", fill=C["muted"], font=("Segoe UI", 8),
                           text="blue band = holding   red ticks / hollow dots = halted days   ▲ buy  ▼ sell")
            self._geom = (L, pw, T, H - B)

        def _idx_at(self, x):
            L, pw, *_ = self._geom
            return self.v0 + (x - L) / pw * (self.v1 - self.v0)

        def on_wheel(self, e, direction=None):
            if not self.cur or len(self.cur) < 3 or not hasattr(self, "_geom"):
                return
            d = direction if direction is not None else (1 if e.delta > 0 else -1)
            anchor = self._idx_at(e.x)
            f = 0.75 if d > 0 else 1 / 0.75
            n = len(self.cur) - 1
            span = min(max((self.v1 - self.v0) * f, min(10, n)), n)
            frac = (anchor - self.v0) / max(self.v1 - self.v0, 1e-9)
            self.v0 = min(max(0, anchor - frac * span), n - span)
            self.v1 = self.v0 + span
            self.draw_chart()

        def on_press(self, e):
            self.drag = (e.x, self.v0, self.v1)

        def on_drag(self, e):
            if not self.drag or not hasattr(self, "_geom"):
                return
            x0, a, b = self.drag
            n = len(self.cur) - 1
            shift = -(e.x - x0) / self._geom[1] * (b - a)
            shift = min(max(shift, -a), n - b)
            self.v0, self.v1 = a + shift, b + shift
            self.draw_chart()

        def on_move(self, e):
            if not self.cur or not hasattr(self, "_geom"):
                return
            L, pw, T, Bt = self._geom
            i = int(round(self._idx_at(e.x)))
            if 0 <= i < len(self.cur) and L <= e.x <= L + pw:
                s = self.cur
                self.status.set(f"{s.dates[i]}   price {fnum(s.prices[i])}   day #{i + 1:,}" +
                                ("" if s.ok[i] else "   HALTED"))
                self.chart.delete("cross")
                self.chart.create_line(e.x, T, e.x, Bt, fill=C["muted"], dash=(2, 3), tags="cross")

        def on_dbl(self, e):
            if not self.cur or not hasattr(self, "_geom"):
                return
            i = int(round(self._idx_at(e.x)))
            self.set_start(i - int(self.win_var.get()) // 2)
            self.nb.select(1)

        # --------------------------------------------------- DAG window
        def setup_dag(self):
            if not self.res:
                self.dag.delete("all")
                return
            n = self.res["n"]
            self.start_sc.configure(from_=0, to=max(1, n - 2))
            labels = ["Start of timeline", "End of timeline"]
            idxs = [0, max(0, n - int(self.win_var.get()))]
            for i, t in enumerate(self.res["trades"], 1):
                labels += [f"Trade {i}: BUY", f"Trade {i}: SELL"]
                idxs += [t["buy_idx"] - 3, t["sell_idx"] - 3]
            self._jumps = idxs
            self.jump.configure(values=labels)
            first = self.res["trades"][0]["buy_idx"] - 3 if self.res["trades"] else 0
            self.set_start(first)

        def set_start(self, v):
            if not self.res:
                return
            v = int(min(max(0, v), max(0, self.res["n"] - 2)))
            self.start_var.set(v)
            self.start_sc.set(v)
            self.start_lbl.configure(text=f"{v + 1:,}")
            self.schedule_dag()

        def on_scale(self):
            if not self.res:
                return
            v = int(float(self.start_sc.get()))
            if v != self.start_var.get():
                self.start_var.set(v)
                self.start_lbl.configure(text=f"{v + 1:,}")
                self.schedule_dag()

        def shift(self, sign):
            self.set_start(self.start_var.get() + sign * max(1, int(self.win_var.get()) // 2))

        def do_jump(self):
            i = self.jump.current()
            if i >= 0:
                self.set_start(self._jumps[i])

        def schedule_dag(self):
            if self.dag_job:
                self.after_cancel(self.dag_job)
            self.dag_job = self.after(30, self.draw_dag)

        def draw_dag(self, upto=None):
            self.dag_job = None
            cv = self.dag
            cv.delete("all")
            r, s = self.res, self.cur
            if not r:
                cv.create_text(30, 30, anchor="w", fill=C["muted"], text="Solve an asset first.")
                return
            n, S, best, ps = r["n"], r["S"], r["best"], r["path_stage"]
            try:
                W = max(3, min(30, int(self.win_var.get())))
            except (ValueError, tk.TclError):
                W = 12
            d0 = min(self.start_var.get(), max(0, n - 1))
            cols = max(1, min(W, n - d0))
            if upto is None:
                upto = cols
            final = upto >= cols
            LM, TM, DY, RAD = 150, 74, 74, 15
            DX = max(64, min(110, (max(cv.winfo_width(), 600) - LM - 30) / cols))
            pos = lambda j, st: (LM + j * DX, TM + (S - 1 - st) * DY)
            cv.configure(scrollregion=(0, 0, LM + (cols + 1) * DX, TM + S * DY + 80))
            label_all = cols <= 7

            for st in range(S):
                y = pos(0, st)[1]
                name = "S0  no shares" if st == 0 else (f"S{st}  holding (trade {(st + 1) // 2})" if st % 2
                                                        else f"S{st}  sold {st // 2} trade(s)")
                cv.create_line(LM - 20, y, LM + cols * DX + 20, y, fill=C["grid"])
                cv.create_text(10, y, anchor="w", text=name, font=("Segoe UI", 9, "bold"))

            for j in range(cols + 1):
                d, x = d0 + j, LM + j * DX
                if d < n:
                    good = s.ok[d]
                    colr = C["ink"] if good else C["halt"]
                    cv.create_text(x, 12, text=s.dates[d], font=("Segoe UI", 8, "bold"), fill=colr)
                    cv.create_text(x, 28, text=f"day #{d + 1:,}", font=("Segoe UI", 8), fill=C["muted"])
                    cv.create_text(x, 44, text=fnum(s.prices[d]) + ("" if good else " HALTED"),
                                   font=("Segoe UI", 9, "bold"), fill=colr)
                else:
                    cv.create_text(x, 12, text="end", font=("Segoe UI", 9, "bold"), fill=C["muted"])

            def draw_edge(d, st, st2, action, w, on_path, reach):
                (x1, y1), (x2, y2) = pos(d - d0, st), pos(d + 1 - d0, st2)
                col = {"WAIT": C["wait"], "BUY": C["buy"], "SELL": C["sell"]}[action]
                if on_path:
                    cv.create_line(x1, y1, x2, y2, fill=C["path"], width=6, capstyle="round")
                cv.create_line(x1, y1, x2, y2, fill=col, width=2 if reach else 1, arrow="last",
                               arrowshape=(9, 11, 4), dash=() if reach else (3, 3))
                if action != "WAIT" and (on_path or label_all):
                    tid = cv.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=f"{w:+.4g}",
                                         font=("Segoe UI", 8, "bold"), fill=col)
                    bb = cv.bbox(tid)
                    bg = cv.create_rectangle(bb[0] - 1, bb[1], bb[2] + 1, bb[3], fill=C["panel"], outline="")
                    cv.tag_lower(bg, tid)

            for pass_path in (False, True):
                if pass_path and not final:
                    break
                for j in range(min(upto, cols)):
                    d = d0 + j
                    p = s.prices[d]
                    for st in range(S):
                        reach = best[d * S + st] != NEG_INF
                        on_wait = final and ps[d] == st and ps[d + 1] == st
                        if on_wait == pass_path:
                            draw_edge(d, st, st, "WAIT", 0.0, on_wait, reach)
                        if s.ok[d] and st < S - 1:
                            on_act = final and ps[d] == st and ps[d + 1] == st + 1
                            if on_act == pass_path:
                                draw_edge(d, st, st + 1, "BUY" if st % 2 == 0 else "SELL",
                                          -p if st % 2 == 0 else p - r["fee"], on_act, reach)

            for j in range(min(upto, cols) + 1):
                d = d0 + j
                if d > n:
                    break
                for st in range(S):
                    x, y = pos(j, st)
                    v = best[d * S + st]
                    reach = v != NEG_INF
                    onp = final and ps[d] == st
                    item = cv.create_oval(x - RAD, y - RAD, x + RAD, y + RAD,
                                          fill=C["gold"] if onp else (C["node"] if reach else C["dead"]),
                                          outline=C["path"] if onp else C["muted"], width=2 if onp else 1)
                    cv.create_text(x, y, text=f"{st}", font=("Segoe UI", 8), fill=C["ink"])
                    cv.create_text(x, y + RAD + 9, text=fnum(v) if reach else "-inf", font=("Segoe UI", 8),
                                   fill=C["ink"] if reach else C["muted"])
                    tip = (f"node (day #{d + 1:,}, stage {st}):  best profit reaching it = {v:,.6g}"
                           if reach else f"node (day #{d + 1:,}, stage {st}):  unreachable")
                    cv.tag_bind(item, "<Enter>", lambda e, t=tip: self.status.set(t))

            ly = TM + S * DY + 10
            for i, (nm, col) in enumerate([("WAIT (0)", C["wait"]), ("BUY (-price)", C["buy"]),
                                           ("SELL (+price - fee)", C["sell"]), ("optimal path", C["path"])]):
                x = LM + i * 175
                cv.create_line(x, ly, x + 30, ly, fill=col, width=4 if i == 3 else 3)
                cv.create_text(x + 36, ly, anchor="w", text=nm, font=("Segoe UI", 9))
            cv.create_text(LM, ly + 24, anchor="w", fill=C["muted"], font=("Segoe UI", 9),
                           text=f"Days {d0 + 1:,}-{min(d0 + cols, n):,} of {n:,}.  Number under a node = best total profit of any "
                                f"path reaching it (computed over ALL earlier days).  Dashed = unreachable.")

        def animate(self):
            if not self.res:
                return
            self.anim_stop()
            self.nb.select(1)
            n, d0 = self.res["n"], self.start_var.get()
            cols = max(1, min(int(self.win_var.get()), n - d0))
            self._step = 0

            def tick():
                self._step += 1
                self.draw_dag(upto=self._step)
                self.anim = self.after(450, tick) if self._step < cols else None
            tick()

        def anim_stop(self):
            if self.anim:
                self.after_cancel(self.anim)
                self.anim = None

        # --------------------------------------------------- tests tab
        def do_selftest(self):
            self.nb.select(4)
            self._write(self.log, "Comparing fast DAG solver, explicit-graph reference and exhaustive search\n"
                                  "on 500 random tiny cases...\n")

            def work(emit):
                return run_self_test(500)

            def done(res):
                wp, wt = res
                self._write(self.log, f"profit mismatches: {wp}\ntrade-choice mismatches: {wt}\n"
                                      + ("PASS - all three agree\n" if wp == wt == 0 else "FAIL\n"), True)
            self.run_bg(work, done, "Running correctness test...")

        def do_speed(self):
            self.nb.select(4)
            self._write(self.log, f"{'days':>7} | {'DAG ms':>9} | {'brute ms':>10} | {'DAG edges':>10} | {'brute pairs':>12} | same?\n")

            def work(emit):
                rng = random.Random(1)
                for n in (100, 500, 1000, 2000, 4000):
                    s = random_series("T", n, rng)
                    days = s.days()
                    tg = median_time(lambda: solve_dag(s.prices, s.ok, 1, 0))
                    tb = median_time(lambda: brute_force_pairs(days, 0), 2)
                    a = solve_dag(s.prices, s.ok, 1, 0)
                    b, cmp_ = brute_force_pairs(days, 0)
                    emit(None, None, f"{n:7d} | {tg * 1000:9.2f} | {tb * 1000:10.2f} | {a['relaxations']:10d} | "
                                     f"{cmp_:12d} | {abs(a['profit'] - b) < 1e-9}\n")
                return None
            self.run_bg(work, lambda _r: self._write(
                self.log, "\nDAG work grows linearly (days x stages); brute force grows as days squared.\n", True),
                "Timing...")

        def do_stress(self):
            self.nb.select(4)
            self._write(self.log, "200,000 days, 3 trades, fee 0.5 ...\n")

            def work(emit):
                s = random_series("BIG", 200000, random.Random(7))
                return solve_dag(s.prices, s.ok, 3, 0.5, emit)
            self.run_bg(work, lambda r: self._write(
                self.log, f"profit {fnum(r['profit'])}   time {r['seconds']:.2f} s   "
                          f"nodes {r['nodes']:,}   edges {r['relaxations']:,}\n", True), "Stress test...")

    App().mainloop()


# ======================================================================
# PART 6: CONSOLE MODES
# ======================================================================
def cli(path, k=1, fee=0.0):
    t = time.perf_counter()
    data, rep = load_csv(path)
    print(f"Loaded {rep['rows_kept']:,} of {rep['rows_read']:,} rows in {time.perf_counter() - t:.2f}s  "
          f"(missing {rep['missing_price']}, invalid price {rep['invalid_price']}, "
          f"bad status {rep['invalid_status']}, duplicates {rep['duplicates']})")
    print(f"{'asset':14s} {'days':>8s} {'halted':>7s} {'profit':>16s} {'trades':>6s} {'ms':>9s}  check")
    for name, n, h, p, tr, ms, chk in solve_all(data, k, fee):
        print(f"{name:14s} {n:8,d} {h:7,d} {fnum(p):>16s} {tr:6d} {ms:9.1f}  {chk}")


def demo():
    small = make_days([7, 1, 5, 3, 6, 4, 9, 2])
    p, ok = [d[1] for d in small], [d[2] for d in small]
    print("1 trade :", fnum(solve_dag(p, ok, 1)["profit"]), "(expected 8)")
    print("2 trades:", fnum(solve_dag(p, ok, 2)["profit"]), "(expected 10)")
    print("self-test (profit mismatches, trade mismatches):", run_self_test(500))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--demo" in sys.argv:
        demo()
    elif "--cli" in sys.argv:
        cli(args[0], int(args[1]) if len(args) > 1 else 1, float(args[2]) if len(args) > 2 else 0.0)
    else:
        try:
            launch_gui(args[0] if args else None)
        except Exception as e:
            if e.__class__.__name__ == "TclError" or isinstance(e, ImportError):
                print(f"GUI unavailable ({e}). Running console demo instead.\n")
                demo()
            else:
                raise
