# DroneServer.py
import socket
import threading
import tkinter as tk
from tkinter import ttk
import json
import time
import random
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from collections import deque
import datetime

SENSOR_PORT = 8888
CENTRAL_IP = "127.0.0.1"
CENTRAL_PORT = 6000

# Configuration parameters
MAX_BATTERY_LEVEL = 100
BATTERY_THRESHOLD = 20
BATTERY_DRAIN_RATE = 1  # % per 10 seconds
BATTERY_CHARGE_RATE = 5  # % per 10 seconds
ANOMALY_TEMP_RANGE = (15, 35)  # Normal temperature range
ANOMALY_HUMIDITY_RANGE = (30, 70)  # Normal humidity range
DATA_BUFFER_SIZE = 100  # Number of data points to keep for visualization

# Global variables
sensor_data_buffer = []
data_history = {}  # Store data history for each sensor
battery_level = MAX_BATTERY_LEVEL
drone_status = "Active"  # "Active" or "Returning to Base"
returning_to_base = False
log_buffer = []
connected_sensors = set()
temperature_history = deque(maxlen=DATA_BUFFER_SIZE)
humidity_history = deque(maxlen=DATA_BUFFER_SIZE)
timestamps = deque(maxlen=DATA_BUFFER_SIZE)

# Lock for thread-safe operations
lock = threading.Lock()

def handle_sensor(conn, addr, gui_log):
    sensor_id = None
    with conn:
        gui_log(f"Connected to sensor at {addr}")
        while True:
            try:
                data = conn.recv(1024)
                if not data:
                    break
                
                decoded = json.loads(data.decode())
                sensor_id = decoded['sensor_id']
                
                with lock:
                    if sensor_id not in connected_sensors:
                        connected_sensors.add(sensor_id)
                        gui_log(f"New sensor registered: {sensor_id}")
                    
                    # Check for anomalies
                    anomalies = []
                    if not (ANOMALY_TEMP_RANGE[0] <= decoded['temperature'] <= ANOMALY_TEMP_RANGE[1]):
                        anomaly = f"Temperature anomaly detected: {decoded['temperature']}°C from {sensor_id}"
                        anomalies.append(anomaly)
                        gui_log(anomaly)
                    
                    if not (ANOMALY_HUMIDITY_RANGE[0] <= decoded['humidity'] <= ANOMALY_HUMIDITY_RANGE[1]):
                        anomaly = f"Humidity anomaly detected: {decoded['humidity']}% from {sensor_id}"
                        anomalies.append(anomaly)
                        gui_log(anomaly)
                    
                    # Add anomaly flag to data
                    decoded['anomalies'] = anomalies
                    
                    # Store in buffer for processing
                    sensor_data_buffer.append(decoded)
                    
                    # Store for visualization
                    if sensor_id not in data_history:
                        data_history[sensor_id] = {'temperature': [], 'humidity': [], 'timestamps': []}
                    
                    data_history[sensor_id]['temperature'].append(decoded['temperature'])
                    data_history[sensor_id]['humidity'].append(decoded['humidity'])
                    data_history[sensor_id]['timestamps'].append(decoded['timestamp'])
                    
                    # Update global history for charts
                    temperature_history.append(decoded['temperature'])
                    humidity_history.append(decoded['humidity'])
                    timestamps.append(datetime.datetime.fromisoformat(decoded['timestamp'].replace('Z', '+00:00')))
                
                gui_log(f"Received from {sensor_id}: Temp={decoded['temperature']}°C, Humidity={decoded['humidity']}%")
            
            except json.JSONDecodeError:
                gui_log(f"Invalid JSON from {addr}")
                break
            except Exception as e:
                gui_log(f"Error handling sensor data: {e}")
                break
    
    with lock:
        if sensor_id and sensor_id in connected_sensors:
            connected_sensors.remove(sensor_id)
    
    gui_log(f"Disconnected sensor at {addr}")

def start_sensor_server(gui_log):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", SENSOR_PORT))
    server.listen(5)
    gui_log(f"Drone listening on port {SENSOR_PORT}")
    
    while True:
        try:
            conn, addr = server.accept()
            threading.Thread(target=handle_sensor, args=(conn, addr, gui_log)).start()
        except Exception as e:
            gui_log(f"Error accepting connection: {e}")
            time.sleep(1)

