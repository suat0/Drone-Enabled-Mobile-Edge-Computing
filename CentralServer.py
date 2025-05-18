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
data_received = False  # Flag to indicate if any data has been received

# Lock for thread safety
lock = threading.Lock()

def handle_drone(conn, addr, gui_log):
    with conn:
        gui_log(f"Connected to drone at {addr}")
        try:
            data = conn.recv(4096)
            if data:
                try:
                    decoded = json.loads(data.decode())
                    drone_id = decoded.get("drone_id", "unknown")
                    
                    with lock:
                        global data_received
                        data_received = True
                        
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
                        
                        # Only update sensor data if it's provided
                        if "avg_temperature" in decoded and "avg_humidity" in decoded:
                            drones_data[drone_id]["avg_temperature"].append(decoded["avg_temperature"])
                            drones_data[drone_id]["avg_humidity"].append(decoded["avg_humidity"])
                            # Update global history for charts
                            temperature_history.append(decoded["avg_temperature"])
                            humidity_history.append(decoded["avg_humidity"])
                        
                        # Always update these fields
                        drones_data[drone_id]["timestamps"].append(decoded["timestamp"])
                        drones_data[drone_id]["battery_level"] = decoded.get("battery_level", 0)
                        drones_data[drone_id]["status"] = decoded.get("drone_status", "Unknown")
                        
                        # Update connected sensors if provided
                        if "connected_sensors" in decoded:
                            drones_data[drone_id]["connected_sensors"] = decoded["connected_sensors"]
                        
                        # Update timestamp for charts
                        current_time = datetime.datetime.fromisoformat(decoded["timestamp"].replace('Z', '+00:00'))
                        timestamps.append(current_time)
                        
                        # Handle anomalies if provided
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
                    if "avg_temperature" in decoded and "avg_humidity" in decoded:
                        gui_log(f"Received from {drone_id}: Avg Temp={decoded['avg_temperature']}°C, Avg Humidity={decoded['avg_humidity']}%, Status={decoded.get('drone_status', 'Unknown')}, Battery={decoded.get('battery_level', 'Unknown')}%")
                    else:
                        gui_log(f"Status Update from {drone_id}: Status={decoded.get('drone_status', 'Unknown')}, Battery={decoded.get('battery_level', 'Unknown')}%")
                    
                except json.JSONDecodeError:
                    gui_log(f"Invalid JSON received from {addr}")
                except Exception as e:
                    gui_log(f"Error processing data: {e}")
        except Exception as e:
            gui_log(f"Error handling drone connection: {e}")
    
    gui_log(f"Disconnected drone at {addr}")

