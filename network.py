"""Use the Windows certificate store for outbound HTTPS in managed environments."""

from __future__ import annotations


def configure_tls() -> None:
    try:
        import truststore
        truststore.inject_into_ssl()
    except ImportError:
        # Standard Python certificate handling remains the fallback.
        pass
