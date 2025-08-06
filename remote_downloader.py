import os
import sys
import paramiko
import shutil

def download_remote_directory(sftp, remote_dir, local_dir):
    os.makedirs(local_dir, exist_ok=True)
    for item in sftp.listdir_attr(remote_dir):
        remote_item_path = os.path.join(remote_dir, item.filename)
        local_item_path = os.path.join(local_dir, item.filename)
        if item.st_mode & 0o40000: # Check if it is a directory
            download_remote_directory(sftp, remote_item_path, local_item_path)
        else:
            sys.stdout.write(f"Downloading {item.filename}...\n")
            sftp.get(remote_item_path, local_item_path)

def main():
    if len(sys.argv) < 5:
        sys.stderr.write("Usage: python remote_downloader.py <source_path> <destination> <host> <user>\n")
        sys.exit(1)

    source_path = sys.argv[1]
    destination = sys.argv[2]
    host = sys.argv[3]
    user = sys.argv[4]
    password = os.environ.get('SSH_PASSWORD')

    ssh = None
    sftp = None
    try:
        sys.stdout.write(f"Connecting to {user}@{host}...\n")
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, username=user, password=password, timeout=10)
        ssh = client
        sys.stdout.write("SSH connection established.\n")

        sftp = ssh.open_sftp()
        sys.stdout.write(f"Starting download from {source_path} to {destination}\n")
        
        os.makedirs(destination, exist_ok=True)
        for item in sftp.listdir_attr(source_path):
            remote_item_path = os.path.join(source_path, item.filename)
            local_item_path = os.path.join(destination, item.filename)
            if item.st_mode & 0o40000: # Check if it is a directory
                download_remote_directory(sftp, remote_item_path, local_item_path)
            else:
                sys.stdout.write(f"Downloading {item.filename}...\n")
                sftp.get(remote_item_path, local_item_path)

        sys.stdout.write(f"Download complete to {destination}\n")
        sys.exit(0)

    except Exception as e:
        sys.stderr.write(f"Error during download: {e}\n")
        sys.exit(1)
    finally:
        if sftp:
            sftp.close()
        if ssh:
            ssh.close()

if __name__ == "__main__":
    main()