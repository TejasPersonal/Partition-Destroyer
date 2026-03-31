import os
import re
import socket
import subprocess
import sys
from typing import TypeVar

import parted

T = TypeVar("T")

# To get updates made to a disk not done by the script need to be fetched by parted.newDisk(drive)
# or parted.newDisk(disk.device)


def is_super_user():
    return os.geteuid() == 0


def run_as_super_user() -> int:
    result = subprocess.run(["sudo", sys.executable] + sys.argv)
    return result.returncode


def is_online() -> bool:
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=3)
        return True
    except OSError:
        return False


def normalize_whitespace(model: str) -> str:
    return re.sub(r"\s+", " ", model).strip()


def user_list_selection(array: list[T], what: str) -> T:
    print()
    while True:
        try:
            selection = int(input(f"[Number] {what}: "))
            if not 0 <= selection < len(array):
                print()
                print("ERROR: Index out of range")
                print()
                continue
            return array[selection]
        except ValueError:
            print()
            print("ERROR: Invalid input! Please enter a natural number")
            print()
            continue


def request_drive() -> parted.Device:
    drive_list: list[parted.Device] = [
        drive for drive in parted.getAllDevices() if drive.type != parted.DEVICE_UNKNOWN
    ]

    for index, drive in enumerate(drive_list):
        print(
            f"{index}. {normalize_whitespace(drive.model)}",
            f"    {parted.devices[drive.type]}",
            f"    {drive.getSize('GB'):.2f}GiB",
            sep="\n",
            end="\n\n",
        )

    return user_list_selection(drive_list, "Drive")


def get_region_list(disk: parted.Disk) -> list[parted.Partition]:
    partition_list: list[parted.Partition] = list(disk.partitions)
    free_partition_list: list[parted.Partition] = disk.getFreeSpacePartitions()

    region_list: list[parted.Partition] = partition_list + free_partition_list
    region_list.sort(key=lambda region: region.geometry.start)

    return region_list


def print_regions(region_list: list[parted.Partition]):
    for index, region in enumerate(region_list):
        if region.type == parted.PARTITION_FREESPACE:
            print(f"{index}. {region.getSize('GB'):.3f} GiB FREE SPACE")
            continue

        file_system = getattr(region.fileSystem, "type", "unknown")

        print(f"{index}. {region.getSize('GB'):.2f} GiB {file_system}")


def get_mount_path_list(partition: parted.Partition) -> list[str] | None:
    partition_path = f"/dev/{partition.getDeviceNodeName()}"
    result = subprocess.run(
        ["findmnt", "-n", "-o", "TARGET", partition_path],
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines() if result.returncode == 0 else None


def recursive_unmount(mount_path: str):
    subprocess.run(
        ["umount", "-R", mount_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def configure_space(disk: parted.Disk):
    while True:
        print()

        region_list = get_region_list(disk)
        print_regions(region_list)

        partition = user_list_selection(region_list, "Delete Partition")

        print()

        if partition.type == parted.PARTITION_FREESPACE:
            print("ERROR: Cannot delete free space")
            continue

        # partition.busy is a dynamic property
        if partition.busy:
            mount_path_list = get_mount_path_list(partition)
            if mount_path_list is None:
                print("ERROR: Partition is busy")
                continue
            mount_paths = ", ".join(mount_path_list)
            print(f"Partition is busy and mounted at {mount_paths}")
            print()

            should_unmount = input("[Enter] Continue / [y] Unmount: ").strip() == "y"
            if not should_unmount:
                continue

            for mount_path in mount_path_list:
                recursive_unmount(mount_path)

            print()

            if partition.busy:
                print("ERROR: Partition is still busy")
                continue

            print(f"Partition was unmounted from {mount_paths}")
            print()

        commitment = input(
            "Are you sure you want to delete the partition? ([Enter] Cancel / [y] Confirm): "
        ).strip()

        if commitment == "y":
            disk.deletePartition(partition)
            disk.commit()
            print()
            print("Partition was deleted")
