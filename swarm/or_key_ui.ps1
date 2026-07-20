# or_key_ui.ps1
# Local GUI to enter your OpenRouter API key (BYOK / OpenRouter key).
# Runs entirely on this machine. The key is written to:
#   - $env:OPENROUTER_API_KEY        (current PowerShell session)
#   - $env:USERPROFILE\.openrouter.json (persistent config, used by swarm_or_agent.ps1)
#   - optional: user-level environment variable (survives reboots)
# The key is NEVER sent to the assistant or any chat.

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$form = New-Object Windows.Forms.Form
$form.Text = "OpenRouter API Key"
$form.Width = 560
$form.Height = 280
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false

$lbl = New-Object Windows.Forms.Label
$lbl.Text = "Paste your OpenRouter API key (sk-or-...):"
$lbl.Location = "20,20"; $lbl.Size = "500,20"
$form.Controls.Add($lbl)

$txt = New-Object Windows.Forms.TextBox
$txt.Location = "20,50"; $txt.Size = "500,22"
$txt.PasswordChar = "*"          # mask the key
$txt.UseSystemPasswordChar = $true
$form.Controls.Add($txt)

$chkPersist = New-Object Windows.Forms.CheckBox
$chkPersist.Text = "Persist as user environment variable (survives reboot)"
$chkPersist.Location = "20,85"; $chkPersist.Size = "500,20"
$chkPersist.Checked = $true
$form.Controls.Add($chkPersist)

$btn = New-Object Windows.Forms.Button
$btn.Text = "Save & set env"
$btn.Location = "20,130"; $btn.Size = "160,30"
$form.Controls.Add($btn)

$status = New-Object Windows.Forms.Label
$status.Text = ""
$status.Location = "20,175"; $status.Size = "500,40"
$status.ForeColor = "DarkGreen"
$form.Controls.Add($status)

$btn.Add_Click({
    $key = $txt.Text.Trim()
    if (-not $key) { $status.Text = "Key is empty."; $status.ForeColor = "DarkRed"; return }

    # 1) current session env var
    $env:OPENROUTER_API_KEY = $key

    # 2) persistent config file (read by swarm_or_agent.ps1)
    $cfg = Join-Path $env:USERPROFILE ".openrouter.json"
    @{ api_key = $key; base_url = "https://openrouter.ai/api/v1" } | ConvertTo-Json | Set-Content $cfg -Encoding UTF8

    # 3) optional user-level env var
    if ($chkPersist.Checked) {
        [System.Environment]::SetEnvironmentVariable("OPENROUTER_API_KEY", $key, "User")
    }

    $status.Text = "Saved. Key is set for this session and written to:`n$cfg"
    $status.ForeColor = "DarkGreen"
})

[void]$form.ShowDialog()
