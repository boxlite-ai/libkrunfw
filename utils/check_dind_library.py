"""Verify the kernel exposed by a native libkrunfw library against its input."""

import argparse
import ctypes
import hashlib
import json
import platform
from pathlib import Path

from elftools.elf.elffile import ELFFile


def check(image, library, abi):
    arch = platform.machine()
    machines = {"x86_64": "EM_X86_64", "aarch64": "EM_AARCH64"}
    if arch not in machines:
        raise ValueError(f"unsupported native architecture: {arch}")
    with library.open("rb") as stream:
        elf = ELFFile(stream)
        if elf["e_machine"] != machines[arch]:
            raise ValueError("library architecture does not match the host")
        dynamic = elf.get_section_by_name(".dynamic")
        sonames = (
            []
            if dynamic is None
            else [tag.soname for tag in dynamic.iter_tags("DT_SONAME")]
        )
        if sonames != [f"libkrunfw.so.{abi}"]:
            raise ValueError(f"unexpected SONAME: {sonames}")

    if arch == "x86_64":
        with image.open("rb") as stream:
            elf = ELFFile(stream)
            if elf["e_machine"] != machines[arch]:
                raise ValueError("kernel architecture does not match the host")
            segments = sorted(
                (s for s in elf.iter_segments() if s["p_type"] == "PT_LOAD"),
                key=lambda s: s["p_paddr"],
            )
            load = segments[0]["p_vaddr"] & 0xFFFFFFF
            entry = elf["e_entry"]
            end = max(s["p_paddr"] + s["p_filesz"] for s in segments)
            payload = bytearray(end - load)
            for segment in segments:
                offset = segment["p_paddr"] - load
                payload[offset : offset + segment["p_filesz"]] = segment.data()
    else:
        payload = bytearray(image.read_bytes())
        if payload[56:60] != b"ARM\x64":
            raise ValueError("kernel is not an arm64 Image")
        load = entry = 0x80000000
    payload.extend(b"\0" * (-len(payload) % 65536))

    firmware = ctypes.CDLL(str(library.resolve()))
    firmware.krunfw_get_version.restype = ctypes.c_int
    if firmware.krunfw_get_version() != abi:
        raise ValueError("firmware ABI mismatch")
    firmware.krunfw_get_kernel.argtypes = [ctypes.POINTER(ctypes.c_size_t)] * 3
    firmware.krunfw_get_kernel.restype = ctypes.c_void_p
    actual_load, actual_entry, size = (ctypes.c_size_t() for _ in range(3))
    pointer = firmware.krunfw_get_kernel(
        ctypes.byref(actual_load), ctypes.byref(actual_entry), ctypes.byref(size)
    )
    if (actual_load.value, actual_entry.value, size.value) != (
        load,
        entry,
        len(payload),
    ):
        raise ValueError("kernel load address, entry address or size mismatch")
    if not pointer or pointer % 65536:
        raise ValueError("kernel bundle must be aligned to 64 KiB")
    if ctypes.string_at(pointer, size.value) != payload:
        raise ValueError("bundled kernel bytes differ from the input image")
    return {
        "architecture": arch,
        "abi_version": abi,
        "kernel_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
        "library_sha256": hashlib.sha256(library.read_bytes()).hexdigest(),
        "load_address": hex(load),
        "entry_address": hex(entry),
        "bundle_size": size.value,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("library", type=Path)
    parser.add_argument("abi", type=int)
    args = parser.parse_args()
    print(json.dumps(check(args.image, args.library, args.abi), indent=2))
