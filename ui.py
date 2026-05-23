import datetime

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import database as db

# ── matplotlib CJK font ──
import matplotlib
matplotlib.rcParams["font.family"] = ["Microsoft YaHei", "Segoe UI", "sans-serif"]

# ── Patch CTkFont default to Microsoft YaHei ──
import customtkinter.windows.widgets.font as _ctk_font_mod
_orig = _ctk_font_mod.CTkFont.__init__
def _patched(self, family=None, *args, **kwargs):
    if family is None:
        family = "Microsoft YaHei"
    _orig(self, family=family, *args, **kwargs)
_ctk_font_mod.CTkFont.__init__ = _patched

# ── Color palette (GitHub-dark inspired) ──
BG       = "#0d1117"
SURFACE  = "#161b22"
CARD     = "#21262d"
BORDER   = "#30363d"
PRIMARY  = "#58a6ff"
SUCCESS  = "#3fb950"
WARNING  = "#d29922"
DANGER   = "#f85149"
TEXT     = "#f0f6fc"
TEXT_SEC = "#8b949e"

CHART_COLORS = ["#58a6ff", "#3fb950", "#d29922", "#f85149", "#bc8cff", "#79c0ff"]

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


def _fmt(seconds: int) -> str:
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{h} 小时 {m} 分"
    if m:
        return f"{m} 分 {s} 秒"
    return f"{s} 秒"


