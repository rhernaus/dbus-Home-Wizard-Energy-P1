#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}"  )" &> /dev/null && pwd  )
DAEMON_NAME=${SCRIPT_DIR##*/}

rm /service/$DAEMON_NAME
kill $(pgrep -f "python $SCRIPT_DIR/dbus_home_wizard_energy_p1.py")
kill $(pgrep -f 'supervise $DAEMON_NAME')
chmod a-x $SCRIPT_DIR/service/run
$SCRIPT_DIR/restart.sh
