#!/usr/bin/env fish
# Idle detection script for desktop light and monitor control
# Checks every 30/60 seconds for mouse/keyboard activity
# If no activity for 1 hour, turns off light and monitor, then exits

set -l CHECK_INTERVAL 60
set -l IDLE_THRESHOLD 3600  # 1 hour in seconds
set -l LAST_ACTIVITY (date +%s)

function ts
    date '+%Y-%m-%d %H:%M:%S'
end

function get_idle_time
    # Get idle time in seconds from macOS IOKit HID system
    set -l idle_ns (ioreg -c IOHIDSystem | grep "\"HIDIdleTime\" =" | sed 's/.*= //' | head -1)
    if test -z "$idle_ns"
        echo 0
        return 0
    end
    # Convert nanoseconds to seconds
    math "ceil($idle_ns / 1000000000)"
end

function turn_off_light
    # set -x exports PATH as environment variable (fish syntax, PATH is a list)
    set -x PATH /opt/homebrew/bin /usr/local/bin $PATH
    uvx mijiaAPI set --dev_name "书房台灯" --prop_name "on" --value False
end

function turn_off_monitor
    pmset displaysleepnow
end

function cleanup_and_exit
    echo "["(ts)"] Activity timeout reached. Turning off light and monitor..."

    if turn_off_light
        echo "["(ts)"] ✓ Light turned off"
    else
        echo "["(ts)"] ✗ Failed to turn off light"
    end

    if turn_off_monitor
        echo "["(ts)"] ✓ Monitor turned off"
    else
        echo "["(ts)"] ✗ Failed to turn off monitor"
    end

    echo "["(ts)"] Exiting idle detection script"
    exit 0
end

# fish signal handling: --on-signal replaces bash's trap builtin
function __on_sigint --on-signal INT
    echo ""
    echo "["(ts)"] Interrupted — exiting without triggering actions"
    exit 0
end

echo "["(ts)"] Starting idle detection (check every $CHECK_INTERVAL seconds, timeout after $IDLE_THRESHOLD seconds)"

while true
    set -l current_time (date +%s)
    set -l idle_time (get_idle_time)
    set -l time_since_last_activity (math "$current_time - $LAST_ACTIVITY")

    # If idle time is small, activity was just detected — reset counter
    if test $idle_time -lt 5
        set LAST_ACTIVITY $current_time
        echo "["(ts)"] Activity detected (idle: $idle_time s, counter reset)"
    else
        if test $time_since_last_activity -ge $IDLE_THRESHOLD
            cleanup_and_exit
        else
            set -l remaining (math "$IDLE_THRESHOLD - $time_since_last_activity")
            echo "["(ts)"] No activity (idle: $idle_time s, $remaining s remaining before timeout)"
        end
    end

    sleep $CHECK_INTERVAL
end
