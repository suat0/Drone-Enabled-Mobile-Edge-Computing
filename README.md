# Environmental Monitoring System

A distributed environmental monitoring system using IoT sensors, edge computing drones, and a central server for real-time data collection, anomaly detection, and visualization.

## System Architecture

The system consists of three main components:

1. **Sensor Nodes** (`SensorNode.py`) - Simulated environmental sensors that collect temperature and humidity data
2. **Drone Edge Server** (`DroneEdgeServer.py`) - Edge computing nodes that aggregate sensor data and manage battery/flight operations  
3. **Central Server** (`CentralServer.py`) - Main monitoring dashboard that receives data from multiple drones

```
[Sensor Nodes] → [Drone Edge Server] → [Central Server]
     ↓                    ↓                    ↓
 Generate data      Process & aggregate    Visualize & monitor
```

## Features

### Central Server
- **Real-time Dashboard**: Live monitoring of all connected drones
- **Data Visualization**: Temperature and humidity charts with historical data
- **Anomaly Detection**: Automatic detection and logging of environmental anomalies
- **Drone Management**: Monitor battery levels, status, and connected sensors
- **Multi-tabbed Interface**: Organized view for dashboard, anomalies, and logs

### Drone Edge Server
- **Sensor Data Aggregation**: Collects data from multiple environmental sensors
- **Battery Simulation**: Realistic battery management with automatic return-to-base
- **Local Processing**: Real-time anomaly detection and data buffering
- **Manual Controls**: Override battery levels and flight operations
- **Real-time Charts**: Local visualization of sensor data

### Sensor Nodes
- **Data Generation**: Simulated temperature and humidity readings
- **Anomaly Injection**: Configurable anomaly generation for testing
- **Robust Connection**: Automatic reconnection handling
- **Customizable Parameters**: Adjustable transmission intervals and anomaly frequency

## Installation

### Prerequisites
- Python 3.7 or higher
- Required Python packages:

```bash
pip install tkinter matplotlib socket threading json time random datetime collections argparse
```

### Clone or Download
Download all three Python files:
- `CentralServer.py`
- `DroneEdgeServer.py`
- `SensorNode.py`

## Usage

### Quick Start

1. **Start the Central Server**:
```bash
python CentralServer.py
```
The central server will start listening on port 6000.

2. **Start a Drone Edge Server**:
```bash
python DroneEdgeServer.py
```
The drone will start listening for sensors on port 8888 and connect to the central server.

3. **Start Sensor Nodes**:
```bash
python SensorNode.py --sensor_id sensor1
python SensorNode.py --sensor_id sensor2 --anomaly_frequency 10
```

### Advanced Configuration

#### Sensor Node Options
```bash
python SensorNode.py [options]

Options:
  --drone_ip IP          IP address of the drone (default: 127.0.0.1)
  --drone_port PORT      Port number of the drone (default: 8888)
  --sensor_id ID         Unique identifier for this sensor (default: sensor1)
  --interval SECONDS     Data transmission interval (default: 2)
  --anomaly_frequency N  1 in N chance to generate anomalous data (default: 20)
```

#### Example Multi-Sensor Setup
```bash
# Normal sensors
python SensorNode.py --sensor_id temp_sensor_1 --interval 3
python SensorNode.py --sensor_id humidity_sensor_1 --interval 5

# Sensor with frequent anomalies for testing
python SensorNode.py --sensor_id test_sensor --anomaly_frequency 5
```

## Configuration

### Network Ports
- **Central Server**: Port 6000
- **Drone Edge Server**: Port 8888
- **IP Configuration**: Default is localhost (127.0.0.1)

### Anomaly Detection Thresholds
Edit the configuration in the Drone Edge Server:
```python
ANOMALY_TEMP_RANGE = (15, 35)    # Normal temperature range (°C)
ANOMALY_HUMIDITY_RANGE = (30, 70)  # Normal humidity range (%)
```

### Battery Management
```python
MAX_BATTERY_LEVEL = 100
BATTERY_THRESHOLD = 20           # Return to base threshold
BATTERY_DRAIN_RATE = 1           # % per 10 seconds
BATTERY_CHARGE_RATE = 5          # % per 10 seconds
```

## System Monitoring

### Central Server Dashboard
- **Drone Status Tab**: Real-time status of all connected drones
  - Battery levels
  - Current status (Active/Returning to Base)
  - Connected sensors
  - Last update timestamp

- **Anomalies Tab**: Comprehensive anomaly tracking
  - Total anomaly count
  - Temperature vs humidity anomalies
  - Detailed anomaly log with timestamps

- **Logs Tab**: System-wide activity log

### Drone Edge Server Interface
- **Dashboard**: Current drone status and sensor connections
- **Real-time Charts**: Temperature and humidity visualization
- **Manual Controls**: Battery level override and flight commands
- **Logs**: Local drone activity

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Ensure the target server is running
   - Check IP addresses and ports
   - Verify firewall settings

2. **No Data Appearing**
   - Confirm sensors are connected to the correct drone port
   - Check that the drone is not in "Returning to Base" mode
   - Verify JSON data format

3. **GUI Not Responding**
   - Close and restart the application
   - Check for Python tkinter installation
   - Ensure matplotlib is properly installed

### Debug Mode
Add debug prints by modifying the `gui_log` function calls throughout the code.

## Development

### Adding New Sensor Types
Modify the `generate_sensor_data()` function in `SensorNode.py`:
```python
def generate_sensor_data(sensor_id, with_anomaly=False, anomaly_type=None):
    # Add new sensor data fields here
    return {
        "sensor_id": sensor_id,
        "temperature": temperature,
        "humidity": humidity,
        "pressure": pressure,  # New field
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
```

### Extending Anomaly Detection
Add new anomaly types in the drone edge server:
```python
# Add to handle_sensor function
if not (PRESSURE_RANGE[0] <= decoded['pressure'] <= PRESSURE_RANGE[1]):
    anomaly = f"Pressure anomaly detected: {decoded['pressure']}hPa from {sensor_id}"
    anomalies.append(anomaly)
```

## License

This project is open source and available under the MIT License.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs for error messages
3. Ensure all dependencies are installed
4. Verify network configuration
