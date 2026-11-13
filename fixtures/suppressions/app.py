import os  # noqa: F401 unused on purpose, kept for the plugin API
x = os.getcwd()  # type: ignore[attr-defined]
subprocess.run(cmd)  # nosec B603 trusted constant command
password = "# noqa: E501 inside a string is no mark"
# nosemgrep: python.lang.security.audit.exec-use -- sandboxed by design
y = 1  # noqa
