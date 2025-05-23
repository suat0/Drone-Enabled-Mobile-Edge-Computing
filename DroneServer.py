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
import queue
import logging
from contextlib import contextmanager

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

# Thread-safe queues for better communication
log_queue = queue.Queue()
gui_update_queue = queue.Queue()

# Improved locks
data_lock = threading.RLock()  # Re-entrant lock for nested operations
status_lock = threading.RLock()

# Server control
server_running = True
server_socket = None

@contextmanager
def safe_lock(lock):
    """Context manager for safe lock handling"""
    acquired = False
    try:
        acquired = lock.acquire(timeout=1.0)  # 1 second timeout
        if not acquired:
            raise TimeoutError("Could not acquire lock")
        yield
    finally:
        if acquired:
            lock.release()

def setup_logging():
    """Setup proper logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('drone_server.log')
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

def handle_sensor(conn, addr, gui_log):
    """Improved sensor handler with better error handling and non-blocking operations"""
    sensor_id = None
    conn.settimeout(5.0)  # Set socket timeout
    
    try:
        with conn:
            gui_log(f"Connected to sensor at {addr}")
            
            while server_running:
                try:
                    # Check if we're returning to base before receiving data
                    with safe_lock(status_lock):
                        if returning_to_base:
                            gui_log(f"Disconnecting sensor at {addr} - Drone is returning to base")
                            break

                    # Non-blocking receive with timeout
                    data = conn.recv(1024)
                    if not data:
                        break
                    
                    # Check again after receiving data
                    with safe_lock(status_lock):
                        if returning_to_base:
                            gui_log(f"Discarding data from {addr} - Drone is returning to base")
                            continue

                    decoded = json.loads(data.decode())
                    sensor_id = decoded['sensor_id']
                    
                    # Process data in separate thread to avoid blocking
                    threading.Thread(
                        target=process_sensor_data, 
                        args=(decoded, sensor_id, gui_log),
                        daemon=True
                    ).start()
                    
                except socket.timeout:
                    # Check if we should continue or break
                    with safe_lock(status_lock):
                        if returning_to_base:
                            break
                    continue
                    
                except json.JSONDecodeError as e:
                    gui_log(f"Invalid JSON from {addr}: {e}")
                    break
                    
                except Exception as e:
                    logger.error(f"Error handling sensor data from {addr}: {e}")
                    break
                    
    except Exception as e:
        logger.error(f"Connection error with {addr}: {e}")
    finally:
        # Clean up sensor connection
        if sensor_id:
            with safe_lock(data_lock):
                connected_sensors.discard(sensor_id)
        gui_log(f"Disconnected sensor at {addr}")

def process_sensor_data(decoded, sensor_id, gui_log):
    """Process sensor data in separate thread to avoid blocking"""
    try:
        with safe_lock(data_lock):
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
            
            # Convert to local time
            utc_time = datetime.datetime.fromisoformat(decoded['timestamp'].replace('Z', '+00:00'))
            local_time = utc_time.astimezone()
            timestamps.append(local_time)
            
        gui_log(f"Received from {sensor_id}: Temp={decoded['temperature']}°C, Humidity={decoded['humidity']}%")
        
    except Exception as e:
        logger.error(f"Error processing sensor data: {e}")

def start_sensor_server(gui_log):
    """Improved sensor server with better connection handling"""
    global server_socket, server_running
    
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.settimeout(1.0)  # Set timeout for accept operations
        server_socket.bind(("0.0.0.0", SENSOR_PORT))
        server_socket.listen(10)  # Increased backlog
        gui_log(f"Drone listening on port {SENSOR_PORT}")
        
        while server_running:
            try:
                conn, addr = server_socket.accept()
                
                with safe_lock(status_lock):
                    if returning_to_base:
                        # Reject connection if returning to base
                        conn.close()
                        gui_log(f"Rejected sensor connection from {addr} - Drone is returning to base")
                        continue
                
                # Start handler thread with daemon flag
                handler_thread = threading.Thread(
                    target=handle_sensor, 
                    args=(conn, addr, gui_log),
                    daemon=True
                )
                handler_thread.start()
                
            except socket.timeout:
                # Normal timeout, continue checking server_running
                continue
            except Exception as e:
                if server_running:  # Only log if we're still supposed to be running
                    logger.error(f"Error accepting connection: {e}")
                    time.sleep(0.1)  # Brief pause before retry
                    
    except Exception as e:
        logger.error(f"Server startup error: {e}")
    finally:
        if server_socket:
            server_socket.close()

def send_status_updates(gui_log):
    """Improved status updates with connection pooling"""
    retry_delay = 1
    max_retry_delay = 30
    
    while server_running:
        try:
            gui_log("Connecting to central server for status updates...")
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10.0)  # Set connection timeout
            s.connect((CENTRAL_IP, CENTRAL_PORT))
            gui_log("Connected to central server for status updates.")
            retry_delay = 1  # Reset retry delay on successful connection

            while server_running:
                time.sleep(5)  # Send updates every 5 seconds
                
                try:
                    with safe_lock(status_lock):
                        # Always send only essential data
                        payload = {
                            "drone_id": "drone1",
                            "drone_status": drone_status,
                            "battery_level": battery_level,
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
                        }

                    s.sendall(json.dumps(payload).encode() + b"\n")
                    gui_log(f"Status Update: Status={drone_status}, Battery={battery_level}%")
                    
                except socket.error as send_error:
                    gui_log(f"Error sending status update: {send_error}")
                    break  # Reconnect
                except Exception as e:
                    logger.error(f"Unexpected error in status update: {e}")
                    break

        except Exception as conn_error:
            if server_running:
                gui_log(f"Could not connect to central server for status updates: {conn_error}")
                time.sleep(min(retry_delay, max_retry_delay))
                retry_delay = min(retry_delay * 2, max_retry_delay)  # Exponential backoff

def forward_to_central(gui_log):
    """Improved central forwarding with better error handling"""
    global sensor_data_buffer
    retry_delay = 1
    max_retry_delay = 30

    while server_running:
        try:
            gui_log("Connecting to central server for sensor data...")
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10.0)
            s.connect((CENTRAL_IP, CENTRAL_PORT))
            gui_log("Connected to central server for sensor data.")
            retry_delay = 1  # Reset retry delay

            while server_running:
                time.sleep(5)
                
                try:
                    with safe_lock(data_lock):
                        if not sensor_data_buffer:
                            continue
                            
                        with safe_lock(status_lock):
                            if returning_to_base:
                                continue

                        # Process buffer data
                        buffer_copy = sensor_data_buffer.copy()
                        sensor_data_buffer.clear()  # Clear buffer after copying
                        
                        if not buffer_copy:
                            continue

                    # Calculate outside of lock
                    avg_temp = sum(d["temperature"] for d in buffer_copy) / len(buffer_copy)
                    avg_hum = sum(d["humidity"] for d in buffer_copy) / len(buffer_copy)
                    
                    all_anomalies = []
                    for data in buffer_copy:
                        if 'anomalies' in data and data['anomalies']:
                            all_anomalies.extend(data['anomalies'])

                    with safe_lock(status_lock):
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

                    s.sendall(json.dumps(payload).encode() + b"\n")
                    gui_log(f"Sensor Data: Avg Temp={payload['avg_temperature']}°C, Avg Humidity={payload['avg_humidity']}%")
                    if all_anomalies:
                        gui_log(f"Forwarded anomalies: {len(all_anomalies)}")
                        
                except socket.error as send_error:
                    gui_log(f"Error sending sensor data: {send_error}")
                    break  # Reconnect
                except Exception as e:
                    logger.error(f"Unexpected error in data forwarding: {e}")
                    break

        except Exception as conn_error:
            if server_running:
                gui_log(f"Could not connect to central server for sensor data: {conn_error}")
                time.sleep(min(retry_delay, max_retry_delay))
                retry_delay = min(retry_delay * 2, max_retry_delay)

def simulate_battery(gui_log, battery_var, status_var):
    """Improved battery simulation with thread safety"""
    global battery_level, drone_status, returning_to_base
    
    while server_running:
        time.sleep(10)  # Update battery every 10 seconds
        
        try:
            with safe_lock(status_lock):
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
            
            # Update GUI in main thread
            gui_update_queue.put(('battery', battery_level))
            gui_update_queue.put(('status', drone_status))
            
        except Exception as e:
            logger.error(f"Error in battery simulation: {e}")

def start_gui():
    global server_running
    
    root = tk.Tk()
    root.title("Drone Edge Server")
    root.geometry("1000x700")
    
    # Handle window close event
    def on_closing():
        global server_running
        server_running = False
        if server_socket:
            server_socket.close()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
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
    
    # Create matplotlib figure with improved spacing
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 5), gridspec_kw={'hspace': 0.5})

    # Temperature axis with proper configuration
    ax1.set_title('Temperature (°C)', fontsize=11, pad=10)
    ax1.set_ylim(0, 40)
    ax1.grid(True, linestyle='--', alpha=0.7)
    ax1.set_ylabel('Temperature (°C)', fontsize=10)
    temp_line, = ax1.plot([], [], 'r-', linewidth=2)

    # Humidity axis with proper configuration
    ax2.set_title('Humidity (%)', fontsize=11, pad=10)
    ax2.set_ylim(0, 100)
    ax2.grid(True, linestyle='--', alpha=0.7)
    ax2.set_ylabel('Humidity (%)', fontsize=10)
    hum_line, = ax2.plot([], [], 'b-', linewidth=2)

    # Apply tight layout with additional padding
    fig.tight_layout(pad=3.0)

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
                with safe_lock(status_lock):
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
        with safe_lock(status_lock):
            returning_to_base = True
            drone_status = "Returning to Base"
            status_var.set(drone_status)
        gui_log("Manually triggered return to base")
    
    ttk.Button(battery_control_frame, text="Force Return to Base", command=force_return).grid(row=1, column=0, columnspan=3, padx=5, pady=5)
    
    # Resume normal operation
    def resume_operation():
        global returning_to_base, drone_status
        with safe_lock(status_lock):
            returning_to_base = False
            drone_status = "Active"
            status_var.set(drone_status)
        gui_log("Manually resumed normal operation")
    
    ttk.Button(battery_control_frame, text="Resume Normal Operation", command=resume_operation).grid(row=2, column=0, columnspan=3, padx=5, pady=5)
    
    # Define log function with queue
    def gui_log(message):
        log_queue.put(message)
    
    # Process log queue
    def process_log_queue():
        try:
            while True:
                message = log_queue.get_nowait()
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                log_text.insert(tk.END, f"[{timestamp}] {message}\n")
                log_text.see(tk.END)
                log_buffer.append(f"[{timestamp}] {message}")
        except queue.Empty:
            pass
        finally:
            root.after(100, process_log_queue)  # Check queue every 100ms
    
    # Process GUI updates
    def process_gui_updates():
        try:
            while True:
                update_type, value = gui_update_queue.get_nowait()
                if update_type == 'battery':
                    battery_var.set(value)
                elif update_type == 'status':
                    status_var.set(value)
        except queue.Empty:
            pass
        finally:
            root.after(200, process_gui_updates)  # Check queue every 200ms
    
    # Function to update the charts (optimized)
    def update_charts():
        if not server_running:
            return
            
        try:
            with safe_lock(data_lock):
                if len(temperature_history) > 0 and len(humidity_history) > 0:
                    # Get the data from the deques
                    temp_data = list(temperature_history)
                    hum_data = list(humidity_history)
                    
                    # Create x-axis data points (indices)
                    x_data = list(range(len(temp_data)))
                    
                    # Update the plot data
                    temp_line.set_xdata(x_data)
                    temp_line.set_ydata(temp_data)
                    hum_line.set_xdata(x_data)
                    hum_line.set_ydata(hum_data)
                    
                    # Adjust the plot limits
                    if len(x_data) > 1:
                        ax1.set_xlim(0, len(x_data) - 1)
                        ax2.set_xlim(0, len(x_data) - 1)
                        
                        # Set real-time labels on x-axis
                        if len(timestamps) > 0:
                            # Select a few timestamps for labels to avoid overcrowding
                            num_labels = min(5, len(timestamps))
                            if num_labels > 1:
                                label_indices = [int(i * (len(timestamps) - 1) / (num_labels - 1)) for i in range(num_labels)]
                                time_labels = [timestamps[i].strftime("%H:%M:%S") for i in label_indices]
                                
                                ax1.set_xticks(label_indices)
                                ax1.set_xticklabels(time_labels, rotation=45, fontsize=8)
                                ax2.set_xticks(label_indices)
                                ax2.set_xticklabels(time_labels, rotation=45, fontsize=8)
                    
                    # Update titles with current values
                    if temp_data:
                        ax1.set_title(f'Temperature: {temp_data[-1]:.1f}°C', fontsize=11)
                    if hum_data:
                        ax2.set_title(f'Humidity: {hum_data[-1]:.1f}%', fontsize=11)
                    
                    # Update connected sensors text
                    sensors_text.delete(1.0, tk.END)
                    if connected_sensors:
                        sensors_text.insert(tk.END, f"Connected sensors ({len(connected_sensors)}): {', '.join(connected_sensors)}")
                    else:
                        sensors_text.insert(tk.END, "No sensors connected")
                    
                    # Force a redraw of the canvas
                    canvas.draw_idle()
        except Exception as e:
            logger.error(f"Error updating charts: {e}")
        finally:
            # Schedule the next update
            root.after(2000, update_charts)  # Update every 2 seconds instead of 1
    
    # Start server threads
    threading.Thread(target=start_sensor_server, args=(gui_log,), daemon=True).start()
    threading.Thread(target=forward_to_central, args=(gui_log,), daemon=True).start()
    threading.Thread(target=send_status_updates, args=(gui_log,), daemon=True).start()
    threading.Thread(target=simulate_battery, args=(gui_log, battery_var, status_var), daemon=True).start()
    
    # Initial log
    gui_log("Drone Edge Server started")
    
    # Start the update loops
    root.after(100, process_log_queue)
    root.after(200, process_gui_updates)
    root.after(2000, update_charts)
    
    # Start the main loop
    root.mainloop()

if __name__ == "__main__":
    start_gui()