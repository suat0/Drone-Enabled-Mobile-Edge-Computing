# SensorNode.py
import socket
import time
import json
import argparse
import random
from datetime import datetime
import sys

def generate_sensor_data(sensor_id, with_anomaly=False, anomaly_type=None):
    """
    Generate simulated sensor data with optional anomalies
    """
    # Normal ranges
    if not with_anomaly or anomaly_type != "temperature":
        temperature = round(random.uniform(20, 30), 2)
    else:
        # Generate temperature anomaly (outside normal range)
        temperature = round(random.choice([
            random.uniform(0, 15),  # Too cold
            random.uniform(36, 50)  # Too hot
        ]), 2)
    
    if not with_anomaly or anomaly_type != "humidity":
        humidity = round(random.uniform(40, 60), 2)
    else:
        # Generate humidity anomaly (outside normal range)
        humidity = round(random.choice([
            random.uniform(0, 25),  # Too dry
            random.uniform(75, 100)  # Too humid
        ]), 2)
    
    return {
        "sensor_id": sensor_id,
        "temperature": temperature,
        "humidity": humidity,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

def main(drone_ip, drone_port, sensor_id, interval, anomaly_frequency):
    """
    Main function to connect to drone and send sensor data
    
    Parameters:
    drone_ip (str): IP address of the drone
    drone_port (int): Port number of the drone
    sensor_id (str): Unique identifier for this sensor
    interval (int): Time interval between data transmissions in seconds
    anomaly_frequency (int): 1 in X chance to generate anomalous data
    """
    connection_attempts = 0
    data_sent_count = 0
    
    print(f"[{sensor_id}] Starting sensor node...")
    print(f"[{sensor_id}] Configured to connect to Drone at {drone_ip}:{drone_port}")
    print(f"[{sensor_id}] Data transmission interval: {interval} seconds")
    print(f"[{sensor_id}] Anomaly frequency: 1 in {anomaly_frequency} chance")
    
    while True:
        try:
            connection_attempts += 1
            print(f"[{sensor_id}] Connection attempt #{connection_attempts} to Drone at {drone_ip}:{drone_port}")
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((drone_ip, drone_port))
                print(f"[{sensor_id}] Connected to Drone at {drone_ip}:{drone_port}")
                
                # Reset connection attempts counter on successful connection
                connection_attempts = 0
                
                while True:
                    # Decide if we should generate an anomaly
                    generate_anomaly = random.randint(1, anomaly_frequency) == 1
                    anomaly_type = random.choice(["temperature", "humidity"]) if generate_anomaly else None
                    
                    # Generate and send data
                    data = generate_sensor_data(sensor_id, generate_anomaly, anomaly_type)
                    s.sendall(json.dumps(data).encode())
                    
                    data_sent_count += 1
                    anomaly_msg = f" (ANOMALY: {anomaly_type})" if generate_anomaly else ""
                    print(f"[{sensor_id}] #{data_sent_count} Sent: Temp={data['temperature']}°C, Humidity={data['humidity']}%{anomaly_msg}")
                    
                    time.sleep(interval)
                    
        except ConnectionRefusedError:
            print(f"[{sensor_id}] Connection refused. Drone not available at {drone_ip}:{drone_port}")
            print(f"[{sensor_id}] Retrying in 5 seconds...")
            time.sleep(5)
            
        except ConnectionResetError:
            print(f"[{sensor_id}] Connection reset by drone. Likely drone is returning to base.")
            print(f"[{sensor_id}] Retrying in 5 seconds...")
            time.sleep(5)
            
        except Exception as e:
            print(f"[{sensor_id}] Connection failed: {e}")
            print(f"[{sensor_id}] Retrying in 5 seconds...")
            time.sleep(5)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Environmental Sensor Node Simulator")
    parser.add_argument("--drone_ip", default="127.0.0.1", help="IP address of the drone")
    parser.add_argument("--drone_port", type=int, default=8888, help="Port number of the drone")
    parser.add_argument("--sensor_id", default="sensor1", help="Unique identifier for this sensor")
    parser.add_argument("--interval", type=int, default=5, help="Data transmission interval in seconds")
    parser.add_argument("--anomaly_frequency", type=int, default=20, help="1 in X chance to generate anomalous data")
    
    args = parser.parse_args()
    
    try:
        main(args.drone_ip, args.drone_port, args.sensor_id, args.interval, args.anomaly_frequency)
    except KeyboardInterrupt:
        print(f"\n[{args.sensor_id}] Sensor node stopped by user")
        sys.exit(0)