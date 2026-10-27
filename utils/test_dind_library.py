"""Exercise the ABI checker using the real bundle generator and native libraries."""

import platform
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from check_dind_library import check

ROOT = Path(__file__).resolve().parents[1]


class DinDLibraryTest(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.directory = Path(self.scratch.name)
        self.image, self.bundle = self.make_image("original", 23)

    def run_command(self, *args):
        subprocess.run(args, check=True, capture_output=True)

    def make_image(self, name, marker):
        image = self.directory / name
        if platform.machine() == "x86_64":
            source = image.with_suffix(".c")
            source.write_text(f"const int marker = {marker}; void _start(void) {{}}\n")
            self.run_command(
                "cc",
                "-nostdlib",
                "-static",
                "-Wl,-Ttext-segment=0x100000",
                "-Wl,-e,_start",
                "-o",
                str(image),
                str(source),
            )
            kind = "vmlinux"
        else:
            image.write_bytes(b"\0" * 56 + b"ARM\x64" + bytes([marker]) * 20)
            kind = "Image"
        bundle = image.with_suffix(".bundle.c")
        self.run_command(
            sys.executable,
            str(ROOT / "bin2cbundle.py"),
            "--os",
            "Linux",
            "-t",
            kind,
            str(image),
            str(bundle),
        )
        return image, bundle

    def library(self, bundle=None, abi=5, soname="libkrunfw.so.5"):
        library = self.directory / "firmware.so"
        self.run_command(
            "cc",
            "-fPIC",
            "-shared",
            "-nostdlib",
            f"-DABI_VERSION={abi}",
            f"-Wl,-soname,{soname}",
            "-o",
            str(library),
            str(bundle or self.bundle),
        )
        return library

    def test_generated_bundle_matches_image(self):
        result = check(self.image, self.library(), 5)
        self.assertGreater(result["bundle_size"], 0)
        self.assertEqual(result["abi_version"], 5)

    def test_different_kernel_is_rejected(self):
        _, other_bundle = self.make_image("different", 71)
        with self.assertRaisesRegex(ValueError, "bytes differ"):
            check(self.image, self.library(bundle=other_bundle), 5)

    def test_wrong_abi_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "ABI mismatch"):
            check(self.image, self.library(abi=4), 5)

    def test_variant_soname_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "SONAME"):
            check(self.image, self.library(soname="libkrunfw-dind.so.5"), 5)

    def test_wrong_boot_address_is_rejected(self):
        self.bundle.write_text(
            self.bundle.read_text().replace("*entry_addr =", "*entry_addr = 1 +")
        )
        with self.assertRaisesRegex(ValueError, "address.*mismatch"):
            check(self.image, self.library(), 5)


if __name__ == "__main__":
    unittest.main()
