#!/bin/bash
# Home Wizard Energy P1 Management Script
# Combines install, restart, and uninstall functionality in one script

# Get the script directory
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}"  )" &> /dev/null && pwd  )
DAEMON_NAME=${SCRIPT_DIR##*/}
SERVICE_NAME="dbus_homewizard_p1.py"

# Function to display usage information
show_usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  install    Install the service"
    echo "  restart    Restart the service"
    echo "  uninstall  Uninstall the service"
    echo "  status     Check service status"
    echo "  help       Show this help message"
    echo ""
    exit 1
}

# Function to install the service
install_service() {
    echo "Installing Home Wizard Energy P1 service..."

    # Set permissions for service scripts
    chmod a+x $SCRIPT_DIR/service/run
    chmod 755 $SCRIPT_DIR/service/run

    # Create sym-link to run script in daemon directory
    if [ -h /service/$DAEMON_NAME ]; then
        echo "Service link already exists, removing old link..."
        rm /service/$DAEMON_NAME
    fi

    ln -s $SCRIPT_DIR/service /service/$DAEMON_NAME
    echo "Service link created."

    # Add install-script to rc.local to be ready for firmware update
    filename=/data/rc.local
    if [ ! -f $filename ]; then
        touch $filename
        chmod 755 $filename
        echo "#!/bin/bash" >> $filename
        echo >> $filename
    fi

    grep -qxF "$SCRIPT_DIR/manage.sh install" $filename || echo "$SCRIPT_DIR/manage.sh install" >> $filename
    echo "Installation complete. Service should start automatically."

    # Check for Venus OS environment
    if [ -d /opt/victronenergy/dbus-systemcalc-py/ext/velib_python ]; then
        echo "Venus OS detected, using system velib_python module."

        # Create symlinks to the system velib_python modules
        mkdir -p $SCRIPT_DIR/dbus-systemcalc-py/ext
        ln -sf /opt/victronenergy/dbus-systemcalc-py/ext/velib_python $SCRIPT_DIR/dbus-systemcalc-py/ext/
        echo "Created symlink to system velib_python module."
    else
        # Not on Venus OS, try to initialize git submodules
        if [ ! -f $SCRIPT_DIR/dbus-systemcalc-py/ext/velib_python/vedbus.py ]; then
            echo "Initializing git submodules..."

            # Check if git is available
            if command -v git &> /dev/null; then
                cd $SCRIPT_DIR
                git submodule update --init --recursive
            else
                echo "WARNING: git not found. Cannot initialize submodules."
                echo "Please manually ensure the required modules are available."
            fi
        fi
    fi
}

# Function to restart the service
restart_service() {
    echo "Restarting Home Wizard Energy P1 service..."

    # Kill any existing processes
    pkill -f "python3 $SCRIPT_DIR/$SERVICE_NAME" || echo "No running service found to kill."

    # Wait a moment
    sleep 1

    # Verify the service is running
    check_status
}

# Function to uninstall the service
uninstall_service() {
    echo "Uninstalling Home Wizard Energy P1 service..."

    # Remove service link
    if [ -h /service/$DAEMON_NAME ]; then
        rm /service/$DAEMON_NAME
        echo "Service link removed."
    else
        echo "Service link not found, already uninstalled?"
    fi

    # Kill any running processes
    pkill -f "python3 $SCRIPT_DIR/$SERVICE_NAME" || echo "No running service found."
    pkill -f "supervise $DAEMON_NAME" || echo "No supervise process found."

    # Disable service script
    chmod a-x $SCRIPT_DIR/service/run
    echo "Service script disabled."

    # Remove from rc.local
    if [ -f /data/rc.local ]; then
        sed -i "\#$SCRIPT_DIR/manage.sh install#d" /data/rc.local
        echo "Removed from rc.local startup script."
    fi

    echo "Uninstallation complete."
}

# Function to check service status
check_status() {
    echo "Checking Home Wizard Energy P1 service status..."

    # Check if service link exists
    if [ -h /service/$DAEMON_NAME ]; then
        echo "Service is installed."
    else
        echo "Service is not installed."
    fi

    # Check if process is running
    if pgrep -f "python3 $SCRIPT_DIR/$SERVICE_NAME" > /dev/null; then
        echo "Service is running."
        pid=$(pgrep -f "python3 $SCRIPT_DIR/$SERVICE_NAME")
        echo "Process ID: $pid"
    else
        echo "Service is not running."
    fi
}

# Main script logic
case "$1" in
    install)
        install_service
        ;;
    restart)
        restart_service
        ;;
    uninstall)
        uninstall_service
        ;;
    status)
        check_status
        ;;
    help|--help|-h)
        show_usage
        ;;
    *)
        if [ -z "$1" ]; then
            show_usage
        else
            echo "Unknown command: $1"
            show_usage
        fi
        ;;
esac

exit 0