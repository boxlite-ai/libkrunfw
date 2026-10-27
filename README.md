# libkrunfw

```libkrunfw``` is a library bundling a Linux kernel in a dynamic library in a way that can be easily consumed by [libkrun](https://github.com/containers/libkrun).

By having the kernel bundled in a dynamic library, ```libkrun``` can leave to the linker the work of mapping the sections into the process, and then directly inject those mappings into the guest without any kind of additional work nor processing.

## Building

### Linux (generic variant)

#### Requirements
* The toolchain your distribution needs to build a Linux kernel.
* Python 3
* ```pyelftools``` (package ```python3-pyelftools``` in Fedora and Ubuntu)

#### Building and installing the library
```
make
sudo make install
```

### Linux (DinD and Docker Swarm variant)

The generic kernel is intentionally lean. The DinD patch adds built-in bridge,
nftables, storage and namespace support, plus **VXLAN** for Swarm overlay networks
and **IPVS** (TCP/UDP, round-robin, connection tracking) for VIPs and ingress.
It also enables the IPVS/u32 xtables matches used through `iptables-nft`.
All required features are `=y`: these guests do not ship a loadable module tree.
Legacy iptables backends remain disabled.

Build from a fresh checkout on Linux x86_64 or aarch64, with the requirements
above. If reusing a build directory after changing the variant or configuration,
run `make VARIANT=-dind clean` first; keep `tarballs/` to reuse downloads.
The upstream Makefile does not track configuration changes in an existing
kernel source tree.

```sh
arch=$(uname -m)
case "$arch" in
  x86_64) image=vmlinux ;;
  aarch64) image=arch/arm64/boot/Image ;;
  *) echo "unsupported DinD architecture: $arch" >&2; exit 1 ;;
esac
sources=$(sed -n 's/^KERNEL_VERSION = //p' Makefile)
cp "config-libkrunfw_$arch" config-libkrunfw-dind_x86_64
git apply --check config-patches/0001-dind-kernel-config.patch
git apply config-patches/0001-dind-kernel-config.patch
if [ "$arch" != x86_64 ]; then
  mv config-libkrunfw-dind_x86_64 "config-libkrunfw-dind_$arch"
fi
make VARIANT=-dind "$sources/$image"
bin="libkrunfw-kernel-dind-$arch.bin"
cp "$sources/$image" "$bin"
utils/check-dind-kernel.sh "$sources" "$bin"
cp "$sources/.config" "$bin.config"
sha256sum "$bin" > "$bin.sha256"
sha256sum "$bin.config" > "$bin.config.sha256"
```

The x86_64 binary is ELF; aarch64 is a raw `Image`. For a shared-library consumer,
`make VARIANT=-dind` bundles the same kernel as `libkrunfw-dind.so.5.4.0`.
Select this artifact explicitly in the VMM and restart the guests. An existing
generic library or an already running guest does not acquire the new features.

For consumers that load the standard `libkrunfw.so.5` name, package the verified
binary from the commands above:

```sh
make -f utils/Makefile test-dind-library
make -f utils/Makefile package-dind DIND_SOURCES="$sources" DIND_IMAGE="$bin"
(cd dist/dind && sha256sum -c "libkrunfw-dind-$arch.tgz.sha256")
```

Set `PYTHON=/path/to/python` when using a virtual environment with `pyelftools`.
Packaging is native Linux x86_64 or aarch64 and does not rebuild the kernel.
`DIND_OUTPUT` overrides the default `dist/dind` directory. The resulting
`libkrunfw-dind-<arch>.tgz` contains `lib64/libkrunfw.so.5.4.0`, the standard
`.so.5`/`.so` symlinks, and a `libkrunfw.so.5` SONAME. Its ABI remains 5.
The archive name identifies the DinD variant; consumers select its download URL
and **archive** SHA256 rather than the standalone kernel's SHA256.

Before packaging, the script checks the image's embedded configuration. It then
loads the generated library and compares its exported kernel bytes, padding,
load address, entry address and ABI against that exact image. It repeats this
check after extracting the archive. The effective config, licenses and an
artifact manifest with kernel/library hashes are under
`share/doc/libkrunfw-dind/`. Archive metadata is normalized; `SOURCE_DATE_EPOCH`
sets its timestamp (default zero).

The [DinD workflow](.github/workflows/publish-release-dind-bin.yml) builds both
architectures on relevant PRs and manual dispatch. Before upload, it checks
the resolved Kconfig values and extracts the configuration from the actual
binary, requiring an exact match. The binary, effective config, standard-ABI
firmware archive and their checksums are retained together. Only a manual run
with `release_tag` publishes release assets, after both architecture builds and
library checks pass. New DinD archives can be attached to an existing release
without replacing the generic firmware archives. Replacing an existing asset
requires updating consumers pinned to its previous checksum.

Build checks do not replace guest runtime verification. In a disposable guest
booted with the new artifact, install `iproute2` and `ipvsadm` and run:

```sh
uname -r
zcat /proc/config.gz | sha256sum  # compare with the artifact's .config
ip link add proof-vx type vxlan id 4210 dev eth0 dstport 4789
ip -d link show proof-vx
ip link del proof-vx
ipvsadm -A -t 10.255.254.1:9999 -s rr
ipvsadm -Ln
ipvsadm -D -t 10.255.254.1:9999
```

Then verify real Docker services: default VIP and DNSRR service-name requests,
cross-node overlay traffic, and ingress from a node without the backend task.
The VMM must provide guest capabilities/cgroups and reachable node addresses;
[Docker's Swarm network prerequisites](https://docs.docker.com/engine/swarm/swarm-tutorial/#open-protocols-and-ports-between-the-hosts)
still apply. This configuration covers ordinary unencrypted overlays; it does
not qualify encrypted overlays or supply the VMM's inter-node network.

See the [x86_64 runtime validation](docs/dind-swarm-validation.md) for artifact
hashes, the observed failure/pass comparison, and tested topology limits.

### Linux (SEV variant)

#### Requirements
* The toolchain your distribution needs to build a Linux kernel.
* Python 3
* ```pyelftools``` (package ```python3-pyelftools``` in Fedora and Ubuntu)

#### Building and installing the library
```
make SEV=1
sudo make SEV=1 install
```

### macOS

#### Requirements

Compiling a Linux kernel natively on macOS is not an easy feat. For this reason, the recommended way for building ```libkrunfw``` in this platform is by already having installed a binary version of [krunvm](https://github.com/containers/krunvm) and its dependencies ([libkrun](https://github.com/containers/libkrun), and ```libkrunfw``` itself), such as the one available in the [krunvm Homebrew repo](https://github.com/slp/homebrew-krun), and then executing the [build_on_krunvm.sh](build_on_krunvm.sh) script found in this repository.

This will create a lightweight Linux VM using ```krunvm``` with the current working directory mapped inside it, and build the kernel on it.

#### Building the library using krunvm
```
./build_on_krunvm.sh
make
```

By default, the build environment is based on a Fedora image. There is also a Debian variant which can be selected by setting the `BUILDER` environment variable.

```
BUILDER=debian ./build_on_krunvm.sh
```

In general, `./build_on_krunvm.sh` will always delegate to `./build_on_krunvm_${BUILDER}.sh` so additional environments can be added like this if needed.

### Windows (cross-compilation from Linux)

#### Requirements
* A Linux host with the toolchain needed to build a Linux kernel.
* The MinGW-w64 cross-compiler (`x86_64-w64-mingw32-gcc`), available as `mingw-w64-gcc` (Fedora) or `gcc-mingw-w64-x86-64` (Debian/Ubuntu).
* Python 3
* ```pyelftools``` (package ```python3-pyelftools``` in Fedora and Ubuntu)

#### How it works

The Windows build uses a dedicated kernel configuration (`config-libkrunfw-windows_x86_64`) that enables Hyper-V guest enlightenments (`CONFIG_HYPERV`, `CONFIG_HYPERV_TIMER`, `CONFIG_HYPERV_UTILS`), allowing the guest kernel to take advantage of the Windows Hypervisor Platform (WHP).

The kernel bundle is aligned to 4K pages (instead of 64K on Linux) to match the page granularity used by x86_64 Windows and WHP, avoiding alignment mismatches when the VMM maps the kernel into guest memory.

The resulting `libkrunfw.dll` is produced using the MinGW-w64 toolchain and can be consumed by the Windows build of [libkrun](https://github.com/containers/libkrun).

#### Building the library
```
make OS=Windows
```

This will:
1. Download and patch the kernel sources.
2. Build the kernel using the Windows-specific configuration.
3. Generate the C bundle with 4K page alignment.
4. Cross-compile `libkrunfw.dll` using `x86_64-w64-mingw32-gcc`.

## Known limitations

* To save memory, the embedded kernel is configured with ```CONFIG_NR_CPUS=8```, which limits the maximum number of supported CPUs to 8. If this kernel runs in a VM with more CPUs, only the first 8 will be initialized and used.

## License

This library bundles a Linux kernel but does not execute any code from it, acting as a mere storage format. As a consequence, this library does not constitute a derivative work of the Linux kernel. Thus, the following licenses apply:

* **Linux kernel**: GPL-2.0-only

* **Files contained in the ```patches``` directory**: GPL-2.0-only

* **Library code, including automatically-generated code**: LGPL-2.1-only

Therefore, distributions of this library in binary form are required to be accompanied by the source code of the Linux kernel bundled in the binary along with the code of the library itself, but other programs linking against this library are not required to be licensed under the GPL-2.0-only nor the LGPL-2.1-only licenses.
