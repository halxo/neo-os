"""Graphical GTK3 Installer Wizard for NeoOS Gentoo OpenRC (with CLI fallback)."""
from __future__ import annotations

import argparse
import sys
import threading
from typing import List, Optional

from .backend import GentooInstaller, InstallConfig
from .desktops import DesktopOption, load_desktops
from .hardware import HardwareProfile, probe_hardware


def run_cli(args: argparse.Namespace) -> int:
    hw = probe_hardware()
    cfg = InstallConfig(
        target_disk=args.disk or (hw.disks[0].path if hw.disks else "/dev/sda"),
        filesystem=args.filesystem,
        enable_swap=not args.no_swap,
        install_mode=args.mode,
        desktop_id=args.desktop,
        hostname=args.hostname,
        username=args.username,
        user_password=args.password,
        root_password=args.password,
        timezone=args.timezone,
        dry_run=args.dry_run,
    )
    installer = GentooInstaller(cfg, hardware=hw)
    result = installer.run()
    print(f"\nInstall finished: {result}")
    return 0


def run_gui(dry_run: bool = False) -> int:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib, Gtk

    hw: HardwareProfile = probe_hardware()
    desktops: List[DesktopOption] = load_desktops()

    class NeoInstallerWindow(Gtk.Window):
        def __init__(self) -> None:
            super().__init__(title="NeoOS Installer (Gentoo + OpenRC)")
            self.set_default_size(860, 620)
            self.set_position(Gtk.WindowPosition.CENTER)
            self.set_border_width(14)

            self.vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            self.add(self.vbox)

            header = Gtk.Label()
            header.set_markup(
                "<span size='x-large' weight='bold'>NeoOS — Gentoo OpenRC Easy Installer</span>\n"
                "<span size='small'>Autocompiles a hardware-tailored Linux kernel for this machine</span>"
            )
            header.set_xalign(0)
            self.vbox.pack_start(header, False, False, 0)

            self.stack = Gtk.Stack()
            self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
            self.vbox.pack_start(self.stack, True, True, 0)

            self.pages = [
                ("welcome", self._build_welcome_page()),
                ("disk", self._build_disk_page()),
                ("mode", self._build_mode_page()),
                ("desktop", self._build_desktop_page()),
                ("user", self._build_user_page()),
                ("install", self._build_install_page()),
            ]
            for name, widget in self.pages:
                self.stack.add_named(widget, name)
            self.page_idx = 0

            nav = Gtk.Box(spacing=8)
            self.back_btn = Gtk.Button(label="Back")
            self.back_btn.connect("clicked", self._on_back)
            self.next_btn = Gtk.Button(label="Next")
            self.next_btn.get_style_context().add_class("suggested-action")
            self.next_btn.connect("clicked", self._on_next)
            nav.pack_start(self.back_btn, False, False, 0)
            nav.pack_end(self.next_btn, False, False, 0)
            self.vbox.pack_end(nav, False, False, 0)
            self._update_nav()

        def _build_welcome_page(self) -> Gtk.Widget:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            info = (
                f"<b>Detected Hardware Profile</b>\n"
                f"• CPU: {hw.cpu_model} ({hw.cpu_cores} threads, safe compile jobs: -j{hw.makeopts_jobs})\n"
                f"• Memory: {hw.ram_mb} MiB\n"
                f"• Firmware: {hw.firmware.upper()}\n"
                f"• GPU / Video Cards: {', '.join(hw.video_cards)}\n"
                f"• Virtualization: {hw.hypervisor}\n"
                f"• Loaded Kernel Modules: {len(hw.loaded_modules)} detected for localmodconfig\n\n"
                "NeoOS will install Gentoo Linux with <b>OpenRC</b>, autocompile a custom kernel "
                "tailored to this system (with automatic <code>gentoo-kernel</code> fallback), "
                "and configure your chosen desktop environment."
            )
            lbl = Gtk.Label()
            lbl.set_markup(info)
            lbl.set_line_wrap(True)
            lbl.set_xalign(0)
            box.pack_start(lbl, False, False, 10)
            return box

        def _build_disk_page(self) -> Gtk.Widget:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            box.pack_start(Gtk.Label(label="Select Target Disk (will be erased):", xalign=0), False, False, 0)
            self.disk_combo = Gtk.ComboBoxText()
            if hw.disks:
                for d in hw.disks:
                    self.disk_combo.append(d.path, f"{d.path} — {d.size_human} ({d.model})")
            else:
                self.disk_combo.append("/dev/sda", "/dev/sda (No disks detected — VirtualBox / dry-run)")
            self.disk_combo.set_active(0)
            box.pack_start(self.disk_combo, False, False, 0)

            box.pack_start(Gtk.Label(label="Root Filesystem:", xalign=0), False, False, 0)
            self.fs_combo = Gtk.ComboBoxText()
            self.fs_combo.append("ext4", "ext4 (Recommended — fast & reliable)")
            self.fs_combo.append("btrfs", "btrfs (Copy-on-write snapshots)")
            self.fs_combo.set_active(0)
            box.pack_start(self.fs_combo, False, False, 0)

            self.swap_check = Gtk.CheckButton(label="Create 4 GiB swap partition (recommended for compiling)")
            self.swap_check.set_active(True)
            box.pack_start(self.swap_check, False, False, 0)
            return box

        def _build_mode_page(self) -> Gtk.Widget:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            box.pack_start(
                Gtk.Label(label="Choose Package Installation Mode:", xalign=0), False, False, 0
            )
            self.mode_binpkg = Gtk.RadioButton.new_with_label_from_widget(
                None,
                "Precompiled (Gentoo Official Binhost) — Fast install; kernel is still autocompiled for your hardware",
            )
            self.mode_source = Gtk.RadioButton.new_with_label_from_widget(
                self.mode_binpkg,
                "Compile from Source (-march=native) — Pure Gentoo source build optimized for this CPU",
            )
            self.mode_binpkg.set_active(True)
            box.pack_start(self.mode_binpkg, False, False, 4)
            box.pack_start(self.mode_source, False, False, 4)
            return box

        def _build_desktop_page(self) -> Gtk.Widget:
            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            scroll.add(box)

            self.desktop_radios = {}
            group: Optional[Gtk.RadioButton] = None
            for opt in desktops:
                rb = Gtk.RadioButton.new_with_label_from_widget(
                    group, f"{opt.name} [{opt.category}] — {opt.description}"
                )
                if group is None:
                    group = rb
                    rb.set_active(True)
                self.desktop_radios[opt.id] = rb
                box.pack_start(rb, False, False, 2)
            return scroll

        def _build_user_page(self) -> Gtk.Widget:
            grid = Gtk.Grid(column_spacing=12, row_spacing=10)
            self.hostname_entry = Gtk.Entry(text="neoos")
            self.user_entry = Gtk.Entry(text="neo")
            self.pass_entry = Gtk.Entry(text="neo")
            self.pass_entry.set_visibility(False)
            self.tz_entry = Gtk.Entry(text="UTC")

            fields = [
                ("Hostname:", self.hostname_entry),
                ("Username:", self.user_entry),
                ("Password (user & root):", self.pass_entry),
                ("Timezone (e.g. America/Los_Angeles):", self.tz_entry),
            ]
            for row, (label, entry) in enumerate(fields):
                grid.attach(Gtk.Label(label=label, xalign=0), 0, row, 1, 1)
                grid.attach(entry, 1, row, 1, 1)
            return grid

        def _build_install_page(self) -> Gtk.Widget:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            self.status_label = Gtk.Label(label="Ready to install NeoOS (Gentoo + OpenRC).", xalign=0)
            self.progress_bar = Gtk.ProgressBar()
            self.log_view = Gtk.TextView(editable=False, monospace=True)
            scroll = Gtk.ScrolledWindow()
            scroll.add(self.log_view)
            box.pack_start(self.status_label, False, False, 0)
            box.pack_start(self.progress_bar, False, False, 0)
            box.pack_start(scroll, True, True, 0)
            return box

        def _selected_desktop(self) -> str:
            for did, rb in self.desktop_radios.items():
                if rb.get_active():
                    return did
            return "kde"

        def _update_nav(self) -> None:
            self.back_btn.set_sensitive(self.page_idx > 0 and self.page_idx < len(self.pages) - 1)
            if self.page_idx == len(self.pages) - 2:
                self.next_btn.set_label("Install Now")
            elif self.page_idx == len(self.pages) - 1:
                self.next_btn.set_label("Close")
                self.next_btn.set_sensitive(False)
            else:
                self.next_btn.set_label("Next")
                self.next_btn.set_sensitive(True)

        def _on_back(self, _btn) -> None:
            if self.page_idx > 0:
                self.page_idx -= 1
                self.stack.set_visible_child_name(self.pages[self.page_idx][0])
                self._update_nav()

        def _on_next(self, _btn) -> None:
            if self.page_idx == len(self.pages) - 1:
                Gtk.main_quit()
                return
            self.page_idx += 1
            self.stack.set_visible_child_name(self.pages[self.page_idx][0])
            self._update_nav()
            if self.page_idx == len(self.pages) - 1:
                self._start_install()

        def _append_log(self, text: str) -> None:
            buf = self.log_view.get_buffer()
            buf.insert(buf.get_end_iter(), text + "\n")
            mark = buf.create_mark(None, buf.get_end_iter(), False)
            self.log_view.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)

        def _start_install(self) -> None:
            cfg = InstallConfig(
                target_disk=self.disk_combo.get_active_id() or "/dev/sda",
                filesystem=self.fs_combo.get_active_id() or "ext4",
                enable_swap=self.swap_check.get_active(),
                install_mode="binpkg" if self.mode_binpkg.get_active() else "source",
                desktop_id=self._selected_desktop(),
                hostname=self.hostname_entry.get_text().strip() or "neoos",
                username=self.user_entry.get_text().strip() or "neo",
                user_password=self.pass_entry.get_text() or "neo",
                root_password=self.pass_entry.get_text() or "neo",
                timezone=self.tz_entry.get_text().strip() or "UTC",
                dry_run=dry_run,
            )

            def worker() -> None:
                try:
                    installer = GentooInstaller(
                        cfg,
                        hardware=hw,
                        log_callback=lambda line: GLib.idle_add(self._append_log, line),
                        progress_callback=lambda pct, msg: GLib.idle_add(
                            self._set_progress, pct, msg
                        ),
                    )
                    installer.run()
                    GLib.idle_add(self._on_done, True, "Installation finished! You may now reboot.")
                except Exception as exc:
                    GLib.idle_add(self._append_log, f"\n[ERROR] {exc} (full log: /var/log/neo-installer.log)")
                    GLib.idle_add(self._on_done, False, f"Installation failed: {exc}")

            threading.Thread(target=worker, daemon=True).start()

        def _set_progress(self, pct: float, msg: str) -> None:
            self.progress_bar.set_fraction(pct)
            self.status_label.set_text(msg)

        def _on_done(self, ok: bool, msg: str) -> None:
            self.status_label.set_text(msg)
            self.next_btn.set_sensitive(True)
            if not ok:
                self.back_btn.set_sensitive(True)

    win = NeoInstallerWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="NeoOS Gentoo OpenRC Installer")
    parser.add_argument("--cli", action="store_true", help="Run non-interactive CLI mode")
    parser.add_argument("--dry-run", action="store_true", help="Simulate install without modifying disks")
    parser.add_argument("--disk", default=None, help="Target disk (e.g. /dev/sda)")
    parser.add_argument("--filesystem", choices=("ext4", "btrfs"), default="ext4")
    parser.add_argument("--no-swap", action="store_true")
    parser.add_argument("--mode", choices=("binpkg", "source"), default="binpkg")
    parser.add_argument("--desktop", default="kde")
    parser.add_argument("--hostname", default="neoos")
    parser.add_argument("--username", default="neo")
    parser.add_argument("--password", default="neo")
    parser.add_argument("--timezone", default="UTC")
    args = parser.parse_args(argv)

    if args.cli:
        return run_cli(args)
    try:
        return run_gui(dry_run=args.dry_run)
    except Exception as exc:
        print(f"GTK3 GUI unavailable ({exc}); falling back to CLI mode.", file=sys.stderr)
        return run_cli(args)


if __name__ == "__main__":
    raise SystemExit(main())
