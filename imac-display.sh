#!/bin/bash

set -euo pipefail

ACTION="${1:-toggle}"
TARGET="${2:-imac}"

case "$ACTION" in
  connect|disconnect|toggle|status) ;;
  *)
    echo "Usage: $0 {connect|disconnect|toggle|status} [display-name]" >&2
    exit 2
    ;;
esac

osascript - "$ACTION" "$TARGET" <<'APPLESCRIPT'
use scripting additions

on run argv
  set requestedAction to item 1 of argv
  set targetName to item 2 of argv

  tell application "System Settings" to activate

  tell application "System Events"
    if UI elements enabled is false then error "Accessibility permission is required for the app running this script."
    set settingsProcess to process "System Settings"
    tell settingsProcess to set frontmost to true

    my waitForWindow(settingsProcess, 15)
    my openDisplaysPane(settingsProcess)
    my waitForDisplaysPane(settingsProcess, 15)

    set addButton to my findElementByIdentifier(settingsProcess, "AXPopUpButton", "plus")
    if addButton is missing value then error "Could not find the Add display menu in System Settings."
    click addButton

    set targetItem to my waitForAirPlayMenuItem(settingsProcess, targetName, 8)
    if targetItem is missing value then
      key code 53
      if requestedAction is "disconnect" or requestedAction is "status" then return targetName & ": disconnected"
      error "AirPlay display “" & targetName & "” is not available."
    end if

    set isConnected to my menuItemIsChecked(targetItem)
    if isConnected is missing value then set isConnected to my targetIsConnected(settingsProcess, targetName)

    if requestedAction is "status" then
      key code 53
      if isConnected then return targetName & ": connected"
      return targetName & ": disconnected"
    end if

    if requestedAction is "toggle" then
      if isConnected then
        set requestedAction to "disconnect"
      else
        set requestedAction to "connect"
      end if
    end if

    if requestedAction is "connect" and isConnected then
      key code 53
      return targetName & ": already connected"
    end if
    if requestedAction is "disconnect" and isConnected is false then
      key code 53
      return targetName & ": already disconnected"
    end if

    click targetItem
    if requestedAction is "connect" then return targetName & ": connected"
    return targetName & ": disconnected"
  end tell
end run

on waitForWindow(settingsProcess, timeoutSeconds)
  repeat (timeoutSeconds * 4) times
    tell settingsProcess
      if exists window 1 then return
    end tell
    delay 0.25
  end repeat
  error "System Settings did not open in time."
end waitForWindow

on openDisplaysPane(settingsProcess)
  if my findElementByIdentifier(settingsProcess, "AXPopUpButton", "plus") is not missing value then return
  tell application "System Events"
    tell settingsProcess
      set allItems to entire contents of window 1
      repeat with anItem in allItems
        try
          if role of anItem is "AXRow" and name of anItem is "Displays" then
            select anItem
            return
          end if
        end try
      end repeat
    end tell
  end tell
  error "Could not navigate to Displays. Open System Settings > Displays once, then run the script again."
end openDisplaysPane

on waitForDisplaysPane(settingsProcess, timeoutSeconds)
  repeat (timeoutSeconds * 4) times
    if my findElementByIdentifier(settingsProcess, "AXPopUpButton", "plus") is not missing value then return
    delay 0.25
  end repeat
  error "The Displays settings pane did not load in time."
end waitForDisplaysPane

on targetIsConnected(settingsProcess, targetName)
  tell application "System Events"
    tell settingsProcess
      set allItems to entire contents of window 1
      repeat with anItem in allItems
        try
          if role of anItem is "AXButton" then
            set itemDescription to description of anItem
            if itemDescription is "Airplay Video " & targetName then return true
          end if
        end try
      end repeat
    end tell
  end tell
  return false
end targetIsConnected

on menuItemIsChecked(menuItem)
  tell application "System Events"
    try
      set markCharacter to value of attribute "AXMenuItemMarkChar" of menuItem
      if markCharacter is missing value or markCharacter is "" then return false
      return true
    on error
      return missing value
    end try
  end tell
end menuItemIsChecked

on findElementByIdentifier(settingsProcess, wantedRole, wantedIdentifier)
  tell application "System Events"
    tell settingsProcess
      if not (exists window 1) then return missing value
      set allItems to entire contents of window 1
      repeat with anItem in allItems
        try
          if role of anItem is wantedRole and value of attribute "AXIdentifier" of anItem is wantedIdentifier then return anItem
        end try
      end repeat
    end tell
  end tell
  return missing value
end findElementByIdentifier

on waitForAirPlayMenuItem(settingsProcess, targetName, timeoutSeconds)
  repeat (timeoutSeconds * 5) times
    tell application "System Events"
      tell settingsProcess
        set allItems to entire contents
        repeat with anItem in allItems
          try
            if role of anItem is "AXMenuItem" and name of anItem is targetName then
              if value of attribute "AXIdentifier" of anItem is "airplayvideo" then return anItem
            end if
          end try
        end repeat
      end tell
    end tell
    delay 0.2
  end repeat
  return missing value
end waitForAirPlayMenuItem

APPLESCRIPT
