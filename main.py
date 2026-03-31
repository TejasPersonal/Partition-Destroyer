#!/usr/bin/env python3

import parted

import core


def main() -> int:
    if not core.is_super_user():
        return core.run_as_super_user()

    print(
        """
        WARNING!
        --------------------------------------------
         DO NOT PERFORM ANY DISK-RELATED OPERATIONS
         (E.G., CREATING OR DELETING PARTITIONS)
         OUTSIDE THE TOOL WHILE IT IS RUNNING.
        --------------------------------------------
        """
    )
    print()

    drive = core.request_drive()

    print()
    print(core.normalize_whitespace(drive.model), parted.devices[drive.type])

    try:
        disk = parted.newDisk(drive)
    except parted.DiskException:
        print("Drive has no partition table")
        print()
        commitment = (
            input("Create partition table ([Enter] Cancel / [gpt] / [mbr]): ")
            .strip()
            .lower()
        )
        print()
        if commitment == "gpt":
            disk = parted.freshDisk(drive, "gpt")
            disk.commit()
        elif commitment == "mbr":
            disk = parted.freshDisk(drive, "mbr")
            disk.commit()
        else:
            return 0

    print("Partitions:")
    core.configure_space(disk)

    region_list = core.get_region_list(disk)
    core.print_regions(region_list)

    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
    except KeyboardInterrupt:
        print()
        exit_code = 0
    exit(exit_code)
