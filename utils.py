# Dynamic port assignment - find available ports immediately
import socket


def find_available_port(
    preferred_port: int, host: str = "localhost", max_attempts: int = 100
) -> int:
    """
    Find an available port starting from the preferred port.

    Args:
        preferred_port: The port to try first
        host: Host to check ports on (default: localhost)
        max_attempts: Maximum number of ports to try

    Returns:
        Available port number
    """

    def _is_port_available(port: int) -> bool:
        """Check if a specific port is available (not in use)."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)  # Set a short timeout
                result = sock.connect_ex((host, port))
                return result != 0  # Port is available if connection fails
        except Exception:
            return True  # Assume available if we can't check

    # Check if preferred port is available
    if _is_port_available(preferred_port):
        return preferred_port

    # Find alternative port
    for i in range(1, max_attempts + 1):
        candidate_port = preferred_port + i
        if candidate_port > 65535:  # Port number limit
            break

        if _is_port_available(candidate_port):
            return candidate_port

    # If no available port found, issue a warning and return preferred port
    # The application will fail later with a proper error message
    print(f"⚠️  Warning: Could not find an available port starting from {preferred_port}")
    return preferred_port
