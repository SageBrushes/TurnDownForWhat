"""Tests for network utility functions."""
import pytest
import ipaddress
from unittest.mock import Mock, patch


def test_get_local_ip_returns_valid_ip():
    """Test that get_local_ip returns a valid IP address."""
    # When: Get local IP
    from app.utils.network import get_local_ip

    result = get_local_ip()

    # Then: Should be a valid IP address string
    assert isinstance(result, str)
    # Should be parseable as IP address
    ip = ipaddress.ip_address(result)
    assert ip.version == 4  # IPv4


def test_get_local_ip_returns_non_loopback():
    """Test that get_local_ip doesn't return loopback address."""
    # When: Get local IP
    from app.utils.network import get_local_ip

    result = get_local_ip()

    # Then: Should not be loopback (127.x.x.x)
    assert not result.startswith("127.")


def test_get_local_ip_returns_private_network():
    """Test that get_local_ip returns a private network address."""
    # When: Get local IP
    from app.utils.network import get_local_ip

    result = get_local_ip()

    # Then: Should be in private IP ranges (192.168.x.x, 10.x.x.x, 172.16-31.x.x)
    ip = ipaddress.ip_address(result)
    assert ip.is_private


def test_get_local_ip_with_multiple_interfaces():
    """Test get_local_ip with multiple network interfaces."""
    # Given: Mock multiple network interfaces with ifaddr
    from app.utils.network import get_local_ip

    with patch("app.utils.network.ifaddr.get_adapters") as mock_adapters:
        # Mock adapter with multiple IPs
        mock_adapter = Mock()

        # Loopback IP (should be skipped)
        loopback_ip = Mock()
        loopback_ip.is_IPv4 = True
        loopback_ip.ip = "127.0.0.1"

        # Valid private IP (should be selected)
        private_ip = Mock()
        private_ip.is_IPv4 = True
        private_ip.ip = "192.168.1.100"

        mock_adapter.ips = [loopback_ip, private_ip]
        mock_adapters.return_value = [mock_adapter]

        # When: Get local IP
        result = get_local_ip()

        # Then: Should return the private IP, not loopback
        assert result == "192.168.1.100"


def test_get_local_ip_no_network():
    """Test get_local_ip behavior when no network is available."""
    # Given: No network interfaces available
    from app.utils.network import get_local_ip

    with patch("app.utils.network.ifaddr.get_adapters") as mock_adapters:
        mock_adapters.return_value = []

        # When: Get local IP
        # Then: Should return fallback or raise error
        with pytest.raises(RuntimeError) as exc_info:
            get_local_ip()

        assert "No network interface found" in str(exc_info.value)


def test_get_local_ip_only_loopback():
    """Test get_local_ip when only loopback interface exists."""
    # Given: Only loopback interface
    from app.utils.network import get_local_ip

    with patch("app.utils.network.ifaddr.get_adapters") as mock_adapters:
        mock_adapter = Mock()
        loopback_ip = Mock()
        loopback_ip.is_IPv4 = True
        loopback_ip.ip = "127.0.0.1"
        mock_adapter.ips = [loopback_ip]
        mock_adapters.return_value = [mock_adapter]

        # When: Get local IP
        # Then: Should raise error (no non-loopback IP found)
        with pytest.raises(RuntimeError) as exc_info:
            get_local_ip()

        assert "No non-loopback" in str(exc_info.value) or "No network interface found" in str(exc_info.value)


def test_get_local_ip_filters_ipv6():
    """Test that get_local_ip filters out IPv6 addresses."""
    # Given: Mix of IPv4 and IPv6 addresses
    from app.utils.network import get_local_ip

    with patch("app.utils.network.ifaddr.get_adapters") as mock_adapters:
        mock_adapter = Mock()

        # IPv6 address (should be skipped)
        ipv6 = Mock()
        ipv6.is_IPv4 = False
        ipv6.is_IPv6 = True
        ipv6.ip = "fe80::1"

        # IPv4 address (should be selected)
        ipv4 = Mock()
        ipv4.is_IPv4 = True
        ipv4.ip = "192.168.1.50"

        mock_adapter.ips = [ipv6, ipv4]
        mock_adapters.return_value = [mock_adapter]

        # When: Get local IP
        result = get_local_ip()

        # Then: Should return IPv4 address only
        assert result == "192.168.1.50"


def test_get_local_ip_prefers_192_168():
    """Test that get_local_ip prefers 192.168.x.x addresses when multiple are available."""
    # Given: Multiple private IPs from different ranges
    from app.utils.network import get_local_ip

    with patch("app.utils.network.ifaddr.get_adapters") as mock_adapters:
        mock_adapter = Mock()

        # 10.x.x.x address
        ip_10 = Mock()
        ip_10.is_IPv4 = True
        ip_10.ip = "10.0.0.5"

        # 192.168.x.x address (preferred)
        ip_192 = Mock()
        ip_192.is_IPv4 = True
        ip_192.ip = "192.168.1.100"

        # 172.16.x.x address
        ip_172 = Mock()
        ip_172.is_IPv4 = True
        ip_172.ip = "172.16.0.10"

        mock_adapter.ips = [ip_10, ip_192, ip_172]
        mock_adapters.return_value = [mock_adapter]

        # When: Get local IP
        result = get_local_ip()

        # Then: Should prefer 192.168.x.x
        assert result == "192.168.1.100"
