# DinD / Swarm kernel validation (2026-10-22)

## Defect and fix

The DinD configuration at `8734a17` enables Docker bridge networking but omits
Swarm's IPVS and VXLAN support. A successful `docker swarm init` does not exercise
either data path. In the published x86_64 DinD kernel, actual VXLAN creation
returns `Unknown device type`; adding an IPVS TCP or UDP service returns
`Protocol not available`.

The fix extends the existing DinD patch with built-in IPVS TCP/UDP, round-robin
scheduling and conntrack integration, VXLAN, bridge VLAN filtering, conntrack
zones/netlink and the IPVS/u32 xtables matches. `IKCONFIG`/`IKCONFIG_PROC` make
the effective configuration inspectable in both the image and running guest.
The iptables-nft backend is preserved; legacy tables remain disabled.

The release workflow verifies the resolved configuration against the
configuration embedded in the binary it uploads. Both architectures must finish
before a manually requested release upload. PR builds have read-only repository
permissions and cannot publish releases.

## Built and booted artifacts

Linux x86_64/KVM, Linux 6.12.87, GCC 13.3.0 and Docker 27.5.1 were used locally.
The standard Makefile built `vmlinux` and bundled it through `bin2cbundle.py`.
The library's ABI is 5; every ELF load segment and the entry/load addresses were
compared with the library's exported kernel bundle.

| Artifact | SHA-256 |
| --- | --- |
| Original published DinD ELF | `d6686ee95c855e42fe0a1fd89442d3a6cefbc0c762b981a3b45aefd5b788fc75` |
| Fixed DinD ELF | `3c6cfc8015a1ba05cebabecd37967d665f2a0f81424b69f8d43d6e87feaceb92` |
| Fixed `libkrunfw-dind.so.5.4.0` | `efa3c0885534aac2ec317c92db6525d5fd471209df70b76f9afb261f30fa0c5f` |
| Effective/embedded/guest configuration | `222145c409003538787f50cb8171bb08625b14345ecf94dda1ea93ae98e8fd48` |

The fixed library was explicitly selected in fresh BoxLite guests. The copied
startup library hash and guest `/proc/config.gz` hash matched these artifacts.
Actual VXLAN creation/deletion and IPVS TCP/UDP service creation/listing/deletion
then succeeded. These results do not depend on `lsmod` or configuration alone.

## Behavioral checks

The native BoxLite SDK launched the guests; each ran its own `dockerd`, with no
host Docker socket mount. Service assertions reuse the
[BoxLite Swarm acceptance checks](https://github.com/boxlite-ai/boxlite/blob/2c9111e32603cc67a6e73ac7da3e5da6c3a7bbce/apps/infra-local/compose/swarm_acceptance.py).

| Check | Result |
| --- | --- |
| Docker info, pull, build and run with unique image content | PASS |
| Two-service Compose application, HTTP 200 and expected content | PASS |
| Swarm init, Ready/Active node status | PASS |
| Default VIP and separate DNSRR service-name HTTP requests | PASS |
| Ingress and separate host publication through BoxLite tunnels | PASS |
| `--network host`, including guest/container network namespace equality | PASS |
| Two guests: constrained backend/client on each node, A→B and B→A in VIP and DNSRR modes | PASS: four directed requests |
| Ingress through A, with the sole backend task constrained to B | PASS |

Service inspections, DNS answers, task NodeIDs, VXLAN devices and nonzero IPVS
counters were retained. Internal service requests used no published ports and
clients had no HTTP proxy environment. A guest OpenVPN IP link transported the
two-node underlay over a BoxLite TCP tunnel; Docker still carried the service
traffic over its own overlay. Download proxy settings were limited to guest
package/image acquisition. All test Boxes were removed afterward.

## Regression and scope

- `utils/check-dind-kernel.sh` fails on the original resolved configurations for
  both architectures. The fixed x86_64 artifact passes; passing the old release
  binary with the new configuration is also rejected.
- The fixed aarch64 configuration passes the required built-in option checks
  after `olddefconfig`; native aarch64 compilation and boot were not run locally.
- `actionlint` and `bash -n` pass. See the [build commands](../README.md#linux-dind-and-docker-swarm-variant)
  for regenerating and checking artifacts.
- The two guests ran under one native SDK runtime on one physical Linux host.
  This is cross-guest kernel validation, not a rerun of distinct REST runners or
  different physical hosts. Encrypted overlays were not qualified.
- This change does not replace already published release assets. Publish the
  fixed revision under a new release tag, then update consumers' pinned hashes
  and restart their guests.

Local evidence includes `artifact-provenance.json`, `probe-released.json`,
`probe-fixed.json`, `libkrunfw-single-e671f251.json` and
`libkrunfw-two-native-guests-8f6df599.json`, with corresponding command logs.
Raw guest logs remain outside Git because Swarm setup can contain join tokens.
