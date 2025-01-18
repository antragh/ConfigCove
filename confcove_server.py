#!/usr/bin/env python3
import os
import logging
import json
import paramiko
from pathlib import Path

# Load machines' details
ASSETS_FILE = "./assets.json"
BACKUP_DIR = "/opt/ConfigCove_repo"
# TRACKED_FILE = "~/tracked_files.txt"  # ~ or $HOME

LOGLEVEL = logging.INFO
# LOGLEVEL = logging.DEBUG


class CustomFormatter(logging.Formatter):
    """Custom Formatter to add colors and different templates for DEBUG and INFO"""
    # Define log format templates
    # format_debug = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
    # format_info = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    # format_warn = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # format_debug = "%(levelname)-8s | %(message)s (%(filename)s:%(lineno)d)"
    format_debug = "%(asctime)s | %(message)s (%(module)s.%(funcName)s@%(lineno)d)"
    format_info  = "%(message)s"
    format_warn  = "%(levelname)-8s | %(filename)s:%(lineno)d | %(message)s"
    format_error = format_warn
    format_critical = format_error

    BLACK = "\033[30m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    LIGHT_RED = "\033[91m"
    ORANGE = "\033[38;5;214m"
    RESET = "\033[0m"

    FORMATS = {
        logging.DEBUG: BLACK + format_debug + RESET,
        logging.INFO: GREEN + format_info + RESET,
        logging.WARNING: YELLOW + format_warn + RESET,
        logging.ERROR: ORANGE + format_error + RESET,
        logging.CRITICAL: LIGHT_RED + format_critical + RESET
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def setup_logging():
    """Set up logging configuration with custom formatter."""
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    ch = logging.StreamHandler()
    ch.setLevel(LOGLEVEL)
    ch.setFormatter(CustomFormatter())

    logger.addHandler(ch)
    # setup_logging()


def connect_ssh(host, username, password=None, key_path=None):
    """Establish an SSH connection to a remote host or returns Mone object if fails."""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        if not password:  # password overrides authentication with default key_path
            key_path = os.path.expanduser(key_path)
            ssh.connect(host, username=username, key_filename=key_path, timeout=10)  # Timeout in seconds
        else:
            ssh.connect(host, username=username, password=password, timeout=10)  # Timeout in seconds
        logger.debug(f"Connected to {host}")
        return ssh
    except paramiko.AuthenticationException:
        logger.error(f"Authentication failed when connecting to {host}. Check your username/password or key file.")
    except paramiko.SSHException as ssh_exception:
        logger.error(f"SSH error occurred while connecting to {host}: {ssh_exception}")
    except TimeoutError:
        logger.error(f"Connection to {host} timed out. Ensure the host is reachable.")
    except Exception as e:
        logger.error(f"An unexpected error occurred while connecting to {host}: {e}")
    return None  # connect_ssh()


def list_remote_files(ssh_client, remote_path):
    """
    Lists files matching a given path on the remote system. Supports directories and wildcards.
    """
    # Check if the remote path is a directory
    stdin, stdout, stderr = ssh_client.exec_command(f'if [ -d "{remote_path}" ]; then echo "dir"; fi')
    if stdout.read().decode().strip() == "dir":
        # If it's a directory, list all files recursively
        stdin, stdout, stderr = ssh_client.exec_command(f'find "{remote_path}" -type f')
        files = stdout.read().decode().splitlines()
    else:
        # Handle wildcards or specific files
        stdin, stdout, stderr = ssh_client.exec_command(f'ls -d {remote_path}')
        files = stdout.read().decode().splitlines()

    return files  # lis


def download_files(ssh_client, remote_files, local_base_dir, remote_base_dir):
    """
    Downloads the specified remote files to the local directory, preserving structure.
    """
    sftp = ssh_client.open_sftp()
    for remote_file in remote_files:
        # Ensure that remote_base_dir is properly formatted (ends with '/')
        if remote_base_dir.endswith('/'):
            local_file = f"{local_base_dir}{remote_file}"
        else:
            local_file = os.path.join(local_base_dir, remote_file[1:])

        # Ensure that the local directory exists before downloading
        local_dir = os.path.dirname(local_file)
        if not os.path.exists(local_dir):
            os.makedirs(local_dir, exist_ok=True)

        try:
            sftp.get(remote_file, str(local_file))
            logger.debug(f"Downloaded {remote_file}")
        except FileNotFoundError as e:
            logger.error(f"Remote file {remote_file} not found: {e}")
        except PermissionError as e:
            logger.error(f"Permission denied while downloading {remote_file}: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred while downloading {remote_file}: {e}")
    sftp.close()
    # download_files()


def process_tracked_files(ssh_client, tracked_file_path, local_backup_dir):
    """
    Processes each entry in the tracked_files.txt and downloads the files.
    """
    stdin, stdout, stderr = ssh_client.exec_command(f'cat "{tracked_file_path}"')
    tracked_paths = stdout.read().decode().splitlines()

    for remote_path in tracked_paths:
        logger.info(f"Processing path: {remote_path}")
        remote_files = list_remote_files(ssh_client, remote_path)
        download_files(ssh_client, remote_files, local_backup_dir, remote_path)
    # process_tracked_files()


def get_tracked_file_path(ssh_client, tracked_file_path):
    """
    Expands the '~' and '$HOME' in the given path on the remote (client) machine.
    """
    # Replaces '~' with '$HOME' for the remote session
    if '~' in tracked_file_path:
        tracked_file_path = tracked_file_path.replace('~', '$HOME')

    if '$HOME' in tracked_file_path:
    # If the path contains '~' or '$HOME' expand accordingly
        stdin, stdout, stderr = ssh_client.exec_command('echo $HOME')
        home_dir = stdout.read().decode().strip()
        # Replace $HOME with the remote user's home directory
        expanded_path = tracked_file_path.replace('$HOME', home_dir)
    else:
        expanded_path = tracked_file_path

    return expanded_path  # get_tracked_file_path()


def backup_machine(machine, defaults, backup_dir):
    name = machine["name"]
    host = machine["host"]
    username = machine.get("username", defaults.get("username"))
    password = machine.get("password", defaults.get("password"))
    key_path = machine.get("key_path", defaults.get("key_path"))
    tracked_file_path = machine.get("tracked_file_path", defaults.get("tracked_file_path"))

    logger.info(f"\nBacking up: {name} ({host})")
    ssh = connect_ssh(host, username, password, key_path)
    if ssh is None:
        logger.error(f"Skipping backup for {host} due to connection failure.")
        return

    try:
        tracked_file_path = get_tracked_file_path(ssh, tracked_file_path)
        # logger.debug(f"Tracked file path: {tracked_file_path}")
        local_backup_dir = os.path.join(backup_dir, machine["name"])
        process_tracked_files(ssh, tracked_file_path, local_backup_dir)
    finally:
        ssh.close()
        logger.debug(f"Connection to {host} closed.")
    # backup_machine()


def main():
    try:
        with open(ASSETS_FILE, "r") as f:
            # assets = json.load(f)
            json_without_comments = ''.join(line for line in f if not line.strip().startswith('//'))
        assets = json.loads(json_without_comments)
    except FileNotFoundError:
        logger.critical(f"Configuration file {ASSETS_FILE} not found.")
        return

    defaults = assets.get("defaults", {})
    machines = assets.get("machines", [])
    if not machines:
        logger.critical("No machines found in the configuration file.")
        return
    for machine in machines:
        backup_machine(machine, defaults, BACKUP_DIR)

    # load_machines()


if __name__ == "__main__":
    global logger
    setup_logging()
    logger = logging.getLogger(__name__)
    logging.getLogger("paramiko").setLevel(logging.WARNING)
    main()
