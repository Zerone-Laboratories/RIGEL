# Skill: mobile_aci

Auxiliary Compute Interface (ACI) workflows for Android/ztOS-connected devices.

## Scope

Use this skill when the task involves interacting with a connected auxiliary device (phone/tablet) via the `ztos_aci_*` tools.

## Prerequisites

- ACI service must be initialized and at least one device should be connected.
- If device discovery fails, start by running `list_usb_devices` to confirm the device is visible.

## Tools

- initialize_auxiliary_compute_unit
- list_usb_devices
- ztos_aci_list_devices
- ztos_aci_get_device_info
- ztos_aci_set_volume
- ztos_aci_send_notification
- ztos_aci_ring_device
- ztos_aci_send_file
- ztos_aci_share_url
- ztos_aci_run_command
- ztos_aci_send_sms
- ztos_aci_list_user_contacts

## Workflows

### Workflow: Initialize ACI (first-run)

1. Call `initialize_auxiliary_compute_unit`.
2. Call `ztos_aci_list_devices`.
3. If no devices are returned:
   - Call `list_usb_devices` and ensure the device is connected/unlocked.
   - Retry `ztos_aci_list_devices`.

### Workflow: Pick a device (device_id first)

This is the entrypoint for most ACI actions.

1. Call `ztos_aci_list_devices`.
2. Choose the best device (prefer online/connected, then most recently seen).
3. Extract and store the `device_id` for subsequent calls.

### Workflow: Get device info

1. Ensure you have `device_id` using the “Pick a device” workflow.
2. Call `ztos_aci_get_device_info(device_id=...)`.

### Workflow: Set device volume

1. Ensure you have `device_id` using the “Pick a device” workflow.
2. If your task requires current state first, call `ztos_aci_get_device_info(device_id=...)` and read any reported audio/volume fields.
3. Call `ztos_aci_set_volume(device_id=..., volume=...)`.
4. Optional validation: call `ztos_aci_get_device_info(device_id=...)` again.

### Workflow: Notify / ring device

1. Ensure you have `device_id` using the “Pick a device” workflow.
2. For a notification: call `ztos_aci_send_notification(device_id=..., title=..., message=...)`.
3. For ringing: call `ztos_aci_ring_device(device_id=...)`.

### Workflow: Share a URL

1. Ensure you have `device_id` using the “Pick a device” workflow.
2. Call `ztos_aci_share_url(device_id=..., url=...)`.

### Workflow: Send a file

1. Ensure you have `device_id` using the “Pick a device” workflow.
2. Ensure you have a local file path.
3. Call `ztos_aci_send_file(device_id=..., file_path=...)`.

### Workflow: Run a command on device

1. Ensure you have `device_id` using the “Pick a device” workflow.
2. Call `ztos_aci_run_command(device_id=..., command=...)`.

## Safety / Guardrails

- Always obtain `device_id` first (`ztos_aci_list_devices`) before calling device-specific tools.
- If multiple devices are connected, never assume: pick explicitly and (if needed) show the user the chosen device details.
