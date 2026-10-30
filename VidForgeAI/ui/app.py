"""VidForge AI Studio — professional dark desktop UI (Tkinter, ships inside .exe).

Tabs: Create (AI Director) · Timeline Editor · Captions (216 presets + creator) ·
Media Browser (stock APIs + built-in research browser) · Audio (hardened Edge-TTS
+ local voices) · Clipper (short/long + smart highlights) · Agent/MCP · Settings.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import (captions, config, director, media_search, render_engine,
                  tts_engine)  # noqa: E402

BG, BG2, CARD, TXT, MUT, ACC, ACC2 = "#0d1117", "#161b22", "#1c2330", "#e6edf3", "#8b949e", "#ff3b5c", "#3fb6ff"
FONT = "Segoe UI"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{config.APP_NAME} — {config.APP_TAGLINE}")
        self.geometry("1280x800")
        self.configure(bg=BG)
        self.minsize(1024, 680)
        self.q = queue.Queue()
        self.cancel = threading.Event()
        self._build_style()
        self._header()
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=1, padx=10, pady=(0, 10))
        for title, build in [("🎬  AI Create", self.tab_create),
                             ("⚡  Forge Studio", self.tab_forge),
                             ("🧠  Timeline Editor", self.tab_timeline),
                             ("💬  Captions", self.tab_captions),
                             ("🌐  Media Browser", self.tab_media),
                             ("🎙  Audio / TTS", self.tab_audio),
                             ("✂️  Clipper", self.tab_clipper),
                             ("🤖  Agent / MCP", self.tab_agent),
                             ("⚙️  Settings", self.tab_settings)]:
            fr = ttk.Frame(self.nb)
            self.nb.add(fr, text=title)
            build(fr)
        self.statusbar = tk.Label(self, text="Ready — no API keys needed to start creating.",
                                  anchor="w", bg=BG2, fg=MUT, padx=12, pady=4, font=(FONT, 9))
        self.statusbar.pack(fill="x", side="bottom")
        self.after(120, self._pump)

    # ------------------------------------------------------------ infra
    def _build_style(self):
        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except Exception:
            pass
        st.configure(".", background=BG, foreground=TXT, font=(FONT, 10))
        st.configure("TNotebook", background=BG, borderwidth=0)
        st.configure("TNotebook.Tab", background=BG2, foreground=MUT, padding=(14, 8),
                    font=(FONT, 10, "bold"))
        st.map("TNotebook.Tab", background=[("selected", CARD)], foreground=[("selected", TXT)])
        st.configure("TFrame", background=BG)
        st.configure("Card.TFrame", background=CARD)
        st.configure("TLabel", background=BG, foreground=TXT)
        st.configure("Muted.TLabel", background=BG, foreground=MUT)
        st.configure("TButton", background=ACC, foreground="white", font=(FONT, 10, "bold"),
                    padding=(12, 7), borderwidth=0)
        st.map("TButton", background=[("active", "#ff5f7a")])
        st.configure("Ghost.TButton", background=BG2, foreground=TXT)
        st.map("Ghost.TButton", background=[("active", CARD)])
        st.configure("TEntry", fieldbackground=BG2, foreground=TXT, insertcolor=TXT,
                    borderwidth=1, lightcolor=BG2, darkcolor=BG2)
        st.configure("TCombobox", fieldbackground=BG2, background=CARD, foreground=TXT,
                    arrowcolor=TXT)
        st.configure("Horizontal.TProgressbar", background=ACC2, troughcolor=BG2)
        st.configure("Treeview", background=BG2, fieldbackground=BG2, foreground=TXT,
                    rowheight=26, borderwidth=0)
        st.configure("Treeview.Heading", background=CARD, foreground=TXT, font=(FONT, 10, "bold"))
        self.option_add("*TCombobox*Listbox.background", BG2)
        self.option_add("*TCombobox*Listbox.foreground", TXT)
        self.option_add("*TCombobox*Listbox.selectBackground", ACC)

    def _header(self):
        h = tk.Frame(self, bg=BG, height=64)
        h.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(h, text="Vid", font=("Segoe UI", 22, "bold"), bg=BG, fg=ACC).pack(side="left")
        tk.Label(h, text="Forge", font=("Segoe UI", 22, "bold"), bg=BG, fg=TXT).pack(side="left")
        tk.Label(h, text="AI", font=("Segoe UI", 22, "bold"), bg=BG, fg=ACC2).pack(side="left")
        tk.Label(h, text="   " + config.APP_TAGLINE, font=(FONT, 10), bg=BG, fg=MUT).pack(side="left")
        tk.Button(h, text="▶ Open last output", command=self._open_last, bg=BG2, fg=MUT,
                  relief="flat", font=(FONT, 9)).pack(side="right")

    def _pump(self):
        try:
            while True:
                fn, args = self.q.get_nowait()
                fn(*args)
        except queue.Empty:
            pass
        self.after(120, self._pump)

    def ui(self, fn, *a):
        self.q.put((fn, a))

    def set_status(self, t, prog=None):
        self.statusbar.config(text=t)
        if prog is not None and hasattr(self, "_prog"):
            self._prog["value"] = prog * 100

    def run_bg(self, work, done):
        def wrap():
            try:
                r = work()
                self.ui(done, r, None)
            except Exception as e:
                self.ui(done, None, e)
        threading.Thread(target=wrap, daemon=True).start()

    def _open_last(self):
        p = getattr(self, "_last_out", None)
        if p and os.path.exists(p):
            subprocess.Popen(["explorer", "/select,", p] if sys.platform.startswith("win")
                             else ["xdg-open", os.path.dirname(p)])

    # ------------------------------------------------------------ CREATE tab
    def tab_create(self, fr):
        pad = dict(padx=14, pady=6)
        top = ttk.Frame(fr); top.pack(fill="x", **pad)
        tk.Label(top, text="Video idea / topic  (or paste a reference video link for style cues)",
                 fg=MUT, bg=BG).pack(anchor="w")
        self.idea = tk.Text(top, height=3, bg=BG2, fg=TXT, insertbackground=TXT,
                            font=(FONT, 11), relief="flat", wrap="word")
        self.idea.pack(fill="x", pady=4)

        row = ttk.Frame(fr); row.pack(fill="x", **pad)
        b = lambda l, w: (tk.Label(row, text=l, fg=MUT, bg=BG, font=(FONT, 9)), w)

        tk.Label(row, text="Format", fg=MUT, bg=BG).grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.fmt = ttk.Combobox(row, values=["long", "short"], width=8, state="readonly")
        self.fmt.set("long"); self.fmt.grid(row=1, column=0)
        self.fmt.bind("<<ComboboxSelected>>", lambda e: setattr(self, "_tmin_hint", None))

        tk.Label(row, text="Length (minutes)", fg=MUT, bg=BG).grid(row=0, column=1, padx=12, sticky="w")
        self.tmin = tk.Spinbox(row, from_=0.2, to=15, increment=0.5, width=6,
                               bg=BG2, fg=TXT, buttonbackground=CARD, relief="flat",
                               font=(FONT, 11))
        self.tmin.delete(0, "end"); self.tmin.insert(0, "3")
        self.tmin.grid(row=1, column=1, padx=12)

        tk.Label(row, text="Style", fg=MUT, bg=BG).grid(row=0, column=2, padx=12, sticky="w")
        self.style = ttk.Combobox(row, values=["documentary", "energetic shorts", "explainer",
                                               "storytelling", "product ad", "top-10 list",
                                               "news recap", "reaction"], width=16, state="readonly")
        self.style.set("documentary"); self.style.grid(row=1, column=2, padx=12)

        tk.Label(row, text="Voice", fg=MUT, bg=BG).grid(row=0, column=3, padx=12, sticky="w")
        self.voice = ttk.Combobox(row, values=[
            "en-US-AriaNeural", "en-US-GuyNeural", "en-GB-SoniaNeural", "en-AU-NatashaNeural",
            "en-US-JennyNeural", "ur-PK-IraNeural", "hi-IN-SwaraNeural", "es-MX-DaliaNeural"],
            width=20)
        self.voice.set(config.CFG["tts_voice"]); self.voice.grid(row=1, column=3, padx=12)

        tk.Label(row, text="Caption preset", fg=MUT, bg=BG).grid(row=0, column=4, padx=12, sticky="w")
        fams = sorted({p.family for p in captions.LIBRARY})
        self.capfam = ttk.Combobox(row, values=fams, width=16, state="readonly")
        self.capfam.set("Pop Bounce"); self.capfam.grid(row=1, column=4, padx=12)

        tk.Label(row, text="Music file (optional)", fg=MUT, bg=BG).grid(row=0, column=5, padx=12, sticky="w")
        mf = ttk.Frame(row); mf.grid(row=1, column=5, padx=12)
        self.music_var = tk.StringVar()
        tk.Entry(mf, textvariable=self.music_var, width=18, bg=BG2, fg=TXT,
                 insertbackground=TXT, relief="flat").pack(side="left")
        ttk.Button(mf, text="…", width=3, style="Ghost.TButton",
                   command=lambda: self.music_var.set(
                       filedialog.askopenfilename(filetypes=[("Audio", "*.mp3 *.wav *.m4a *.ogg")]) or "")
                   ).pack(side="left")

        opts = ttk.Frame(fr); opts.pack(fill="x", **pad)
        self.auto_stock = tk.BooleanVar(value=True)
        self.use_browser = tk.BooleanVar(value=bool(config.CFG.get("browser_fallback_enabled", False)))
        self.lufs = tk.BooleanVar(value=True)
        for var, lbl in [(self.auto_stock, "Auto-source royalty-free b-roll"),
                         (self.use_browser, "Use built-in browser for real event footage"),
                         (self.lufs, "Loudness normalize (-14 LUFS YouTube)")]:
            tk.Checkbutton(opts, text=lbl, variable=var, bg=BG, fg=TXT, selectcolor=BG2,
                           activebackground=BG, activeforeground=TXT).pack(side="left", padx=(0, 18))

        ctl = ttk.Frame(fr); ctl.pack(fill="x", **pad)
        self.go_btn = ttk.Button(ctl, text="🚀  Generate Video", command=self.on_generate)
        self.go_btn.pack(side="left")
        ttk.Button(ctl, text="✍ Preview Script only", style="Ghost.TButton",
                   command=self.on_preview_script).pack(side="left", padx=8)
        ttk.Button(ctl, text="⏹ Cancel", style="Ghost.TButton",
                   command=self.cancel.set).pack(side="left")
        self._prog = ttk.Progressbar(ctl, length=260, mode="determinate")
        self._prog.pack(side="right")

        body = ttk.Frame(fr); body.pack(fill="both", expand=True, **pad)
        tk.Label(body, text="Director log", fg=MUT, bg=BG).pack(anchor="w")
        self.log = tk.Text(body, bg="#0a0e14", fg="#9fe8b8", insertbackground=TXT,
                           relief="flat", font=("Consolas", 10), state="disabled")
        self.log.pack(fill="both", expand=True)
        self.script_view = tk.Text(fr, height=8, bg=BG2, fg=TXT, relief="flat", font=(FONT, 10))

    def _logline(self, s):
        self.log.config(state="normal")
        self.log.insert("end", s + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def on_preview_script(self):
        idea = self.idea.get("1.0", "end").strip()
        if not idea:
            return messagebox.showwarning("VidForge", "Enter an idea first.")
        def work():
            return director.write_script(idea, int(float(self.tmin.get()) * 60), self.fmt.get(),
                                         self.style.get())
        def done(r, e):
            if e:
                return self._logline("ERROR: " + str(e))
            self.script_view.delete("1.0", "end")
            for i, sc in enumerate(r["scenes"]):
                self.script_view.insert("end", f"[Scene {i+1}] VO: {sc['narration']}\n"
                                        f"          VISUAL: {sc.get('visual_query','')}\n\n")
            self.script_view.pack(fill="x", pady=4)
        self.run_bg(work, done)

    def on_generate(self):
        idea = self.idea.get("1.0", "end").strip()
        if not idea:
            return messagebox.showwarning("VidForge", "Enter a video idea / topic.")
        self.cancel.clear()
        self.log.config(state="normal"); self.log.delete("1.0", "end"); self.log.config(state="disabled")
        fam = self.capfam.get()
        preset = next((p.id for p in captions.LIBRARY if p.family == fam), None)
        def work():
            return director.generate_video(
                idea, fmt=self.fmt.get(), target_minutes=float(self.tmin.get()),
                caption_preset=preset, voice=self.voice.get(),
                music_path=self.music_var.get() or None, use_browser=self.use_browser.get(),
                style=self.style.get(),
                progress=lambda p, m: self.ui(self._gen_progress, p, m))
        def done(r, e):
            self._prog["value"] = 0
            if e:
                self._logline("❌ " + str(e))
                return messagebox.showerror("Render failed", str(e)[:900])
            self._last_out = r["output"]
            self._logline(f"\n✅ DONE  {r['output']}")
            self._logline(f"   duration {r['duration_s']}s · editable project: {r.get('project_json')}")
            if messagebox.askyesno("VidForge", "Video ready!\nOpen the folder?"):
                subprocess.Popen(["explorer", r["project_dir"]] if sys.platform.startswith("win")
                                 else ["xdg-open", r["project_dir"]])
        self.run_bg(work, done)

    def _gen_progress(self, p, m):
        self._prog["value"] = p * 100
        self._logline(m)
        self.set_status(m, p)

    # ------------------------------------------------------------ FORGE STUDIO tab
    def tab_forge(self, fr):
        """⚡ Forge Studio — full-control AI short/long video factory (core.forge)."""
        from core import forge as _forge
        pad = dict(padx=14, pady=5)
        hdr = ttk.Frame(fr); hdr.pack(fill="x", **pad)
        tk.Label(hdr, text="⚡  FORGE STUDIO — full-control AI video builder "
                           "(short 9:16 · long 16:9)", fg=ACC2, bg=BG,
                 font=(FONT, 13, "bold")).pack(side="left")
        self._forge_cap = tk.Label(hdr, text="", fg=MUT, bg=BG, font=(FONT, 9))
        self._forge_cap.pack(side="right")
        try:
            st = _forge.forge_status()
            self._forge_cap.config(
                text=f"Remotion {'✓' if st['remotion_ready'] else 'PIL-fallback'} · "
                     f"{st['caption_presets']} caption presets · "
                     f"{st['providers_enabled']} stock providers · LLM: {st['llm']}")
        except Exception:
            pass

        body = ttk.Frame(fr); body.pack(fill="both", expand=True)
        left = ttk.Frame(body); left.pack(side="left", fill="both", expand=True, padx=(14, 6))
        right = ttk.Frame(body); right.pack(side="right", fill="y", padx=(6, 14))

        # --- idea / script -------------------------------------------------
        tk.Label(left, text="Video idea / topic   —   ya apna professional script paste karo (tab switch neeche)",
                 fg=MUT, bg=BG).pack(anchor="w")
        self.fg_idea = tk.Entry(left, bg=BG2, fg=TXT, insertbackground=TXT,
                                relief="flat", font=(FONT, 12))
        self.fg_idea.pack(fill="x", pady=(2, 4))
        self.fg_mode = tk.StringVar(value="idea")     # idea | script
        seg = ttk.Frame(left); seg.pack(anchor="w")
        for val, lbl in [("idea", "💡 Idea → AI writes script"),
                         ("script", "📝 Use my pasted script")]:
            tk.Radiobutton(seg, text=lbl, variable=self.fg_mode, value=val,
                           bg=BG, fg=TXT, selectcolor=BG2, activebackground=BG,
                           activeforeground=TXT, command=self._fg_mode_toggle,
                           font=(FONT, 9)).pack(side="left", padx=(0, 14))
        self.fg_script = tk.Text(left, height=8, bg="#0a0e14", fg="#cdd9e5",
                                 insertbackground=TXT, relief="flat",
                                 font=("Consolas", 10), wrap="word")
        tk.Label(left, text="Script format:  ## Scene 1 … VO: narration … Visual: b-roll cue   "
                            "(bare paragraphs bhi chalte hain)",
                 fg=MUT, bg=BG, font=(FONT, 8)).pack(anchor="w")

        # --- control grid --------------------------------------------------
        g = ttk.Frame(left); g.pack(fill="x", pady=6)
        lab = lambda r, c, t: tk.Label(g, text=t, fg=MUT, bg=BG, font=(FONT, 9)).grid(
            row=r, column=c, sticky="w", padx=(0, 10))
        def combo(vals, dflt, w=13):
            cb = ttk.Combobox(g, values=vals, width=w, state="readonly")
            cb.set(dflt)
            return cb

        lab(0, 0, "Format"); self.fg_fmt = combo(["short (9:16 vertical)", "long (16:9 wide)"],
                                                 "long (16:9 wide)", 16); self.fg_fmt.grid(row=1, column=0)
        lab(0, 1, "Length min"); self.fg_min = tk.Spinbox(g, from_=0.2, to=20, increment=0.5,
                                                          width=6, bg=BG2, fg=TXT,
                                                          buttonbackground=CARD, relief="flat",
                                                          font=(FONT, 11)); self.fg_min.delete(0, "end")
        self.fg_min.insert(0, "3"); self.fg_min.grid(row=1, column=1, sticky="w")
        lab(0, 2, "Style"); self.fg_style = combo(
            ["documentary", "energetic shorts", "explainer", "storytelling",
             "product ad", "top-10 list", "news recap", "reaction"], "documentary", 15)
        self.fg_style.grid(row=1, column=2, sticky="w")
        lab(0, 3, "Visual mode"); self.fg_vmode = combo(
            ["auto", "stock", "hyperframe", "mixed (stock+HUD)", "image (Ken-Burns)"],
            "auto", 17); self.fg_vmode.grid(row=1, column=3, sticky="w")

        lab(2, 0, "Narrator voice"); self.fg_voice = combo([
            "en-US-AriaNeural", "en-US-GuyNeural", "en-GB-SoniaNeural",
            "en-AU-NatashaNeural", "en-US-JennyNeural", "ur-PK-IraNeural",
            "hi-IN-SwaraNeural", "es-MX-DaliaNeural"], config.CFG["tts_voice"], 18)
        self.fg_voice.grid(row=3, column=0, columnspan=2, sticky="w", pady=(10, 0))
        lab(2, 2, "Rate"); self.fg_rate = combo(
            ["-20%", "-10%", "+0%", "+8%", "+15%", "+25%"], "+8%"); self.fg_rate.grid(row=3, column=2, sticky="w", pady=(10, 0))
        lab(2, 3, "Pitch"); self.fg_pitch = combo(
            ["-20Hz", "-10Hz", "+0Hz", "+10Hz", "+20Hz"], "+0Hz"); self.fg_pitch.grid(row=3, column=3, sticky="w", pady=(10, 0))

        fams = sorted({p.family for p in captions.LIBRARY})
        lab(4, 0, "Caption preset (family)"); self.fg_capfam = combo(fams, "Pop Bounce", 18)
        self.fg_capfam.grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 0))
        subs = [p.id for p in captions.LIBRARY if p.family == "Pop Bounce"]
        lab(4, 2, "Exact template"); self.fg_cappreset = combo(subs, subs[0], 22)
        self.fg_cappreset.grid(row=5, column=2, columnspan=2, sticky="w", pady=(10, 0))
        self.fg_capfam.bind("<<ComboboxSelected>>", self._fg_fill_presets)

        lab(6, 0, "Music bed volume"); mf = ttk.Frame(g); mf.grid(row=7, column=0, columnspan=2, sticky="w")
        self.fg_musicvol = tk.Scale(mf, from_=0, to=40, orient="horizontal", length=110,
                                    bg=BG, fg=TXT, troughcolor=BG2, highlightthickness=0,
                                    showvalue=True)
        self.fg_musicvol.set(16); self.fg_musicvol.pack(side="left")
        self.fg_music = tk.StringVar()
        me = tk.Entry(mf, textvariable=self.fg_music, width=14, bg=BG2, fg=TXT,
                      insertbackground=TXT, relief="flat"); me.pack(side="left", padx=4)
        ttk.Button(mf, text="…", width=3, style="Ghost.TButton",
                   command=lambda: self.fg_music.set(
                       filedialog.askopenfilename(
                           filetypes=[("Audio", "*.mp3 *.wav *.m4a *.ogg")]) or "")).pack(side="left")
        lab(6, 2, "Transition"); self.fg_trans = combo(
            ["cut", "fade", "slide", "wipe", "glitch"], "fade"); self.fg_trans.grid(row=7, column=2, sticky="w")
        lab(6, 3, "Watermark (optional)"); self.fg_wm = tk.Entry(g, width=16, bg=BG2, fg=TXT,
                                                                 insertbackground=TXT, relief="flat")
        self.fg_wm.grid(row=7, column=3, sticky="w")

        lab(8, 0, "Hook line (extra opening scene)"); self.fg_hook = tk.Entry(
            g, width=30, bg=BG2, fg=TXT, insertbackground=TXT, relief="flat")
        self.fg_hook.grid(row=9, column=0, columnspan=2, sticky="w", pady=(10, 0))
        lab(8, 2, "CTA / outro line"); self.fg_cta = tk.Entry(
            g, width=30, bg=BG2, fg=TXT, insertbackground=TXT, relief="flat")
        self.fg_cta.grid(row=9, column=2, columnspan=2, sticky="w", pady=(10, 0))

        chkrow = ttk.Frame(left); chkrow.pack(fill="x", pady=4)
        self.fg_ken = tk.BooleanVar(value=True)
        self.fg_lufs = tk.BooleanVar(value=True)
        self.fg_chap = tk.BooleanVar(value=True)
        self.fg_pbar = tk.BooleanVar(value=False)
        self.fg_browser = tk.BooleanVar(value=bool(config.CFG.get("browser_fallback_enabled", False)))
        for var, lbl in [(self.fg_ken, "Ken-Burns on stills"), (self.fg_lufs, "-14 LUFS master"),
                         (self.fg_chap, "Chapter markers"), (self.fg_pbar, "Force progress bar"),
                         (self.fg_browser, "Browser real-footage fallback")]:
            tk.Checkbutton(chkrow, text=lbl, variable=var, bg=BG, fg=TXT, selectcolor=BG2,
                           activebackground=BG, activeforeground=TXT,
                           font=(FONT, 9)).pack(side="left", padx=(0, 12))

        ctl = ttk.Frame(left); ctl.pack(fill="x", pady=6)
        ttk.Button(ctl, text="⚡  FORGE VIDEO", command=self.on_forge).pack(side="left")
        ttk.Button(ctl, text="Preview scenes", style="Ghost.TButton",
                   command=self.on_forge_preview).pack(side="left", padx=8)
        ttk.Button(ctl, text="⏹ Cancel", style="Ghost.TButton",
                   command=self.cancel.set).pack(side="left")
        self.fg_prog = ttk.Progressbar(ctl, length=200, mode="determinate"); self.fg_prog.pack(side="right")

        # --- right side: log + output buttons -------------------------------
        tk.Label(right, text="Forge log", fg=MUT, bg=BG).pack(anchor="w")
        self.fg_log = tk.Text(right, width=52, bg="#0a0e14", fg="#ffd97a",
                              insertbackground=TXT, relief="flat", font=("Consolas", 10),
                              state="disabled")
        self.fg_log.pack(fill="both", expand=True, pady=4)
        brow = ttk.Frame(right); brow.pack(fill="x")
        ttk.Button(brow, text="📂 Open output folder", style="Ghost.TButton",
                   command=self._fg_open_out).pack(side="left")
        ttk.Button(brow, text="▶ Play final.mp4", style="Ghost.TButton",
                   command=self._fg_play).pack(side="left", padx=6)
        self._fg_last_dir = None

    def _fg_mode_toggle(self):
        if self.fg_mode.get() == "script":
            self.fg_script.pack(fill="x", pady=4)
        else:
            self.fg_script.pack_forget()

    def _fg_fill_presets(self, *_):
        fam = self.fg_capfam.get()
        ids = [p.id for p in captions.LIBRARY if p.family == fam]
        self.fg_cappreset["values"] = ids
        if ids:
            self.fg_cappreset.set(ids[0])

    def _fg_write_log(self, s):
        self.fg_log.config(state="normal")
        self.fg_log.insert("end", s + "\n"); self.fg_log.see("end")
        self.fg_log.config(state="disabled")

    def _fg_common_kwargs(self):
        from core import forge as _forge
        fmt = "short" if self.fg_fmt.get().startswith("short") else "long"
        return dict(fmt=fmt,
                    target_minutes=float(self.fg_min.get()),
                    style=self.fg_style.get(),
                    voice=self.fg_voice.get(),
                    rate=self.fg_rate.get(), pitch=self.fg_pitch.get(),
                    visual_mode=("mixed" if self.fg_vmode.get().startswith("mixed")
                                 else "image" if self.fg_vmode.get().startswith("image")
                                 else self.fg_vmode.get()),
                    caption_preset=self.fg_cappreset.get() or None,
                    music_path=self.fg_music.get() or None,
                    music_volume=self.fg_musicvol.get() / 100.0,
                    hook=self.fg_hook.get(), cta=self.fg_cta.get(),
                    transitions=self.fg_trans.get(),
                    ken_burns=self.fg_ken.get(), lufs=self.fg_lufs.get(),
                    chapters=self.fg_chap.get(),
                    progress_bar=(True if self.fg_pbar.get() else None),
                    watermark=self.fg_wm.get(),
                    use_browser=(True if self.fg_browser.get() else False))

    def on_forge_preview(self):
        idea = self.fg_idea.get().strip()
        txt = self.fg_script.get("1.0", "end").strip() if self.fg_mode.get() == "script" else ""
        if not idea and not txt:
            return messagebox.showwarning("Forge Studio", "Idea likho ya script paste karo.")
        def work():
            from core import forge as _forge
            if txt:
                title, scenes = _forge.script_to_scenes(txt, idea=idea)
            else:
                sc = director.write_script(idea, int(float(self.fg_min.get()) * 60),
                                           self.fg_fmt.get().split()[0], self.fg_style.get())
                title, scenes = sc["title"], sc["scenes"]
            return {"title": title, "scenes": scenes}
        def done(r, e):
            if e:
                return self._fg_write_log("ERROR: " + str(e))
            self._fg_write_log(f"— preview: “{r['title']}” ({len(r['scenes'])} scenes)")
            for i, s in enumerate(r["scenes"]):
                self._fg_write_log(f"  [{i+1}] VO: {s['narration'][:90]}")
                self._fg_write_log(f"      VISUAL: {s.get('visual_query','')}")
        self.run_bg(work, done)

    def on_forge(self):
        from core import forge as _forge
        idea = self.fg_idea.get().strip()
        txt = self.fg_script.get("1.0", "end").strip() if self.fg_mode.get() == "script" else ""
        if not idea and not txt:
            return messagebox.showwarning("Forge Studio", "Idea likho ya script paste karo.")
        kw = self._fg_common_kwargs()
        self.cancel.clear()
        self.fg_log.config(state="normal"); self.fg_log.delete("1.0", "end"); self.fg_log.config(state="disabled")
        self._fg_write_log(f"⚡ FORGE START · {kw['fmt']} · mode={kw['visual_mode']} · "
                           f"captions={kw['caption_preset']}")
        def work():
            return _forge.forge_create(idea or txt.splitlines()[0][:60],
                                       script_text=txt or None,
                                       progress=lambda p, m: self.ui(self._fg_progress, p, m))
        def done(r, e):
            self.fg_prog["value"] = 0
            if e:
                self._fg_write_log("❌ " + str(e))
                return messagebox.showerror("Forge failed", str(e)[:900])
            self._fg_last_dir = r.get("project_dir")
            self._last_out = r["output"]
            self._fg_write_log(f"✅ DONE → {r['output']}")
            self._fg_write_log(f"   {r['duration_s']}s · SRT: {r.get('captions_srt','')}")
            if messagebox.askyesno("Forge Studio", "Video ready!\nOpen the folder?"):
                self._fg_open_out()
        self.run_bg(work, done)

    def _fg_progress(self, p, m):
        self.fg_prog["value"] = p * 100
        self._fg_write_log(m)

    def _fg_open_out(self):
        d = self._fg_last_dir
        if d and os.path.exists(d):
            subprocess.Popen(["explorer", d] if sys.platform.startswith("win")
                             else ["xdg-open", d])

    def _fg_play(self):
        d = self._fg_last_dir
        f = os.path.join(d, "final.mp4") if d else ""
        if f and os.path.exists(f):
            if sys.platform.startswith("win"):
                os.startfile(f)  # noqa: S606 — default player
            else:
                subprocess.Popen(["xdg-open", f])

    # ------------------------------------------------------------ TIMELINE tab
    def tab_timeline(self, fr):
        bar = ttk.Frame(fr); bar.pack(fill="x", padx=10, pady=8)
        ttk.Button(bar, text="📂 Open project.json", style="Ghost.TButton",
                   command=self.load_project).pack(side="left")
        ttk.Button(bar, text="⬆ Move clip up", style="Ghost.TButton",
                   command=lambda: self.move_row(-1)).pack(side="left", padx=4)
        ttk.Button(bar, text="⬇ Move down", style="Ghost.TButton",
                   command=lambda: self.move_row(1)).pack(side="left")
        ttk.Button(bar, text="🗑 Delete clip", style="Ghost.TButton",
                   command=self.del_row).pack(side="left", padx=4)
        ttk.Button(bar, text="＋ Add clip from file", style="Ghost.TButton",
                   command=self.add_clip).pack(side="left")
        ttk.Button(bar, text="🎨 Edit selected clip", style="Ghost.TButton",
                   command=self.edit_clip).pack(side="left", padx=4)
        ttk.Button(bar, text="▶ RENDER THIS TIMELINE", command=self.render_project)\
            .pack(side="right")
        cols = ("id", "kind", "source", "in", "out", "speed", "transition", "kenburns", "layer")
        self.tree = ttk.Treeview(fr, columns=cols, show="headings", height=14)
        widths = dict(zip(cols, (50, 80, 380, 60, 60, 60, 90, 90, 50)))
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=10)
        self.proj_dir = None
        self.proj = None

    def load_project(self):
        path = filedialog.askopenfilename(filetypes=[("VidForge project", "*.json")])
        if not path:
            return
        self.proj = json.load(open(path, encoding="utf-8"))
        self.proj_dir = os.path.dirname(path)
        self._refresh_tree()
        self.set_status(f"Loaded {os.path.basename(path)} — edit clips then RENDER.")

    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for c in self.proj.get("clips", []):
            self.tree.insert("", "end", values=(c.get("id"), c.get("kind"),
                              os.path.basename(str(c.get("source", ""))), c.get("in_s"),
                              c.get("out_s"), c.get("speed"), c.get("transition"),
                              c.get("ken_burns") or "-", c.get("layer")))

    def move_row(self, d):
        sel = self.tree.selection()
        if not sel or not self.proj:
            return
        items = list(self.tree.get_children())
        i = items.index(sel[0]); j = max(0, min(len(items) - 1, i + d))
        clips = self.proj["clips"]
        clips[i], clips[j] = clips[j], clips[i]
        self._refresh_tree()

    def del_row(self):
        sel = self.tree.selection()
        if sel and self.proj:
            idx = list(self.tree.get_children()).index(sel[0])
            self.proj["clips"].pop(idx)
            self._refresh_tree()

    def add_clip(self):
        if not self.proj:
            return messagebox.showinfo("VidForge", "Open a project first (or generate one).")
        p = filedialog.askopenfilename(filetypes=[("Media", "*.mp4 *.mov *.webm *.jpg *.png *.jpeg *.webp")])
        if not p:
            return
        dur = render_engine.media_duration(p) or 5.0
        kind = "image" if p.lower().endswith((".jpg", ".png", ".jpeg", ".webp")) else "video"
        self.proj["clips"].append({"id": f"c{len(self.proj['clips'])}", "kind": kind,
                                   "source": p, "in_s": 0.0, "out_s": dur, "speed": 1.0,
                                   "transition": "fade", "ken_burns": "", "volume": 1.0,
                                   "layer": 0, "pip": None, "label": "", "meta": {}})
        self._refresh_tree()

    def edit_clip(self):
        sel = self.tree.selection()
        if not sel or not self.proj:
            return
        idx = list(self.tree.get_children()).index(sel[0])
        c = self.proj["clips"][idx]
        w = tk.Toplevel(self); w.title(f"Edit clip {c['id']}"); w.geometry("420x420"); w.configure(bg=BG)
        g = lambda lbl, val, typ="str": (tk.Label(w, text=lbl, bg=BG, fg=MUT).pack(anchor="w", padx=12, pady=(8, 0)),
                                         (e := tk.Entry(w, bg=BG2, fg=TXT, insertbackground=TXT, relief="flat", font=(FONT, 11))),
                                         e.insert(0, str(val)), e.pack(fill="x", padx=12))
        outs = {}
        for key, label in [("in_s", "Trim in (s)"), ("out_s", "Trim out (s)"), ("speed", "Speed (0.25–4)"),
                           ("volume", "Volume"), ("transition", "Transition (cut/fade/slideleft/wipe/glitch)"),
                           ("ken_burns", "Ken-Burns (none/zoomin/zoomout/panleft/panright)"),
                           ("layer", "Layer (0 main, 1 pip)"), ("label", "Lower-third label")]:
            e = tk.Entry(w, bg=BG2, fg=TXT, insertbackground=TXT, relief="flat", font=(FONT, 11))
            tk.Label(w, text=label, bg=BG, fg=MUT).pack(anchor="w", padx=12, pady=(6, 0))
            e.insert(0, str(c.get(key, ""))); e.pack(fill="x", padx=12)
            outs[key] = e

        def save():
            for k, e in outs.items():
                v = e.get()
                try:
                    c[k] = float(v) if k in ("in_s", "out_s", "speed", "volume") else int(v) if k == "layer" else v
                except ValueError:
                    pass
            json.dump(self.proj, open(os.path.join(self.proj_dir, "project.json"), "w", encoding="utf-8"), indent=2)
            self._refresh_tree(); w.destroy()
        ttk.Button(w, text="Save", command=save).pack(pady=14)

    def render_project(self):
        if not self.proj:
            return messagebox.showinfo("VidForge", "Open a project first.")
        json.dump(self.proj, open(os.path.join(self.proj_dir, "project.json"), "w", encoding="utf-8"), indent=2)
        out = os.path.join(self.proj_dir, "final.mp4")
        words = [wd for ws in self.proj.get("word_timestamps", []) for wd in ws]
        tl = render_engine.Timeline(
            width=self.proj["canvas"]["w"], height=self.proj["canvas"]["h"],
            fps=self.proj["canvas"]["fps"], crf=self.proj["canvas"].get("crf", 19),
            clips=[render_engine.Clip(**c) for c in self.proj["clips"]],
            voiceover=self.proj["voiceover"], music=self.proj.get("music"),
            captions_preset=self.proj["captions"]["preset"],
            captions_enabled=self.proj["captions"]["enabled"],
            watermark=self.proj.get("watermark", ""), title=self.proj.get("title", ""),
            chapters=self.proj.get("chapters", []))
        if words and tl.captions_enabled:
            with open(os.path.join(self.proj_dir, "captions.ass"), "w", encoding="utf-8") as f:
                f.write(captions.render_ass(tl.captions_preset, tl.width, tl.height, words))
        def work():
            return render_engine.render(tl, out, self.proj_dir,
                                        progress_cb=lambda p: self.ui(self._gen_progress, p, f"Rendering {int(p*100)}%"))
        def done(r, e):
            self._prog["value"] = 0
            if e:
                return messagebox.showerror("Render failed", str(e)[:900])
            self._last_out = out
            messagebox.showinfo("VidForge", "Timeline rendered → " + out)
        self.run_bg(work, done)

    # ------------------------------------------------------------ CAPTIONS tab
    def tab_captions(self, fr):
        left = ttk.Frame(fr); left.pack(side="left", fill="y", padx=10, pady=10)
        tk.Label(left, text="216 animated presets", bg=BG, fg=MUT).pack(anchor="w")
        self.cap_filter = ttk.Combobox(left, values=["All families"] + sorted({p.family for p in captions.LIBRARY}),
                                       state="readonly", width=22)
        self.cap_filter.set("All families"); self.cap_filter.pack(fill="x", pady=4)
        self.cap_list = tk.Listbox(left, bg=BG2, fg=TXT, width=34, height=22, relief="flat",
                                   font=(FONT, 10), selectbackground=ACC)
        self.cap_list.pack(fill="both", expand=True)
        self.cap_filter.bind("<<ComboboxSelected>>", lambda e: self._fill_cap_list())
        self.cap_list.bind("<<ListboxSelect>>", lambda e: self._show_cap_preview())
        self._fill_cap_list()

        right = ttk.Frame(fr); right.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        tk.Label(right, text="Live preview", bg=BG, fg=MUT).pack(anchor="w")
        self.cap_img = tk.Label(right, bg="#12121a")
        self.cap_img.pack(pady=6)
        ttk.Button(right, text="✔ Use as default for new videos", style="Ghost.TButton",
                   command=self._use_cap).pack(anchor="w", pady=4)

        creator = tk.LabelFrame(right, text="Create your own caption template", bg=BG, fg=TXT,
                                font=(FONT, 10, "bold"))
        creator.pack(fill="x", pady=10)
        fields = {}
        grid = ttk.Frame(creator); grid.pack(fill="x", padx=8, pady=6)
        rows = [("name", "Name"), ("font", "Font"), ("palette", "Palette (white/yellow_pop/cyan_neon/hot_pink/matrix/fire)"),
                ("position", "Position (bottom/center/top/lower-third)"),
                ("anim", "Animation (pop/karaoke/neon/zoom/shake/wave/drop/flip/typewriter/slide/fade/minimal/box/meme/lower3rd/outline)"),
                ("size_pct", "Size % of height (4–9)"), ("border_px", "Outline px")]
        for i, (k, lbl) in enumerate(rows):
            tk.Label(grid, text=lbl, bg=BG, fg=MUT, font=(FONT, 9)).grid(row=i, column=0, sticky="w", padx=4)
            e = tk.Entry(grid, bg=BG2, fg=TXT, insertbackground=TXT, relief="flat", width=28)
            e.grid(row=i, column=1, sticky="we", padx=4, pady=1)
            fields[k] = e
        fields["name"].insert(0, "My Custom Pop")
        fields["font"].insert(0, "Arial Black")
        fields["palette"].insert(0, "hot_pink")
        fields["position"].insert(0, "bottom")
        fields["anim"].insert(0, "pop")
        fields["size_pct"].insert(0, "6.5")
        fields["border_px"].insert(0, "3")

        def create():
            try:
                p = captions.CaptionPreset(
                    id="custom-" + fields["name"].get().lower().replace(" ", "-"),
                    name=fields["name"].get(), family="Custom", font=fields["font"].get(),
                    size_pct=float(fields["size_pct"].get()), palette=fields["palette"].get(),
                    position=fields["position"].get(), bold=True, italic=False,
                    border_px=int(fields["border_px"].get()), shadow_px=0,
                    anim=fields["anim"].get(), per_word=True)
                captions.save_custom_preset(p)
                captions.LIBRARY.append(p); captions._BY_ID[p.id] = p
                self._fill_cap_list()
                messagebox.showinfo("VidForge", "Caption template saved: " + p.name)
            except Exception as e:
                messagebox.showerror("Error", str(e))
        ttk.Button(creator, text="💾 Save new template", command=create).pack(pady=6)

    def _fill_cap_list(self):
        self.cap_list.delete(0, "end")
        f = self.cap_filter.get()
        self._shown = [p for p in captions.LIBRARY if f == "All families" or p.family == f]
        for p in self._shown[:300]:
            self.cap_list.insert("end", p.name)

    def _show_cap_preview(self):
        sel = self.cap_list.curselection()
        if not sel:
            return
        p = self._shown[sel[0]]
        png = os.path.join(config.CACHE_DIR, f"capprev_{p.id}.png")
        try:
            captions.preview_png(p.id, png)
            img = tk.PhotoImage(file=png)
            self.cap_img.config(image=img); self.cap_img.image = img
        except Exception:
            pass

    def _use_cap(self):
        sel = self.cap_list.curselection()
        if sel:
            config.CFG["caption_default"] = self._shown[sel[0]].id
            config.save_config(config.CFG)
            self.set_status("Default caption → " + self._shown[sel[0]].name)

    # ------------------------------------------------------------ MEDIA tab
    def tab_media(self, fr):
        bar = ttk.Frame(fr); bar.pack(fill="x", padx=10, pady=8)
        self.mq = tk.Entry(bar, bg=BG2, fg=TXT, insertbackground=TXT, relief="flat", font=(FONT, 11))
        self.mq.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.mk = ttk.Combobox(bar, values=["video", "image"], width=8, state="readonly")
        self.mk.set("video"); self.mk.pack(side="left", padx=4)
        ttk.Button(bar, text="Search all stock APIs", command=self.media_search).pack(side="left", padx=6)
        ttk.Button(bar, text="🌐 Open in built-in browser", style="Ghost.TButton",
                   command=self.browser_go).pack(side="left")
        cols = ("source", "kind", "license", "credit", "url")
        self.mtree = ttk.Treeview(fr, columns=cols, show="headings")
        for c, w in zip(cols, (90, 70, 260, 160, 520)):
            self.mtree.heading(c, text=c.title()); self.mtree.column(c, width=w)
        self.mtree.pack(fill="both", expand=True, padx=10)
        ctx = tk.Menu(self, tearoff=0)
        ctx.add_command(label="Download & add to pool", command=self.media_download)
        self.mtree.bind("<Double-1>", lambda e: self.media_download())

    def media_search(self):
        q = self.mq.get().strip()
        if not q:
            return
        def work():
            return media_search.search_all(q, kind=self.mk.get())
        def done(r, e):
            self.mtree.delete(*self.mtree.get_children())
            self._assets = r or []
            for a in self._assets:
                self.mtree.insert("", "end", values=(a["source"], a["kind"], a.get("license", "")[:40],
                                                   str(a.get("credit", ""))[:24], a["url"][:120]))
            self.set_status(f"{len(self._assets)} royalty-free results for '{q}' (double-click to download)")
            if e:
                messagebox.showerror("Search failed", str(e)[:600])
        self.run_bg(work, done)

    def media_download(self):
        sel = self.mtree.selection()
        if not sel or not hasattr(self, "_assets"):
            return
        idx = list(self.mtree.get_children()).index(sel[0])
        a = self._assets[idx]
        def work():
            return media_search.fetch_asset(a)
        def done(r, e):
            if e:
                return messagebox.showerror("Download failed", str(e)[:600])
            self.pool = getattr(self, "pool", [])
            self.pool.append(r)
            self.set_status(f"Saved to media pool: {r}")
            messagebox.showinfo("VidForge", "Downloaded ✓\nUse 'Add clip from file' in Timeline Editor.")
        self.run_bg(work, done)

    def browser_go(self):
        url = self.mq.get().strip()
        if not url.startswith("http"):
            url = "https://duckduckgo.com/?q=" + url.replace(" ", "+")
        def work():
            from core.browser import ForgeBrowser, quick_fetch_page
            try:
                with ForgeBrowser(headless=True) as br:
                    t = br.goto(url)
                    return {"title": t, "media": br.sniff_media()}
            except Exception:
                return quick_fetch_page(url)
        def done(r, e):
            if e:
                return messagebox.showerror("Browser failed", str(e)[:600] +
                                           "\nTip: pip install playwright && playwright install chromium")
            self.mtree.delete(*self.mtree.get_children())
            media = r.get("media") or [{"kind": "image", "url": u} for u in r.get("images", [])] + \
                    [{"kind": "video", "url": u} for u in r.get("videos", [])]
            self._assets = [{**m, "source": "browser", "license": "web capture – verify reuse",
                             "credit": r.get("title", "")[:20]} for m in media]
            for a in self._assets:
                self.mtree.insert("", "end", values=(a["source"], a["kind"], a["license"],
                                                   a["credit"], a["url"][:120]))
            self.set_status(f"Sniffed {len(media)} media files from page")
        self.run_bg(work, done)

    # ------------------------------------------------------------ AUDIO tab
    def tab_audio(self, fr):
        box = ttk.Frame(fr); box.pack(fill="x", padx=12, pady=10)
        tk.Label(box, text="Hardened Edge-TTS (auto-retry + voice rotation) + fully offline local voices",
                 bg=BG, fg=MUT).pack(anchor="w")
        self.tts_text = tk.Text(box, height=5, bg=BG2, fg=TXT, insertbackground=TXT,
                                relief="flat", font=(FONT, 11))
        self.tts_text.pack(fill="x", pady=6)
        row = ttk.Frame(box); row.pack(fill="x")
        tk.Label(row, text="Engine", bg=BG, fg=MUT).pack(side="left")
        self.tts_eng = ttk.Combobox(row, values=["edge", "pyttsx3", "espeak"], width=10, state="readonly")
        self.tts_eng.set(config.CFG["tts_engine"]); self.tts_eng.pack(side="left", padx=6)
        tk.Label(row, text="Voice", bg=BG, fg=MUT).pack(side="left")
        self.tts_voice = ttk.Combobox(row, values=[
            "en-US-AriaNeural", "en-US-GuyNeural", "en-GB-RyanNeural", "en-US-AnaNeural",
            "ur-PK-IraNeural", "hi-IN-MadhurNeural", "tr-TR-EmelNeural", "es-ES-ElviraNeural"], width=22)
        self.tts_voice.set(config.CFG["tts_voice"]); self.tts_voice.pack(side="left", padx=6)
        tk.Label(row, text="Rate", bg=BG, fg=MUT).pack(side="left")
        self.tts_rate = ttk.Combobox(row, values=["-25%", "-10%", "+0%", "+8%", "+20%", "+40%"], width=7)
        self.tts_rate.set(config.CFG["tts_rate"]); self.tts_rate.pack(side="left", padx=6)
        ttk.Button(row, text="▶ Test & Save", command=self.tts_test).pack(side="left", padx=12)
        ttk.Button(row, text="Fetch ALL voices", style="Ghost.TButton",
                   command=self.fetch_voices).pack(side="left")
        self.audio_note = tk.Label(fr, text="", bg=BG, fg="#9fe8b8", wraplength=1100, justify="left")
        self.audio_note.pack(fill="x", padx=12)

    def fetch_voices(self):
        def work():
            return tts_engine.list_edge_voices()
        def done(r, e):
            if e or not r:
                self.audio_note.config(text="Could not list voices (network?): " + str(e))
                return
            names = [v["ShortName"] for v in r]
            self.tts_voice["values"] = names
            self.audio_note.config(text=f"Loaded {len(names)} Edge voices — type to filter (e.g. 'ur', 'hi', 'de').")
        self.run_bg(work, done)

    def tts_test(self):
        txt = self.tts_text.get("1.0", "end").strip()
        if not txt:
            return
        out = os.path.join(config.CACHE_DIR, "tts_test.mp3")
        cfg = config.CFG
        cfg.update({"tts_engine": self.tts_eng.get(), "tts_voice": self.tts_voice.get(),
                    "tts_rate": self.tts_rate.get()})
        config.save_config(cfg)
        def work():
            return tts_engine.synthesize(txt, out, engine=self.tts_eng.get(),
                                         voice=self.tts_voice.get(), rate=self.tts_rate.get(),
                                         word_timestamps_json=out + ".words.json")
        def done(r, e):
            if e:
                return messagebox.showerror("TTS failed", str(e)[:800])
            self.audio_note.config(text=f"OK via {r['engine']} ({r.get('voice','local')}) → {out}")
            try:
                if sys.platform.startswith("win"):
                    os.startfile(out)
            except Exception:
                pass
        self.run_bg(work, done)

    # ------------------------------------------------------------ CLIPPER tab
    def tab_clipper(self, fr):
        box = ttk.Frame(fr); box.pack(fill="x", padx=12, pady=10)
        row = ttk.Frame(box); row.pack(fill="x")
        self.clip_src = tk.StringVar()
        tk.Entry(row, textvariable=self.clip_src, bg=BG2, fg=TXT, insertbackground=TXT,
                 relief="flat", font=(FONT, 11), width=70).pack(side="left")
        ttk.Button(row, text="…", style="Ghost.TButton", command=lambda: self.clip_src.set(
            filedialog.askopenfilename(filetypes=[("Video", "*.mp4 *.mov *.mkv *.webm")]) or "")
        ).pack(side="left", padx=4)
        ttk.Button(box, text="🔎 Find smart highlight moments", command=self.find_clips)\
            .pack(anchor="w", pady=8)
        cols = ("start", "end", "score")
        self.clip_tree = ttk.Treeview(fr, columns=cols, show="headings", height=8)
        for c, w in zip(cols, (120, 120, 100)):
            self.clip_tree.heading(c, text=c.title()); self.clip_tree.column(c, width=w)
        self.clip_tree.pack(fill="x", padx=12)
        o = ttk.Frame(fr); o.pack(fill="x", padx=12, pady=10)
        self.clip_vertical = tk.BooleanVar(value=True)
        tk.Checkbutton(o, text="Reframe vertical 9:16 (Shorts/Reels/TikTok)", variable=self.clip_vertical,
                       bg=BG, fg=TXT, selectcolor=BG2, activebackground=BG).pack(side="left")
        tk.Label(o, text="Speed", bg=BG, fg=MUT).pack(side="left", padx=(20, 2))
        self.clip_speed = ttk.Combobox(o, values=["0.5", "1.0", "1.5", "2.0"], width=5)
        self.clip_speed.set("1.0"); self.clip_speed.pack(side="left")
        ttk.Button(o, text="✂ Export selected clip", command=self.export_clip).pack(side="right")

    def find_clips(self):
        src = self.clip_src.get()
        if not src:
            return
        def work():
            return director.smart_clip_finder(src)
        def done(r, e):
            self.clip_tree.delete(*self.clip_tree.get_children())
            self._clips = r or []
            for c in self._clips:
                self.clip_tree.insert("", "end", values=(c["start_s"], c["end_s"], c["score"]))
            if e:
                messagebox.showerror("Failed", str(e)[:600])
        self.run_bg(work, done)

    def export_clip(self):
        sel = self.clip_tree.selection()
        if not sel:
            return messagebox.showinfo("Clipper", "Pick a segment above (or enter times in Smart list).")
        c = self._clips[list(self.clip_tree.get_children()).index(sel[0])]
        out = filedialog.asksaveasfilename(defaultextension=".mp4", initialfile=f"clip_{c['start_s']}.mp4")
        if not out:
            return
        def work():
            return director.clip_video(self.clip_src.get(), c["start_s"], c["end_s"], out,
                                       vertical=self.clip_vertical.get(),
                                       speed=float(self.clip_speed.get()))
        def done(r, e):
            if e:
                return messagebox.showerror("Clip failed", str(e)[:600])
            self._last_out = r
            messagebox.showinfo("Clipper", "Clip exported ✓ " + r)
        self.run_bg(work, done)

    # ------------------------------------------------------------ AGENT tab
    def tab_agent(self, fr):
        tk.Label(fr, text="Give any AI agent FULL control of this studio over MCP "
               "(Model Context Protocol) — 23 tools: research → script → TTS → stock → browser → "
               "motion graphics → timeline → render.",
               bg=BG, fg=TXT, wraplength=1150, justify="left", font=(FONT, 11)).pack(anchor="w", padx=14, pady=12)
        srv = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mcp", "server.py"))
        snippet = json.dumps({"mcpServers": {"vidforge": {
            "command": sys.executable, "args": [srv]}}}, indent=2)
        box = tk.Text(fr, height=12, bg="#0a0e14", fg="#7fd4ff", relief="flat", font=("Consolas", 10))
        box.pack(fill="x", padx=14)
        box.insert("1.0", snippet)
        row = ttk.Frame(fr); row.pack(pady=8)
        ttk.Button(row, text="📋 Copy config", style="Ghost.TButton",
                   command=lambda: (self.clipboard_clear(), self.clipboard_append(snippet),
                                    self.set_status("MCP config copied"))).pack(side="left")
        ttk.Button(row, text="🩺 Self-test MCP server", command=self.mcp_test).pack(side="left", padx=8)
        self.agent_log = tk.Label(fr, text="", bg=BG, fg="#9fe8b8", wraplength=1100, justify="left")
        self.agent_log.pack(fill="x", padx=14)

    def mcp_test(self):
        srv = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mcp", "server.py"))
        req = '\n'.join([json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
                          json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})])
        def work():
            p = subprocess.run([sys.executable, srv], input=req, capture_output=True, text=True, timeout=60)
            return p.stdout
        def done(r, e):
            self.agent_log.config(text=("Handshake OK — server listed its tools ✓" if r and '"tools"' in r
                                        else "Test failed: " + str(e or r)[:400]))
        self.run_bg(work, done)

    # ------------------------------------------------------------ SETTINGS tab
    def tab_settings(self, fr):
        cfg = config.CFG
        keys = [("pexels_api_key", "Pexels API key (free signup: pexels.com/api)"),
                ("pixabay_api_key", "Pixabay API key (free signup: pixabay.com/api)"),
                ("unsplash_access_key", "Unsplash Access key"),
                ("openai_api_key", "OpenAI key (script brain; optional)"),
                ("anthropic_api_key", "Anthropic key (optional alternative)"),
                ("ollama_model", "Ollama model for 100% local LLM (offline brain)"),
                ("chrome_path", "Chrome/Edge executable for built-in browser (blank=auto)"),
                ("default_crf", "Quality CRF (16 high … 23 small)")]
        entries = {}
        box = ttk.Frame(fr); box.pack(fill="x", padx=14, pady=10)
        for i, (k, lbl) in enumerate(keys):
            tk.Label(box, text=lbl, bg=BG, fg=MUT, font=(FONT, 9)).grid(row=i, column=0, sticky="w", padx=4, pady=3)
            e = tk.Entry(box, bg=BG2, fg=TXT, insertbackground=TXT, relief="flat", width=52, font=(FONT, 10))
            e.insert(0, str(cfg.get(k, ""))); e.grid(row=i, column=1, sticky="we", padx=4)
            entries[k] = e
        mixrow = ttk.Frame(fr); mixrow.pack(fill="x", padx=14)
        self.mixkit = tk.BooleanVar(value=cfg.get("mixkit_enabled", True))
        tk.Checkbutton(mixrow, text="Enable Mixkit free catalogue (keyless)", variable=self.mixkit,
                       bg=BG, fg=TXT, selectcolor=BG2, activebackground=BG).pack(side="left")

        def save():
            for k, e in entries.items():
                v = e.get()
                cfg[k] = int(v) if k == "default_crf" and v.isdigit() else v
            cfg["mixkit_enabled"] = self.mixkit.get()
            config.save_config(cfg)
            messagebox.showinfo("VidForge", "Settings saved ✓")
        ttk.Button(fr, text="💾 Save settings", command=save).pack(pady=14, anchor="w", padx=14)
        tk.Label(fr, text="Tip: everything works WITHOUT keys too — Archive.org + Mixkit + built-in "
               "browser + local director + Edge-TTS cover you keyless.",
               bg=BG, fg=MUT, wraplength=1100, justify="left").pack(anchor="w", padx=14)


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
