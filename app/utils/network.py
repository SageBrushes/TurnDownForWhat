"""Network utility functions for detecting local IP addresses."""
import ifaddr
import ipaddress
from typing import Optional


def get_local_ip() -> str:
    """
    Get the local IP address of this machine on the network.

    Prefers 192.168.x.x addresses when multiple private IPs are available.
    Filters out loopback (127.x.x.x) and IPv6 addresses.

    Returns:
        str: Local IPv4 address as a string (e.g., "192.168.1.100")

    Raises:
        RuntimeError: If no suitable network interface is found
    """
    preferred_ip: Optional[str] = None
    fallback_ip: Optional[str] = None

    for adapter in ifaddr.get_adapters():
        for ip in adapter.ips:
            # Only process IPv4 addresses
            if not ip.is_IPv4:
                continue

            ip_str = ip.ip

            # Skip loopback addresses
            if ip_str.startswith("127."):
                continue

            # Validate it's a private IP
            try:
                ip_obj = ipaddress.ip_address(ip_str)
                if not ip_obj.is_private:
                    continue
            except ValueError:
                continue

            # Prefer 192.168.x.x addresses (most common for home networks)
            if ip_str.startswith("192.168."):
                preferred_ip = ip_str
                break

            # Keep any other private IP as fallback
            if fallback_ip is None:
                fallback_ip = ip_str

        # If we found a preferred IP, stop searching
        if preferred_ip:
            break

    # Return preferred IP first, then fallback, or raise error
    result = preferred_ip or fallback_ip

    if result is None:
        raise RuntimeError(
            "No network interface found with a non-loopback IPv4 address. "
            "Please ensure you are connected to a network."
        )

    return result
