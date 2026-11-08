#!/usr/bin/env bash
# Record how the goggles meet an Android phone over USB-C, in both data roles.
#
# The phone must already be connected over wireless adb, with the goggles plugged
# into its USB-C port. The script:
#   1. records the phone's USB state in its current role (normally host),
#   2. switches the phone port to the device role, which leaves the goggles the
#      host role, and records whether they start Android Open Accessory mode,
#   3. restores the original roles and records the state again.
# Logcat covers the whole run. Device serial strings are redacted from every file.
#
# Usage: tools/research/android_accessory_probe.sh LABEL [SECONDS_IN_DEVICE_ROLE] [POWER_ROLE]
#   LABEL, for example otg-on or otg-off, names the output directory.
#   POWER_ROLE for step 2 defaults to the current one; "sink" lets the goggles
#   power the phone, which also asks for a power-role swap.
set -euo pipefail

label=${1:?Usage: $0 LABEL [SECONDS_IN_DEVICE_ROLE]}
hold=${2:-20}
power_request=${3:-}
[[ -z $power_request || $power_request =~ ^(source|sink)$ ]] || { echo "POWER_ROLE must be source or sink" >&2; exit 2; }
[[ $label =~ ^[A-Za-z0-9_-]+$ ]] || { echo "LABEL may contain letters, digits, - and _ only" >&2; exit 2; }
[[ $hold =~ ^[0-9]+$ ]] && (( hold >= 5 && hold <= 120 )) || { echo "SECONDS must be 5-120" >&2; exit 2; }

root=$(cd "$(dirname "$0")/../.." && pwd)
out="$root/work/android/$(date +%Y%m%d-%H%M%S)-$label"
mkdir -p "$out"

# Goggles report their serial in the product name (Goggles3-<serial>).
redact() { sed -E 's/(product_name=Goggles[0-9A-Za-z]*-)[0-9A-Za-z]+/\1<redacted>/; s/(mSerial=|serial=|serial_number=)[^,} ]+/\1<redacted>/'; }
note() { echo "$*"; echo "$(date +%T.%3N) $*" >> "$out/steps.txt"; }

[[ $(adb get-state 2>/dev/null) == device ]] || { echo "adb sees no phone. Run adb connect first." >&2; exit 1; }
port=$(adb shell dumpsys usb | awk '/usb_ports=/{f=1} f && /id=/{sub(/.*id=/,""); print; exit}')
[[ -n $port ]] || { echo "No USB-C port reported by the phone" >&2; exit 1; }
read -r power data < <(adb shell dumpsys usb | awk '/port_manager=/{f=1} f && /power_role=/ && !p{sub(/.*=/,""); p=$0} f && /data_role=/ && !d{sub(/.*=/,""); d=$0} END{print p, d}')

restore() {
    note "Restoring port $port to $power $data"
    adb shell dumpsys usb set-port-roles "$port" "$power" "$data" >> "$out/steps.txt" 2>&1 || true
}
snapshot() {
    adb shell dumpsys usb | redact > "$out/$1-dumpsys-usb.txt"
    {
        echo "== $1"
        # An empty match is a result here, not an error
        grep -E 'current_functions=|connected=|configured=|host_connected=|current_mode=|power_role=|data_role=' \
            "$out/$1-dumpsys-usb.txt" | head -9 || true
        grep -E 'manufacturer_name=|product_name=|vendor_id=|product_id=' "$out/$1-dumpsys-usb.txt" | head -4 || true
        grep -iE -A8 'accessory=\{|mManufacturer|UsbAccessory\[' "$out/$1-dumpsys-usb.txt" | head -20 || true
    } | tee -a "$out/summary.txt" || true
}

{
    echo "label=$label hold=$hold port=$port initial_roles=$power/$data"
    adb shell getprop ro.product.manufacturer; adb shell getprop ro.product.model
    adb shell getprop ro.build.version.release
} > "$out/phone.txt"

adb logcat -c || true
adb logcat -v threadtime > "$out/logcat-raw.txt" 2>&1 &
logcat_pid=$!
trap 'restore; kill $logcat_pid 2>/dev/null || true' EXIT

note "Step 1: current roles $power/$data"
snapshot 1-initial

step_power=${power_request:-$power}
note "Step 2: phone port -> $step_power device (goggles get the host role), holding ${hold}s"
adb shell dumpsys usb set-port-roles "$port" "$step_power" device 2>&1 | tee -a "$out/steps.txt"
for (( i = 5; i <= hold; i += 5 )); do
    sleep 5
    note "  ${i}s in device role"
done
snapshot 2-device-role

restore
trap 'kill $logcat_pid 2>/dev/null || true' EXIT
sleep 5
snapshot 3-restored

kill $logcat_pid 2>/dev/null || true
wait $logcat_pid 2>/dev/null || true
redact < "$out/logcat-raw.txt" | grep -iE 'usb|accessory|dji|typec|otg|aoa' > "$out/logcat-usb.txt" || true
rm -f "$out/logcat-raw.txt"
echo "== role switch lines in logcat" | tee -a "$out/summary.txt"
grep -iE 'role switch|Setting USB port|data_role|power_role' "$out/logcat-usb.txt" | head -20 | tee -a "$out/summary.txt" || true
echo "== accessory lines in logcat" | tee -a "$out/summary.txt"
grep -iE 'accessory|mManufacturer|com\.dji' "$out/logcat-usb.txt" | head -20 | tee -a "$out/summary.txt" || true
echo "Output: $out"
