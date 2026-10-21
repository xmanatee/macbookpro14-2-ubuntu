# Optional reference settings

These files were used on the physical reference machine. They are not installed by the minimal image build.

## Conservative CPU package power

For the reference i7-7567U only: verify `cat /sys/devices/virtual/dmi/id/product_name` is `MacBookPro14,2`; inspect `/sys/class/powercap/intel-rapl:0/name` and the two constraint names. The supplied rule additionally matches `package-0`, `long_term` and `short_term` before setting 23 W / 28 W. Record the current values and establish a cooling baseline first.

```sh
sudo install -m 0644 extras/99-macbook-t1-power.rules /etc/udev/rules.d/99-macbook-t1-power.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --action=change --subsystem-match=powercap --sysname-match=intel-rapl:0
```

Read the power limits back and measure a real sustained workload. This trades some peak performance for a lower heat budget; it does not certify the cooling system. To retire the policy, remove its rule, reload udev and reboot or deliberately restore your recorded limits. Removing the file alone does not undo limits already written to hardware.

## GNOME privacy

The three files under `desktop-privacy/` form a dconf local database and profile: location, technical/usage reports, recent files and application-usage history are disabled and locked; desktop idle sleep is disabled. The main image installs no desktop.

Before applying on a desktop installation, inspect its existing `/etc/dconf/profile/user` and local databases, and verify the relevant GNOME schemas/keys exist. Integrate the supplied entries into your existing profile instead of overwriting organization/user policy. Install the settings under `/etc/dconf/db/local.d/` with the locks under `local.d/locks/`, then run `sudo dconf update` and log out/in. These settings cover GNOME policy, not telemetry in arbitrary applications installed later.