# ═══════════════════════════════════════════════════════════════
class UsageApp(ctk.CTk):
    def __init__(self, tracker):
        super().__init__()
        self.tracker = tracker
        self.title("使用时间统计")
        self.geometry("1100x720")
        self.minsize(960, 640)
        self.configure(fg_color=BG)

        self._pulse = False  # timer blink state

        self._build_ui()
        self._pulse_loop()
        self._refresh_loop()

    # ── UI 构建 ────────────────────────────────────────────────

    def _build_ui(self):
        # ── 顶部栏 ──
        top = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0, height=50)
        top.pack(fill="x")
        top.pack_propagate(False)

        ctk.CTkLabel(
            top, text="📊  使用时间统计",
            font=ctk.CTkFont(size=18, weight="bold"), text_color=TEXT
        ).pack(side="left", padx=24)

        self._status_lbl = ctk.CTkLabel(
            top, text="追踪中 ...",
            font=ctk.CTkFont(size=12), text_color=TEXT_SEC
        )
        self._status_lbl.pack(side="right", padx=24)

        # ── 主区域 (可滚动) ──
        body = ctk.CTkScrollableFrame(self, fg_color=BG)
        body.pack(fill="both", expand=True, padx=20, pady=(14, 20))

        # ── 第一行：三个统计卡片 ──
        stat_row = ctk.CTkFrame(body, fg_color="transparent")
        stat_row.pack(fill="x", pady=(0, 16))
        stat_row.grid_columnconfigure((0, 1, 2), weight=1, uniform="stat")

        self._card_today = self._stat_card(stat_row, "📅  今日总计", "—", 0, PRIMARY)
        self._card_week  = self._stat_card(stat_row, "📅  本周总计", "—", 1, SUCCESS)
        self._card_sess  = self._stat_card(stat_row, "⚡  当前会话", "—", 2, DANGER)

        # ── 第二行：图表 (左右对称) ──
        chart_row = ctk.CTkFrame(body, fg_color="transparent")
        chart_row.pack(fill="x", pady=(0, 16))
        chart_row.grid_columnconfigure((0, 1), weight=1, uniform="chart")

        # 左图表
        box1 = ctk.CTkFrame(chart_row, fg_color=CARD, corner_radius=10)
        box1.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ctk.CTkLabel(
            box1, text="今日各应用时长",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=TEXT
        ).pack(anchor="w", padx=14, pady=(10, 0))

        self._fig1 = Figure(figsize=(4.5, 2.8), dpi=90, facecolor=CARD)
        self._ax1 = self._fig1.add_subplot(111)
        self._canvas1 = FigureCanvasTkAgg(self._fig1, master=box1)
        self._canvas1.get_tk_widget().pack(fill="both", expand=True, padx=6, pady=(0, 6))

        # 右图表
        box2 = ctk.CTkFrame(chart_row, fg_color=CARD, corner_radius=10)
        box2.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        ctk.CTkLabel(
            box2, text="近 7 天趋势",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=TEXT
        ).pack(anchor="w", padx=14, pady=(10, 0))

        self._fig2 = Figure(figsize=(4.5, 2.8), dpi=90, facecolor=CARD)
        self._ax2 = self._fig2.add_subplot(111)
        self._canvas2 = FigureCanvasTkAgg(self._fig2, master=box2)
        self._canvas2.get_tk_widget().pack(fill="both", expand=True, padx=6, pady=(0, 6))

        # ── 第三行：应用排行 ──
        bottom = ctk.CTkFrame(body, fg_color=CARD, corner_radius=10)
        bottom.pack(fill="x")
        ctk.CTkLabel(
            bottom, text="📋  应用排行（今日）",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=TEXT
        ).pack(anchor="w", padx=14, pady=(10, 6))

        self._app_box = ctk.CTkFrame(bottom, fg_color="transparent")
        self._app_box.pack(fill="x", padx=14, pady=(0, 12))
        self._app_empty_lbl = ctk.CTkLabel(
            self._app_box, text="暂无数据，切换窗口后自动记录",
            font=ctk.CTkFont(size=12), text_color=TEXT_SEC
        )
        self._app_empty_lbl.pack(pady=14)

    # ── 统计卡片工厂 ──

    def _stat_card(self, parent, title, value, col, accent):
        f = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=10,
                         border_width=1, border_color=BORDER)
        f.grid(row=0, column=col, sticky="nsew", padx=6, pady=4)
        ctk.CTkLabel(
            f, text=title,
            font=ctk.CTkFont(size=12), text_color=TEXT_SEC
        ).pack(anchor="w", padx=16, pady=(12, 2))
        lbl = ctk.CTkLabel(
            f, text=value,
            font=ctk.CTkFont(size=24, weight="bold"), text_color=accent
        )
        lbl.pack(anchor="w", padx=16, pady=(0, 12))
        return lbl

    # ── 进度条行 ──

    def _progress_row(self, parent, rank, name, seconds, max_secs):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=3)
        row.grid_columnconfigure(0, weight=0)  # 排名
        row.grid_columnconfigure(1, weight=0)  # 名称
        row.grid_columnconfigure(2, weight=1)  # 进度条
        row.grid_columnconfigure(3, weight=0)  # 时长

        ctk.CTkLabel(
            row, text=f"#{rank}",
            font=ctk.CTkFont(size=11), text_color=TEXT_SEC, width=28
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            row, text=name,
            font=ctk.CTkFont(size=12), text_color=TEXT,
            width=100, anchor="w"
        ).grid(row=0, column=1, sticky="w", padx=(0, 8))

        bar = ctk.CTkProgressBar(
            row, height=10, corner_radius=5,
            progress_color=PRIMARY, fg_color=SURFACE
        )
        bar.grid(row=0, column=2, sticky="ew", padx=(0, 8))
        bar.set(min(seconds / max_secs, 1.0) if max_secs > 0 else 0)

        ctk.CTkLabel(
            row, text=_fmt(seconds),
            font=ctk.CTkFont(size=11, weight="bold"), text_color=PRIMARY,
            width=90, anchor="e"
        ).grid(row=0, column=3, sticky="e")

    # ── 动画：计时器脉冲 ──

    def _pulse_loop(self):
        if self.tracker.current_app:
            self._pulse = not self._pulse
            self._card_sess.configure(
                text_color="#ff7b72" if self._pulse else DANGER)
        else:
            self._card_sess.configure(text_color=DANGER)
        self.after(800, self._pulse_loop)

    # ── 定时刷新 ──

    def _refresh_loop(self):
        self._update_session()
        self._update_stats()
        self._update_charts()
        self._update_app_list()
        self.after(2000, self._refresh_loop)

    def _update_session(self):
        app = self.tracker.current_app
        secs = self.tracker.session_elapsed
        if app:
            self._card_sess.configure(text=f"{app} · {_fmt(secs)}")
        else:
            self._card_sess.configure(text="—")
        self._status_lbl.configure(
            text=f"追踪中 · {datetime.datetime.now():%H:%M:%S}")

    def _update_stats(self):
        self._card_today.configure(text=_fmt(db.get_today_total()))
        self._card_week.configure(text=_fmt(db.get_week_total()))

    def _update_charts(self):
        self._plot_today()
        self._plot_week()

    def _plot_today(self):
        self._ax1.clear()
        rows = db.get_today_summary()
        if not rows:
            self._ax1.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                           color=TEXT_SEC, fontsize=12)
            self._ax1.set_facecolor(CARD)
            self._canvas1.draw_idle()
            return

        names = [(r[0][:14] + "…") if len(r[0]) > 14 else r[0] for r in rows[:6]]
        vals  = [r[1] / 60 for r in rows[:6]]
        cols  = CHART_COLORS[:len(names)]

        self._ax1.barh(names[::-1], vals[::-1], color=cols[::-1],
                       height=0.55, edgecolor="none")
        self._ax1.set_xlabel("分钟", color=TEXT_SEC, fontsize=8)
        self._ax1.tick_params(colors=TEXT_SEC, labelsize=8)
        self._ax1.set_facecolor(CARD)
        self._fig1.patch.set_facecolor(CARD)
        for s in self._ax1.spines.values():
            s.set_visible(False)
        self._ax1.grid(axis="x", alpha=0.08)
        self._ax1.invert_yaxis()
        self._canvas1.draw_idle()

    def _plot_week(self):
        self._ax2.clear()
        rows = db.get_daily_totals(7)
        if not rows:
            self._ax2.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                           color=TEXT_SEC, fontsize=12)
            self._ax2.set_facecolor(CARD)
            self._canvas2.draw_idle()
            return

        dates, vals = [], []
        for d_str, secs in rows:
            dates.append(datetime.date.fromisoformat(d_str).strftime("%m/%d"))
            vals.append(secs / 3600)

        self._ax2.plot(dates, vals, color=PRIMARY, linewidth=2.5,
                       marker="o", markersize=6,
                       markerfacecolor=PRIMARY, markeredgecolor=CARD,
                       markeredgewidth=1.5)
        self._ax2.fill_between(range(len(dates)), vals, alpha=0.1, color=PRIMARY)
        self._ax2.set_ylabel("小时", color=TEXT_SEC, fontsize=8)
        self._ax2.tick_params(colors=TEXT_SEC, labelsize=8)
        self._ax2.set_facecolor(CARD)
        self._fig2.patch.set_facecolor(CARD)
        for s in self._ax2.spines.values():
            s.set_visible(False)
        self._ax2.grid(alpha=0.08)
        self._canvas2.draw_idle()

    def _update_app_list(self):
        rows = db.get_today_summary()
        for w in self._app_box.winfo_children():
            w.destroy()

        if not rows:
            self._app_empty_lbl = ctk.CTkLabel(
                self._app_box, text="暂无数据，切换窗口后自动记录",
                font=ctk.CTkFont(size=12), text_color=TEXT_SEC
            )
            self._app_empty_lbl.pack(pady=14)
            return

        max_secs = rows[0][1]
        for i, (name, secs) in enumerate(rows[:8], 1):
            self._progress_row(self._app_box, i, name, secs, max_secs)

    # ── 关闭 ──

    def on_close(self):
        self.tracker.stop()
        self.destroy()
