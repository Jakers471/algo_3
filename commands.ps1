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
            # The chart is a local web app: start the server, then open the URL.
            Label = 'Chart'
            Submenu = @{
                Title = 'Chart  -  browse and replay bars in the browser'
                Items = @(
                    @{ Label = 'Open chart  (serves http://127.0.0.1:8765)'; Run = { python -m src.cli.chart --open } },
                    @{ Label = 'Open chart, auto-reload on Python edits  (dev)'; Run = { python -m src.cli.chart --open --reload } },
                    @{ Label = 'Serve only  (no browser)'; Run = { python -m src.cli.chart } },
                    @{ Label = 'Rebuild bar cache, then serve  (after new data)'; Run = { python -m src.cli.chart --repack } },
                    @{ Label = 'Stop chart server  (confirm port closed)'; Run = { python -m src.cli.chart --stop } },
                    @{ Label = 'Snapshot table  (desktop window; attach to the running replay)'; Run = { python -m src.cli.table } },
                    @{ Label = 'Snapshot table  -  30s rung'; Run = { python -m src.cli.table --rung 30s } },
                    @{ Label = 'Snapshot table  -  3m rung'; Run = { python -m src.cli.table --rung 3m } },
                    @{ Label = 'Snapshot table  -  15m rung'; Run = { python -m src.cli.table --rung 15m } },
                    @{ Label = 'Snapshot tables  -  all three rungs at once (30s / 3m / 15m)'; Run = { foreach ($r in '30s','3m','15m') { Start-Process -FilePath 'python' -ArgumentList '-m','src.cli.table','--rung',$r } } },
                    @{ Label = 'Snapshot table  -  session card only  (the session_stats block, nothing else)'; Run = { python -m src.cli.table --group session_stats } }
                )
            }
        },
        @{
            # Live market feed: record it verbatim so we can see what it sends.
            Label = 'Live'
            Submenu = @{
                Title = 'Live  -  record the TopstepX market feed'
                Items = @(
                    @{ Label = 'Record 60s  (NQ front month)'; Run = { python -m src.cli.capture --seconds 60 } },
                    @{ Label = 'Record 5 min  (NQ front month)'; Run = { python -m src.cli.capture --seconds 300 } },
                    @{ Label = 'Record 5 min + market depth  (high volume)'; Run = { python -m src.cli.capture --seconds 300 --depth } }
                )
            }
        },
        @{
            Label = 'Data'
            Submenu = @{
                Title = 'Data'
                Items = @(
                    @{ Label = 'Load & summarize bars  (python -m src.cli.data NQ 5m)'; Run = { python -m src.cli.data NQ 5m } },
                    @{ Label = 'Rebuild bars from ticks  (15s/1m/5m/15m/1h/4h + delta)'; Run = { python -m src.cli.resample } },
                    @{ Label = 'Build volume at price  (ticks -> 1-tick histograms, ~80s)'; Run = { python -m src.cli.vap --timeframe 30s --verify } },
                    @{ Label = 'Build session-history table  (percentile-vs-history for session_stats)'; Run = { python -m src.cli.session_history --symbol NQT --timeframe 5m } },
                    @{ Label = 'Build session catalog  (the card, every explore session, every bar -> parquet)'; Run = { python -m src.cli.session_catalog } },
                    @{ Label = 'Audit backtest data  (regenerate DATA_AUDIT.json/.md)'; Run = { python scratch/audit_parquet.py } },
                    @{ Label = 'Compare NT8 Parquet vs ProjectX API'; Run = { python scratch/compare_data.py } }
                )
            }
        },
        @{
            Label = 'Analysis'
            Submenu = @{
                Title = 'Analysis'
                Items = @(
                    @{ Label = 'Break sequences  (continuation / consolidation, NY session)'; Run = { python -m scratch.analysis.break_sequences --session ny } },
                    @{ Label = 'Break sequences  (sweep the retrace dial)'; Run = { python -m scratch.analysis.break_sequences --session ny --retrace 1.5 3.0 5.0 } },
                    @{ Label = 'Break sequences  (all hours)'; Run = { python -m scratch.analysis.break_sequences --session all } },
                    @{ Label = 'Timeframe scaling  (open the measured chart)'; Run = { Start-Process 'scratch/analysis/timeframe_scaling.html' } },
                    @{ Label = 'Volatility seasonality  (regenerate + open the report)'; Run = { python -m scratch.analysis.seasonality_report; Start-Process 'scratch/analysis/range_scale_seasonality.html' } },
                    @{ Label = 'Leg zoom  (one 15m leg -> 3m -> 30s, three PNGs)'; Run = { python -m scratch.analysis.leg_zoom } },
                    @{ Label = 'Scale ladder  (is RETRACE tunable? swing count vs threshold, two nulls)'; Run = { python -m scratch.analysis.scale_ladder } },
                    @{ Label = 'Regime plane  (is regime a thing? every leg as drift x impulse, three PNGs)'; Run = { python -m scratch.analysis.regime_plane } },
                    @{ Label = 'Retracement  (does a leg give back less than the last? does it persist?)'; Run = { python -m scratch.analysis.retracement } },
                    @{ Label = 'Flow edge  (does order flow at a break predict the next break?)'; Run = { python -m scratch.analysis.flow_edge } },
                    @{ Label = 'Expectancy  (what does a bracket at a break earn, after costs?)'; Run = { python -m scratch.analysis.expectancy } },
                    @{ Label = 'Forecast paper  (can you forecast tomorrow''s volatility? train/test)'; Run = { python -m scratch.analysis.forecast_paper; Start-Process 'scratch/analysis/forecast_paper.html' } },
                    @{ Label = 'Edge paper  (why reward:risk cannot beat a coin - optional stopping)'; Run = { python -m scratch.analysis.edge_paper; Start-Process 'scratch/analysis/edge_paper.html' } },
                    @{ Label = 'Discipline paper  (is trading 90% risk management?)'; Run = { python -m scratch.analysis.discipline_paper; Start-Process 'scratch/analysis/discipline_paper.html' } },
                    @{ Label = 'Value width  (draw balanced vs imbalanced value areas)'; Run = { python -m scratch.analysis.value_width_draw } },
                    @{ Label = 'Stack scan  (does profile + MA squeeze stacked beat either alone?)'; Run = { python -m scratch.analysis.stack_scan; Start-Process 'scratch/analysis/stack_scan.html' } },
                    @{ Label = 'MA squeeze  (does the coiled spring exist? composite + real examples)'; Run = { python -m scratch.analysis.ma_squeeze; Start-Process 'scratch/analysis/ma_squeeze.html' } },
                    @{ Label = 'MA scan  (are 10/20/50/100/200 MAs useful? regression + cross study)'; Run = { python -m scratch.analysis.ma_scan; Start-Process 'scratch/analysis/ma_scan.html' } },
                    @{ Label = 'Ribbon regime  (calibrate the regime cutoffs: align/width/agree over NQT)'; Run = { python -m scratch.analysis.ribbon_regime } },
                    @{ Label = 'Session window study  (choose N for session_stats'' recent/prior phase detector)'; Run = { python -m scratch.session_research.session_window_study } },
                    @{ Label = 'Session interrogation  (explore population: clock artifact, distributions, breaks vs traps)'; Run = { python -m scratch.session_research.session_interrogation } },
                    @{ Label = 'MTF regime returns  (does 1h+1d bull>70 beat 1h alone? conditional fwd returns)'; Run = { python -m scratch.mtf_regime.forward_returns } },
                    @{ Label = 'MTF regime sweep  (b-(a\b) across thresholds 30..70: is the 1d filter noise?)'; Run = { python -m scratch.mtf_regime.sweep } },
                    @{ Label = 'MTF regime fade  (does shorting a high bull-fan pay? swept over threshold)'; Run = { python -m scratch.mtf_regime.fade } },
                    @{ Label = 'MTF regime plots  (the findings as one PNG: state returns, decoration, fade)'; Run = { python -m scratch.mtf_regime.plots } },
                    @{ Label = 'MTF regime validate  (ES out-of-sample + time-split + episode clustering)'; Run = { python -m scratch.mtf_regime.validate } },
                    @{ Label = 'Vol regime  (does realized-vol level condition returns? full harness, NQ+ES)'; Run = { python -m scratch.vol_regime.study } },
                    @{ Label = 'Seasonality  (pre-registered: overnight vs intraday, turn-of-month, dow)'; Run = { python -m scratch.seasonality.study } },
                    @{ Label = 'Intraday  (pre-registered: last-30m momentum + overnight-gap, NQ+ES OOS)'; Run = { python -m scratch.intraday.study } },
                    @{ Label = 'ORB / value area  (pre-registered: VA-escape continuation, VA vs range, POC anchor)'; Run = { python -m scratch.orb_va.study } },
                    @{ Label = 'ORB / value area fills  (stage-6: tape-measured slippage + costs on 20y)'; Run = { python -m scratch.orb_va.fills } },
                    @{ Label = 'ORB / value area revisit  (pullback + failed-breakout fade, both killed)'; Run = { python -m scratch.orb_va.revisit } },
                    @{ Label = 'Pre-FOMC drift  (pre-registered: Lucca-Moench 24h window vs benchmark, NQ+ES)'; Run = { python -m scratch.fomc_drift.study } },
                    @{ Label = 'Pre-FOMC drift tails  (stage-3: tails, concentration, costs, sub-window)'; Run = { python -m scratch.fomc_drift.tails } },
                    @{ Label = 'Pre-FOMC drift day-leg  (09:30->14:00 flat-by-close variant, own kill line)'; Run = { python -m scratch.fomc_drift.dayleg } },
                    @{ Label = 'Pre-FOMC drift vs buy-and-hold  (context: 8 exposed days/yr against 252)'; Run = { python -m scratch.fomc_drift.benchmark_compare } },
                    @{ Label = 'Day-type classifier  (does London sort the NY session? context-only verdict)'; Run = { python -m scratch.daytype.study } },
                    @{ Label = 'Order-flow imbalance  (the last directional door: OFI 15/30m fwd returns)'; Run = { python -m scratch.orderflow.study } },
                    @{ Label = 'TS momentum  (MOP 2012 on the two-index universe: weekly ensemble, capped)'; Run = { python -m scratch.tsmom.study } },
                    @{ Label = 'Indicator scan  (regress ALL indicator fields vs next move)'; Run = { python -m scratch.analysis.indicator_scan; Start-Process 'scratch/analysis/indicator_scan.html' } },
                    @{ Label = 'Quant report  (alpha vs beta tearsheet, no candlesticks)'; Run = { python -m scratch.analysis.quant_report; Start-Process 'scratch/analysis/quant_report.html' } },
                    @{ Label = 'HFT paper  (is tick data more predictable? yes - and unreachable)'; Run = { python -m scratch.analysis.hft_paper; Start-Process 'scratch/analysis/hft_paper.html' } },
                    @{ Label = 'Magnitude paper  (regenerate + open the HTML paper)'; Run = { python -m scratch.analysis.magnitude_paper; Start-Process 'scratch/analysis/magnitude_paper.html' } },
                    @{ Label = 'Magnitude  (why the sign is a coin and the size is not - three PNGs)'; Run = { python -m scratch.analysis.magnitude } },
                    @{ Label = 'Profile edge  (does the volume profile beat range_scale?)'; Run = { python -m scratch.analysis.profile_edge } },
                    @{ Label = 'MTF confluence  (do LTF reactions cluster at an HTF value-area edge?)'; Run = { python -m scratch.analysis.mtf_confluence } },
                    @{ Label = 'Window render  (candles + structure + per-leg profiles, gaps collapsed)'; Run = { python -m scratch.analysis.window_render } },
                    @{ Label = 'Scale-free structure  (swings stacked in range_scale: 4 windows)'; Run = { python -m scratch.analysis.scale_free_structure } },
                    @{ Label = 'Week view  (a full week: candles + the dimensionless map)'; Run = { python -m scratch.analysis.week_view } },
                    @{ Label = 'Structure scales  (the structure profile across timeframes)'; Run = { python -m scratch.analysis.structure_scales } },
                    @{ Label = 'Recurrence  (price stripped to same-place-or-not, time on both axes)'; Run = { python -m scratch.analysis.recurrence } },
                    @{ Label = 'Geometry zoo  (one week, eight price-free representations)'; Run = { python -m scratch.analysis.geometry_zoo } },
                    @{ Label = 'RQA fingerprint  (the recurrence plot as scalars: RR / DET / LAM / Lmax)'; Run = { python -m scratch.analysis.rqa } },
                    @{ Label = 'Regime overlay  (rolling recurrence rate under the candles, causal)'; Run = { python -m scratch.analysis.regime_overlay } },
                    @{ Label = 'Regime test  (does the RR regime persist / predict past a null?)'; Run = { python -m scratch.analysis.regime_test } },
                    @{ Label = 'Second break  (draw the break-of-structure long on one day)'; Run = { python -m scratch.analysis.second_break } },
                    @{ Label = 'Second break test  (grade it full-data: R:R ladder + breakeven vs null)'; Run = { python -m scratch.analysis.second_break_test } },
                    @{ Label = 'Fractal break  (30s context + 15s entry, 1:3, graded vs null)'; Run = { python -m scratch.analysis.fractal_break } },
                    @{ Label = 'Outcomes  (label every bar: which barrier first? the cost wall + always-long)'; Run = { python -m scratch.analysis.outcomes } },
                    @{ Label = 'Straddle  (buy the expansion, never the direction: does a coil pay?)'; Run = { python -m scratch.analysis.straddle } },
                    @{ Label = 'Structure variants  (six ways to draw swings/legs/breaks)'; Run = { python -m scratch.mockups.structure_variants } }
                )
            }
        },
        @{
            Label = 'Maintenance'
            Submenu = @{
                Title = 'Maintenance'
                Items = @(
                    @{ Label = 'Field contract  (which indicator publishes which column)'; Run = { python -m src.cli.fields } },
                    @{ Label = 'Field contract  (regenerate FIELDS.md)'; Run = { python -m src.cli.fields --write } },
                    @{ Label = 'Run tests  (pytest)'; Run = { python -m pytest tests/ -q } },
                    @{ Label = 'Project audit  (docs drift + dead code)'; Run = { python scratch/audit_project.py } }
                )
            }
        }
    )
}

Show-Menu -Menu $root -IsRoot $true
Clear-Host
