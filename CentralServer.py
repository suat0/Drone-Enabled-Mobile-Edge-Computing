# CentralServer.py
import socket
import threading
import tkinter as tk
from tkinter import ttk
import json
import time
import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from collections import deque

CENTRAL_PORT = 6000
DATA_HISTORY_SIZE = 100  # Number of data points to keep

# Global variables for data storage
drones_data = {}  # Store data for each drone
temperature_history = deque(maxlen=DATA_HISTORY_SIZE)
humidity_history = deque(maxlen=DATA_HISTORY_SIZE)
timestamps = deque(maxlen=DATA_HISTORY_SIZE)
anomalies_history = []  # Store anomalies

# Lock for thread safety
lock = threading.Lock()

def handle_drone(conn, addr, gui_log, update_dashboard):
    with conn:
        gui_log(f"Connected to drone at {addr}")
        while True:
            try:
                data = conn.recv(4096)
                if not data:
                    break
                
                decoded = json.loads(data.decode())
                drone_id = decoded.get("drone_id", "unknown")
                
                with lock:
                    # Update drone data
                    if drone_id not in drones_data:
                        drones_data[drone_id] = {
                            "avg_temperature": [],
                            "avg_humidity": [],
                            "timestamps": [],
                            "battery_level": 0,
                            "status": "Unknown",
                            "connected_sensors": []
                        }
                    
                    drones_data[drone_id]["avg_temperature"].append(decoded["avg_temperature"])
                    drones_data[drone_id]["avg_humidity"].append(decoded["avg_humidity"])
                    drones_data[drone_id]["timestamps"].append(decoded["timestamp"])
                    drones_data[drone_id]["battery_level"] = decoded.get("battery_level", 0)
                    drones_data[drone_id]["status"] = decoded.get("drone_status", "Unknown")
                    drones_data[drone_id]["connected_sensors"] = decoded.get("connected_sensors", [])
                    
                    # Update global history for charts
                    temperature_history.append(decoded["avg_temperature"])
                    humidity_history.append(decoded["avg_humidity"])
                    timestamps.append(datetime.datetime.fromisoformat(decoded["timestamp"].replace('Z', '+00:00')))
                    
                    # Handle anomalies
                    if "anomalies" in decoded and decoded["anomalies"]:
                        for anomaly in decoded["anomalies"]:
                            anomaly_record = {
                                "drone_id": drone_id,
                                "timestamp": decoded["timestamp"],
                                "description": anomaly
                            }
                            anomalies_history.append(anomaly_record)
                            gui_log(f"Anomaly from {drone_id}: {anomaly}")
                
                # Log the received data
                gui_log(f"Received from {drone_id}: Avg Temp={decoded['avg_temperature']}°C, Avg Humidity={decoded['avg_humidity']}%, Status={decoded.get('drone_status', 'Unknown')}, Battery={decoded.get('battery_level', 'Unknown')}%")
                
                # Signal to update the dashboard
                update_dashboard()
                
            except json.JSONDecodeError:
                gui_log(f"Invalid JSON received from {addr}")
                break
            except Exception as e:
                gui_log(f"Error handling drone data: {e}")
                break
    
    gui_log(f"Disconnected drone at {addr}")

def start_server(gui_log, update_dashboard):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", CENTRAL_PORT))
    server.listen(5)
    gui_log(f"Central Server listening on port {CENTRAL_PORT}")
    
    while True:
        try:
            conn, addr = server.accept()
            threading.Thread(target=handle_drone, args=(conn, addr, gui_log, update_dashboard)).start()
        except Exception as e:
            gui_log(f"Error accepting connection: {e}")
            time.sleep(1)

