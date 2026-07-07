# ===========================================================================
#  commands.ps1  -  the algo_3 command hub (arrow-key menu).
#
#  Launched by commands.bat. Navigate with Up/Down, Enter to select, Esc to
#  go back (or quit at the top). Menus nest: a category opens a submenu.
#
#  To add a command: drop a new item into the menu tree at the bottom of this
#  file. An item is either:
#     @{ Label = '...'; Run = { <command> } }        a runnable command
#     @{ Label = '...'; Submenu = @{ Title=...; Items=@(...) } }   a submenu
#  Keep it updated and cleaned. Wire in every runnable command AND persistent
#  scratch tool (audits, generators, comparisons) so Jake can run them here.
# ===========================================================================

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

function Show-Menu {
    param(
        [hashtable]$Menu,
        [bool]$IsRoot = $false
    )

    $items = @($Menu.Items)
    $index = 0

    while ($true) {
        Clear-Host
        Write-Host ''
        Write-Host ("  " + $Menu.Title) -ForegroundColor Cyan
        Write-Host ("  " + ('-' * ($Menu.Title.Length + 2))) -ForegroundColor DarkCyan
        Write-Host ''

        if ($items.Count -eq 0) {
            Write-Host '     (nothing here yet)' -ForegroundColor DarkGray
        }
        for ($i = 0; $i -lt $items.Count; $i++) {
            $it = $items[$i]
            $marker = if ($it.Submenu) { '>' } else { ' ' }
            $line = "  $marker $($it.Label)"
            if ($i -eq $index) {
                Write-Host ("  " + $line.PadRight(52)) -ForegroundColor Black -BackgroundColor Cyan
            } else {
                Write-Host ("  " + $line) -ForegroundColor Gray
            }
        }

        Write-Host ''
        $back = if ($IsRoot) { 'Left quit' } else { 'Left back' }
        Write-Host "     Up/Down move    Enter/Right select    $back" -ForegroundColor DarkGray

        $key = [Console]::ReadKey($true)
        switch ($key.Key) {
            'UpArrow'   { if ($items.Count) { $index = ($index - 1 + $items.Count) % $items.Count } }
            'DownArrow' { if ($items.Count) { $index = ($index + 1) % $items.Count } }
            { $_ -in 'Enter', 'RightArrow' } {
                if ($items.Count -gt 0) {
                    $sel = $items[$index]
                    if ($sel.Submenu) {
                        Show-Menu -Menu $sel.Submenu -IsRoot $false
                    }
                    elseif ($sel.Run) {
                        Clear-Host
                        Write-Host ("  Running: " + $sel.Label) -ForegroundColor Cyan
                        Write-Host ''
                        & $sel.Run
                        Write-Host ''
                        Write-Host '  Done. Press any key to return to the menu...' -ForegroundColor Green
                        [Console]::ReadKey($true) | Out-Null
                    }
                }
            }
            'LeftArrow' { return }
            'Escape'    { return }
        }
    }
}

# --- menu tree -------------------------------------------------------------
# Add categories and commands here. Nesting is just a Submenu on an item.

$root = @{
    Title = 'algo_3  command menu'
    Items = @(
        @{
            Label = 'Setup'
            Submenu = @{
                Title = 'Setup'
                Items = @(
                    @{ Label = 'Install dependencies  (pip install -r requirements.txt)'; Run = { python -m pip install -r requirements.txt } }
                )
            }
        },
        @{
            Label = 'Backtest'
            Submenu = @{
                Title = 'Backtest'
                Items = @(
                    @{ Label = 'Run from config  (run_configs/breakout_nq5m.json)'; Run = { python -m src.cli.backtest run_configs/breakout_nq5m.json } },
                    @{ Label = 'Walk-forward from config  (run_configs/wfa_breakout_nq5m.json)'; Run = { python -m src.cli.walkforward run_configs/wfa_breakout_nq5m.json } }
                )
            }
        },
        @{
            Label = 'Data'
            Submenu = @{
                Title = 'Data'
                Items = @(
                    @{ Label = 'Load & summarize bars  (python -m src.cli.data NQ 5m)'; Run = { python -m src.cli.data NQ 5m } },
                    @{ Label = 'Audit backtest data  (regenerate DATA_AUDIT.json/.md)'; Run = { python scratch/audit_parquet.py } },
                    @{ Label = 'Compare NT8 Parquet vs ProjectX API'; Run = { python scratch/compare_data.py } }
                )
            }
        },
        @{
            Label = 'Maintenance'
            Submenu = @{
                Title = 'Maintenance'
                Items = @(
                    @{ Label = 'Run tests  (pytest)'; Run = { python -m pytest tests/ -q } },
                    @{ Label = 'Project audit  (docs drift + dead code)'; Run = { python scratch/audit_project.py } }
                )
            }
        }
    )
}

Show-Menu -Menu $root -IsRoot $true
Clear-Host
