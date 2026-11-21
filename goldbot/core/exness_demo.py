"""Opt-in, read-only identity check for the manually vetted Exness KE demo."""

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


PROFILE = "exness-ke-mt5-pro-demo"
SYMBOL = "XAUUSD"
KE_COMPANY = "Exness (KE) Limited"
EXNESS_COMPANIES = {KE_COMPANY, "Exness Technologies Ltd", "Exness Technologies Ltd."}


class VerificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class DemoProfile:
    terminal: Path = field(repr=False)
    server: str
    login: int = field(repr=False)

    @classmethod
    def from_environment(cls, env):
        if env.get("GOLDBOT_DEMO_PROFILE") != PROFILE:
            raise VerificationError("Exness KE demo profile is disabled.")
        terminal = Path(env.get("GOLDBOT_EXNESS_TERMINAL", ""))
        if not terminal.is_absolute() or terminal.name.casefold() != "terminal64.exe":
            raise VerificationError("Select an explicit MT5 desktop executable.")
        server = env.get("GOLDBOT_EXNESS_DEMO_SERVER", "")
        if not re.fullmatch(r"Exness(?:KE)?-MT5(?:Trial|Demo)[A-Za-z0-9-]*", server, re.IGNORECASE):
            raise VerificationError("An exact, recognized Exness MT5 demo server is required.")
        login = env.get("GOLDBOT_EXNESS_DEMO_LOGIN", "")
        if not re.fullmatch(r"[1-9][0-9]{0,19}", login):
            raise VerificationError("A locally confirmed demo account reference is required.")
        return cls(terminal, server, int(login))


def running_terminals():
    powershell = Path(os.environ["SystemRoot"]) / (
        "System32/WindowsPowerShell/v1.0/powershell.exe"
    )
    result = subprocess.run(
        [str(powershell), "-NoProfile", "-NonInteractive", "-Command",
         "Get-Process -Name terminal64 -ErrorAction SilentlyContinue | "
         "ForEach-Object { ConvertTo-Json -Compress -InputObject ([string]$_.Path) }"],
        capture_output=True, text=True, timeout=10, check=True,
    )
    return [json.loads(line) for line in result.stdout.splitlines()]


def require_running_terminal(terminal, processes):
    if not terminal.is_file() or not processes or any(not path for path in processes):
        raise VerificationError("The selected desktop terminal could not be verified as running.")
    matches = sum(Path(path).resolve() == terminal.resolve() for path in processes)
    if matches != 1:
        raise VerificationError("Exactly one running instance must match the selected terminal.")


def check_identity(mt5, profile):
    terminal = mt5.terminal_info()
    if terminal is None or not getattr(terminal, "connected", False):
        raise VerificationError("MT5 is disconnected or terminal information is unavailable.")
    directory = getattr(terminal, "path", "")
    if not directory or Path(directory).resolve() != profile.terminal.resolve().parent:
        raise VerificationError("MT5 returned a different terminal path.")
    account = mt5.account_info()
    if getattr(account, "trade_mode", None) != mt5.ACCOUNT_TRADE_MODE_DEMO:
        raise VerificationError("A confirmed MT5 demo session is required.")
    if getattr(account, "company", None) not in EXNESS_COMPANIES:
        raise VerificationError("MT5 reported an unrecognized broker company.")
    if getattr(account, "server", None) != profile.server:
        raise VerificationError("The active MT5 server differs from the verified demo server.")
    if getattr(account, "login", None) != profile.login:
        raise VerificationError("The active MT5 account differs from the verified demo account.")
    if getattr(account, "currency", None) != "USD":
        raise VerificationError("The active demo account must use USD.")
    return terminal, account


def verify(mt5, profile, discover=running_terminals):
    """Return allowlisted evidence. The API never receives login or password."""
    try:
        require_running_terminal(profile.terminal, discover())
        try:
            if not mt5.initialize(str(profile.terminal), timeout=5000):
                raise VerificationError("Read-only MT5 attachment failed.")
            terminal, account = check_identity(mt5, profile)
            symbol = mt5.symbol_info(SYMBOL)
            if getattr(symbol, "name", None) != SYMBOL or getattr(symbol, "custom", None) is not False:
                raise VerificationError("The exact non-custom XAUUSD symbol is unavailable.")
            _, final_account = check_identity(mt5, profile)
            if final_account.company != account.company:
                raise VerificationError("The broker company changed during verification.")
            return {
                "profile": PROFILE,
                "server": profile.server,
                "company": account.company,
                "ke_entity_reported_by_terminal": account.company == KE_COMPANY,
                "account_variant_evidence": "Manual Personal Area confirmation",
                "mode": "demo",
                "symbol": SYMBOL,
                "currency": "USD",
                "requested_balance_matches": account.balance == 3000,
                "requested_leverage_matches": account.leverage == 100,
                "terminal_build": int(terminal.build),
            }
        finally:
            mt5.shutdown()
    except VerificationError:
        raise
    except Exception:
        raise VerificationError("MT5 verification failed while inspecting the selected session.") from None
