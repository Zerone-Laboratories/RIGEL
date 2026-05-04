from __future__ import annotations

from typing import Any, Tuple

from PyQt6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage


DBUS_SERVICE = "com.rigel.RigelService"
DBUS_PATH = "/com/rigel/RigelService"
DBUS_INTERFACE = "com.rigel.RigelService"
DBUS_DAEMON_SERVICE = "org.freedesktop.DBus"
DBUS_DAEMON_PATH = "/org/freedesktop/DBus"
DBUS_DAEMON_INTERFACE = "org.freedesktop.DBus"


class RigelDbusClient:
    def __init__(self, use_system_bus: bool = True) -> None:
        self.connection = QDBusConnection.systemBus() if use_system_bus else QDBusConnection.sessionBus()
        self.service_interface = QDBusInterface(DBUS_SERVICE, DBUS_PATH, DBUS_INTERFACE, self.connection)
        self.dbus_interface = QDBusInterface(
            DBUS_DAEMON_SERVICE,
            DBUS_DAEMON_PATH,
            DBUS_DAEMON_INTERFACE,
            self.connection,
        )
        self.service_interface.setTimeout(120000)
        self.dbus_interface.setTimeout(120000)

    def is_service_available(self) -> bool:
        msg = self.dbus_interface.call("NameHasOwner", DBUS_SERVICE)
        if msg.type() == QDBusMessage.MessageType.ReplyMessage and msg.arguments():
            return bool(msg.arguments()[0])
        return False

    def call(self, method: str, *args: Any) -> Tuple[bool, str]:
        if not self.is_service_available():
            return False, "RIGEL D-Bus service is not running on system bus."

        msg = self.service_interface.call(method, *args)
        if msg.type() == QDBusMessage.MessageType.ErrorMessage:
            return False, f"{msg.errorName()}: {msg.errorMessage()}"

        if msg.type() != QDBusMessage.MessageType.ReplyMessage:
            return False, "Unexpected D-Bus response type."

        values = msg.arguments()
        if not values:
            return True, "OK"

        rendered = []
        for value in values:
            if isinstance(value, (list, tuple)):
                rendered.append(", ".join(str(item) for item in value))
            else:
                rendered.append(str(value))

        return True, "\n".join(rendered)
