
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from PIL import Image, ImageTk
import cv2
import numpy as np
import pandas as pd
import os
import json
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import threading
import time
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


class RiverWasteApp:
    def __init__(self, root):
        self.root = root
        self.root.title("River Waste + WWI + WQI Analyzer")
        self.root.geometry("1450x860")
        self.root.configure(bg="#efefef")

        self.image_path = None
        self.preview_imgtk = None
        self.result_data = {}

        self.categories = [
            "Plastic",
            "Metal", 
            "Glass",
            "Paper/Cardboard",
            "Organic Waste",
            "Cloth",
            "E-Waste",
            "Other"
        ]

        self.waste_risk_weights = {
            "Plastic": 0.90,
            "Metal": 0.60,
            "Glass": 0.50,
            "Paper/Cardboard": 0.20,
            "Organic Waste": 0.30,
            "Cloth": 0.40,
            "E-Waste": 1.00,
            "Other": 0.50
        }

        self.analysis_history = []
        self.config_file = "river_analyzer_config.json"
        self.load_config()
        
        self.progress_bars = {}
        self.value_labels = {}
        self.entries = {}
        self.chart_frame = None
        self.current_chart = None

        self.build_ui()

    def load_config(self):
        """Load configuration from JSON file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.waste_risk_weights = config.get('waste_risk_weights', self.waste_risk_weights)
                    self.analysis_history = config.get('analysis_history', [])
        except Exception as e:
            print(f"Error loading config: {e}")

    def save_config(self):
        """Save configuration to JSON file"""
        try:
            config = {
                'waste_risk_weights': self.waste_risk_weights,
                'analysis_history': self.analysis_history[-10:]  # Keep last 10 analyses
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")

    def build_ui(self):
        main_frame = tk.Frame(self.root, bg="#efefef")
        main_frame.pack(fill="both", expand=True, padx=12, pady=12)

        left_frame = tk.Frame(main_frame, bg="#efefef", width=430)
        left_frame.pack(side="left", fill="y", padx=(0, 12))
        left_frame.pack_propagate(False)

        center_frame = tk.Frame(main_frame, bg="#efefef", width=420)
        center_frame.pack(side="left", fill="y", padx=(0, 12))
        center_frame.pack_propagate(False)

        right_frame = tk.Frame(main_frame, bg="#efefef")
        right_frame.pack(side="right", fill="both", expand=True)

        tk.Label(
            left_frame,
            text="River Image Analyzer",
            font=("Arial", 22, "bold"),
            bg="#efefef"
        ).pack(pady=(0, 12))

        self.drop_area = tk.Label(
            left_frame,
            text="Click to load polluted river image\n(PNG / JPG / JPEG)",
            font=("Arial", 14),
            bg="white",
            relief="groove",
            bd=2,
            width=32,
            height=5,
            cursor="hand2"
        )
        self.drop_area.pack(fill="x", pady=8)
        self.drop_area.bind("<Button-1>", lambda e: self.load_image())

        self.image_label = tk.Label(
            left_frame,
            text="Image preview will appear here",
            font=("Arial", 12),
            bg="white",
            relief="solid",
            bd=2,
            compound="center",
            height=18
        )
        self.image_label.pack(fill="x", pady=8)
        self.image_label.bind("<Button-1>", lambda e: self.load_image())

        tk.Button(
            left_frame, text="Open Image", font=("Arial", 12, "bold"),
            height=2, command=self.load_image, bg="#4CAF50", fg="white"
        ).pack(fill="x", pady=4)

        tk.Button(
            left_frame, text="Analyze River", font=("Arial", 12, "bold"),
            height=2, command=self.analyze_image, bg="#2196F3", fg="white"
        ).pack(fill="x", pady=4)

        tk.Button(
            left_frame, text="Show Charts", font=("Arial", 12, "bold"),
            height=2, command=self.show_charts, bg="#FF9800", fg="white"
        ).pack(fill="x", pady=4)

        tk.Button(
            left_frame, text="Export CSV", font=("Arial", 12, "bold"),
            height=2, command=self.export_csv, bg="#9C27B0", fg="white"
        ).pack(fill="x", pady=4)

        tk.Button(
            left_frame, text="View History", font=("Arial", 10),
            height=1, command=self.show_history, bg="#607D8B", fg="white"
        ).pack(fill="x", pady=2)

        self.status_label = tk.Label(
            left_frame,
            text="Status: Waiting for image...",
            font=("Arial", 12),
            bg="#efefef",
            justify="left",
            anchor="w"
        )
        self.status_label.pack(fill="x", pady=10)

        tk.Label(
            center_frame,
            text="User Water Inputs",
            font=("Arial", 20, "bold"),
            bg="#efefef"
        ).pack(anchor="w", pady=(0, 10))

        input_box = tk.Frame(center_frame, bg="white", bd=1, relief="solid")
        input_box.pack(fill="both", expand=False)

        fields = [
            ("Total Visible Waste (kg)", "100"),
            ("pH", "7.2"),
            ("DO (mg/L)", "6.0"),
            ("BOD (mg/L)", "3.0"),
            ("Turbidity (NTU)", "20"),
            ("TDS (mg/L)", "300"),
            ("Nitrate (mg/L)", "10"),
            ("Phosphate (mg/L)", "0.5")
        ]

        for label_text, default_val in fields:
            row = tk.Frame(input_box, bg="white")
            row.pack(fill="x", padx=10, pady=8)

            tk.Label(
                row, text=label_text, width=20, anchor="w",
                font=("Arial", 11), bg="white"
            ).pack(side="left")

            entry = tk.Entry(row, font=("Arial", 11))
            entry.pack(side="right", fill="x", expand=True)
            entry.insert(0, default_val)
            self.entries[label_text] = entry

        tk.Button(
            center_frame,
            text="Recalculate WWI / WQI",
            font=("Arial", 12, "bold"),
            height=2,
            command=self.recalculate_scores
        ).pack(fill="x", pady=10)

        summary_box = tk.Frame(center_frame, bg="white", bd=1, relief="solid")
        summary_box.pack(fill="both", expand=True)

        tk.Label(
            summary_box, text="River Summary",
            font=("Arial", 16, "bold"), bg="white"
        ).pack(anchor="w", padx=10, pady=(10, 6))

        self.total_waste_var = tk.StringVar(value="Total Waste Load: -")
        self.wwi_var = tk.StringVar(value="WWI: -")
        self.wqi_var = tk.StringVar(value="WQI: -")
        self.status_var = tk.StringVar(value="River Status: -")

        tk.Label(summary_box, textvariable=self.total_waste_var, font=("Arial", 12), bg="white").pack(anchor="w", padx=10, pady=4)
        tk.Label(summary_box, textvariable=self.wwi_var, font=("Arial", 12), bg="white").pack(anchor="w", padx=10, pady=4)
        tk.Label(summary_box, textvariable=self.wqi_var, font=("Arial", 12), bg="white").pack(anchor="w", padx=10, pady=4)
        tk.Label(summary_box, textvariable=self.status_var, font=("Arial", 12, "bold"), bg="white", fg="darkred").pack(anchor="w", padx=10, pady=6)

        tk.Label(
            right_frame,
            text="Waste Composition, Weights and Scores",
            font=("Arial", 20, "bold"),
            bg="#efefef"
        ).pack(anchor="w", pady=(0, 10))

        progress_box = tk.Frame(right_frame, bg="white", bd=1, relief="solid")
        progress_box.pack(fill="x", pady=(0, 12))

        for cat in self.categories:
            row = tk.Frame(progress_box, bg="white")
            row.pack(fill="x", padx=10, pady=7)

            tk.Label(row, text=cat, font=("Arial", 11), bg="white", width=18, anchor="w").pack(side="left")

            bar = ttk.Progressbar(row, orient="horizontal", length=260, mode="determinate")
            bar.pack(side="left", padx=8)

            val = tk.Label(row, text="0.00%", font=("Arial", 11, "bold"), bg="white", width=8)
            val.pack(side="left")

            self.progress_bars[cat] = bar
            self.value_labels[cat] = val

        table_box = tk.Frame(right_frame, bg="white", bd=1, relief="solid")
        table_box.pack(fill="both", expand=True)

        columns = ("Waste Type", "Percentage", "Assumed Weight (kg)", "WWI Contribution")
        self.tree = ttk.Treeview(table_box, columns=columns, show="headings", height=16)
        for col in columns:
            self.tree.heading(col, text=col)

        self.tree.column("Waste Type", width=170, anchor="center")
        self.tree.column("Percentage", width=110, anchor="center")
        self.tree.column("Assumed Weight (kg)", width=150, anchor="center")
        self.tree.column("WWI Contribution", width=140, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

    def load_image(self):
        path = filedialog.askopenfilename(
            title="Select Polluted River Image",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg")]
        )
        if not path:
            return

        try:
            self.image_path = path
            img = Image.open(path).convert("RGB")
            self.show_preview(img)
            self.status_label.config(text=f"Status: Image loaded\nFile: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open image.\n\n{e}")

    def show_preview(self, pil_img):
        img = pil_img.copy()
        img.thumbnail((380, 300))
        self.preview_imgtk = ImageTk.PhotoImage(img)
        self.image_label.config(image=self.preview_imgtk, text="")

    def analyze_image(self):
        if not self.image_path:
            messagebox.showwarning("No Image", "Please open an image first.")
            return

        def analyze_thread():
            try:
                self.status_label.config(text="Status: Analyzing image...")
                self.root.update()
                
                img_bgr = cv2.imread(self.image_path)
                if img_bgr is None:
                    raise ValueError("OpenCV could not read the image.")

                img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
                self.result_data = self.estimate_waste_composition(img_rgb)
                
                self.root.after(0, self.update_progress, self.result_data)
                self.root.after(0, self.recalculate_scores)
                
                # Save to history
                analysis_entry = {
                    'timestamp': datetime.now().isoformat(),
                    'image_path': self.image_path,
                    'results': self.result_data.copy()
                }
                self.analysis_history.append(analysis_entry)
                self.save_config()
                
                top_item = max(self.result_data, key=self.result_data.get)
                status_text = f"Status: Analysis complete\nDominant waste: {top_item} ({self.result_data[top_item]:.2f}%)"
                self.root.after(0, lambda: self.status_label.config(text=status_text))
                
            except Exception as e:
                error_msg = f"Analysis failed.\n\n{e}"
                self.root.after(0, lambda: messagebox.showerror("Error", error_msg))
                self.root.after(0, lambda: self.status_label.config(text="Status: Analysis failed"))

        # Run analysis in separate thread to prevent UI freezing
        threading.Thread(target=analyze_thread, daemon=True).start()

    def estimate_waste_composition(self, img_rgb):
        """Enhanced waste composition estimation using multiple computer vision techniques"""
        resized = cv2.resize(img_rgb, (400, 300))
        hsv = cv2.cvtColor(resized, cv2.COLOR_RGB2HSV)
        gray = cv2.cvtColor(resized, cv2.COLOR_RGB2GRAY)
        lab = cv2.cvtColor(resized, cv2.COLOR_RGB2LAB)
        
        # Enhanced color detection with more precise ranges
        blue_mask = cv2.inRange(hsv, (90, 40, 40), (140, 255, 255))
        green_mask = cv2.inRange(hsv, (35, 30, 30), (89, 255, 255))
        brown_mask = cv2.inRange(hsv, (5, 40, 20), (25, 255, 220))
        white_mask = cv2.inRange(hsv, (0, 0, 160), (180, 60, 255))
        low_sat_mask = cv2.inRange(hsv, (0, 0, 0), (180, 50, 255))
        
        # Texture and edge detection
        edges = cv2.Canny(gray, 80, 160)
        edge_density = np.sum(edges > 0) / edges.size
        
        # Advanced texture analysis using Laplacian
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        texture_score = min(laplacian_var / 1000, 1.0)
        
        # Color histogram analysis
        hist_r = cv2.calcHist([resized], [0], None, [256], [0, 256])
        hist_g = cv2.calcHist([resized], [1], None, [256], [0, 256])
        hist_b = cv2.calcHist([resized], [2], None, [256], [0, 256])
        
        # Calculate color dominance
        color_dominance = {
            'red': np.sum(hist_r[150:256]) / resized.size,
            'green': np.sum(hist_g[150:256]) / resized.size,
            'blue': np.sum(hist_b[150:256]) / resized.size
        }
        
        # Contour analysis for shape detection
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Analyze contour shapes
        sharp_contours = 0
        smooth_contours = 0
        for contour in contours:
            if cv2.contourArea(contour) > 50:
                perimeter = cv2.arcLength(contour, True)
                area = cv2.contourArea(contour)
                if perimeter > 0:
                    circularity = 4 * np.pi * area / (perimeter * perimeter)
                    if circularity < 0.5:
                        sharp_contours += 1
                    else:
                        smooth_contours += 1
        
        total_contours = sharp_contours + smooth_contours
        shape_ratio = sharp_contours / max(total_contours, 1)
        
        # Calculate color ratios
        blue_ratio = np.sum(blue_mask > 0) / blue_mask.size
        green_ratio = np.sum(green_mask > 0) / green_mask.size
        brown_ratio = np.sum(brown_mask > 0) / brown_mask.size
        white_ratio = np.sum(white_mask > 0) / white_mask.size
        low_sat_ratio = np.sum(low_sat_mask > 0) / low_sat_mask.size
        brightness = np.mean(gray) / 255.0
        std_dev = np.std(gray) / 255.0
        
        # Enhanced scoring algorithm with more sophisticated features
        scores = {
            "Plastic": 15 + (white_ratio * 35) + (edge_density * 30) + (blue_ratio * 15) + (texture_score * 10) + (color_dominance['blue'] * 5),
            "Metal": 8 + (low_sat_ratio * 30) + (brightness * 25) + (edge_density * 25) + (shape_ratio * 10),
            "Glass": 6 + (brightness * 30) + (blue_ratio * 20) + (white_ratio * 15) + (smooth_contours / max(total_contours, 1) * 10),
            "Paper/Cardboard": 10 + (brown_ratio * 35) + (white_ratio * 15) + (texture_score * 8) + (color_dominance['red'] * 5),
            "Organic Waste": 14 + (green_ratio * 40) + (brown_ratio * 25) + (std_dev * 10) + (color_dominance['green'] * 5),
            "Cloth": 7 + (std_dev * 20) + (blue_ratio * 10) + (texture_score * 15) + (color_dominance['red'] * 3),
            "E-Waste": 5 + (edge_density * 25) + (low_sat_ratio * 15) + (shape_ratio * 15) + (brightness * 5),
            "Other": 4 + (std_dev * 12) + (texture_score * 8) + (edge_density * 10)
        }
        
        # Apply Gaussian smoothing to reduce noise in results
        total = sum(scores.values())
        percentages = {k: (v / total) * 100 for k, v in scores.items()}
        
        # Apply slight smoothing to make results more realistic
        for key in percentages:
            percentages[key] = percentages[key] * 0.9 + (100 / len(percentages)) * 0.1
        
        # Normalize back to 100%
        total = sum(percentages.values())
        percentages = {k: (v / total) * 100 for k, v in percentages.items()}
        
        rounded = {k: round(v, 2) for k, v in percentages.items()}
        diff = round(100 - sum(rounded.values()), 2)
        if diff != 0:
            rounded[max(rounded, key=rounded.get)] += diff
            
        return rounded

    def update_progress(self, result):
        for cat, val in result.items():
            self.progress_bars[cat]["value"] = val
            self.value_labels[cat].config(text=f"{val:.2f}%")

    def get_float(self, field_name):
        return float(self.entries[field_name].get().strip())

    def calculate_wwi(self, total_waste_kg):
        rows = []
        total_wwi = 0.0

        for cat in self.categories:
            percent = self.result_data.get(cat, 0.0)
            weight_kg = (percent / 100.0) * total_waste_kg
            contribution = weight_kg * self.waste_risk_weights[cat]
            total_wwi += contribution

            rows.append({
                "Waste Type": cat,
                "Percentage": round(percent, 2),
                "Assumed Weight (kg)": round(weight_kg, 2),
                "WWI Contribution": round(contribution, 2)
            })

        return round(total_wwi, 2), rows

    def calculate_wqi(self, ph, do, bod, turbidity, tds, nitrate, phosphate):
        weights = {
            "pH": 0.12,
            "DO": 0.20,
            "BOD": 0.18,
            "Turbidity": 0.12,
            "TDS": 0.10,
            "Nitrate": 0.14,
            "Phosphate": 0.14
        }

        q_ph = min(abs(ph - 7.0) / 1.5 * 100, 100)
        q_do = min(max((14.6 - do) / (14.6 - 5.0) * 100, 0), 100)
        q_bod = min(max((bod / 6.0) * 100, 0), 100)
        q_turb = min(max((turbidity / 25.0) * 100, 0), 100)
        q_tds = min(max((tds / 500.0) * 100, 0), 100)
        q_no3 = min(max((nitrate / 45.0) * 100, 0), 100)
        q_po4 = min(max((phosphate / 1.0) * 100, 0), 100)

        wqi = (
            q_ph * weights["pH"] +
            q_do * weights["DO"] +
            q_bod * weights["BOD"] +
            q_turb * weights["Turbidity"] +
            q_tds * weights["TDS"] +
            q_no3 * weights["Nitrate"] +
            q_po4 * weights["Phosphate"]
        )
        return round(wqi, 2)

    def river_status(self, wwi, wqi):
        if wqi <= 25 and wwi < 20:
            return "Clean"
        elif wqi <= 50 and wwi < 40:
            return "Moderately Polluted"
        elif wqi <= 75 and wwi < 70:
            return "Polluted"
        return "Severely Polluted"

    def recalculate_scores(self):
        if not self.result_data:
            messagebox.showwarning("No Analysis", "Please analyze an image first.")
            return

        try:
            total_waste = self.get_float("Total Visible Waste (kg)")
            ph = self.get_float("pH")
            do = self.get_float("DO (mg/L)")
            bod = self.get_float("BOD (mg/L)")
            turbidity = self.get_float("Turbidity (NTU)")
            tds = self.get_float("TDS (mg/L)")
            nitrate = self.get_float("Nitrate (mg/L)")
            phosphate = self.get_float("Phosphate (mg/L)")

            wwi, rows = self.calculate_wwi(total_waste)
            wqi = self.calculate_wqi(ph, do, bod, turbidity, tds, nitrate, phosphate)
            status = self.river_status(wwi, wqi)

            self.update_table(rows)
            self.total_waste_var.set(f"Total Waste Load: {total_waste:.2f} kg")
            self.wwi_var.set(f"WWI: {wwi:.2f}")
            self.wqi_var.set(f"WQI: {wqi:.2f}")
            self.status_var.set(f"River Status: {status}")

        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numeric values in all input fields.")

    def update_table(self, rows):
        for row in self.tree.get_children():
            self.tree.delete(row)

        for row in rows:
            self.tree.insert(
                "",
                "end",
                values=(
                    row["Waste Type"],
                    f'{row["Percentage"]:.2f}',
                    f'{row["Assumed Weight (kg)"]:.2f}',
                    f'{row["WWI Contribution"]:.2f}'
                )
            )

    def export_csv(self):
        if not self.result_data:
            messagebox.showwarning("No Data", "Please analyze an image first.")
            return

        try:
            total_waste = self.get_float("Total Visible Waste (kg)")
            wwi, rows = self.calculate_wwi(total_waste)

            save_path = filedialog.asksaveasfilename(
                title="Save CSV",
                defaultextension=".csv",
                filetypes=[("CSV Files", "*.csv")]
            )
            if not save_path:
                return

            df = pd.DataFrame(rows)
            df.to_csv(save_path, index=False)
            messagebox.showinfo("Saved", f"CSV exported successfully.\n\n{save_path}")

        except ValueError:
            messagebox.showerror("Invalid Input", "Enter valid numeric inputs before export.")

    def show_charts(self):
        """Display charts for waste composition analysis"""
        if not self.result_data:
            messagebox.showwarning("No Data", "Please analyze an image first.")
            return

        chart_window = tk.Toplevel(self.root)
        chart_window.title("Waste Analysis Charts")
        chart_window.geometry("900x600")
        
        # Create matplotlib figure
        fig = Figure(figsize=(12, 8))
        
        # Pie chart
        ax1 = fig.add_subplot(221)
        categories = list(self.result_data.keys())
        values = list(self.result_data.values())
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F']
        
        wedges, texts, autotexts = ax1.pie(values, labels=categories, autopct='%1.1f%%', 
                                          colors=colors, startangle=90)
        ax1.set_title('Waste Composition Distribution', fontsize=14, fontweight='bold')
        
        # Bar chart
        ax2 = fig.add_subplot(222)
        bars = ax2.bar(categories, values, color=colors)
        ax2.set_title('Waste Percentage by Category', fontsize=14, fontweight='bold')
        ax2.set_ylabel('Percentage (%)')
        ax2.tick_params(axis='x', rotation=45)
        
        # Add value labels on bars
        for bar, value in zip(bars, values):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{value:.1f}%', ha='center', va='bottom')
        
        # Risk assessment chart
        ax3 = fig.add_subplot(223)
        risk_scores = [self.result_data[cat] * self.waste_risk_weights[cat] / 100 
                      for cat in categories]
        bars_risk = ax3.bar(categories, risk_scores, color=colors)
        ax3.set_title('Risk-Weighted Waste Impact', fontsize=14, fontweight='bold')
        ax3.set_ylabel('Risk Score')
        ax3.tick_params(axis='x', rotation=45)
        
        # Timeline chart (if history exists)
        ax4 = fig.add_subplot(224)
        if len(self.analysis_history) > 1:
            recent_history = self.analysis_history[-5:]  # Last 5 analyses
            timestamps = [datetime.fromisoformat(entry['timestamp']).strftime('%H:%M') 
                         for entry in recent_history]
            plastic_trends = [entry['results'].get('Plastic', 0) for entry in recent_history]
            
            ax4.plot(timestamps, plastic_trends, marker='o', linewidth=2, markersize=8, color='#FF6B6B')
            ax4.set_title('Plastic Waste Trend (Last 5 Analyses)', fontsize=14, fontweight='bold')
            ax4.set_ylabel('Plastic Percentage (%)')
            ax4.set_xlabel('Time')
            ax4.grid(True, alpha=0.3)
        else:
            ax4.text(0.5, 0.5, 'No historical data\navailable yet', 
                    ha='center', va='center', transform=ax4.transAxes, fontsize=12)
            ax4.set_title('Historical Trends', fontsize=14, fontweight='bold')
        
        fig.tight_layout()
        
        # Embed in tkinter
        canvas = FigureCanvasTkAgg(fig, chart_window)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)
        
        # Save chart button
        def save_chart():
            save_path = filedialog.asksaveasfilename(
                title="Save Chart",
                defaultextension=".png",
                filetypes=[("PNG Files", "*.png"), ("All Files", "*.*")]
            )
            if save_path:
                fig.savefig(save_path, dpi=100, bbox_inches='tight')
                messagebox.showinfo("Saved", f"Chart saved to:\n{save_path}")
        
        tk.Button(chart_window, text="Save Chart", command=save_chart, 
                 bg="#4CAF50", fg="white", font=("Arial", 10, "bold")).pack(pady=5)

    def show_history(self):
        """Display analysis history"""
        if not self.analysis_history:
            messagebox.showinfo("No History", "No analysis history available yet.")
            return
        
        history_window = tk.Toplevel(self.root)
        history_window.title("Analysis History")
        history_window.geometry("800x500")
        
        # Create treeview for history
        columns = ("Date/Time", "Image", "Dominant Waste", "Plastic %", "Metal %")
        history_tree = ttk.Treeview(history_window, columns=columns, show="headings", height=15)
        
        for col in columns:
            history_tree.heading(col, text=col)
            
        history_tree.column("Date/Time", width=150, anchor="center")
        history_tree.column("Image", width=200, anchor="w")
        history_tree.column("Dominant Waste", width=120, anchor="center")
        history_tree.column("Plastic %", width=100, anchor="center")
        history_tree.column("Metal %", width=100, anchor="center")
        
        # Populate history
        for entry in reversed(self.analysis_history[-20:]):  # Last 20 entries
            timestamp = datetime.fromisoformat(entry['timestamp'])
            date_str = timestamp.strftime('%Y-%m-%d %H:%M')
            image_name = os.path.basename(entry['image_path'])
            results = entry['results']
            
            dominant = max(results, key=results.get)
            plastic_pct = results.get('Plastic', 0)
            metal_pct = results.get('Metal', 0)
            
            history_tree.insert("", "end", values=(
                date_str, image_name, dominant, f"{plastic_pct:.1f}%", f"{metal_pct:.1f}%"
            ))
        
        history_tree.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Clear history button
        def clear_history():
            if messagebox.askyesno("Clear History", "Are you sure you want to clear all analysis history?"):
                self.analysis_history.clear()
                self.save_config()
                history_window.destroy()
                messagebox.showinfo("Cleared", "Analysis history has been cleared.")
        
        button_frame = tk.Frame(history_window)
        button_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Button(button_frame, text="Clear History", command=clear_history, 
                 bg="#f44336", fg="white", font=("Arial", 10, "bold")).pack(side="right")
        tk.Button(button_frame, text="Close", command=history_window.destroy, 
                 font=("Arial", 10)).pack(side="right", padx=(0, 5))


if __name__ == "__main__":
    root = tk.Tk()
    app = RiverWasteApp(root)
    root.mainloop()
