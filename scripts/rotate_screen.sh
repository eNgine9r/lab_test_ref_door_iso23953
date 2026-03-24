#!/usr/bin/env bash
set -euo pipefail

PREFERRED_ROTATION="${SCREEN_ROTATION:-left}"
CONFIG_CANDIDATES=(/boot/firmware/config.txt /boot/config.txt)

apply_config_txt() {
  local cfg="$1"
  [[ -w "$cfg" ]] || return 1

  if rg -q '^lcd_rotate=' "$cfg"; then
    sed -i 's/^lcd_rotate=.*/lcd_rotate=3/' "$cfg"
  elif rg -q '^display_rotate=' "$cfg"; then
    sed -i 's/^display_rotate=.*/display_rotate=3/' "$cfg"
  else
    printf '\n# Door test kiosk vertical orientation\ndisplay_rotate=3\n' >> "$cfg"
  fi
  return 0
}

for cfg in "${CONFIG_CANDIDATES[@]}"; do
  if [[ -f "$cfg" ]] && apply_config_txt "$cfg"; then
    echo "Rotation saved in $cfg (takes effect after reboot)."
    exit 0
  fi
done

if command -v xrandr >/dev/null 2>&1; then
  display_name="${XRANDR_DISPLAY:-}"
  if [[ -z "$display_name" ]]; then
    display_name="$(xrandr | awk '/ connected/{print $1; exit}')"
  fi
  if [[ -n "$display_name" ]]; then
    xrandr --output "$display_name" --rotate "$PREFERRED_ROTATION" || true
    echo "Applied runtime rotation via xrandr to $display_name."
    exit 0
  fi
fi

echo "Unable to apply display rotation automatically."
exit 0