def forward_to_central(gui_log):
    global sensor_data_buffer
    
    while True:
        time.sleep(5)  # Forward data every 5 seconds
        
        with lock:
            if not sensor_data_buffer or returning_to_base:
                continue
            
            # Process the data
            if sensor_data_buffer:
                avg_temp = sum(d["temperature"] for d in sensor_data_buffer) / len(sensor_data_buffer)
                avg_hum = sum(d["humidity"] for d in sensor_data_buffer) / len(sensor_data_buffer)
                
                # Collect all anomalies
                all_anomalies = []
                for data in sensor_data_buffer:
                    if 'anomalies' in data and data['anomalies']:
                        all_anomalies.extend(data['anomalies'])
                
                payload = {
                    "drone_id": "drone1",
                    "avg_temperature": round(avg_temp, 2),
                    "avg_humidity": round(avg_hum, 2),
                    "anomalies": all_anomalies,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "drone_status": drone_status,
                    "battery_level": battery_level,
                    "connected_sensors": list(connected_sensors)
                }
                
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.connect((CENTRAL_IP, CENTRAL_PORT))
                        s.sendall(json.dumps(payload).encode())
                        gui_log(f"Forwarded to Central: Avg Temp={payload['avg_temperature']}°C, Avg Humidity={payload['avg_humidity']}%")
                        if all_anomalies:
                            gui_log(f"Forwarded anomalies: {len(all_anomalies)}")
                    
                    # Clear buffer after successful transmission
                    sensor_data_buffer = []
                    
                except Exception as e:
                    gui_log(f"Central server unreachable: {e}")

def simulate_battery(gui_log, battery_var, status_var):
    global battery_level, drone_status, returning_to_base
    
    while True:
        time.sleep(10)  # Update battery every 10 seconds
        
        with lock:
            if returning_to_base:
                # Charging
                battery_level = min(MAX_BATTERY_LEVEL, battery_level + BATTERY_CHARGE_RATE)
                if battery_level >= MAX_BATTERY_LEVEL:
                    returning_to_base = False
                    drone_status = "Active"
                    gui_log("Battery fully charged. Drone is now active.")
            else:
                # Discharging
                battery_level = max(0, battery_level - BATTERY_DRAIN_RATE)
                if battery_level <= BATTERY_THRESHOLD:
                    returning_to_base = True
                    drone_status = "Returning to Base"
                    gui_log(f"Battery level ({battery_level}%) below threshold. Returning to base.")
        
        # Update GUI
        battery_var.set(battery_level)
        status_var.set(drone_status)

