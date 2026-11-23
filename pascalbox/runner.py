"""Free Pascal toolchain discovery, compilation and interactive process runs."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
CREATE_NEW_CONSOLE = 0x00000010 if os.name == "nt" else 0

CONSOLE_SCRIPT = r"""@echo off
chcp %PASCAL_BOX_CODEPAGE% >nul
title Pascal Box Program
echo.
"%PASCAL_BOX_EXE%"
set "PASCAL_BOX_EXIT=%ERRORLEVEL%"
echo.
if not "%PASCAL_BOX_EXIT%"=="0" echo Program exited with code %PASCAL_BOX_EXIT%.
echo Press any key to close this window . . .
pause >nul
exit /b %PASCAL_BOX_EXIT%
"""


def _decode_console(raw: bytes) -> str:
    if not raw:
        return ""
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


@dataclass
class CompileResult:
    ok: bool
    output: str
    returncode: int
    elapsed: float
    exe_path: Path | None
    source: Path | None
    command: list[str] = field(default_factory=list)
    error: str = ""


class FpcToolchain:
    def __init__(self) -> None:
        self.fpc = self._find_fpc()
        self.version = self._read_version()

    @staticmethod
    def _find_fpc() -> str | None:
        env = os.environ.get("PASCAL_BOX_FPC")
        if env and Path(env).is_file():
            return env
        found = shutil.which("fpc")
        if found:
            return found
        common = [
            Path(r"D:\fpc\bin\i386-Win32\fpc.exe"),
            Path(r"C:\FPC\3.2.2\bin\i386-Win32\fpc.exe"),
            Path(r"C:\FPC\3.2.2\bin\x86_64-Win64\fpc.exe"),
            Path(r"C:\fpc\bin\i386-Win32\fpc.exe"),
            Path("/usr/bin/fpc"),
            Path("/usr/local/bin/fpc"),
        ]
        for candidate in common:
            if candidate.is_file():
                return str(candidate)
        return None

    def _read_version(self) -> str:
        if not self.fpc:
            return ""
        try:
            result = subprocess.run(
                [self.fpc, "-iV"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=8,
                creationflags=CREATE_NO_WINDOW,
            )
            return _decode_console(result.stdout).strip().splitlines()[0]
        except (OSError, subprocess.SubprocessError, IndexError):
            return ""

    @property
    def available(self) -> bool:
        return bool(self.fpc)

    def executable_for(self, source: Path) -> Path:
        return source.with_suffix(".exe" if os.name == "nt" else "")

    def compile_async(
        self,
        source: Path,
        callback: Callable[[CompileResult], None],
        *,
        extra_args: list[str] | None = None,
    ) -> None:
        thread = threading.Thread(
            target=self._compile_worker,
            args=(source, callback, extra_args or []),
            daemon=True,
        )
        thread.start()

    def _compile_worker(
        self,
        source: Path,
        callback: Callable[[CompileResult], None],
        extra_args: list[str],
    ) -> None:
        started = time.perf_counter()
        source = source.resolve()
        exe = self.executable_for(source)
        if not self.fpc:
            callback(
                CompileResult(
                    ok=False,
                    output="未找到 Free Pascal 编译器 fpc。\n"
                    "请安装 FPC 并把 fpc.exe 加入 PATH，或通过 PASCAL_BOX_FPC 环境变量指定路径。",
                    returncode=-1,
                    elapsed=time.perf_counter() - started,
                    exe_path=None,
                    source=source,
                    error="FPC_NOT_FOUND",
                )
            )
            return
        command = [
            self.fpc,
            "-Mobjfpc",
            "-Sh",
            "-O2",
            "-vw",
            f"-o{exe}",
            source.name,
            *extra_args,
        ]
        try:
            process = subprocess.run(
                command,
                cwd=str(source.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=180,
                creationflags=CREATE_NO_WINDOW,
            )
            elapsed = time.perf_counter() - started
            output = _decode_console(process.stdout).replace("\r\n", "\n").replace("\r", "\n")
            ok = process.returncode == 0 and exe.is_file()
            if process.returncode == 0 and not exe.is_file():
                output += "\n编译器返回成功，但没有找到生成的 exe 文件。\n"
            callback(
                CompileResult(
                    ok=ok,
                    output=output,
                    returncode=process.returncode,
                    elapsed=elapsed,
                    exe_path=exe if exe.is_file() else None,
                    source=source,
                    command=command,
                )
            )
        except subprocess.TimeoutExpired:
            callback(
                CompileResult(
                    ok=False,
                    output="编译超时（超过 180 秒）。\n",
                    returncode=-1,
                    elapsed=time.perf_counter() - started,
                    exe_path=None,
                    source=source,
                    command=command,
                    error="TIMEOUT",
                )
            )
        except OSError as exc:
            callback(
                CompileResult(
                    ok=False,
                    output=f"无法启动编译器：{exc}\n",
                    returncode=-1,
                    elapsed=time.perf_counter() - started,
                    exe_path=None,
                    source=source,
                    command=command,
                    error=str(exc),
                )
            )


class ProgramRunner:
    """Runs a program in a separate console window, then pauses it there."""

    def __init__(self) -> None:
        self.process: subprocess.Popen | None = None
        self._waiter: threading.Thread | None = None
        self._script: Path | None = None
        self.running = False

    def start(
        self,
        exe: Path,
        cwd: Path,
        emit: Callable[[tuple], None],
        *,
        encoding: str = "utf-8",
    ) -> bool:
        if self.running:
            return False
        if os.name != "nt":
            emit(("error", "外部终端运行仅支持 Windows。"))
            return False
        script = None
        try:
            handle, script_name = tempfile.mkstemp(
                prefix="pascal_box_run_", suffix=".bat"
            )
            os.close(handle)
            script = Path(script_name)
            script.write_text(CONSOLE_SCRIPT, encoding="ascii", newline="\r\n")
            env = os.environ.copy()
            env["PASCAL_BOX_EXE"] = str(exe)
            env["PASCAL_BOX_CODEPAGE"] = (
                "936" if encoding == "gb18030" else "65001"
            )
            comspec = env.get("COMSPEC", "cmd.exe")
            process = subprocess.Popen(
                [comspec, "/d", "/c", str(script)],
                cwd=str(cwd),
                env=env,
                creationflags=CREATE_NEW_CONSOLE,
            )
        except OSError as exc:
            if script is not None:
                script.unlink(missing_ok=True)
            emit(("error", f"无法启动程序：{exc}"))
            return False
        self.process = process
        self._script = script
        self.running = True
        self._waiter = threading.Thread(
            target=self._wait_for_exit,
            args=(process, script, emit),
            daemon=True,
        )
        self._waiter.start()
        return True

    def _wait_for_exit(
        self,
        process: subprocess.Popen,
        script: Path,
        emit: Callable[[tuple], None],
    ) -> None:
        try:
            code = process.wait()
        except OSError:
            code = -1
        finally:
            self.running = False
            try:
                script.unlink(missing_ok=True)
            except OSError:
                pass
        emit(("exit", code))

    def stop(self) -> None:
        process = self.process
        if process is None or process.poll() is not None:
            return
        if os.name == "nt":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=CREATE_NO_WINDOW,
                    timeout=5,
                )
                return
            except (OSError, subprocess.SubprocessError):
                pass
        try:
            process.terminate()
        except OSError:
            pass

    @property
    def pid(self) -> int | None:
        return self.process.pid if self.process is not None else None
