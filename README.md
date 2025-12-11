# piNASPWMFanControl

PWM fan control script for a fan controlled by a Raspberry Pi 5 to cool HDDs in a NAS.

## Features

- **PWM Fan Control**: Precise fan speed control using hardware PWM on Raspberry Pi 5
- **Tachometer Reading**: Real-time RPM monitoring from the fan's tach pin
- **HDD Temperature Monitoring**: Automatic temperature reading from multiple HDDs
- **Dynamic Duty Cycle**: Adjustable fan speeds based on configurable temperature thresholds
- **JSON Configuration**: Easy-to-customize settings without code changes
- **Systemd Integration**: Auto-start on boot with service management
- **Logging**: Comprehensive logging with adjustable log levels

## Requirements

- Raspberry Pi 5
- Python 3.7 or higher
- PWM-capable fan with tachometer output
- HDDs with S.M.A.R.T. support

### Hardware Connections

1. **PWM Pin**: Connect the fan's PWM control wire to a PWM-capable GPIO pin (default: GPIO 18)
2. **Tach Pin**: Connect the fan's tachometer wire to a GPIO pin (default: GPIO 23)
3. **Ground**: Connect fan ground to Pi ground
4. **Power**: Connect fan power (5V/12V depending on fan) to appropriate power source

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/HattMarris1/piNASPWMFanControl.git
   cd piNASPWMFanControl
   ```

2. Install dependencies:
   ```bash
   pip3 install -r requirements.txt
   ```

3. Install required system tools for HDD temperature reading:
   ```bash
   sudo apt-get update
   sudo apt-get install hddtemp smartmontools
   ```

4. Create your configuration file:
   ```bash
   cp config.json.example config.json
   nano config.json  # Edit as needed
   ```

## Configuration

Edit `config.json` to customize the behavior:

```json
{
  "pwm_pin": 18,                    // GPIO pin for PWM control
  "tach_pin": 23,                   // GPIO pin for tachometer
  "pwm_frequency": 25000,           // PWM frequency in Hz
  "update_interval": 5,             // Seconds between updates
  "rpm_sample_time": 2,             // Seconds to measure RPM
  "tach_pulses_per_revolution": 2,  // Tach pulses per fan revolution
  "log_level": "INFO",              // DEBUG, INFO, WARNING, ERROR
  "hdd_devices": [                  // List of HDD devices to monitor
    "/dev/sda",
    "/dev/sdb"
  ],
  "temperature_thresholds": [       // Temp to duty cycle mapping
    {"temp": 30, "duty_cycle": 0},   // Fan off below 30°C
    {"temp": 35, "duty_cycle": 30},  // 30% at 35°C
    {"temp": 40, "duty_cycle": 50},  // 50% at 40°C
    {"temp": 45, "duty_cycle": 70},  // 70% at 45°C
    {"temp": 50, "duty_cycle": 100}  // 100% at 50°C+
  ]
}
```

### Temperature Thresholds

The script uses linear interpolation between temperature thresholds. For example:
- At 32.5°C (between 30°C and 35°C): duty cycle = 15%
- At 47.5°C (between 45°C and 50°C): duty cycle = 85%

## Usage

### Manual Run

Run the script manually for testing:

```bash
sudo python3 fan_control.py
```

Or with a custom config file:

```bash
sudo python3 fan_control.py /path/to/config.json
```

**Note**: Root privileges are required for GPIO access and reading HDD temperatures.

### Run as a Service

For automatic startup on boot:

1. Copy files to system location:
   ```bash
   sudo mkdir -p /opt/piNASPWMFanControl
   sudo cp fan_control.py /opt/piNASPWMFanControl/
   sudo cp config.json /opt/piNASPWMFanControl/
   ```

2. Install and enable the systemd service:
   ```bash
   sudo cp fan-control.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable fan-control.service
   sudo systemctl start fan-control.service
   ```

3. Check service status:
   ```bash
   sudo systemctl status fan-control.service
   ```

4. View logs:
   ```bash
   sudo journalctl -u fan-control.service -f
   ```

## Troubleshooting

### GPIO Permissions

If you get GPIO permission errors:
```bash
sudo usermod -a -G gpio $USER
```
Then log out and back in.

### HDD Temperature Reading

Test HDD temperature reading:
```bash
sudo hddtemp /dev/sda
# or
sudo smartctl -A /dev/sda | grep Temperature
```

### PWM Not Working

- Verify GPIO pin supports PWM (GPIO 18 recommended for Pi 5)
- Check fan connection and power supply
- Try increasing `pwm_frequency` or decreasing it (typically 25kHz works well)

### Tachometer Reading Issues

- Ensure fan has a tachometer output wire
- Check `tach_pulses_per_revolution` setting (usually 2 for 4-pin fans)
- Verify pull-up resistor configuration

## Raspberry Pi 5 Notes

This script uses the `lgpio` library which is compatible with Raspberry Pi 5's GPIO chip (gpiochip4). The older `RPi.GPIO` library is not compatible with Pi 5.

### GPIO Chip

The script automatically uses gpiochip4 for Raspberry Pi 5. If using a different board, you may need to adjust the chip number in the code.

## License

This project is open source and available under the MIT License.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues and questions, please use the GitHub issue tracker.
