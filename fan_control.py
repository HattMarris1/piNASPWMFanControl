#!/usr/bin/env python3
"""
PWM Fan Control for Raspberry Pi 5
Controls a PWM fan based on HDD temperatures with tachometer reading support.
"""

import time
import json
import logging
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

try:
    import lgpio
except ImportError:
    print("Error: lgpio library not found. Install with: pip install lgpio")
    sys.exit(1)


class FanController:
    """Controls PWM fan speed based on HDD temperatures with tach monitoring."""

    def __init__(self, config_path: str = "config.json"):
        """
        Initialize the fan controller.
        
        Args:
            config_path: Path to the JSON configuration file
        """
        self.config = self._load_config(config_path)
        self.chip_handle = None
        self.pwm_pin = self.config['pwm_pin']
        self.tach_pin = self.config['tach_pin']
        self.tach_pulses = 0
        self.last_rpm = 0
        
        # Setup logging
        log_level = getattr(logging, self.config.get('log_level', 'INFO'))
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Initialize GPIO
        self._setup_gpio()
        
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            return config
        except FileNotFoundError:
            print(f"Config file {config_path} not found. Creating default config.")
            default_config = self._get_default_config()
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=2)
            return default_config
    
    def _get_default_config(self) -> Dict:
        """Get default configuration."""
        return {
            "pwm_pin": 18,
            "tach_pin": 23,
            "pwm_frequency": 25000,
            "update_interval": 5,
            "rpm_sample_time": 2,
            "tach_pulses_per_revolution": 2,
            "log_level": "INFO",
            "hdd_devices": ["/dev/sda", "/dev/sdb"],
            "temperature_thresholds": [
                {"temp": 30, "duty_cycle": 0},
                {"temp": 35, "duty_cycle": 30},
                {"temp": 40, "duty_cycle": 50},
                {"temp": 45, "duty_cycle": 70},
                {"temp": 50, "duty_cycle": 100}
            ]
        }
    
    def _setup_gpio(self):
        """Initialize GPIO pins for PWM and tachometer."""
        try:
            # Open GPIO chip (gpiochip4 on Raspberry Pi 5)
            self.chip_handle = lgpio.gpiochip_open(4)
            
            # Setup PWM pin
            lgpio.gpio_claim_output(self.chip_handle, self.pwm_pin)
            
            # Setup tachometer pin with pull-up
            lgpio.gpio_claim_input(self.chip_handle, self.tach_pin, lgpio.SET_PULL_UP)
            
            # Setup alert for tach pin (rising edge for pulse counting)
            lgpio.gpio_claim_alert(
                self.chip_handle,
                self.tach_pin,
                lgpio.RISING_EDGE
            )
            
            # Register callback for tachometer
            self.callback = lgpio.callback(
                self.chip_handle,
                self.tach_pin,
                lgpio.RISING_EDGE,
                self._tach_callback
            )
            
            self.logger.info(f"GPIO initialized - PWM pin: {self.pwm_pin}, Tach pin: {self.tach_pin}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize GPIO: {e}")
            raise
    
    def _tach_callback(self, chip, gpio, level, timestamp):
        """Callback for tachometer pulses."""
        # Count rising edges for RPM calculation
        self.tach_pulses += 1
    
    def set_fan_speed(self, duty_cycle: int):
        """
        Set fan speed using PWM duty cycle.
        
        Args:
            duty_cycle: PWM duty cycle percentage (0-100)
        """
        duty_cycle = max(0, min(100, duty_cycle))
        
        try:
            if duty_cycle == 0:
                # Turn off PWM
                lgpio.tx_pwm(self.chip_handle, self.pwm_pin, 0, 0)
            else:
                # Set PWM with given duty cycle
                lgpio.tx_pwm(
                    self.chip_handle,
                    self.pwm_pin,
                    self.config['pwm_frequency'],
                    duty_cycle
                )
            
            self.logger.debug(f"Set fan duty cycle to {duty_cycle}%")
            
        except Exception as e:
            self.logger.error(f"Failed to set fan speed: {e}")
    
    def read_rpm(self) -> int:
        """
        Read fan RPM from tachometer pin using callback-based pulse counting.
        
        Returns:
            Fan speed in RPM
        """
        sample_time = self.config['rpm_sample_time']
        pulses_per_rev = self.config['tach_pulses_per_revolution']
        
        # Reset pulse counter
        self.tach_pulses = 0
        start_time = time.time()
        
        # Wait for the sample time while callbacks count pulses
        time.sleep(sample_time)
        
        # Calculate RPM from counted pulses
        elapsed_time = time.time() - start_time
        pulses = self.tach_pulses
        
        # Calculate RPM: (pulses / pulses_per_revolution) * (60 seconds / elapsed_time)
        if pulses > 0:
            rpm = (pulses / pulses_per_rev) * (60 / elapsed_time)
        else:
            rpm = 0
        
        self.last_rpm = int(rpm)
        return self.last_rpm
    
    def get_hdd_temperatures(self) -> List[float]:
        """
        Get temperatures of all configured HDD devices.
        
        Returns:
            List of temperatures in Celsius
        """
        temperatures = []
        
        for device in self.config['hdd_devices']:
            try:
                # Try using hddtemp via system call
                result = subprocess.run(
                    ['hddtemp', '-n', device],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    temp = float(result.stdout.strip())
                    temperatures.append(temp)
                    self.logger.debug(f"Temperature for {device}: {temp}°C")
                else:
                    # Try smartctl as fallback
                    result = subprocess.run(
                        ['smartctl', '-A', device],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        for line in result.stdout.split('\n'):
                            if 'Temperature_Celsius' in line or 'Airflow_Temperature_Cel' in line:
                                parts = line.split()
                                temp = float(parts[-1])
                                temperatures.append(temp)
                                self.logger.debug(f"Temperature for {device}: {temp}°C")
                                break
                                
            except (subprocess.TimeoutExpired, subprocess.SubprocessError, ValueError, IndexError) as e:
                self.logger.warning(f"Failed to read temperature for {device}: {e}")
                # Use a default temperature if we can't read it
                temperatures.append(40.0)
        
        if not temperatures:
            self.logger.warning("No HDD temperatures could be read, using default")
            temperatures.append(40.0)
        
        return temperatures
    
    def calculate_duty_cycle(self, temperature: float) -> int:
        """
        Calculate duty cycle based on temperature thresholds.
        
        Args:
            temperature: Current temperature in Celsius
            
        Returns:
            Duty cycle percentage (0-100)
        """
        thresholds = self.config['temperature_thresholds']
        
        # Sort thresholds by temperature
        thresholds = sorted(thresholds, key=lambda x: x['temp'])
        
        # If temperature is below the lowest threshold
        if temperature <= thresholds[0]['temp']:
            return thresholds[0]['duty_cycle']
        
        # If temperature is above the highest threshold
        if temperature >= thresholds[-1]['temp']:
            return thresholds[-1]['duty_cycle']
        
        # Interpolate between thresholds
        for i in range(len(thresholds) - 1):
            if thresholds[i]['temp'] <= temperature < thresholds[i + 1]['temp']:
                # Linear interpolation
                temp_range = thresholds[i + 1]['temp'] - thresholds[i]['temp']
                duty_range = thresholds[i + 1]['duty_cycle'] - thresholds[i]['duty_cycle']
                temp_diff = temperature - thresholds[i]['temp']
                
                duty_cycle = thresholds[i]['duty_cycle'] + (duty_range * temp_diff / temp_range)
                return int(duty_cycle)
        
        return thresholds[-1]['duty_cycle']
    
    def run(self):
        """Main control loop."""
        self.logger.info("Starting fan controller...")
        self.logger.info(f"PWM frequency: {self.config['pwm_frequency']} Hz")
        self.logger.info(f"Update interval: {self.config['update_interval']} seconds")
        
        try:
            while True:
                # Get HDD temperatures
                temperatures = self.get_hdd_temperatures()
                max_temp = max(temperatures)
                
                # Calculate required duty cycle
                duty_cycle = self.calculate_duty_cycle(max_temp)
                
                # Set fan speed
                self.set_fan_speed(duty_cycle)
                
                # Read fan RPM (this takes rpm_sample_time seconds)
                rpm = self.read_rpm()
                
                # Log status
                self.logger.info(
                    f"Max HDD temp: {max_temp:.1f}°C | "
                    f"Duty cycle: {duty_cycle}% | "
                    f"Fan RPM: {rpm}"
                )
                
                # Wait before next update
                time.sleep(self.config['update_interval'])
                
        except KeyboardInterrupt:
            self.logger.info("Shutting down fan controller...")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up GPIO resources."""
        if self.chip_handle is not None:
            try:
                # Cancel callback
                if hasattr(self, 'callback') and self.callback is not None:
                    self.callback.cancel()
                
                # Turn off PWM
                lgpio.tx_pwm(self.chip_handle, self.pwm_pin, 0, 0)
                lgpio.gpiochip_close(self.chip_handle)
                self.logger.info("GPIO resources cleaned up")
            except Exception as e:
                self.logger.error(f"Error during cleanup: {e}")


def main():
    """Main entry point."""
    config_path = "config.json"
    
    # Check for config file argument
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    
    controller = FanController(config_path)
    controller.run()


if __name__ == "__main__":
    main()
