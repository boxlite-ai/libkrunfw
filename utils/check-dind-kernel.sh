#!/usr/bin/env bash
# Check Kconfig's resolved values and the configuration in the shipped image.
set -euo pipefail

if [[ $# != 2 ]]; then
    echo "usage: $0 KERNEL_SOURCES KERNEL_IMAGE" >&2
    exit 2
fi
sources=$1
image=$2
config="$sources/.config"

# Guests have no module tree. =m is as unusable here as a missing option.
required=(
    NAMESPACES NET_NS PID_NS IPC_NS UTS_NS
    CGROUPS MEMCG CPUSETS CGROUP_BPF BPF_SYSCALL POSIX_MQUEUE KEYS
    OVERLAY_FS VETH BRIDGE BRIDGE_NETFILTER BRIDGE_VLAN_FILTERING VLAN_8021Q
    NETFILTER NETFILTER_ADVANCED NETFILTER_XTABLES
    NF_CONNTRACK NF_CONNTRACK_ZONES NF_CT_NETLINK NF_NAT
    NETFILTER_XT_MARK NETFILTER_XT_MATCH_ADDRTYPE NETFILTER_XT_MATCH_CONNTRACK
    NETFILTER_XT_MATCH_IPVS NETFILTER_XT_MATCH_U32
    NETFILTER_XT_TARGET_MASQUERADE NETFILTER_XT_TARGET_REDIRECT
    NF_TABLES NF_TABLES_INET NF_TABLES_IPV4 NF_TABLES_IPV6
    NFT_COMPAT NFT_CT NFT_MASQ NFT_NAT NFT_REDIR
    IP_VS IP_VS_PROTO_TCP IP_VS_PROTO_UDP IP_VS_RR IP_VS_NFCT
    VXLAN NET_UDP_TUNNEL IKCONFIG IKCONFIG_PROC
)
failed=0
for option in "${required[@]}"; do
    if ! grep -qx "CONFIG_$option=y" "$config"; then
        echo "CONFIG_$option is not built into the DinD kernel" >&2
        failed=1
    fi
done
[[ $failed == 0 ]] || exit 1

embedded=$(mktemp)
trap 'rm -f "$embedded"' EXIT
"$sources/scripts/extract-ikconfig" "$image" > "$embedded"
cmp "$config" "$embedded"
echo "PASS: DinD/Swarm features are built in; embedded config matches $config"
