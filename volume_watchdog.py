#!/usr/bin/env python3
"""
Volume watchdog - runs as a systemd service.
Every minute, Mon-Fri 10am-4pm: if any Sonos speaker is above MAX_VOLUME, set it to MAX_VOLUME.
"""
import socket
import time
import sys
from datetime import datetime

MAX_VOLUME = 10
SPEAKER_MAX_OVERRIDES = {
    "Window": 20,
}
CHECK_INTERVAL = 60  # seconds


def is_enforcement_window() -> bool:
    """Return True if current time is Mon-Fri between 10:00 and 16:00."""
    now = datetime.now()
    # Monday=0, Friday=4
    if now.weekday() > 4:
        return False
    return 10 <= now.hour < 16


def find_sonos_ips(timeout: float = 3.0) -> list[str]:
    msg = (
        b"M-SEARCH * HTTP/1.1\r\n"
        b"HOST: 239.255.255.250:1900\r\n"
        b'MAN: "ssdp:discover"\r\n'
        b"MX: 2\r\n"
        b"ST: urn:schemas-upnp-org:device:ZonePlayer:1\r\n\r\n"
    )
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.settimeout(timeout)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.sendto(msg, ("239.255.255.250", 1900))
    found: set[str] = set()
    try:
        while True:
            _, addr = sock.recvfrom(1024)
            found.add(addr[0])
    except socket.timeout:
        pass
    finally:
        sock.close()
    return list(found)


def check_and_enforce(ips: list[str]) -> None:
    from soco import SoCo

    acted = False
    for ip in ips:
        try:
            speaker = SoCo(ip)
            name = speaker.player_name
            vol = speaker.volume
            limit = SPEAKER_MAX_OVERRIDES.get(name, MAX_VOLUME)
            if vol > limit:
                speaker.volume = limit
                print(f"  ↓ {name}: {vol} → {limit}", flush=True)
                acted = True
        except Exception as e:
            print(f"  ! {ip}: {e}", flush=True)

    if not acted:
        print(f"  ✓ all speakers within limits", flush=True)


def main():
    print(f"Volume watchdog started — max {MAX_VOLUME}, Mon-Fri 10:00-16:00", flush=True)
    print(f"Checking every {CHECK_INTERVAL}s\n", flush=True)

    ips: list[str] = []

    try:
        while True:
            now_str = time.strftime("%Y-%m-%d %H:%M:%S")

            if not is_enforcement_window():
                print(f"[{now_str}] outside enforcement window, sleeping", flush=True)
                time.sleep(CHECK_INTERVAL)
                continue

            # Re-discover periodically in case speakers come/go
            if not ips:
                print(f"[{now_str}] discovering speakers...", end=" ", flush=True)
                ips = find_sonos_ips()
                if not ips:
                    print("none found, will retry next cycle", flush=True)
                    time.sleep(CHECK_INTERVAL)
                    continue
                print(f"found {len(ips)}", flush=True)

            print(f"[{now_str}]", flush=True)
            check_and_enforce(ips)
            print(flush=True)
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        print("\nWatchdog stopped.")


if __name__ == "__main__":
    main()
