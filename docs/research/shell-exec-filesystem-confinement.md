# Filesystem confinement for `shell_exec`

Research note. Question: can the process spawned by the `shell_exec` tool be
structurally prevented from reading/writing outside the vault root,
independent of the UI approval gate? Investigated against primary sources
(man pages on the local machine, Apple documentation) plus live testing on
this machine (macOS 27.0, build 26A428, arm64, unprivileged user `coordt`,
uid 501).

## 1. `sandbox-exec` / Seatbelt profiles

**Status: officially deprecated, but functional and usable by an unsandboxed app.**

`man sandbox-exec` on this machine (macOS 27.0) reads:

```
NAME
     sandbox-exec – execute within a sandbox (DEPRECATED)
...
     The sandbox-exec command is DEPRECATED.  Developers who wish to sandbox
     an app should instead adopt the App Sandbox feature described in the App
     Sandbox Design Guide.
```

Same wording, same deprecation notice, appears in `man sandbox_init` (the C
API `sandbox_init()`/`sandbox_free_error()` that `sandbox-exec` itself wraps)
and in `man sandbox` (7). The deprecation notice has been present in Apple's
shipped man pages since at least the 2017 revision date printed at the
bottom of the page (`Mac OS X — March 9, 2017`) and is unchanged on this
current build, i.e. Apple has left it in "deprecated but shipping" limbo for
years rather than removing it. There is no public replacement API for
*ad hoc, caller-defined* filesystem confinement of an arbitrary child
process — the suggested replacement, App Sandbox, is a different mechanism
entirely (see below).

One concrete, version-specific regression found during testing: `man
sandbox_init` on this build states the legacy **named** profiles
(`kSBXProfileNoWrite`, `kSBXProfileNoInternet`, etc.) are hard-disabled as of
recent SDKs:

```
     These profiles must not be used when building against macOS SDK >= 27.0.
     Processes opting into them will be killed on attempt to do so.
```

This doesn't affect us — we're not using named profiles, we'd write a custom
`.sb` profile via `-f`/`-p` — but it's evidence Apple is actively tightening,
not just ignoring, this deprecated facility, and a future OS revision
disabling custom profiles entirely is a real (if unquantifiable) risk for a
long-lived app that depends on this for a security property.

### Does the caller need to be App-Sandboxed to use it?

No. Verified directly: `sandbox-exec` was invoked from an ordinary,
non-App-Sandboxed interactive shell process (`zsh`, uid 501, no sandbox
entitlements) and successfully placed a *child* process into a custom
Seatbelt profile:

```
$ codesign -dv --entitlements - /bin/zsh
... flags=0x0(none) ...        # no App Sandbox entitlement on the caller
$ sandbox-exec -f deny3.sb sh -c "echo ok > .../vault/w.txt"   # succeeds
$ sandbox-exec -f deny3.sb sh -c "echo pwned > .../outside/pwned.txt"
sh: .../outside/pwned.txt: Operation not permitted               # denied
```

