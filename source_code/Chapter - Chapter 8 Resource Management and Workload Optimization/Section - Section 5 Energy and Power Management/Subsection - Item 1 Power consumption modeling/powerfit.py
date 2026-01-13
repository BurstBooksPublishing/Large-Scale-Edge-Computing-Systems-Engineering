#!/usr/bin/env python3
# Production-ready: robust sampling, exception handling, CSV logging, and linear fit.
import time, csv, sys
import numpy as np
import psutil
from Adafruit_INA219 import INA219

SAMPLE_INTERVAL = 0.1            # seconds
SAMPLES = 600                    # collect 60s of data

ina = INA219()                   # initialize sensor (I2C)
ina.configure()                  # default gain and bus ADC

times, utils, powers = [], [], []
try:
    for i in range(SAMPLES):
        t = time.time()
        cpu_u = psutil.cpu_percent(interval=None)/100.0
        voltage = ina.voltage()   # volts
        current = ina.current()   # mA
        power_w = voltage * (current/1000.0)
        times.append(t); utils.append(cpu_u); powers.append(power_w)
        time.sleep(SAMPLE_INTERVAL)
except KeyboardInterrupt:
    pass

# Prepare arrays and fit P = a * u + b
U = np.vstack([np.array(utils), np.ones(len(utils))]).T
y = np.array(powers)
coeffs, residuals, *_ = np.linalg.lstsq(U, y, rcond=None)
a, b = coeffs
# Dump model and samples
with open('power_model.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['time','cpu_util','power_w'])
    writer.writerows(zip(times, utils, powers))
print(f"Fitted model: P(u) = {a:.4f} * u + {b:.4f}  (residual={residuals})")