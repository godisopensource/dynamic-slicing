#!/usr/bin/env python3
"""
Simple network traffic exporter for Prometheus.
Reads /proc/net/dev and exposes metrics on :8000/metrics
"""
import time
from prometheus_client import start_http_server, Gauge
import re

# Metrics
rx_bytes = Gauge('gnb_network_receive_bytes_total', 'Total bytes received', ['interface'])
tx_bytes = Gauge('gnb_network_transmit_bytes_total', 'Total bytes transmitted', ['interface'])
rx_packets = Gauge('gnb_network_receive_packets_total', 'Total packets received', ['interface'])
tx_packets = Gauge('gnb_network_transmit_packets_total', 'Total packets transmitted', ['interface'])

def read_net_dev():
    """Parse /proc/net/dev and return interface statistics."""
    stats = {}
    with open('/proc/net/dev', 'r') as f:
        lines = f.readlines()[2:]  # Skip header lines
        for line in lines:
            parts = line.split(':')
            if len(parts) != 2:
                continue
            iface = parts[0].strip()
            values = parts[1].split()
            if len(values) >= 16:
                stats[iface] = {
                    'rx_bytes': int(values[0]),
                    'rx_packets': int(values[1]),
                    'tx_bytes': int(values[8]),
                    'tx_packets': int(values[9])
                }
    return stats

def update_metrics():
    """Update Prometheus metrics with current network stats."""
    stats = read_net_dev()
    for iface, values in stats.items():
        # Focus on eth0 (main interface)
        if iface == 'eth0':
            rx_bytes.labels(interface=iface).set(values['rx_bytes'])
            tx_bytes.labels(interface=iface).set(values['tx_bytes'])
            rx_packets.labels(interface=iface).set(values['rx_packets'])
            tx_packets.labels(interface=iface).set(values['tx_packets'])

if __name__ == '__main__':
    # Start Prometheus HTTP server on port 8000
    start_http_server(8000)
    print("Network exporter started on :8000/metrics")
    
    # Update metrics every 5 seconds
    while True:
        try:
            update_metrics()
        except Exception as e:
            print(f"Error updating metrics: {e}")
        time.sleep(5)