`sandbox_init(2)`/`sandbox-exec(1)` puts the *current* (or exec'd child)
process into a sandbox unconditionally — it does not check whether the
calling process is itself inside App Sandbox. This matches `man sandbox` (7):
"The sandbox facility allows applications to voluntarily restrict their
access to operating system resources... New processes inherit the sandbox of
their parent." It's a one-way, self-imposed (or imposed-on-a-child)
restriction, unrelated to whether the *caller* came from the Mac App Store
sandbox. A PyInstaller app distributed outside the App Store, with no App
Sandbox entitlement, can call `sandbox-exec <profile> <command>` as a
subprocess and it works exactly as it would for any other unsandboxed
Terminal process — because that's what it is in this test.

### Can a profile scope file I/O to one directory tree?

Yes, confirmed by direct test. A default-deny profile that allows
`file-write*` only under the vault subpath enforces that boundary:

```
(version 1)
(deny default)
(allow process-exec)
(allow process-fork)
(allow file-read*)
(allow file-write*
  (subpath "/private/tmp/.../vault"))
(allow sysctl-read)
(allow mach-lookup)
(allow iokit-open)
```

Result:
- Write inside `vault/` → succeeds (exit 0, file created).
- Write outside `vault/` (a sibling `outside/` directory) → denied at the
  syscall level: `Operation not permitted`, exit 1, no file created.

This is the standard Seatbelt profile grammar documented (informally — Apple
never published a full `sandbox(7)` language reference; `bsd/sandbox` in the
open-source Darwin kernel sources and the Apple `sandbox` man page's `SEE
ALSO` are the closest primary sources) via `allow`/`deny` rules over
filters like `subpath`, `literal`, and `regex`. The mechanism is a kernel
(TrustedBSD MAC framework / Sandbox.kext) enforcement point, not an
app-level check — a compromised or malicious command running inside the
profile cannot `cd ..` or use an absolute path to escape it; the `open(2)`/
`write(2)` syscalls themselves are denied by the kernel.

### Gotcha found during testing: a naive default-deny profile silently aborts every child process

The first, narrower profile tried (allow only `process-exec`, `process-fork`,
and `file-write*`/`file-read*` on the vault subpath, nothing else) caused
**every** child process — including a plain `/bin/echo hi` with no file
access at all — to die on launch with `SIGABRT`, exit code 134, no stderr
output. The crash report (`~/Library/Logs/DiagnosticReports/echo-*.ips`)
showed the abort happening inside `dyld4` during process startup
(`dyld4::CacheFinder` / `ignition_halt` / `abort_with_reason`), i.e. dyld
itself was denied the reads it needs to map the shared library cache before
the target binary's `main()` ever ran. This is a well-known class of
footgun with Seatbelt: a workable profile needs a broad `(allow file-read*)`
(or explicit allows for the dyld shared cache, loader, and any dynamic
libraries the interpreter/shell needs) in addition to the write restriction
— the *write* boundary is what should be narrow to the vault, not
necessarily the read boundary, unless read-confinement is also a goal (in
which case every system path the shell, Python, or invoked tools dlopen/dyld
need must be allow-listed explicitly, which is a maintenance burden). Fails
closed (good for security) but silently and unhelpfully (bad for debugging
— no message printed to indicate *why* the command "did nothing").

### Notarization / entitlement gotchas

- No special entitlement is required to *call* `sandbox-exec` as a
  subprocess — confirmed above, ordinary unsandboxed processes can do it.
- `sandbox-exec` and the underlying `sandbox_init()` API are themselves
  deprecated; Apple could plausibly restrict, further neuter, or block
  custom profiles in a future release (the SDK 27 named-profile kill switch
  shows this isn't hypothetical), which notarization would not protect
  against — notarization checks code-signing/malware heuristics, not use of
  deprecated APIs, so today's `codesign`/`notarytool` pipeline is not
  expected to flag or block this.
- Shipping the `.sb` profile as a bundled resource (not generated from
  untrusted input at runtime) avoids any injection risk in profile
  construction; the profile path must resolve correctly relative to the
  PyInstaller onedir bundle's resource directory at runtime.
- No macOS entitlement exists to "harden" or "guarantee" this at the OS
  policy layer the way, e.g., Hardened Runtime entitlements do for other
  protections — this is a voluntary, self-applied restriction the app
  chooses to invoke; nothing forces `shell_exec` to always route through it,
  which is a code-review/architecture discipline requirement, not something
  the OS enforces on the app's behalf.

## 2. `chroot(2)` / `chroot(8)`

Confirmed via `man chroot` (macOS 27.0, dated July 20 2021 revision) and live
test. The `chroot(8)` utility man page does not itself state a privilege
requirement in the DESCRIPTION, but the live syscall does:

```
$ whoami; id -u
coordt
501
$ chroot /tmp/claude-501/sbxtest/vault /bin/echo hi
chroot: /tmp/claude-501/sbxtest/vault: Operation not permitted
```

`chroot(2)` requires `root` (superuser) privileges on macOS, same as on
BSD/Linux generally — an ordinary user process gets `EPERM`. This disqualifies
it outright for `shell_exec`: the app runs as the logged-in user with no
elevated privileges, and prompting for an admin password (`sudo`/
`AuthorizationExecuteWithPrivileges`-style escalation) on every tool call, or
even once at startup, to enable a chroot jail is a worse UX and a larger
attack surface than the problem it would solve — it would also mean the app
either runs a persistent privileged helper (its own large security
liability) or re-escalates per command. Not viable for a non-privileged
desktop app.

## 3. Container/namespace equivalents on macOS

macOS has **no OS-level equivalent to Linux namespaces** (mount, PID, user,
network namespaces) usable by an unprivileged regular process. This is a
Linux kernel feature (`unshare(2)`, `clone(2)` with `CLONE_NEWNS` et al.,
`/proc/<pid>/ns/*`) with no macOS (XNU) counterpart — XNU does not implement
namespaces, and tools that depend on them (`bubblewrap`, `firejail`,
`runc`/OCI-style containers) do not run on macOS at all; they are Linux-only
and there is nothing to port to, since the kernel primitive they wrap is
absent.

**Docker Desktop for Mac does not change this.** Docker on macOS runs a
lightweight Linux virtual machine (historically HyperKit-based, more
recently Apple's `Virtualization.framework`) and all containers run *inside
that Linux VM*, using genuine Linux namespaces/cgroups inside the VM guest —
not on the macOS host process directly. This is a fundamentally different
architecture from what `shell_exec` needs: it would mean shipping/managing a
Linux VM as a bundled dependency of the app just to sandbox a shell command,
which is enormous overhead (VM image, virtualization entitlement, boot time,
filesystem bind-mounting the vault into the guest) compared to Seatbelt,
and still would not be "native" confinement of a macOS process — it's
confinement of a process inside an emulated Linux kernel that happens to run
on the same physical machine.

**What macOS does have**, for completeness, that could be confused with
containers but doesn't apply here:
- **App Sandbox** — an entitlement-based mechanism for Mac App
  Store / self-imposed sandboxing of the *app itself*, enforced at
  code-signing/launch time by launchd/AMFI checking entitlements; it
  confines the app's own process (and its children, by inheritance) but
  requires the *outer* app to opt into App Sandbox, which this project has
  already decided against (direct DMG distribution, no App Store sandbox).
  It is not something you attach to just one subprocess without the whole
  app adopting it.
- **Virtualization.framework** — Apple's native hypervisor API (used by
  Docker Desktop, UTM, etc.) for running full Linux/macOS guest VMs. Real
  isolation, but VM-level, not process-level; wildly disproportionate
  overhead for confining a single shell command.

Conclusion: on macOS, for an unprivileged single process, Seatbelt
(`sandbox-exec`) is the only OS-native facility that does what's being asked
for. There is no lightweight namespace/container primitive to reach for
instead.

## 4. Fallback: process-level containment via Python `subprocess`

Not OS confinement — an app-level habit that removes a class of bugs
(shell-metacharacter injection) and fixes the *starting* directory, nothing
more:

```python
subprocess.run(
    shlex.split(command),
    cwd=vault_root,
    shell=False,
    env=scrubbed_env,
)
```

- `shell=False` + `shlex.split(command)` avoids invoking `/bin/sh -c
  <command>`, so shell metacharacters in the command string (`;`, `|`, `` ` ``,
  `$()`, `&&`) are not interpreted — the command is exec'd directly as
  `argv`, closing off shell-injection tricks that could otherwise smuggle in
  a second command.
- `cwd=vault_root` sets only the process's *initial* working directory.
- `env=scrubbed_env` limits inherited environment (e.g. a minimal `PATH`)
  but does not and cannot restrict filesystem syscalls.

**This does not stop filesystem escape.** Nothing here prevents the command
itself — if it's e.g. `cd ../../.. && rm -rf ~` or `cat /etc/passwd` or `cp
secret /Users/me/Desktop/` using an absolute path — from reading or writing
anywhere the user account can normally access. `cwd` only affects relative
paths at the moment the process starts; a `cd` inside the command, or any
absolute path anywhere in the command, ignores it completely. This is
explicitly *not* filesystem confinement — it is injection hygiene plus a
starting directory, and should not be described or relied on as a security
boundary in the spec.

## Recommendation

**Wrap the `shell_exec` child process in `sandbox-exec` with a bundled,
default-deny custom Seatbelt profile**, on top of (not instead of) the
existing `subprocess.run(..., shell=False, cwd=vault_root, env=scrubbed_env)`
hygiene. Concretely: ship a `.sb` profile as an app resource that denies by
default, allows broad `file-read*` (needed for dyld/library loading — see
the gotcha above) but restricts `file-write*` (and, if read-confinement of
vault contents specifically matters more than write-confinement, also
`file-read-data`) to `(subpath <vault_root>)`, and invoke the user's command
via `sandbox-exec -f <profile> -D VAULT=<vault_root> ...` in place of the
current direct `subprocess.run(command, ...)`.

**Limitations, to state plainly in the spec:**
- `sandbox-exec` is a deprecated API. It still works, and works for an
  unsandboxed caller (verified above), but Apple gives no forward
  compatibility guarantee — the SDK-27 kill switch for named profiles is
  evidence they do prune this surface over time. This is a real
  maintenance/longevity risk for a shipping product, not a hypothetical one.
  Recommend runtime-detecting whether `sandbox-exec` is present and
  behaves as expected (e.g. a startup self-test that a confined write
  outside the vault is actually denied) and falling back to refusing to run
  `shell_exec` (not silently downgrading to unconfined execution) if the
  self-test fails on some future OS.
- It confines *filesystem* access (and can additionally restrict network,
  process spawning, IPC, etc. via the same profile grammar) but is a
  process-level boundary, not a content boundary: a command that's allowed
  to read `vault_root` can still exfiltrate its contents over the network
  unless network access is also denied in the profile, and a command that's
  allowed to write inside `vault_root` can still do damage *within* the
  vault (delete/overwrite the user's own files there) — Seatbelt bounds
  *where*, not *what*, and approval-before-run is still the only guard
  against a destructive-but-in-bounds command.
- It does not stop resource exhaustion (fork bombs, infinite loops, huge
  writes inside the vault) — that's a separate concern (rlimits/timeouts),
  not addressed here.
- Writing and testing the profile is a nontrivial, easy-to-get-wrong task
  (see the dyld-abort gotcha above); it needs its own test coverage
  (assert a write outside vault_root is denied, a write inside is allowed,
  and ordinary commands like `ls`/`git`/`python` still run) so a
  regression doesn't silently turn into either "nothing works" (over-broad
  deny, caught by users immediately) or "confinement silently no-ops"
  (under-broad deny — far more dangerous, since it would fail *open*
  without breaking anything visibly).

**Tool schema / approval UX changes:**
- The `shell_exec(command: str)` schema itself does not need to change —
  the profile wrapping happens entirely inside the tool's implementation,
  transparent to the agent/model calling it.
- The approval UI should be updated to state truthfully that commands run
  inside a sandbox restricted to the vault directory (filesystem writes, and
  optionally reads, outside vault_root are denied at the OS level) rather
  than just "cwd is pinned to the vault" — because that's no longer merely a
  starting-directory convention once Seatbelt is in place, and the user's
  trust decision when approving should reflect what's actually enforced.
  Per-session approval memory can remain as-is; Seatbelt is a floor
  underneath the approval gate, not a replacement for it (a within-vault
  destructive command like `rm -rf .` still needs human approval, since
  Seatbelt would allow it).
- Consider surfacing sandbox self-test failures (see above) as a blocking
  error in the approval UI ("sandboxing unavailable on this system, refusing
  to run") rather than allowing an unconfined fallback to run silently.
