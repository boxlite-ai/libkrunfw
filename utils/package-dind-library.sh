#!/usr/bin/env bash
# Package a verified DinD image behind libkrun's ordinary firmware ABI.
set -euo pipefail
if [[ $# != 3 ]]; then
    echo "usage: $0 KERNEL_SOURCES KERNEL_IMAGE OUTPUT_DIR" >&2
    exit 2
fi
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
sources=$(realpath "$1")
image=$(realpath "$2")
python=${PYTHON:-python3}
read -r -a compiler <<< "${CC:-cc}"
[[ $(uname -s) == Linux ]] || { echo 'Linux host required' >&2; exit 1; }
arch=$(uname -m)
case "$arch" in
    x86_64) format=vmlinux; option=X86_64 ;;
    aarch64) format=Image; option=ARM64 ;;
    *) echo "unsupported native architecture: $arch" >&2; exit 1 ;;
esac
grep -qx "CONFIG_$option=y" "$sources/.config"
bash "$root/utils/check-dind-kernel.sh" "$sources" "$image"
abi=$(sed -n 's/^ABI_VERSION = //p' "$root/Makefile")
version=$(sed -n 's/^FULL_VERSION = //p' "$root/Makefile")
[[ $abi =~ ^[0-9]+$ && $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]
epoch=${SOURCE_DATE_EPOCH:-0}
[[ $epoch =~ ^[0-9]+$ ]] || { echo 'invalid SOURCE_DATE_EPOCH' >&2; exit 1; }
mkdir -p "$3"
output=$(realpath "$3")
work=$(mktemp -d "$output/.package-dind.XXXXXX")
trap 'rm -rf "$work"' EXIT
package="$work/package"
metadata="$package/share/doc/libkrunfw-dind"
mkdir -p "$package/lib64" "$metadata"
chmod 755 "$package" "$package/lib64" "$package/share" "$package/share/doc" "$metadata"
library="libkrunfw.so.$version"
"$python" "$root/bin2cbundle.py" --os Linux -t "$format" "$image" "$work/kernel.c"
"${compiler[@]}" -fPIC -shared -nostdlib -DABI_VERSION="$abi" \
    -Wl,-soname,"libkrunfw.so.$abi" -o "$package/lib64/$library" "$work/kernel.c"
ln -s "$library" "$package/lib64/libkrunfw.so.$abi"
ln -s "libkrunfw.so.$abi" "$package/lib64/libkrunfw.so"
"$python" "$root/utils/check_dind_library.py" "$image" "$package/lib64/$library" "$abi" \
    > "$metadata/manifest.json"
cp "$sources/.config" "$metadata/kernel.config"
cp "$root"/LICENSE-* "$metadata/"
chmod 755 "$package/lib64/$library"
chmod 644 "$metadata"/*
archive="libkrunfw-dind-$arch.tgz"
tar --sort=name --mtime="@$epoch" --owner=0 --group=0 --numeric-owner \
    --format=gnu -C "$package" -cf - lib64 share | gzip -n > "$work/$archive"
# Check the extracted bytes and symlinks that consumers will actually receive.
mkdir "$work/extracted"
tar -xzf "$work/$archive" -C "$work/extracted"
"$python" "$root/utils/check_dind_library.py" "$image" \
    "$work/extracted/lib64/libkrunfw.so.$abi" "$abi"
(cd "$work" && sha256sum "$archive" > "$archive.sha256")
mv "$work/$archive" "$work/$archive.sha256" "$output/"
echo "DinD firmware package: $output/$archive"
