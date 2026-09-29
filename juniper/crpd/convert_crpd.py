#!/usr/bin/env python3
"""
vrnetlab / Juniper cRPD Image Builder
Converts EVE-NG/QEMU disk images (junipercrpd-*.tgz) or imports official
Juniper cRPD archives into standardized Docker images.
"""

import os
import sys
import shutil
import tempfile
import subprocess
import re

try:
    import pexpect
except ImportError:
    print("ERROR: 'pexpect' Python module is required.")
    print("Install it using: pip install pexpect (or pacman/apt install python-pexpect)")
    sys.exit(1)


REGISTRY = os.environ.get("REGISTRY", "vrnetlab/")
VENDOR = "juniper"
NAME = "crpd"


def is_native_docker_archive(filepath):
    """Check if archive is already a native Docker image tarball."""
    try:
        res = subprocess.run(
            ["tar", "-ztvf", filepath],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return "manifest.json" in res.stdout
    except Exception:
        return False


def extract_version(filename):
    """Extract version number from image filename."""
    m = re.search(r"(\d+\.\d+[A-Z0-9.\-]+)", filename)
    if m:
        ver = m.group(1).rstrip(".tgz").rstrip(".tar.gz")
        return ver
    return "latest"


def convert_eve_qcow2_to_docker(qcow2_path, version, image_name, final_tar_output=None):
    """
    Extract native Docker image layers from an Alpine Linux QEMU virtual disk (EVE-NG package).
    """
    tmp_dir = tempfile.mkdtemp(prefix="crpd_build_")
    try:
        print(f"--> Extracting boot partition from {os.path.basename(qcow2_path)}")
        subprocess.run(
            ["7z", "e", f"-o{tmp_dir}", qcow2_path, "0.img"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
        part0_img = os.path.join(tmp_dir, "0.img")

        print("--> Extracting kernel and initramfs")
        subprocess.run(
            ["7z", "e", f"-o{tmp_dir}", part0_img, "vmlinuz-virt", "initramfs-virt"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
        vmlinuz = os.path.join(tmp_dir, "vmlinuz-virt")
        initramfs = os.path.join(tmp_dir, "initramfs-virt")

        work_qcow2 = os.path.join(tmp_dir, "work.qcow2")
        print("--> Creating temporary copy of disk image")
        shutil.copyfile(qcow2_path, work_qcow2)

        print("--> Resetting root credentials in virtual disk")
        cmd_reset = [
            "qemu-system-x86_64", "-m", "1024", "-enable-kvm",
            "-drive", f"file={work_qcow2},if=virtio",
            "-kernel", vmlinuz, "-initrd", initramfs,
            "-append", "console=ttyS0", "-nographic", "-serial", "mon:stdio"
        ]
        child = pexpect.spawn(" ".join(cmd_reset), timeout=30)
        child.expect(r"/ #")
        child.sendline("mount /dev/vda3 /sysroot && sed -i 's/^root:[^:]*:/root::/' /sysroot/etc/shadow && umount /sysroot && poweroff -f")
        child.expect(pexpect.EOF, timeout=15)
        child.close()

        export_raw = os.path.join(tmp_dir, "export.raw")
        with open(export_raw, "wb") as f:
            f.truncate(500 * 1024 * 1024)

        print("--> Booting virtual machine to extract Docker layers")
        cmd_export = [
            "qemu-system-x86_64", "-m", "2048", "-enable-kvm",
            "-drive", f"file={work_qcow2},if=virtio",
            "-drive", f"file={export_raw},format=raw,if=virtio",
            "-nographic", "-serial", "mon:stdio"
        ]
        child = pexpect.spawn(" ".join(cmd_export), timeout=60)
        PROMPT = r"crpd:[^#]*#"

        child.expect(r"login:")
        child.sendline("root")
        child.expect(PROMPT)

        child.sendline("stty -echo")
        child.expect(PROMPT)

        target_tag = f"{image_name}:{version}"
        child.sendline(f"docker tag crpd-custom:latest {target_tag}")
        child.expect(PROMPT)

        print("--> Streaming Docker image layers to host...")
        child.sendline(f"docker save {target_tag} | gzip > /dev/vdb && sync && echo __EXPORT_FINISHED__")
        child.expect(r"__EXPORT_FINISHED__", timeout=180)
        child.expect(PROMPT, timeout=15)

        child.sendline("poweroff")
        try:
            child.expect(pexpect.EOF, timeout=10)
        except Exception:
            pass
        child.close(force=True)

        print("--> Loading Docker image into Docker daemon")
        p1 = subprocess.Popen(["gzip", "-dc", export_raw], stdout=subprocess.PIPE)
        subprocess.run(["docker", "load"], stdin=p1.stdout, check=True)
        p1.stdout.close()
        p1.wait()

        if final_tar_output:
            print(f"--> Saving standalone archive: {os.path.basename(final_tar_output)}")
            with open(final_tar_output, "wb") as out_f:
                p_cat = subprocess.Popen(["gzip", "-dc", export_raw], stdout=subprocess.PIPE)
                subprocess.run(["gzip", "-c"], stdin=p_cat.stdout, stdout=out_f, check=True)
                p_cat.stdout.close()
                p_cat.wait()

        print(f"--> Successfully built {target_tag}")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main():
    if len(sys.argv) < 2:
        candidates = [
            f for f in os.listdir(".")
            if f.endswith((".tgz", ".tar.gz", ".qcow2")) and not f.endswith(".docker.tar.gz")
        ]
        if not candidates:
            print("Usage: make (or python3 convert_crpd.py <image-file>)")
            sys.exit(1)
        archive_path = candidates[0]
    else:
        archive_path = sys.argv[1]

    if not os.path.exists(archive_path):
        print(f"ERROR: Image file not found: {archive_path}")
        sys.exit(1)

    version = extract_version(archive_path)
    img_repository = f"{REGISTRY}{VENDOR}_{NAME}"

    print(f"Building docker image using {archive_path} as {img_repository}:{version}")

    # Official Docker image format
    if archive_path.endswith((".tgz", ".tar.gz")) and is_native_docker_archive(archive_path):
        print(f"--> Detected native Docker archive: {archive_path}")
        print("--> Loading into Docker daemon")
        subprocess.run(["docker", "load", "-i", archive_path], check=True)
        # Re-tag to standard vrnetlab naming and remove other alias if desired
        subprocess.run(["docker", "tag", f"crpd:{version}", f"{img_repository}:{version}"], check=False)
        print(f"--> Successfully built {img_repository}:{version}")
        return

    # EVE-NG tgz archive format (contains virtioa.qcow2)
    if archive_path.endswith((".tgz", ".tar.gz")):
        tmp_extract = tempfile.mkdtemp(prefix="crpd_tar_")
        try:
            print(f"--> Extracting archive {archive_path}")
            subprocess.run(["tar", "-zxf", archive_path, "-C", tmp_extract], check=True)
            qcow2_file = None
            for root, _, files in os.walk(tmp_extract):
                for f in files:
                    if f.endswith(".qcow2"):
                        qcow2_file = os.path.join(root, f)
                        break
                if qcow2_file:
                    break
            if not qcow2_file:
                print("ERROR: No .qcow2 disk image found inside archive.")
                sys.exit(1)

            out_archive = os.path.abspath(f"crpd-{version}.docker.tar.gz")
            convert_eve_qcow2_to_docker(qcow2_file, version, img_repository, final_tar_output=out_archive)
        finally:
            shutil.rmtree(tmp_extract, ignore_errors=True)
    elif archive_path.endswith(".qcow2"):
        out_archive = os.path.abspath(f"crpd-{version}.docker.tar.gz")
        convert_eve_qcow2_to_docker(archive_path, version, img_repository, final_tar_output=out_archive)
    else:
        print(f"ERROR: Unsupported image format: {archive_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
