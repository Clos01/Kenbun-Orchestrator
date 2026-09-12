#!/usr/bin/env python3
"""
Docker SRE Agent (Manual Draft)
Monitors Docker daemon for anomalies using the official Docker Python SDK.
1. Orphaned Containers (running but missing compose labels).
2. Healthcheck Loops (marked 'unhealthy' for N consecutive checks).

Usage:
  python3 scripts/docker_sre.py
"""

import time
import logging
import docker
import sys
from requests.exceptions import ConnectionError as RequestsConnectionError

logging.basicConfig(level=logging.INFO, format='%(asctime)s [SRE] %(levelname)s: %(message)s', stream=sys.stderr)

class SREAgent:
    def __init__(self, check_interval_sec=60, unhealthy_threshold=3):
        try:
            self.client = docker.from_env()
        except Exception as e:
            logging.error(f"Failed to initialize Docker client: {e}")
            self.client = None
            
        self.check_interval = check_interval_sec
        
        # Hysteresis tracking
        self.unhealthy_tracker = {}  # { container_id: count_of_consecutive_unhealthy_checks }
        self.alerted_unhealthy = set() # { container_id }
        
        self.starting_tracker = {} # { container_id: count }
        self.alerted_starting = set()
        
        self.known_orphans = set()   # { container_id }
        self.unhealthy_threshold = unhealthy_threshold
        
        # Daemon error backoff
        self.daemon_error_count = 0

    def run_check(self):
        if not self.client:
            logging.error("Docker client not initialized.")
            return
            
        logging.debug("Starting container health scan...")
        
        try:
            containers = self.client.containers.list(all=True)
            if self.daemon_error_count > 0:
                logging.info("Reconnected to Docker daemon successfully.")
            self.daemon_error_count = 0  # Reset on success
        except RequestsConnectionError:
            self.daemon_error_count += 1
            backoff = min(self.check_interval * self.daemon_error_count, 300)
            logging.error(f"Could not fetch containers (daemon down?). Backing off for {backoff}s...")
            time.sleep(backoff - self.check_interval) # Subtract base interval since loop sleeps too
            return
        except Exception as e:
            logging.error(f"Error fetching containers: {e}")
            return

        active_unhealthy = set()
        active_starting = set()
        active_orphans = set()

        for c in containers:
            c_id = c.short_id
            name = c.name
            state = c.status
            labels = c.labels
            
            health_status = 'none'
            if 'Health' in c.attrs['State']:
                health_status = c.attrs['State']['Health']['Status']

            # 1. Orphan Detection
            is_compose = 'com.docker.compose.project' in labels
            if state == 'running' and not is_compose:
                active_orphans.add(c_id)
                if c_id not in self.known_orphans:
                    logging.warning(f"ORPHAN DETECTED: Container '{name}' ({c_id}) is running outside of Docker Compose.")
                    self.known_orphans.add(c_id)

            # 2. Healthcheck Loop Detection
            if health_status == 'unhealthy':
                active_unhealthy.add(c_id)
                self.unhealthy_tracker[c_id] = self.unhealthy_tracker.get(c_id, 0) + 1
                consecutive_failures = self.unhealthy_tracker[c_id]
                
                if consecutive_failures >= self.unhealthy_threshold:
                    if c_id not in self.alerted_unhealthy:
                        logging.error(f"HEALTH LOOP DETECTED: '{name}' has been unhealthy for {consecutive_failures} scans!")
                        self.alerted_unhealthy.add(c_id)
                    elif consecutive_failures % 10 == 0:
                        logging.error(f"HEALTH LOOP PERSISTS: '{name}' is still unhealthy ({consecutive_failures} scans).")
                        
            # 3. Stuck in 'starting'
            elif health_status == 'starting':
                active_starting.add(c_id)
                self.starting_tracker[c_id] = self.starting_tracker.get(c_id, 0) + 1
                consecutive_starting = self.starting_tracker[c_id]
                
                if consecutive_starting >= self.unhealthy_threshold:
                    if c_id not in self.alerted_starting:
                        logging.error(f"STUCK STARTING: '{name}' healthcheck never returns healthy!")
                        self.alerted_starting.add(c_id)
            
            # Recovery
            elif health_status == 'healthy':
                if c_id in self.unhealthy_tracker:
                    logging.info(f"Container '{name}' recovered from unhealthy. Resetting tracker.")
                    del self.unhealthy_tracker[c_id]
                    self.alerted_unhealthy.discard(c_id)
                if c_id in self.starting_tracker:
                    logging.info(f"Container '{name}' finally started healthy. Resetting tracker.")
                    del self.starting_tracker[c_id]
                    self.alerted_starting.discard(c_id)

        # Cleanup stale trackers
        for stale_id in set(self.unhealthy_tracker.keys()) - active_unhealthy:
            del self.unhealthy_tracker[stale_id]
            self.alerted_unhealthy.discard(stale_id)
            
        for stale_id in set(self.starting_tracker.keys()) - active_starting:
            del self.starting_tracker[stale_id]
            self.alerted_starting.discard(stale_id)
            
        for stale_id in self.known_orphans - active_orphans:
            self.known_orphans.remove(stale_id)

    def start_monitoring(self):
        logging.info(f"Starting SRE Agent. Polling every {self.check_interval} seconds...")
        try:
            while True:
                self.run_check()
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            logging.info("SRE Agent shutting down safely.")

if __name__ == "__main__":
    # Test run: Default 10 second polling for immediate testing
    agent = SREAgent(check_interval_sec=10, unhealthy_threshold=3)
    agent.start_monitoring()