def start_gui():
    root = tk.Tk()
    root.title("Drone Edge Server")
    root.geometry("1000x700")
    
    # Create notebook with tabs
    notebook = ttk.Notebook(root)
    notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # Dashboard tab
    dashboard_frame = ttk.Frame(notebook)
    notebook.add(dashboard_frame, text="Dashboard")
    
    # Status frame
    status_frame = ttk.LabelFrame(dashboard_frame, text="Drone Status")
    status_frame.pack(fill=tk.X, padx=5, pady=5)
    
    # Battery level
    battery_var = tk.IntVar(value=battery_level)
    ttk.Label(status_frame, text="Battery Level:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
    battery_progress = ttk.Progressbar(status_frame, variable=battery_var, maximum=MAX_BATTERY_LEVEL, length=200)
    battery_progress.grid(row=0, column=1, padx=5, pady=5)
    battery_label = ttk.Label(status_frame, textvariable=battery_var)
    battery_label.grid(row=0, column=2, padx=5, pady=5)
    ttk.Label(status_frame, text="%").grid(row=0, column=3, padx=0, pady=5, sticky=tk.W)
    
    # Drone status
    status_var = tk.StringVar(value=drone_status)
    ttk.Label(status_frame, text="Status:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
    status_label = ttk.Label(status_frame, textvariable=status_var)
    status_label.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
    
    # Connected sensors
    sensors_frame = ttk.LabelFrame(dashboard_frame, text="Connected Sensors")
    sensors_frame.pack(fill=tk.X, padx=5, pady=5)
    
    sensors_text = tk.Text(sensors_frame, height=3, width=80)
    sensors_text.pack(fill=tk.X, padx=5, pady=5)
    
    # Create chart frame
    chart_frame = ttk.LabelFrame(dashboard_frame, text="Real-time Data")
    chart_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    # Create matplotlib figure
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 5))
    
    # Temperature axis
    ax1.set_title('Temperature (°C)')
    ax1.set_ylim(0, 40)
    temp_line, = ax1.plot([], [], 'r-')
    
    # Humidity axis
    ax2.set_title('Humidity (%)')
    ax2.set_ylim(0, 100)
    hum_line, = ax2.plot([], [], 'b-')
    
    # Add figure to tkinter window
    canvas = FigureCanvasTkAgg(fig, master=chart_frame)
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    # Log tab
    log_frame = ttk.Frame(notebook)
    notebook.add(log_frame, text="Logs")
    
    log_text = tk.Text(log_frame, height=20, width=80)
    log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    log_scroll = ttk.Scrollbar(log_text, command=log_text.yview)
    log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    log_text.config(yscrollcommand=log_scroll.set)
    
    # Manual controls tab
    controls_frame = ttk.Frame(notebook)
    notebook.add(controls_frame, text="Controls")
    
    # Battery control
    battery_control_frame = ttk.LabelFrame(controls_frame, text="Battery Control")
    battery_control_frame.pack(fill=tk.X, padx=5, pady=5)
    
    def set_battery_level():
        global battery_level
        try:
            new_level = int(battery_entry.get())
            if 0 <= new_level <= 100:
                with lock:
                    battery_level = new_level
                    battery_var.set(new_level)
                gui_log(f"Battery level manually set to {new_level}%")
            else:
                gui_log("Battery level must be between 0 and 100")
        except ValueError:
            gui_log("Invalid battery level")
    
    ttk.Label(battery_control_frame, text="Set Battery Level (0-100%):").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
    battery_entry = ttk.Entry(battery_control_frame, width=10)
    battery_entry.grid(row=0, column=1, padx=5, pady=5)
    battery_entry.insert(0, str(battery_level))
    ttk.Button(battery_control_frame, text="Set", command=set_battery_level).grid(row=0, column=2, padx=5, pady=5)
    
    # Force return to base
    def force_return():
        global returning_to_base, drone_status
        with lock:
            returning_to_base = True
            drone_status = "Returning to Base"
            status_var.set(drone_status)
        gui_log("Manually triggered return to base")
    
    ttk.Button(battery_control_frame, text="Force Return to Base", command=force_return).grid(row=1, column=0, columnspan=3, padx=5, pady=5)
    
    # Resume normal operation
    def resume_operation():
        global returning_to_base, drone_status
        with lock:
            returning_to_base = False
            drone_status = "Active"
            status_var.set(drone_status)
        gui_log("Manually resumed normal operation")
    
    ttk.Button(battery_control_frame, text="Resume Normal Operation", command=resume_operation).grid(row=2, column=0, columnspan=3, padx=5, pady=5)
    
    # Define log function
    def gui_log(message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        log_text.see(tk.END)
        
        # Add to buffer for potential forwarding
        log_buffer.append(f"[{timestamp}] {message}")
    
    # Function to update the charts
    def update_charts():
        with lock:
            if timestamps and temperature_history and humidity_history:
                temp_line.set_xdata(range(len(temperature_history)))
                temp_line.set_ydata(temperature_history)
                ax1.set_xlim(0, len(temperature_history))
                
                hum_line.set_xdata(range(len(humidity_history)))
                hum_line.set_ydata(humidity_history)
                ax2.set_xlim(0, len(humidity_history))
                
                # Update connected sensors list
                sensors_text.delete(1.0, tk.END)
                sensors_text.insert(tk.END, f"Connected sensors ({len(connected_sensors)}): {', '.join(connected_sensors)}")
                
                # Redraw the canvas
                canvas.draw()
        
        # Schedule the next update
        root.after(2000, update_charts)
    
    # Start the update function
    update_charts()
    
    # Start server threads
    threading.Thread(target=start_sensor_server, args=(gui_log,), daemon=True).start()
    threading.Thread(target=forward_to_central, args=(gui_log,), daemon=True).start()
    threading.Thread(target=simulate_battery, args=(gui_log, battery_var, status_var), daemon=True).start()
    
    # Initial log
    gui_log("Drone Edge Server started")
    
    # Start the main loop
    root.mainloop()

if __name__ == "__main__":
    start_gui()