# GoldBot Phase 6.9.2 — Exness KE MT5 Pro demo setup

The pinned read-only connectivity check passed on 18 November 2026 for ExnessKE-MT5Trial9, USD demo ending 9498. The profile is opt-in. The terminal reported Exness (KE) Limited. Personal Area Pro status remains unverified. [Connectivity verification](../../reports/phase_6_9_2/connectivity-verification.md) · [Phase 6.9.3](phase-6-9-3.md)

## Manual setup in Exness and MT5

1. Open the [official Exness Kenya demo page](https://www.exness.ke/demo-trading-account/). Use **Try free demo** to reach the official Personal Area. Sign in or complete registration manually. For a Kenyan account, select Kenya as your residence if accurate and check that the applicable agreement names **Exness (KE) Limited**, CMA licence 162. If the demo's entity is unclear, confirm it through the official Personal Area support channel before running GoldBot. Keep any evidence with account identifiers removed. [Kenyan agreement](https://www.exness.ke/cdn/media/exnesske/exness_ke_client_agreement.pdf)
2. In **My Accounts**, choose **Open Account → Pro → Continue**. Choose **Demo**, **MetaTrader 5**, and **USD**. Select **1:100** under **Max leverage** if offered. If you see an execution-type choice, record the option you select for future contract review. Set the trading password inside Exness and choose **Create an Account**. The Pro demo appears under **My Accounts → Demo**. [Account creation](https://get.exness.help/hc/en-us/articles/4408633634322-How-to-create-trading-accounts)
3. On that Pro demo card, use **Set Balance** to set the virtual balance to **USD 3,000**, if offered. If 1:100 was unavailable at creation, check the demo card menu under **Max leverage**. Record the actual settings if either requested value is unavailable. [Demo balance](https://get.exness.help/hc/en-us/articles/360007200571-How-to-top-up-a-demo-account) · [Leverage](https://get.exness.help/hc/en-us/articles/360006922872-Trading-account-settings)
4. Expand that same demo card and note its assigned MT5 server and login privately. Install Exness's official MT5 desktop download in a separate folder if needed to preserve the original MetaQuotes profile. In the dedicated desktop terminal, choose **File → Login to Trade Account** and enter the demo login, password and exact assigned server there. If MT5 needs to discover the server, use **File → Open an Account**, search for **Exness**, select **Exness Technologies Ltd.**, then choose the exact assigned server. Confirm the desktop shows a connected demo account. [Server details](https://get.exness.help/hc/en-us/articles/360012578619-Trading-account-login-and-server-details) · [MT5 desktop guide](https://get.exness.help/hc/en-us/articles/360011514572-MT5-Trading-guide-Desktop)
5. In MT5, right-click **Market Watch**, choose **Symbols**, and show **XAUUSD**. Stop and document the discrepancy if only a suffixed symbol appears. Leave the dedicated desktop terminal open. Keep account numbers and passwords out of chat and reports. [MT5 desktop guide](https://get.exness.help/hc/en-us/articles/360011514572-MT5-Trading-guide-Desktop)

## Read-only identity check

Use this only after separately verifying the Kenyan entity, the Pro demo card and the connected desktop session against the same exact server and login. The profile setting is the operator's confirmation of those prerequisites. A generic Exness company name can confirm the broker brand but does not by itself establish Kenyan routing. If an unexpected server naming convention or company label appears, stop for review. Each separate terminal executable path identifies one installation. The check refuses a missing process, multiple running instances for the selected path, or any unreadable process path.

```powershell
Set-Location D:\GoldBot
$env:GOLDBOT_EXNESS_TERMINAL = Read-Host 'Full path to the dedicated terminal64.exe'
$env:GOLDBOT_EXNESS_DEMO_SERVER = Read-Host 'Exact demo server from the Pro demo card'
$env:GOLDBOT_EXNESS_DEMO_LOGIN = Read-Host 'Demo login from the card (local only)' -MaskInput
$env:GOLDBOT_DEMO_PROFILE = 'exness-ke-mt5-pro-demo'
try {
    & .\.venv\Scripts\python.exe -B -m tools.verify_exness_demo
} finally {
    Remove-Item Env:GOLDBOT_DEMO_PROFILE, Env:GOLDBOT_EXNESS_TERMINAL, Env:GOLDBOT_EXNESS_DEMO_SERVER, Env:GOLDBOT_EXNESS_DEMO_LOGIN -ErrorAction SilentlyContinue
}
```

Use PowerShell 7 for masked local input. MT5 retains control of authentication. The check supplies only the executable path and a timeout to MT5, confirms demo mode, terminal path, account, server, broker company and USD, then checks the exact non-custom XAUUSD symbol and rechecks identity. The output includes whether balance and leverage match the requested settings. Store sanitized Exness evidence under `reports/phase_6_9_2` and any future separately approved Exness data in a dedicated broker directory. The old [Phase 6.9.1 checklist](../../reports/phase_6_9_1/demo-verification.md) records the original diagnostic sequencing. Contract, clock, history and cost probes are outside this setup phase.

[Phase evidence](../../reports/phase_6_9_2/evidence.md)