def start_server(gui_log):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind(("0.0.0.0", CENTRAL_PORT))
        server.listen(5)
        gui_log(f"Central Server listening on port {CENTRAL_PORT}")
        
        while True:
            try:
                conn, addr = server.accept()
                threading.Thread(target=handle_drone, args=(conn, addr, gui_log), daemon=True).start()
            except Exception as e:
                gui_log(f"Error accepting connection: {e}")
                time.sleep(1)
    except Exception as e:
        gui_log(f"Failed to start server: {e}")
        return

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
    
    # Add scrollbar for the table
    drone_scroll = ttk.Scrollbar(drone_status_frame, orient="vertical", command=drone_tree.yview)
    drone_tree.configure(yscrollcommand=drone_scroll.set)
    
    # Pack the table and scrollbar
    drone_tree.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
    drone_scroll.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
    
    # Data visualization frame
    chart_frame = ttk.LabelFrame(dashboard_frame, text="Environmental Data")
    chart_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    # Create matplotlib figure with improved spacing
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5), gridspec_kw={'hspace': 0.5})

    # Temperature axis with proper configuration
    ax1.set_title('Average Temperature (°C)', fontsize=11, pad=10)
    ax1.set_ylim(10, 40)
    ax1.grid(True, linestyle='--', alpha=0.7)
    ax1.set_ylabel('Temperature (°C)', fontsize=10)
    temp_line, = ax1.plot([], [], 'r-', linewidth=2)

    # Humidity axis with proper configuration
    ax2.set_title('Average Humidity (%)', fontsize=11, pad=10)
    ax2.set_ylim(0, 100)
    ax2.grid(True, linestyle='--', alpha=0.7)
    ax2.set_ylabel('Humidity (%)', fontsize=10)
    hum_line, = ax2.plot([], [], 'b-', linewidth=2)

    # Apply tight layout with additional padding
    fig.tight_layout(pad=3.0)
    
    # Add figure to tkinter window
    canvas = FigureCanvasTkAgg(fig, master=chart_frame)
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    # Anomalies tab
    anomalies_frame = ttk.Frame(notebook)
    notebook.add(anomalies_frame, text="Anomalies")
    
    # Anomaly statistics frame
    stats_frame = ttk.LabelFrame(anomalies_frame, text="Anomaly Statistics")
    stats_frame.pack(fill=tk.X, padx=5, pady=5)
    
    # Statistics labels
    anomaly_count_var = tk.StringVar(value="Total Anomalies: 0")
    temp_anomaly_var = tk.StringVar(value="Temperature Anomalies: 0")
    humid_anomaly_var = tk.StringVar(value="Humidity Anomalies: 0")
    
    ttk.Label(stats_frame, textvariable=anomaly_count_var, font=('Arial', 10)).pack(side=tk.LEFT, padx=20, pady=5)
    ttk.Label(stats_frame, textvariable=temp_anomaly_var, font=('Arial', 10)).pack(side=tk.LEFT, padx=20, pady=5)
    ttk.Label(stats_frame, textvariable=humid_anomaly_var, font=('Arial', 10)).pack(side=tk.LEFT, padx=20, pady=5)
    
    # Anomalies table
    anomalies_tree = ttk.Treeview(anomalies_frame, columns=("timestamp", "description"))
    anomalies_tree.heading("#0", text="Drone ID")
    anomalies_tree.heading("timestamp", text="Timestamp")
    anomalies_tree.heading("description", text="Description")
    
    anomalies_tree.column("#0", width=100)
    anomalies_tree.column("timestamp", width=200)
    anomalies_tree.column("description", width=500)
    
    # Add scrollbar for anomalies table
    anomalies_scroll = ttk.Scrollbar(anomalies_frame, orient="vertical", command=anomalies_tree.yview)
    anomalies_tree.configure(yscrollcommand=anomalies_scroll.set)
    
    # Pack the table and scrollbar
    anomalies_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
    anomalies_scroll.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
    
    # Log tab
    log_frame = ttk.Frame(notebook)
    notebook.add(log_frame, text="Logs")
    
    log_text = tk.Text(log_frame, height=20, width=80)
    log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=log_text.yview)
    log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    log_text.config(yscrollcommand=log_scroll.set)
    
    # Status bar
    status_frame = ttk.Frame(root)
    status_frame.pack(fill=tk.X, side=tk.BOTTOM)
    
    status_var = tk.StringVar(value="Server started. Waiting for drone connections...")
    status_label = ttk.Label(status_frame, textvariable=status_var, relief=tk.SUNKEN, anchor=tk.W)
    status_label.pack(fill=tk.X, expand=True, padx=5, pady=2)
    
    # Define the log function
    def gui_log(message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        log_text.see(tk.END)
        status_var.set(message)
    
    # Function to update all UI elements
    def update_ui():
        with lock:
            # Update drone status table
            for item in drone_tree.get_children():
                drone_tree.delete(item)
            
            for drone_id, data in drones_data.items():
                last_update = "N/A"
                if data["timestamps"]:
                    try:
                        timestamp = datetime.datetime.fromisoformat(data["timestamps"][-1].replace('Z', '+00:00'))
                        last_update = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        last_update = data["timestamps"][-1]
                
                sensors_text = ", ".join(data["connected_sensors"])
                
                # Create tag for row based on drone status
                tag = "normal"
                if data["status"] == "Returning to Base":
                    tag = "returning"
                
                drone_tree.insert("", "end", text=drone_id, values=(
                    f"{data['battery_level']}%",
                    data["status"],
                    sensors_text,
                    last_update
                ), tags=(tag,))
            
            # Configure tag colors
            drone_tree.tag_configure("returning", background="#ffe0b3")
            drone_tree.tag_configure("normal", background="#ffffff")
            
            # Update anomalies table
            for item in anomalies_tree.get_children():
                anomalies_tree.delete(item)
            
            for anomaly in anomalies_history:
                timestamp = datetime.datetime.fromisoformat(anomaly["timestamp"].replace('Z', '+00:00'))
                formatted_timestamp = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                
                # Add different tags based on type of anomaly
                tag = "temp_anomaly" if "temperature" in anomaly["description"].lower() else "humid_anomaly"
                
                anomalies_tree.insert("", 0, text=anomaly["drone_id"], values=(
                    formatted_timestamp,
                    anomaly["description"]
                ), tags=(tag,))
            
            # Configure anomaly tag colors
            anomalies_tree.tag_configure("temp_anomaly", background="#ffcccc")
            anomalies_tree.tag_configure("humid_anomaly", background="#cce5ff")
            
            # Update anomaly statistics
            temp_count = sum(1 for a in anomalies_history if "temperature" in a["description"].lower())
            humid_count = sum(1 for a in anomalies_history if "humidity" in a["description"].lower())
            
            anomaly_count_var.set(f"Total Anomalies: {len(anomalies_history)}")
            temp_anomaly_var.set(f"Temperature Anomalies: {temp_count}")
            humid_anomaly_var.set(f"Humidity Anomalies: {humid_count}")
            
            # Update charts
            if len(temperature_history) > 0 and len(humidity_history) > 0:
                # Get data from deques
                temp_data = list(temperature_history)
                hum_data = list(humidity_history)
                x_data = list(range(len(temp_data)))
                
                # Update plot data
                temp_line.set_xdata(x_data)
                temp_line.set_ydata(temp_data)
                hum_line.set_xdata(x_data)
                hum_line.set_ydata(hum_data)
                
                # Update axes limits
                if len(x_data) > 1:
                    ax1.set_xlim(0, max(len(x_data) - 1, 10))
                    ax2.set_xlim(0, max(len(x_data) - 1, 10))
                
                # Add time labels to x-axis
                if len(timestamps) > 0:
                    # Select a few timestamps for labels
                    num_labels = min(5, len(timestamps))
                    label_indices = [int(i * (len(timestamps) - 1) / max(1, num_labels - 1)) for i in range(num_labels)]
                    
                    # Safety check for index bounds
                    label_indices = [idx for idx in label_indices if idx < len(timestamps)]
                    
                    if label_indices:
                        time_labels = [timestamps[i].strftime("%H:%M:%S") for i in label_indices]
                        
                        ax1.set_xticks(label_indices)
                        ax1.set_xticklabels(time_labels, rotation=45, fontsize=8)
                        ax2.set_xticks(label_indices)
                        ax2.set_xticklabels(time_labels, rotation=45, fontsize=8)
                
                # Update titles with current values
                if temp_data:
                    ax1.set_title(f'Average Temperature: {temp_data[-1]:.1f}°C', fontsize=11)
                    # Adjust y-axis if needed
                    temp_min = min(temp_data)
                    temp_max = max(temp_data)
                    margin = max(2, (temp_max - temp_min) * 0.1)
                    ax1.set_ylim(max(0, temp_min - margin), temp_max + margin)
                    
                if hum_data:
                    ax2.set_title(f'Average Humidity: {hum_data[-1]:.1f}%', fontsize=11)
                
                # Redraw the canvas
                canvas.draw()
        
        # Schedule the next update
        root.after(1000, update_ui)
    
    # Start server in a separate thread
    threading.Thread(target=start_server, args=(gui_log,), daemon=True).start()
    
    # Initial log
    gui_log("Central Server started")
    
    # Start the UI update loop
    update_ui()
    
    # Start the main loop
    root.mainloop()

if __name__ == "__main__":
    start_gui()