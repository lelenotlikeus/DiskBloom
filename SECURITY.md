# Security Policy

DiskBloom scans local files and can move files or folders to the system Trash/Recycle Bin.

## Reporting Issues

Please open a private security advisory or contact the maintainers before publishing details for vulnerabilities involving unsafe deletion, path handling, privilege escalation, or unintended data exposure.

## Safety Design

- DiskBloom skips symlinks during scans to avoid recursive traversal surprises.
- Standard deletion uses `send2trash` and asks for confirmation.
- Dangerous deletion targets are blocked, including filesystem roots, the user home folder, Desktop, Documents, Downloads, Windows, and Program Files.
- Permanent deletion is a separate advanced action, requires elevated privileges on Windows, and requires typing `DELETE`.
- Deletion tests use pytest temporary files and folders only; the normal test suite does not delete real user data.
- Permission errors are reported as scan errors and do not stop the whole scan.
