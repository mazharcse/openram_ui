import sys
import subprocess
import os

def main():
    if len(sys.argv) < 5:
        sys.stderr.write("Usage: python remote_downloader.py <source_path> <destination> <host> <user>\n")
        sys.exit(1)

    source_path = sys.argv[1]
    destination = sys.argv[2]
    host = sys.argv[3]
    user = sys.argv[4]
    ssh_key_path = os.path.join(os.path.dirname(__file__), "openram_key")

    if not os.path.exists(ssh_key_path):
        sys.stderr.write(f"Error: SSH key file not found: {ssh_key_path}\n")
        sys.exit(1)

    command = [
        "scp",
        "-r",
        "-i", ssh_key_path,
        f"{user}@{host}:{source_path}",
        destination
    ]

    try:
        sys.stdout.write(f"Starting download from {user}@{host}:{source_path} to {destination}\n")
        process = subprocess.run(command, check=True, capture_output=True, text=True)
        sys.stdout.write("Download complete.\n")
        if process.stdout:
            sys.stdout.write(process.stdout)
        if process.stderr:
            sys.stderr.write(process.stderr)
        sys.exit(0)
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"Error during download: {e.stderr}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