def start_gui():
    root = tk.Tk()
    root.title("Environmental Monitoring Central Server")
    root.geometry("1200x700")
    
    # Create notebook with tabs
    notebook = ttk.Notebook(root)
    notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # Dashboard tab
    dashboard_frame = ttk.Frame(notebook)
    notebook.add(dashboard_frame, text="Dashboard")
    
    # Drone status frame
    drone_status_frame = ttk.LabelFrame(dashboard_frame, text="Drone Status")
    drone_status_frame.pack(fill=tk.X, padx=5, pady=5)
    
    # Drone status table
    drone_tree = ttk.Treeview(drone_status_frame, columns=("battery", "status", "sensors", "last_update"))
    drone_tree.heading("#0", text="Drone ID")
    drone_tree.heading("battery", text="Battery Level")
    drone_tree.heading("status", text="Status")
    drone_tree.heading("sensors", text="Connected Sensors")
    drone_tree.heading("last_update", text="Last Update")
    
    drone_tree.column("#0", width=100)
    drone_tree.column("battery", width=100)
    drone_tree.column("status", width=150)
    drone_tree.column("sensors", width=200)
    drone_tree.column("last_update", width=150)
    
    drone_tree.pack(fill=tk.X, padx=5, pady=5)
    
    # Data visualization frame
    chart_frame = ttk.LabelFrame(dashboard_frame, text="Environmental Data")
    chart_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    # Create matplotlib figure for data visualization
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5))
    
    # Temperature axis
    ax1.set_title('Average Temperature (°C)')
    ax1.set_ylim(10, 40)
    temp_line, = ax1.plot([], [], 'r-')
    
    # Humidity axis
    ax2.set_title('Average Humidity (%)')
    ax2.set_ylim(0, 100)
    hum_line, = ax2.plot([], [], 'b-')
    
    # Add figure to tkinter window
    canvas = FigureCanvasTkAgg(fig, master=chart_frame)
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    # Anomalies tab
    anomalies_frame = ttk.Frame(notebook)
    notebook.add(anomalies_frame, text="Anomalies")
    
    # Anomalies table
    anomalies_tree = ttk.Treeview(anomalies_frame, columns=("timestamp", "description"))
    anomalies_tree.heading("#0", text="Drone ID")
    anomalies_tree.heading("timestamp", text="Timestamp")
    anomalies_tree.heading("description", text="Description")
    
    anomalies_tree.column("#0", width=100)
    anomalies_tree.column("timestamp", width=200)
    anomalies_tree.column("description", width=500)
    
    anomalies_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    # Log tab
    log_frame = ttk.Frame(notebook)
    notebook.add(log_frame, text="Logs")
    
    log_text = tk.Text(log_frame, height=20, width=80)
    log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    log_scroll = ttk.Scrollbar(log_text, command=log_text.yview)
    log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    log_text.config(yscrollcommand=log_scroll.set)
    
    # Define the log function
    def gui_log(message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        log_text.see(tk.END)
    
    # Function to update the dashboard
    def update_dashboard():
        with lock:
            # Update drone status table
            for item in drone_tree.get_children():
                drone_tree.delete(item)
            
            for drone_id, data in drones_data.items():
                last_update = "N/A"
                if data["timestamps"]:
                    timestamp = datetime.datetime.fromisoformat(data["timestamps"][-1].replace('Z', '+00:00'))
                    last_update = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                
                sensors_text = ", ".join(data["connected_sensors"])
                drone_tree.insert("", "end", text=drone_id, values=(
                    f"{data['battery_level']}%",
                    data["status"],
                    sensors_text,
                    last_update
                ))
            
            # Update charts
            if timestamps and temperature_history and humidity_history:
                temp_line.set_xdata(range(len(temperature_history)))
                temp_line.set_ydata(temperature_history)
                ax1.set_xlim(0, len(temperature_history))
                
                hum_line.set_xdata(range(len(humidity_history)))
                hum_line.set_ydata(humidity_history)
                ax2.set_xlim(0, len(humidity_history))
                
                # Redraw the canvas
                canvas.draw()
            
            # Update anomalies table
            for item in anomalies_tree.get_children():
                anomalies_tree.delete(item)
            
            for anomaly in anomalies_history:
                timestamp = datetime.datetime.fromisoformat(anomaly["timestamp"].replace('Z', '+00:00'))
                formatted_timestamp = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                anomalies_tree.insert("", "end", text=anomaly["drone_id"], values=(
                    formatted_timestamp,
                    anomaly["description"]
                ))
    
    # Start server in a separate thread
    threading.Thread(target=start_server, args=(gui_log, update_dashboard), daemon=True).start()
    
    # Initial log
    gui_log("Central Server started")
    
    # Periodic dashboard update
    def schedule_update():
        update_dashboard()
        root.after(2000, schedule_update)
    
    schedule_update()
    
    # Start the main loop
    root.mainloop()

if __name__ == "__main__":
    start_gui()