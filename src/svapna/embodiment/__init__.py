"""Desktop-side embodiment integration.

The ESP32-S3-BOX-3 device is the physical embodiment. This module is
where desktop-side code that talks to it lives — REST clients, audio
streaming, display drivers, sensor-event handlers.

See `embodiment/ROADMAP.md` at the project root for the work plan.
See `embodiment/CURRENT_STATE.md` for where the work currently stands.

This module is the boundary for BUILD-mode heartbeat cycles on the
desktop side: cycles may write here freely but not into the
surrounding `src/svapna/` namespace.
"""

from .esp_client import (  # noqa: F401
    DeviceStatus,
    DisplayPayload,
    EspClient,
    HeartbeatPayload,
)
