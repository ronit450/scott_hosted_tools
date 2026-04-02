#!/usr/bin/env python
"""
Daedalus — AOI Tiling Engine
Simple GUI front-end for daedalus_core.run_tiling()

Analyst workflow:
- Choose AOI mode:
    * Circle AOI (center lat/lon + radius), OR
    * AOI file (KML/KMZ/GeoJSON/SHP/GPKG)
- Set tile size (km)
- Choose output folder
- Click "Run tiling"

Outputs:
- Uses daedalus_core.run_tiling(...) under the hood
- Shows a formatted summary of strategies:
    Balanced, Full, Minimal, Max_coverage, Compact
- Allows hiding/showing strategies in the summary via checkboxes
- Shows a progress bar + status line during runs
- Tooltips explain each strategy when hovering over its checkbox
"""

import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from daedalus_core import (
    run_tiling,
    OUT_DIR as DEFAULT_OUT_DIR,
    TILE_SIZE_KM as DEFAULT_TILE_SIZE_KM,
    CENTER_LAT as DEFAULT_CENTER_LAT,
    CENTER_LON as DEFAULT_CENTER_LON,
    RADIUS_KM as DEFAULT_RADIUS_KM,
)


# --------------------------------------------------
# Simple tooltip helper for Tk widgets
# --------------------------------------------------
class ToolTip:
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None

        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tipwindow or not self.text:
            return
        # Position tooltip near widget
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 20

        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)  # No window decorations
        tw.wm_geometry(f"+{x}+{y}")

        label = tk.Label(
            tw,
            text=self.text,
            justify="left",
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            font=("TkDefaultFont", 9),
            padx=4,
            pady=2,
            wraplength=300,
        )
        label.pack(ipadx=1, ipady=1)

    def hide_tip(self, event=None):
        tw = self.tipwindow
        self.tipwindow = None
        if tw is not None:
            tw.destroy()


