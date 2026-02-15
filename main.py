import json
import random
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import simpledialog
from tkinter import ttk

try:
    import winsound
except ImportError:
    winsound = None


@dataclass
class Cell:
    value: int
    item_ids: list[int]


class AudioManager:
    def __init__(self, base_dir: Path, root: tk.Tk) -> None:
        self.base_dir = base_dir
        self.root = root
        self.bgm_path = self.base_dir / "assets" / "bgm.wav"
        self.clear_path = self.base_dir / "assets" / "clear.wav"
        self.fail_path = self.base_dir / "assets" / "fail.wav"
        self.bgm_playing = False
        self.bgm_enabled = True

    def start_bgm(self) -> None:
        if not self.bgm_enabled:
            return
        if winsound is None or not self.bgm_path.exists():
            return
        try:
            winsound.PlaySound(str(self.bgm_path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
            self.bgm_playing = True
        except RuntimeError:
            pass

    def stop_bgm(self) -> None:
        if winsound is None:
            return
        try:
            winsound.PlaySound(None, 0)
            self.bgm_playing = False
        except RuntimeError:
            pass

    def set_bgm_enabled(self, enabled: bool) -> None:
        self.bgm_enabled = enabled
        if enabled:
            self.start_bgm()
        else:
            self.stop_bgm()

    def play_clear(self) -> None:
        self._play_effect(self.clear_path, "clear")

    def play_fail(self) -> None:
        self._play_effect(self.fail_path, "fail")

    def _play_effect(self, effect_path: Path, mode: str) -> None:
        # winsound는 동시 믹싱이 안 되므로 BGM 재생 중엔 bell로 대체한다.
        if self.bgm_playing:
            self._play_bell(mode)
            return

        if winsound is not None and effect_path.exists():
            try:
                winsound.PlaySound(str(effect_path), winsound.SND_FILENAME | winsound.SND_ASYNC)
                return
            except RuntimeError:
                pass
        self._play_bell(mode)

    def _play_bell(self, mode: str) -> None:
        self.root.bell()
        if mode == "fail":
            self.root.after(60, self.root.bell)


class AppleBoxGame:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("사과 박스 게임")
        self.root.resizable(False, False)
        self.root.configure(bg="#0f172a")

        self.base_dir = Path(__file__).resolve().parent
        self.rank_path = self.base_dir / "rankings.json"
        self.colors = {
            "window_bg": "#0f172a",
            "panel_bg": "#111827",
            "panel_inner": "#1f2937",
            "accent": "#22c55e",
            "accent_soft": "#34d399",
            "text_main": "#e5e7eb",
            "text_muted": "#94a3b8",
            "board_frame": "#16a34a",
            "board_inner": "#b7efc5",
            "board_cell_a": "#d8f8df",
            "board_cell_b": "#cbf3d3",
        }
        self.setup_styles()

        self.rows = 10
        self.cols = 17
        self.cell_size = 34
        self.time_limit = 120

        self.board_w = self.cols * self.cell_size
        self.board_h = self.rows * self.cell_size

        self.outer_pad = 16
        self.inner_pad = 18
        self.top_pad = 24
        self.right_timer_w = 26
        self.bottom_panel_h = 34

        self.inner_x = self.outer_pad + self.inner_pad
        self.inner_y = self.outer_pad + self.top_pad
        self.board_x = self.inner_x + 10
        self.board_y = self.inner_y + 10
        self.timer_x = self.board_x + self.board_w + 12
        self.timer_y = self.board_y + 16
        self.timer_h = self.board_h - 32

        self.inner_w = (self.board_x - self.inner_x) + self.board_w + 12 + self.right_timer_w + 10
        self.inner_h = (self.board_y - self.inner_y) + self.board_h + self.bottom_panel_h

        self.width = self.inner_x + self.inner_w + self.inner_pad
        self.height = self.inner_y + self.inner_h + self.inner_pad

        self.score = 0
        self.moves = 0
        self.time_left = self.time_limit
        self.game_over = False
        self.started = False
        self.paused = False
        self.timer_job: str | None = None

        self.grid: list[list[Cell | None]] = [[None for _ in range(self.cols)] for _ in range(self.rows)]
        self.drag_start: tuple[int, int] | None = None
        self.drag_current: tuple[int, int] | None = None
        self.selection_cell_tag = "selection_cell"

        self.main_area = tk.Frame(root, bg=self.colors["window_bg"])
        self.main_area.pack(padx=8, pady=(8, 0))

        self.canvas = tk.Canvas(
            self.main_area,
            width=self.width,
            height=self.height,
            bg=self.colors["window_bg"],
            highlightthickness=0,
        )
        self.canvas.pack(side="left")

        self.rank_frame = tk.Frame(self.main_area, bg=self.colors["panel_bg"], bd=0)
        self.rank_frame.pack(side="left", fill="y", padx=(10, 0), pady=16)
        self.rank_title = tk.Label(
            self.rank_frame,
            text="TOP 10 랭킹",
            bg=self.colors["accent"],
            fg="#052e16",
            font=("Segoe UI", 12, "bold"),
            padx=10,
            pady=8,
        )
        self.rank_title.pack(fill="x")
        self.rank_list = ttk.Treeview(
            self.rank_frame,
            columns=("rank", "name", "score"),
            show="headings",
            height=18,
        )
        self.rank_list.heading("rank", text="순위")
        self.rank_list.heading("name", text="이름")
        self.rank_list.heading("score", text="점수")
        self.rank_list.column("rank", width=50, anchor="center", stretch=False)
        self.rank_list.column("name", width=120, anchor="w", stretch=False)
        self.rank_list.column("score", width=70, anchor="e", stretch=False)
        self.rank_list.pack(fill="both", expand=True, padx=8, pady=8)

        self.draw_static_layout()
        self.create_hud_items()

        self.selection_id = self.canvas.create_rectangle(0, 0, 0, 0, outline="#0ea5e9", width=3, state="hidden")
        self.pause_overlay_id = self.canvas.create_rectangle(
            self.board_x,
            self.board_y,
            self.board_x + self.board_w,
            self.board_y + self.board_h,
            fill="#0b1f35",
            stipple="gray50",
            outline="",
            state="hidden",
        )
        self.pause_text_id = self.canvas.create_text(
            self.board_x + self.board_w // 2,
            self.board_y + self.board_h // 2,
            text="일시정지",
            fill="white",
            font=("Malgun Gothic", 28, "bold"),
            state="hidden",
        )

        control_frame = tk.Frame(root, bg=self.colors["window_bg"])
        control_frame.pack(fill="x", padx=24, pady=(4, 10))
        self.start_btn = ttk.Button(control_frame, text="Start", command=self.start_game, style="Primary.TButton")
        self.start_btn.pack(side="left", padx=(0, 6))
        self.reset_btn = ttk.Button(control_frame, text="Reset", command=self.reset_game, style="Secondary.TButton")
        self.reset_btn.pack(side="left")

        self.pause_btn = ttk.Button(control_frame, text="일시정지", command=self.toggle_pause, style="Secondary.TButton")
        self.pause_btn.pack(side="left", padx=8)

        self.light_var = tk.BooleanVar(value=True)
        self.light_chk = ttk.Checkbutton(
            control_frame,
            text="Light Colors",
            variable=self.light_var,
            command=self.toggle_light_mode,
            style="Game.TCheckbutton",
        )
        self.light_chk.pack(side="right", padx=(0, 10))

        self.bgm_var = tk.BooleanVar(value=True)
        self.bgm_chk = ttk.Checkbutton(
            control_frame,
            text="BGM",
            variable=self.bgm_var,
            command=self.toggle_bgm,
            style="Game.TCheckbutton",
        )
        self.bgm_chk.pack(side="right", padx=10)

        self.note_lbl = tk.Label(
            control_frame,
            text="♪",
            bg=self.colors["window_bg"],
            fg=self.colors["accent_soft"],
            font=("Segoe UI Symbol", 16, "bold"),
        )
        self.note_lbl.pack(side="right")

        self.start_overlay_id = self.canvas.create_rectangle(
            self.board_x,
            self.board_y,
            self.board_x + self.board_w,
            self.board_y + self.board_h,
            fill="#0b1f35",
            stipple="gray50",
            outline="",
            state="normal",
        )
        self.start_text_id = self.canvas.create_text(
            self.board_x + self.board_w // 2,
            self.board_y + self.board_h // 2,
            text="START 버튼을 눌러 시작",
            fill="white",
            font=("Malgun Gothic", 24, "bold"),
            state="normal",
        )

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.root.bind("<space>", self.toggle_pause)

        self.audio = AudioManager(self.base_dir, self.root)

        self.reset_game()
        self.refresh_rank_panel()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def setup_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure(
            "Primary.TButton",
            font=("Segoe UI", 10, "bold"),
            foreground="#052e16",
            background=self.colors["accent"],
            padding=(12, 6),
            borderwidth=0,
        )
        style.map("Primary.TButton", background=[("active", "#16a34a"), ("pressed", "#15803d")])

        style.configure(
            "Secondary.TButton",
            font=("Segoe UI", 10, "bold"),
            foreground=self.colors["text_main"],
            background="#374151",
            padding=(12, 6),
            borderwidth=0,
        )
        style.map("Secondary.TButton", background=[("active", "#4b5563"), ("pressed", "#334155")])

        style.configure(
            "Game.TCheckbutton",
            font=("Segoe UI", 10, "bold"),
            foreground=self.colors["text_main"],
            background=self.colors["window_bg"],
        )
        style.map("Game.TCheckbutton", background=[("active", self.colors["window_bg"])])

        style.configure(
            "Treeview",
            background="#f8fffa",
            fieldbackground="#f8fffa",
            foreground="#14532d",
            rowheight=24,
            font=("Segoe UI", 10, "bold"),
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
            background="#16a34a",
            foreground="white",
            borderwidth=0,
            padding=4,
        )
        style.map("Treeview", background=[("selected", "#86efac")], foreground=[("selected", "#14532d")])
        style.map("Treeview.Heading", background=[("active", "#15803d")])

    def draw_static_layout(self) -> None:
        for i in range(self.height):
            ratio = i / max(1, self.height)
            g = int(20 + ratio * 18)
            b = int(35 + ratio * 28)
            color = f"#0f{g:02x}{b:02x}"
            self.canvas.create_line(0, i, self.width, i, fill=color, tags=("decor",))

        self.canvas.create_rectangle(
            self.outer_pad + 4,
            self.outer_pad + 6,
            self.width - self.outer_pad + 4,
            self.height - self.outer_pad - 2,
            fill="#0b1220",
            outline="",
            tags=("decor",),
        )
        self.canvas.create_rectangle(
            self.outer_pad,
            self.outer_pad,
            self.width - self.outer_pad,
            self.height - self.outer_pad - 6,
            fill=self.colors["board_frame"],
            outline="#15803d",
            width=3,
            tags=("decor",),
        )
        self.canvas.create_rectangle(
            self.inner_x,
            self.inner_y,
            self.inner_x + self.inner_w,
            self.inner_y + self.inner_h,
            fill=self.colors["board_inner"],
            outline="#dcfce7",
            width=3,
            tags=("decor",),
        )

        for r in range(self.rows):
            for c in range(self.cols):
                x = self.board_x + c * self.cell_size
                y = self.board_y + r * self.cell_size
                tone = self.colors["board_cell_a"] if (r + c) % 2 == 0 else self.colors["board_cell_b"]
                self.canvas.create_rectangle(
                    x,
                    y,
                    x + self.cell_size,
                    y + self.cell_size,
                    fill=tone,
                    outline="#d8f7d8",
                    width=1,
                    tags=("board_bg",),
                )

        self.canvas.create_rectangle(
            self.timer_x,
            self.timer_y,
            self.timer_x + self.right_timer_w,
            self.timer_y + self.timer_h,
            fill="#ecfdf3",
            outline="#16a34a",
            width=2,
            tags=("decor",),
        )

    def create_hud_items(self) -> None:
        self.score_id = self.canvas.create_text(
            self.board_x,
            self.board_y - 12,
            anchor="sw",
            text="SCORE 0",
            font=("Segoe UI", 13, "bold"),
            fill="#052e16",
        )
        self.time_text_id = self.canvas.create_text(
            self.timer_x + self.right_timer_w // 2,
            self.timer_y - 10,
            text=str(self.time_limit),
            font=("Segoe UI", 14, "bold"),
            fill="#16a34a",
        )
        self.timer_fill_id = self.canvas.create_rectangle(
            self.timer_x + 3,
            self.timer_y + 3,
            self.timer_x + self.right_timer_w - 3,
            self.timer_y + self.timer_h - 3,
            fill="#18c839",
            outline="",
        )
        self.info_id = self.canvas.create_text(
            self.board_x + self.board_w // 2,
            self.board_y + self.board_h + 18,
            text="사각형으로 선택한 범위의 합이 10이면 제거",
            font=("Segoe UI", 10, "bold"),
            fill="#065f46",
        )

    def on_close(self) -> None:
        self.cancel_timer_job()
        self.audio.stop_bgm()
        self.root.destroy()

    def cancel_timer_job(self) -> None:
        if self.timer_job is not None:
            self.root.after_cancel(self.timer_job)
            self.timer_job = None

    def start_timer(self) -> None:
        self.cancel_timer_job()
        self.timer_job = self.root.after(1000, self.tick_timer)

    def tick_timer(self) -> None:
        self.timer_job = None
        if self.game_over or self.paused:
            return
        self.time_left = max(0, self.time_left - 1)
        self.update_timer_ui()
        if self.time_left == 0:
            self.finish_game("시간 종료")
            return
        self.start_timer()

    def update_timer_ui(self) -> None:
        ratio = self.time_left / self.time_limit if self.time_limit > 0 else 0
        fill_h = int((self.timer_h - 6) * ratio)
        y1 = self.timer_y + self.timer_h - 3 - fill_h
        y2 = self.timer_y + self.timer_h - 3
        if fill_h <= 0:
            self.canvas.coords(self.timer_fill_id, 0, 0, 0, 0)
        else:
            self.canvas.coords(
                self.timer_fill_id,
                self.timer_x + 3,
                y1,
                self.timer_x + self.right_timer_w - 3,
                y2,
            )

        color = "#18c839"
        if ratio <= 0.5:
            color = "#f2b51d"
        if ratio <= 0.25:
            color = "#f04a2f"
        self.canvas.itemconfig(self.timer_fill_id, fill=color)
        self.canvas.itemconfig(self.time_text_id, text=str(self.time_left), fill=color)

    def reset_game(self) -> None:
        self.cancel_timer_job()
        self.score = 0
        self.moves = 0
        self.time_left = self.time_limit
        self.game_over = False
        self.set_paused(False)

        self.canvas.delete("cell")
        self.canvas.delete(self.selection_cell_tag)
        self.canvas.itemconfig(self.selection_id, state="hidden")

        self.grid = [[None for _ in range(self.cols)] for _ in range(self.rows)]
        for r in range(self.rows):
            for c in range(self.cols):
                self.grid[r][c] = self.make_cell(r, c, random.randint(1, 9))

        self.update_score_ui()
        self.update_timer_ui()
        if self.started:
            self.canvas.itemconfig(self.info_id, text="사각형으로 선택한 범위의 합이 10이면 제거")
            self.canvas.itemconfig(self.start_overlay_id, state="hidden")
            self.canvas.itemconfig(self.start_text_id, state="hidden")
            self.start_timer()
            if self.bgm_var.get():
                self.audio.start_bgm()
        else:
            self.canvas.itemconfig(self.info_id, text="초기 화면입니다. Start 버튼을 눌러주세요.")
            self.canvas.itemconfig(self.start_overlay_id, state="normal")
            self.canvas.itemconfig(self.start_text_id, state="normal")
            self.audio.stop_bgm()

    def toggle_light_mode(self) -> None:
        values: list[list[int | None]] = []
        for r in range(self.rows):
            row: list[int | None] = []
            for c in range(self.cols):
                row.append(None if self.grid[r][c] is None else self.grid[r][c].value)
            values.append(row)

        self.canvas.delete("cell")
        for r in range(self.rows):
            for c in range(self.cols):
                value = values[r][c]
                self.grid[r][c] = None if value is None else self.make_cell(r, c, value)

    def toggle_bgm(self) -> None:
        self.audio.set_bgm_enabled(self.bgm_var.get())

    def toggle_pause(self, event: tk.Event | None = None) -> None:
        if self.game_over or not self.started:
            return
        self.set_paused(not self.paused)

    def set_paused(self, paused: bool) -> None:
        self.paused = paused
        self.pause_btn.config(text="재개" if paused else "일시정지")
        self.canvas.itemconfig(self.pause_overlay_id, state="normal" if paused else "hidden")
        self.canvas.itemconfig(self.pause_text_id, state="normal" if paused else "hidden")

        if paused:
            self.cancel_timer_job()
            self.audio.stop_bgm()
            self.canvas.delete(self.selection_cell_tag)
            self.canvas.itemconfig(self.selection_id, state="hidden")
            self.drag_start = None
            self.drag_current = None
            self.canvas.itemconfig(self.info_id, text="일시정지")
        else:
            if self.started and not self.game_over:
                self.start_timer()
            if self.bgm_var.get():
                self.audio.start_bgm()
            self.canvas.itemconfig(self.info_id, text="사각형으로 선택한 범위의 합이 10이면 제거")

    def board_left(self) -> int:
        return self.board_x

    def board_top(self) -> int:
        return self.board_y

    def make_cell(self, r: int, c: int, value: int) -> Cell:
        x = self.board_x + c * self.cell_size
        y = self.board_y + r * self.cell_size

        margin = 5
        x1 = x + margin
        y1 = y + margin
        x2 = x + self.cell_size - margin
        y2 = y + self.cell_size - margin

        light = self.light_var.get()
        body = "#ff4a3d" if light else "#ef3f33"
        edge = "#e73a2e" if light else "#cc3027"

        shadow_id = self.canvas.create_oval(x1 + 1, y1 + 3, x2 + 1, y2 + 3, fill="#d7352c", outline="", tags=("cell",))
        apple_id = self.canvas.create_oval(x1, y1, x2, y2, fill=body, outline=edge, width=2, tags=("cell",))
        rim_id = self.canvas.create_oval(x1 + 1, y1 + 1, x2 - 1, y2 - 1, outline="#ffb4ab", width=1, tags=("cell",))
        shade_id = self.canvas.create_arc(
            x1 + 1,
            y1 + 9,
            x2 - 1,
            y2 - 1,
            start=220,
            extent=115,
            style=tk.CHORD,
            fill="#de3228",
            outline="",
            tags=("cell",),
        )

        cx = (x1 + x2) / 2
        stem_id = self.canvas.create_line(cx, y1 + 2, cx - 1, y1 - 5, fill="#6b3f1f", width=3, tags=("cell",))
        leaf_id = self.canvas.create_oval(cx + 2, y1 - 8, cx + 14, y1 + 2, fill="#3ddb99", outline="#14ad74", width=1, tags=("cell",))

        tx = int((x1 + x2) / 2)
        ty = int((y1 + y2) / 2) + 1
        outline_ids: list[int] = []
        for ox, oy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)]:
            outline_ids.append(
                self.canvas.create_text(
                    tx + ox,
                    ty + oy,
                    text=str(value),
                    font=("Arial", 16, "bold"),
                    fill="#cf3f0a",
                    tags=("cell",),
                )
            )
        text_id = self.canvas.create_text(tx, ty, text=str(value), font=("Arial", 16, "bold"), fill="white", tags=("cell",))

        item_ids = [
            shadow_id,
            apple_id,
            rim_id,
            shade_id,
            stem_id,
            leaf_id,
            *outline_ids,
            text_id,
        ]
        return Cell(value=value, item_ids=item_ids)

    def update_score_ui(self) -> None:
        self.canvas.itemconfig(self.score_id, text=f"SCORE {self.score}")

    def pixel_to_cell(self, x: int, y: int) -> tuple[int, int] | None:
        bx = x - self.board_x
        by = y - self.board_y
        if bx < 0 or by < 0:
            return None
        c = bx // self.cell_size
        r = by // self.cell_size
        if r < 0 or c < 0 or r >= self.rows or c >= self.cols:
            return None
        return int(r), int(c)

    def normalize_range(self, a: int, b: int) -> tuple[int, int]:
        return (a, b) if a <= b else (b, a)

    def get_selection_cells(self) -> list[tuple[int, int]]:
        if self.drag_start is None or self.drag_current is None:
            return []

        sr, sc = self.drag_start
        er, ec = self.drag_current
        r1, r2 = self.normalize_range(sr, er)
        c1, c2 = self.normalize_range(sc, ec)

        cells: list[tuple[int, int]] = []
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                if self.grid[r][c] is not None:
                    cells.append((r, c))
        return cells

    def show_selection_box(self) -> None:
        if self.drag_start is None or self.drag_current is None:
            self.canvas.delete(self.selection_cell_tag)
            self.canvas.itemconfig(self.selection_id, state="hidden")
            return

        sr, sc = self.drag_start
        er, ec = self.drag_current
        r1, r2 = self.normalize_range(sr, er)
        c1, c2 = self.normalize_range(sc, ec)

        x1 = self.board_x + c1 * self.cell_size + 2
        y1 = self.board_y + r1 * self.cell_size + 2
        x2 = self.board_x + (c2 + 1) * self.cell_size - 2
        y2 = self.board_y + (r2 + 1) * self.cell_size - 2

        self.canvas.coords(self.selection_id, x1, y1, x2, y2)
        self.canvas.itemconfig(self.selection_id, state="normal")

        self.canvas.delete(self.selection_cell_tag)
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cx1 = self.board_x + c * self.cell_size + 1
                cy1 = self.board_y + r * self.cell_size + 1
                cx2 = cx1 + self.cell_size - 2
                cy2 = cy1 + self.cell_size - 2
                self.canvas.create_rectangle(cx1, cy1, cx2, cy2, outline="#38bdf8", width=2, tags=(self.selection_cell_tag,))

    def on_press(self, event: tk.Event) -> None:
        if self.game_over or self.paused or not self.started:
            return
        cell = self.pixel_to_cell(event.x, event.y)
        if cell is None:
            self.drag_start = None
            self.drag_current = None
            self.show_selection_box()
            return
        self.drag_start = cell
        self.drag_current = cell
        self.show_selection_box()

    def on_drag(self, event: tk.Event) -> None:
        if self.drag_start is None or self.game_over or self.paused or not self.started:
            return
        cell = self.pixel_to_cell(event.x, event.y)
        if cell is None:
            return
        self.drag_current = cell
        self.show_selection_box()

    def on_release(self, event: tk.Event) -> None:
        if self.drag_start is None or self.game_over or self.paused or not self.started:
            return

        cell = self.pixel_to_cell(event.x, event.y)
        if cell is not None:
            self.drag_current = cell

        selected = self.get_selection_cells()
        self.canvas.delete(self.selection_cell_tag)
        self.canvas.itemconfig(self.selection_id, state="hidden")

        if not selected:
            self.drag_start = None
            self.drag_current = None
            return

        self.moves += 1
        total = sum(self.grid[r][c].value for r, c in selected if self.grid[r][c] is not None)

        if total == 10:
            self.remove_cells(selected)
            self.score += 10
            self.audio.play_clear()
            self.update_score_ui()
            self.canvas.itemconfig(self.info_id, text=f"성공! +10 ({len(selected)}개 제거)")
            if not self.has_possible_ten():
                self.finish_game("더 이상 10을 만들 수 없음")
        else:
            self.audio.play_fail()
            self.canvas.itemconfig(self.info_id, text=f"합계 {total} (10이 아님)")

        self.drag_start = None
        self.drag_current = None

    def remove_cells(self, cells: list[tuple[int, int]]) -> None:
        for r, c in cells:
            cell = self.grid[r][c]
            if cell is None:
                continue
            for item_id in cell.item_ids:
                self.canvas.delete(item_id)
            self.grid[r][c] = None

    def _area_sum(self, prefix: list[list[int]], r1: int, c1: int, r2: int, c2: int) -> int:
        return prefix[r2 + 1][c2 + 1] - prefix[r1][c2 + 1] - prefix[r2 + 1][c1] + prefix[r1][c1]

    def has_possible_ten(self) -> bool:
        val_prefix = [[0] * (self.cols + 1) for _ in range(self.rows + 1)]
        for r in range(self.rows):
            for c in range(self.cols):
                value = 0 if self.grid[r][c] is None else self.grid[r][c].value
                val_prefix[r + 1][c + 1] = value + val_prefix[r][c + 1] + val_prefix[r + 1][c] - val_prefix[r][c]

        for r1 in range(self.rows):
            for r2 in range(r1, self.rows):
                for c1 in range(self.cols):
                    for c2 in range(c1, self.cols):
                        if self._area_sum(val_prefix, r1, c1, r2, c2) == 10:
                            return True
        return False

    def finish_game(self, reason: str) -> None:
        if self.game_over:
            return
        self.game_over = True
        self.cancel_timer_job()
        self.canvas.delete(self.selection_cell_tag)
        self.canvas.itemconfig(self.selection_id, state="hidden")
        self.canvas.itemconfig(self.info_id, text=f"게임 종료: {reason} | 최종 점수 {self.score}")
        self.record_current_score()

    def start_game(self) -> None:
        self.started = True
        self.reset_game()

    def load_rankings(self) -> list[dict[str, str | int]]:
        if not self.rank_path.exists():
            return []
        try:
            with self.rank_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, OSError):
            pass
        return []

    def save_rankings(self, rankings: list[dict[str, str | int]]) -> None:
        with self.rank_path.open("w", encoding="utf-8") as f:
            json.dump(rankings, f, ensure_ascii=False, indent=2)

    def record_current_score(self) -> None:
        name = simpledialog.askstring("점수 기록", f"점수 {self.score}점을 기록할 이름을 입력하세요:", parent=self.root)
        if name is None:
            return
        clean_name = name.strip() or "Player"

        rankings = self.load_rankings()
        rankings.append(
            {
                "name": clean_name[:20],
                "score": int(self.score),
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        rankings.sort(key=lambda item: int(item.get("score", 0)), reverse=True)
        self.save_rankings(rankings[:10])
        self.refresh_rank_panel()

    def refresh_rank_panel(self) -> None:
        rankings = self.load_rankings()
        for item_id in self.rank_list.get_children():
            self.rank_list.delete(item_id)

        if len(rankings) == 0:
            self.rank_list.insert("", "end", values=("-", "기록 없음", "-"))
            return

        for idx, item in enumerate(rankings[:10], start=1):
            name = str(item.get("name", "Player"))[:14]
            score = int(item.get("score", 0))
            self.rank_list.insert("", "end", values=(idx, name, score))


def main() -> None:
    root = tk.Tk()
    AppleBoxGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
