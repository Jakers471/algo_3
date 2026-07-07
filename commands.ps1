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
#  Keep it updated and cleaned; permanent src/ commands only, never scratch.
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
            Label = 'CLI / Workflows'
            Submenu = @{
                Title = 'CLI / Workflows'
                Items = @()
            }
        },
        @{
            Label = 'Data'
            Submenu = @{
                Title = 'Data'
                Items = @()
            }
        }
    )
}

Show-Menu -Menu $root -IsRoot $true
Clear-Host