class TilerGUI:
    def __init__(self, master: tk.Tk):
        self.master = master
        master.title("Daedalus — AOI Tiling Engine")
        master.geometry("900x650")

        # --- State variables ---
        self.aoi_mode = tk.StringVar(value="file")  # "circle" or "file"
        self.center_lat_var = tk.StringVar(value=str(DEFAULT_CENTER_LAT))
        self.center_lon_var = tk.StringVar(value=str(DEFAULT_CENTER_LON))
        self.radius_km_var = tk.StringVar(value=str(DEFAULT_RADIUS_KM))
        self.tile_size_km_var = tk.StringVar(value=str(DEFAULT_TILE_SIZE_KM))

        self.aoi_file_var = tk.StringVar(value="")
        self.out_dir_var = tk.StringVar(value=str(DEFAULT_OUT_DIR))

        # Status line
        self.status_var = tk.StringVar(value="Status: Ready")

        # Strategy visibility flags (for summary display only)
        self.show_balanced = tk.BooleanVar(value=True)
        self.show_full = tk.BooleanVar(value=True)
        self.show_minimal = tk.BooleanVar(value=True)
        self.show_maxcov = tk.BooleanVar(value=True)
        self.show_compact = tk.BooleanVar(value=True)

        # for disabling/enabling Run button during execution
        self.is_running = False

        self._build_ui()
        self._update_mode_widgets()

    # --------------------------------------------------
    # UI BUILD
    # --------------------------------------------------
    def _build_ui(self):
        # Top frame for AOI mode
        mode_frame = ttk.LabelFrame(self.master, text="AOI Mode", padding=10)
        mode_frame.pack(fill="x", padx=10, pady=5)

        ttk.Radiobutton(
            mode_frame,
            text="AOI file (KML / KMZ / GeoJSON / SHP / GPKG)",
            variable=self.aoi_mode,
            value="file",
            command=self._update_mode_widgets,
        ).grid(row=0, column=0, sticky="w", pady=2)

        ttk.Radiobutton(
            mode_frame,
            text="Circle AOI (center + radius)",
            variable=self.aoi_mode,
            value="circle",
            command=self._update_mode_widgets,
        ).grid(row=0, column=1, sticky="w", pady=2)

        # AOI file frame
        file_frame = ttk.Frame(mode_frame)
        file_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=5)
        mode_frame.columnconfigure(0, weight=1)
        mode_frame.columnconfigure(1, weight=1)

        ttk.Label(file_frame, text="AOI file:").grid(row=0, column=0, sticky="e", padx=2)
        self.aoi_file_entry = ttk.Entry(file_frame, textvariable=self.aoi_file_var)
        self.aoi_file_entry.grid(row=0, column=1, sticky="ew", padx=2)
        file_frame.columnconfigure(1, weight=1)
        ttk.Button(file_frame, text="Browse...", command=self._browse_aoi_file).grid(
            row=0, column=2, padx=2
        )

        # Circle frame
        circle_frame = ttk.LabelFrame(self.master, text="Circle AOI parameters", padding=10)
        circle_frame.pack(fill="x", padx=10, pady=5)
        self.circle_frame = circle_frame  # keep reference for enable/disable

        ttk.Label(circle_frame, text="Center lat:").grid(row=0, column=0, sticky="e", padx=2, pady=2)
        ttk.Entry(circle_frame, textvariable=self.center_lat_var, width=15).grid(
            row=0, column=1, sticky="w", padx=2, pady=2
        )

        ttk.Label(circle_frame, text="Center lon:").grid(row=0, column=2, sticky="e", padx=2, pady=2)
        ttk.Entry(circle_frame, textvariable=self.center_lon_var, width=15).grid(
            row=0, column=3, sticky="w", padx=2, pady=2
        )

        ttk.Label(circle_frame, text="Radius (km):").grid(row=0, column=4, sticky="e", padx=2, pady=2)
        ttk.Entry(circle_frame, textvariable=self.radius_km_var, width=10).grid(
            row=0, column=5, sticky="w", padx=2, pady=2
        )

        # Tile + output
        cfg_frame = ttk.LabelFrame(self.master, text="Tiling configuration", padding=10)
        cfg_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(cfg_frame, text="Tile size (km):").grid(row=0, column=0, sticky="e", padx=2, pady=2)
        ttk.Entry(cfg_frame, textvariable=self.tile_size_km_var, width=10).grid(
            row=0, column=1, sticky="w", padx=2, pady=2
        )

        ttk.Label(cfg_frame, text="Output folder:").grid(row=1, column=0, sticky="e", padx=2, pady=2)
        self.out_dir_entry = ttk.Entry(cfg_frame, textvariable=self.out_dir_var)
        self.out_dir_entry.grid(row=1, column=1, sticky="ew", padx=2, pady=2)
        cfg_frame.columnconfigure(1, weight=1)
        ttk.Button(cfg_frame, text="Browse...", command=self._browse_out_dir).grid(
            row=1, column=2, padx=2, pady=2
        )

        # Strategy filter frame
        strat_frame = ttk.LabelFrame(self.master, text="Strategies to display in summary", padding=10)
        strat_frame.pack(fill="x", padx=10, pady=5)

        # Checkbuttons with tooltips
        self.cb_balanced = ttk.Checkbutton(
            strat_frame, text="Balanced", variable=self.show_balanced
        )
        self.cb_balanced.grid(row=0, column=0, sticky="w", padx=5, pady=2)

        self.cb_full = ttk.Checkbutton(
            strat_frame, text="Full", variable=self.show_full
        )
        self.cb_full.grid(row=0, column=1, sticky="w", padx=5, pady=2)

        self.cb_minimal = ttk.Checkbutton(
            strat_frame, text="Minimal", variable=self.show_minimal
        )
        self.cb_minimal.grid(row=0, column=2, sticky="w", padx=5, pady=2)

        self.cb_maxcov = ttk.Checkbutton(
            strat_frame, text="Max coverage", variable=self.show_maxcov
        )
        self.cb_maxcov.grid(row=0, column=3, sticky="w", padx=5, pady=2)

        self.cb_compact = ttk.Checkbutton(
            strat_frame, text="Compact", variable=self.show_compact
        )
        self.cb_compact.grid(row=0, column=4, sticky="w", padx=5, pady=2)

        # Attach tooltips to strategy checkboxes
        ToolTip(
            self.cb_balanced,
            "Balanced: Best overall score.\n"
            "- High coverage\n"
            "- Moderated overlap\n"
            "- Reasonable tile count\n"
            "Good default choice for most AOIs."
        )
        ToolTip(
            self.cb_full,
            "Full: Prioritizes coverage.\n"
            "- Highest coverage among pruned options\n"
            "- Then chooses the fewest tiles at that coverage\n"
            "Use when avoiding gaps is more important than overlap."
        )
        ToolTip(
            self.cb_minimal,
            "Minimal: Fewest tiles with acceptable coverage.\n"
            "- Minimizes number of images\n"
            "- Ensures coverage ≥ MINIMAL_COVERAGE_FLOOR (e.g. 95%)\n"
            "Use when imagery budget is tight or tasking slots are limited."
        )
        ToolTip(
            self.cb_maxcov,
            "Max coverage: No pruning.\n"
            "- Uses the same grid offset as 'Full'\n"
            "- Keeps ALL tiles that meet the inside_fraction threshold\n"
            "- Highest coverage and highest overlap\n"
            "Use when absolutely no coverage gaps are acceptable."
        )
        ToolTip(
            self.cb_compact,
            "Compact: Core AOI only.\n"
            "- Starts from the Balanced solution\n"
            "- Keeps only tiles with high inside_fraction\n"
            "- Focuses on interior / core of AOI, less edge coverage\n"
            "Use when you only care about the main AOI interior."
        )

        # Run + Status + Progress row
        run_frame = ttk.Frame(self.master)
        run_frame.pack(fill="x", padx=10, pady=5)

        self.run_button = ttk.Button(run_frame, text="Run tiling", command=self._on_run_clicked)
        self.run_button.pack(side="left")

        self.open_out_button = ttk.Button(run_frame, text="Open output folder", command=self._open_output_folder)
        self.open_out_button.pack(side="left", padx=5)

        # Progress bar (indeterminate)
        self.progress = ttk.Progressbar(run_frame, mode="indeterminate", length=160)
        self.progress.pack(side="left", padx=10)

        # Status label on the right
        self.status_label = ttk.Label(run_frame, textvariable=self.status_var)
        self.status_label.pack(side="right")

        # Log / summary text area
        log_frame = ttk.LabelFrame(self.master, text="Run Summary", padding=5)
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.log_text = tk.Text(log_frame, wrap="word", state="disabled")
        self.log_text.pack(fill="both", expand=True)

    # --------------------------------------------------
    # UI HELPERS
    # --------------------------------------------------
    def _update_mode_widgets(self):
        mode = self.aoi_mode.get()
        # Enable/disable AOI file entry
        if mode == "file":
            self.aoi_file_entry.configure(state="normal")
        else:
            self.aoi_file_entry.configure(state="disabled")

        # Enable/disable circle fields
        for child in self.circle_frame.winfo_children():
            if isinstance(child, (ttk.Entry, ttk.Label)):
                state = "normal" if mode == "circle" else "disabled"
                child.configure(state=state)

    def _browse_aoi_file(self):
        filetypes = [
            ("Vector files", "*.kml *.kmz *.geojson *.json *.shp *.gpkg"),
            ("KML", "*.kml"),
            ("KMZ", "*.kmz"),
            ("GeoJSON", "*.geojson *.json"),
            ("Shapefile", "*.shp"),
            ("GeoPackage", "*.gpkg"),
            ("All files", "*.*"),
        ]
        path = filedialog.askopenfilename(title="Select AOI file", filetypes=filetypes)
        if path:
            self.aoi_file_var.set(path)

    def _browse_out_dir(self):
        path = filedialog.askdirectory(title="Select output folder")
        if path:
            self.out_dir_var.set(path)

    def _open_output_folder(self):
        path = self.out_dir_var.get().strip()
        if not path:
            messagebox.showinfo("Output folder", "No output folder selected.")
            return
        out_path = Path(path)
        if not out_path.exists():
            messagebox.showwarning("Output folder", f"Folder does not exist:\n{out_path}")
            return

        try:
            # Windows: use explorer
            import os
            os.startfile(out_path)  # type: ignore[attr-defined]
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder:\n{e}")

    def append_log(self, text: str, newline: bool = True):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + ("\n" if newline else ""))
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    # --------------------------------------------------
    # RUN BUTTON / BACKGROUND EXECUTION
    # --------------------------------------------------
    def _on_run_clicked(self):
        if self.is_running:
            return

        try:
            cfg = self._collect_config()
        except ValueError as e:
            messagebox.showerror("Invalid input", str(e))
            return

        self.is_running = True
        self.run_button.configure(state="disabled")
        self.status_var.set("Status: Running…")
        self._clear_log()
        self.append_log("=== Daedalus run started ===")

        # Start progress bar
        self.progress.start(10)

        thread = threading.Thread(target=self._run_tiling_thread, args=(cfg,), daemon=True)
        thread.start()

    def _collect_config(self) -> dict:
        mode = self.aoi_mode.get()
        tile_size_str = self.tile_size_km_var.get().strip()
        out_dir_str = self.out_dir_var.get().strip()

        if not tile_size_str:
            raise ValueError("Tile size (km) is required.")
        try:
            tile_size_km = float(tile_size_str)
            if tile_size_km <= 0:
                raise ValueError
        except ValueError:
            raise ValueError("Tile size must be a positive number (km).")

        if not out_dir_str:
            raise ValueError("Output folder is required.")
        out_dir = Path(out_dir_str)

        if mode == "file":
            aoi_file = self.aoi_file_var.get().strip()
            if not aoi_file:
                raise ValueError("AOI file is required for 'AOI file' mode.")
            return {
                "use_circle_aoi": False,
                "center_lat": DEFAULT_CENTER_LAT,
                "center_lon": DEFAULT_CENTER_LON,
                "radius_km": DEFAULT_RADIUS_KM,
                "aoi_input": aoi_file,
                "tile_size_km": tile_size_km,
                "out_dir": str(out_dir),
            }
        else:  # circle mode
            lat_str = self.center_lat_var.get().strip()
            lon_str = self.center_lon_var.get().strip()
            rad_str = self.radius_km_var.get().strip()

            try:
                center_lat = float(lat_str)
                center_lon = float(lon_str)
                radius_km = float(rad_str)
            except ValueError:
                raise ValueError("Center lat/lon and radius must be numeric.")

            if radius_km <= 0:
                raise ValueError("Radius (km) must be positive.")

            return {
                "use_circle_aoi": True,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "radius_km": radius_km,
                "aoi_input": None,
                "tile_size_km": tile_size_km,
                "out_dir": str(out_dir),
            }

    def _run_tiling_thread(self, cfg: dict):
        try:
            result = run_tiling(
                use_circle_aoi=cfg["use_circle_aoi"],
                center_lat=cfg["center_lat"],
                center_lon=cfg["center_lon"],
                radius_km=cfg["radius_km"],
                aoi_input=cfg["aoi_input"],
                tile_size_km=cfg["tile_size_km"],
                out_dir=cfg["out_dir"],
            )
            # Summarize results in the GUI
            self._summarize_result(result)
            self.status_var.set("Status: Finished ✔")
        except Exception as e:
            self.append_log("\nERROR: {}".format(e))
            self.status_var.set("Status: Error ❌")
            messagebox.showerror("Error during tiling", str(e))
        finally:
            self.is_running = False
            # Stop progress bar
            self.progress.stop()
            self.run_button.configure(state="normal")

    def _summarize_result(self, result: dict):
        self.append_log("\n=== Tiling complete ===")
        aois = result.get("aois", [])
        if not aois:
            self.append_log("No AOIs returned.")
            return

        # Map strategy name -> visibility flag
        show_flags = {
            "balanced": self.show_balanced.get(),
            "full": self.show_full.get(),
            "minimal": self.show_minimal.get(),
            "max_coverage": self.show_maxcov.get(),
            "compact": self.show_compact.get(),
        }

        for aoi_result in aois:
            name = aoi_result.get("aoi_name", "unknown")
            out_dir = aoi_result.get("output_dir", "")
            self.append_log("\n----------------------------------------")
            self.append_log(f"AOI: {name}")
            self.append_log(f"Output dir: {out_dir}")
            self.append_log(f"KML: {aoi_result.get('kml_path', '')}")
            self.append_log(f"Strategy summary CSV: {aoi_result.get('strategy_summary_path', '')}")
            self.append_log("Strategies:")

            strategies = aoi_result.get("strategies", {})
            order = ["balanced", "full", "minimal", "max_coverage", "compact"]

            recommended_name = None
            recommended_metrics = None

            for strat_name in order:
                if strat_name not in strategies:
                    continue

                # Skip if analyst unchecked this strategy
                if not show_flags.get(strat_name, True):
                    continue

                strat_data = strategies[strat_name]
                m = strat_data.get("metrics", {})
                tiles = m.get("num_tiles", 0)
                cov = m.get("coverage_fraction", 0.0) * 100.0
                overlap = m.get("overlap_percent", 0.0)
                overlap_tiles = m.get("overlap_equiv_tiles", 0.0)
                ox = m.get("offset_x_frac", 0.0)
                oy = m.get("offset_y_frac", 0.0)
                csv_path = strat_data.get("csv_path", "")
                geojson_path = strat_data.get("geojson_path", "")

                pretty_name = strat_name.replace("_", " ").title()
                self.append_log(f"  • {pretty_name}")
                self.append_log(f"      Tiles        : {tiles}")
                self.append_log(f"      Coverage     : {cov:.2f}%")
                self.append_log(f"      Overlap      : {overlap:.2f}% (≈{overlap_tiles:.2f} tiles)")
                self.append_log(f"      Offset       : ({ox:.2f}, {oy:.2f})")
                self.append_log(f"      Centerpoints : {csv_path}")
                self.append_log(f"      Tiles GeoJSON: {geojson_path}")

                # Recommended = first visible strategy in fixed order,
                # preferring Balanced if it's visible.
                if strat_name == "balanced":
                    recommended_name = pretty_name
                    recommended_metrics = (tiles, cov, overlap)
                elif recommended_name is None:
                    recommended_name = pretty_name
                    recommended_metrics = (tiles, cov, overlap)

            if recommended_name and recommended_metrics:
                tiles, cov, overlap = recommended_metrics
                self.append_log(
                    f"\n✅ Recommended for AOI '{name}': {recommended_name} "
                    f"(Tiles={tiles}, Coverage={cov:.2f}%, Overlap={overlap:.2f}%)"
                )

        self.append_log("\n=== Daedalus run finished. You can now open the output folder. ===")


def main():
    root = tk.Tk()
    app = TilerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
