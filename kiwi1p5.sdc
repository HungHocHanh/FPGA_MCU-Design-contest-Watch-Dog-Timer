// ============================================================
// kiwi1p5.sdc – Timing Constraints cho Watchdog Monitor
// ============================================================

// Clock 27 MHz trên pin clk  (chu kỳ ≈ 37.037 ns)
create_clock -name clk -period 37.037 -waveform {0 18.518} [get_ports {clk}]
