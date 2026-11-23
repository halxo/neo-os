"""Hardware discovery for Gentoo make.conf tuning and kernel autocompilation."""
from __future__ import annotations

import dataclasses
import json
import os
import pathlib
import re
import shutil
import subprocess
from typing import List, Optional


@dataclasses.dataclass
class DiskInfo:
    path: str
    size_bytes: int
    size_human: str
    model: str


@dataclasses.dataclass
class HardwareProfile:
    cpu_model: str
    cpu_cores: int
    makeopts_jobs: int
    ram_mb: int
    cpu_flags_x86: List[str]
    video_cards: List[str]
    hypervisor: str  # "virtualbox", "vmware", "kvm", "hyperv", "none"
    firmware: str  # "uefi" or "bios"
    loaded_modules: List[str]
    disks: List[DiskInfo]


def _run(cmd: List[str]) -> str:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=10)
        return proc.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def detect_cpu_model() -> str:
    try:
        for line in pathlib.Path("/proc/cpuinfo").read_text(errors="ignore").splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return "Generic x86_64 CPU"


def detect_ram_mb() -> int:
    try:
        for line in pathlib.Path("/proc/meminfo").read_text(errors="ignore").splitlines():
            if line.startswith("MemTotal:"):
                kb = int(line.split()[1])
                return max(512, kb // 1024)
    except (OSError, ValueError, IndexError):
        pass
    return 4096


def compute_safe_makeopts_jobs(cpu_cores: int, ram_mb: int) -> int:
    """Cap parallel compile jobs to ~1 job per 2 GiB RAM to prevent OOM during C++ builds."""
    mem_cap = max(1, ram_mb // 2048)
    return max(1, min(cpu_cores, mem_cap))


def detect_cpu_flags_x86() -> List[str]:
    if shutil.which("cpuid2cpuflags"):
        out = _run(["cpuid2cpuflags"])
        if ":" in out:
            return out.split(":", 1)[1].strip().split()
    # Fallback: parse /proc/cpuinfo flags against common Gentoo CPU_FLAGS_X86 names
    known = {
        "aes", "avx", "avx2", "f16c", "fma3", "mmx", "mmxext", "pclmul",
        "popcnt", "rdrand", "sha", "sse", "sse2", "sse3", "sse4_1", "sse4_2",
        "ssse3", "avx512f", "avx512dq", "avx512cd", "avx512bw", "avx512vl",
    }
    try:
        text = pathlib.Path("/proc/cpuinfo").read_text(errors="ignore")
        match = re.search(r"^flags\s*:\s*(.+)$", text, re.MULTILINE)
        if match:
            raw = set(match.group(1).split())
            mapped = set()
            for flag in raw:
                if flag in known:
                    mapped.add(flag)
                elif flag == "pni":
                    mapped.add("sse3")
                elif flag == "fma":
                    mapped.add("fma3")
                elif flag == "pclmulqdq":
                    mapped.add("pclmul")
                elif flag == "sha_ni":
                    mapped.add("sha")
            return sorted(mapped)
    except OSError:
        pass
    return ["mmx", "mmxext", "sse", "sse2"]


def detect_hypervisor() -> str:
    dmi_paths = [
        "/sys/class/dmi/id/product_name",
        "/sys/class/dmi/id/sys_vendor",
        "/sys/class/dmi/id/board_vendor",
    ]
    dmi_text = ""
    for path in dmi_paths:
        try:
            dmi_text += " " + pathlib.Path(path).read_text(errors="ignore").lower()
        except OSError:
            pass
    if "virtualbox" in dmi_text or "innotek" in dmi_text:
        return "virtualbox"
    if "vmware" in dmi_text:
        return "vmware"
    if "qemu" in dmi_text or "kvm" in dmi_text or "bochs" in dmi_text:
        return "kvm"
    if "microsoft" in dmi_text and "virtual" in dmi_text:
        return "hyperv"
    return "none"


def detect_video_cards(hypervisor: Optional[str] = None) -> List[str]:
    cards: List[str] = []
    lspci = _run(["lspci", "-nn"]) if shutil.which("lspci") else ""
    lower = lspci.lower()
    if "virtualbox" in lower or "80ee:" in lower or hypervisor == "virtualbox":
        cards.extend(["virtualbox", "vmware", "fbdev", "vesa"])
    if "vmware" in lower or "15ad:" in lower:
        cards.append("vmware")
    if "virtio" in lower or "qxl" in lower or "1af4:" in lower:
        cards.extend(["virgl", "qxl", "fbdev"])
    if re.search(r"vga.*intel|3d.*intel|display.*intel", lower):
        cards.extend(["intel", "iris"])
    if re.search(r"vga.*(amd|ati|radeon)|display.*(amd|radeon)", lower):
        cards.extend(["amdgpu", "radeonsi"])
    if re.search(r"vga.*nvidia|3d.*nvidia", lower):
        cards.extend(["nouveau", "nvidia"])
    if not cards:
        cards = ["fbdev", "vesa", "intel", "amdgpu", "nouveau"]
    # Deduplicate while preserving order
    seen = set()
    return [c for c in cards if not (c in seen or seen.add(c))]


def detect_firmware() -> str:
    return "uefi" if pathlib.Path("/sys/firmware/efi").is_dir() else "bios"


def detect_loaded_modules() -> List[str]:
    modules: List[str] = []
    try:
        for line in pathlib.Path("/proc/modules").read_text(errors="ignore").splitlines():
            parts = line.split()
            if parts:
                modules.append(parts[0])
    except OSError:
        pass
    return sorted(set(modules))


def _human_size(num_bytes: int) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if num_bytes < 1024 or unit == "TiB":
            return f"{num_bytes:.1f} {unit}" if unit != "B" else f"{num_bytes} B"
        num_bytes /= 1024.0  # type: ignore[assignment]
    return f"{num_bytes} B"


def detect_disks() -> List[DiskInfo]:
    if not shutil.which("lsblk"):
        return []
    raw = _run(["lsblk", "-b", "-d", "-J", "-o", "NAME,SIZE,MODEL,TYPE,RM"])
    if not raw:
        return []
    disks: List[DiskInfo] = []
    try:
        data = json.loads(raw)
        for dev in data.get("blockdevices", []):
            if dev.get("type") != "disk":
                continue
            name = dev.get("name", "")
            if not name or name.startswith(("loop", "ram", "sr", "zram")):
                continue
            size = int(dev.get("size") or 0)
            model = (dev.get("model") or "Unknown Disk").strip()
            disks.append(DiskInfo(
                path=f"/dev/{name}",
                size_bytes=size,
                size_human=_human_size(size),
                model=model,
            ))
    except (ValueError, KeyError, TypeError):
        return []
    return disks


def probe_hardware() -> HardwareProfile:
    cores = os.cpu_count() or 2
    ram_mb = detect_ram_mb()
    hypervisor = detect_hypervisor()
    return HardwareProfile(
        cpu_model=detect_cpu_model(),
        cpu_cores=cores,
        makeopts_jobs=compute_safe_makeopts_jobs(cores, ram_mb),
        ram_mb=ram_mb,
        cpu_flags_x86=detect_cpu_flags_x86(),
        video_cards=detect_video_cards(hypervisor),
        hypervisor=hypervisor,
        firmware=detect_firmware(),
        loaded_modules=detect_loaded_modules(),
        disks=detect_disks(),
    )
