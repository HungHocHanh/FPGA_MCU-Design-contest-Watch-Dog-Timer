`timescale 1ns/1ps
module tb_top();

    reg clk;
    reg rst_n;
    reg s1_wdi;
    reg s2_en;
    wire led_wdo;    // = wdo_led_n = ~wdo_n : 0=OK(off), 1=FAULT(on)
    wire led_enout;  // = enout_val          : 0=IDLE,    1=RUNNING/FAULT
    reg rx;
    wire tx;
    integer test_num; // current test index (visible in waveform)

    top uut (
        .clk(clk),
        .rst_n(rst_n),
        .wdi_n(s1_wdi),
        .en_n(s2_en),
        .wdo_led_n(led_wdo),
        .enout_led_n(led_enout),
        .uart_rx(rx),
        .uart_tx(tx)
    );

    // Clock ~27 MHz (half-period = 18.518 ns)
    initial begin
        clk = 0;
        forever #18.518 clk = ~clk;
    end

    // ================================================================
    // HARDWARE LOGIC NOTES (from RTL):
    //
    // EN (top.v line 65):
    //   final_en = en_sw | (~en_clean)
    //   en_n=1 (released) -> en_clean=0 -> final_en=1 -> WDG ON
    //   en_n=0 (pressed)  -> en_clean=1 -> final_en=0 -> WDG OFF
    //
    // KICK (sync_debounce.v):
    //   wdi_fall pulse fires when wdi_n: 0->1 (button release)
    //   Requires 10 ms stable on each edge (CNT_MAX=270,000 cycles)
    //
    // LED POLARITY (top.v line 87-88):
    //   wdo_led_n  = ~wdo_n  -> led_wdo=0 : OK, led_wdo=1 : FAULT
    //   enout_led_n= enout   -> led_enout=0: IDLE, led_enout=1: RUNNING/FAULT
    //
    // WATCHDOG FSM (watchdog_core.v):
    //   IDLE(0)   : wdo_n=1, enout=0, fault=0
    //   ARMING(1) : wdo_n=1, enout=0, fault=0  [counts arm_delay_us = 150 us]
    //   RUNNING(2): wdo_n=1, enout=1, fault=0  [counts tWD_ms = 1600 ms]
    //                 any_kick -> reset timer
    //                 timer==0 -> FAULT
    //   FAULT(3)  : wdo_n=0, enout=1, fault=1  [counts tRST_ms = 200 ms]
    //                 clr_fault | !en -> RUNNING/IDLE
    //                 timer==0 -> auto-recover to RUNNING
    // ================================================================

    initial begin
        rst_n    = 0;
        s1_wdi   = 1;  // WDI button released
        s2_en    = 1;  // EN  button released -> final_en=1 after debounce -> WDG ON
        rx       = 1;  // UART idle
        test_num = 0;

        #2000;
        rst_n = 1;
        $display("[%0t ns] Reset released.", $time);

        // ============================================================
        // TEST 1: WDG auto-starts after reset (en_n=1, released)
        //   Flow: IDLE -> ARMING -> RUNNING
        //   Wait: 10 ms debounce + 150 us arm_delay
        //   EXPECT: led_enout=1 (RUNNING), led_wdo=0 (no fault)
        // ============================================================
        test_num = 1;
        $display("[%0t ns] TEST 1: WDG auto-start after reset", $time);
        #10_500_000;  // debounce 10 ms
        #200_000;     // arm_delay 150 us + margin

        if (led_enout == 1)
            $display("[%0t ns] TEST 1 PASS: led_enout=1, WDG is RUNNING.", $time);
        else
            $display("[%0t ns] TEST 1 FAIL: led_enout=0, WDG did not enter RUNNING!", $time);

        if (led_wdo == 0)
            $display("[%0t ns] TEST 1 PASS: led_wdo=0, no fault yet.", $time);
        else
            $display("[%0t ns] TEST 1 FAIL: led_wdo=1, unexpected FAULT on startup!", $time);

        // ============================================================
        // TEST 2: Valid kick via S1 button before timeout
        //   Press (wdi_n=0) -> hold 10 ms -> release (wdi_n=1) -> wdi_fall pulse
        //   EXPECT: led_wdo=0 (timer reset, still running)
        // ============================================================
        test_num = 2;
        $display("[%0t ns] TEST 2: Valid kick via S1 before timeout", $time);
        #500_000_000;  // wait 500 ms (< tWD = 1600 ms)

        s1_wdi = 0;    // press S1
        #10_500_000;   // debounce press edge
        s1_wdi = 1;    // release S1 -> wdi_fall -> kick
        #10_500_000;   // debounce release edge

        if (led_wdo == 0)
            $display("[%0t ns] TEST 2 PASS: led_wdo=0, kick accepted, timer reset.", $time);
        else
            $display("[%0t ns] TEST 2 FAIL: led_wdo=1, unexpected FAULT after kick!", $time);

        // ============================================================
        // TEST 3: No kick -> TIMEOUT -> FAULT
        //   Wait > tWD_ms = 1600 ms after last kick
        //   EXPECT: led_wdo=1 (FAULT), led_enout=1 (ENOUT stays HIGH in FAULT)
        // ============================================================
        test_num = 3;
        $display("[%0t ns] TEST 3: No kick -> wait 1700 ms -> FAULT", $time);
        #1_700_000_000;  // 1700 ms > 1600 ms

        if (led_wdo == 1)
            $display("[%0t ns] TEST 3 PASS: led_wdo=1, FAULT triggered!", $time);
        else
            $display("[%0t ns] TEST 3 FAIL: led_wdo=0, FAULT did NOT occur!", $time);

        if (led_enout == 1)
            $display("[%0t ns] TEST 3 PASS: led_enout=1, ENOUT held HIGH during FAULT.", $time);
        else
            $display("[%0t ns] TEST 3 FAIL: led_enout=0, unexpected ENOUT drop in FAULT!", $time);

        // ============================================================
        // TEST 4: Kick during FAULT -> must be IGNORED
        //   FAULT state has no any_kick handler in FSM
        //   EXPECT: led_wdo=1 (still FAULT after kick)
        // ============================================================
        test_num = 4;
        $display("[%0t ns] TEST 4: Kick during FAULT (must be ignored)", $time);
        s1_wdi = 0;
        #10_500_000;
        s1_wdi = 1;
        #10_500_000;

        if (led_wdo == 1)
            $display("[%0t ns] TEST 4 PASS: led_wdo=1, kick ignored, still in FAULT.", $time);
        else
            $display("[%0t ns] TEST 4 FAIL: led_wdo=0, kick cleared FAULT - wrong logic!", $time);

        // ============================================================
        // TEST 5: FAULT auto-recovery after tRST_ms = 200 ms
        //   When FAULT timer expires: state->RUNNING, wdo_n=1
        //   EXPECT: led_wdo=0 (fault cleared), led_enout=1 (RUNNING)
        // ============================================================
        test_num = 5;
        $display("[%0t ns] TEST 5: Auto-recovery after tRST = 200 ms", $time);
        #250_000_000;  // 250 ms > 200 ms

        if (led_wdo == 0)
            $display("[%0t ns] TEST 5 PASS: led_wdo=0, FAULT released -> RUNNING.", $time);
        else
            $display("[%0t ns] TEST 5 FAIL: led_wdo=1, still in FAULT after 250 ms!", $time);

        if (led_enout == 1)
            $display("[%0t ns] TEST 5 PASS: led_enout=1, WDG back to RUNNING.", $time);
        else
            $display("[%0t ns] TEST 5 FAIL: led_enout=0, unexpected ENOUT drop!", $time);

        // ============================================================
        // TEST 6: Press and hold S2 (en_n=0) -> Disable -> IDLE
        //   en_n=0 -> en_clean=1 -> final_en=0 -> state->IDLE, fault cleared
        //   EXPECT: led_enout=0 (IDLE), led_wdo=0 (fault cleared on disable)
        // ============================================================
        test_num = 6;
        $display("[%0t ns] TEST 6: Hold S2 -> Disable WDG", $time);
        s2_en = 0;
        #10_500_000;  // debounce

        if (led_enout == 0)
            $display("[%0t ns] TEST 6 PASS: led_enout=0, WDG in IDLE.", $time);
        else
            $display("[%0t ns] TEST 6 FAIL: led_enout=1, WDG not disabled!", $time);

        if (led_wdo == 0)
            $display("[%0t ns] TEST 6 PASS: led_wdo=0, fault cleared on disable.", $time);
        else
            $display("[%0t ns] TEST 6 FAIL: led_wdo=1, fault not cleared!", $time);

        // ============================================================
        // TEST 7: Release S2 (en_n=1) -> Re-enable -> ARMING -> RUNNING
        //   EXPECT: led_enout=1 (RUNNING), led_wdo=0 (no fault)
        // ============================================================
        test_num = 7;
        $display("[%0t ns] TEST 7: Release S2 -> Re-enable WDG", $time);
        s2_en = 1;
        #10_500_000;  // debounce
        #200_000;     // arm_delay

        if (led_enout == 1)
            $display("[%0t ns] TEST 7 PASS: led_enout=1, WDG RUNNING again.", $time);
        else
            $display("[%0t ns] TEST 7 FAIL: led_enout=0, WDG did not re-enable!", $time);

        if (led_wdo == 0)
            $display("[%0t ns] TEST 7 PASS: led_wdo=0, no fault.", $time);
        else
            $display("[%0t ns] TEST 7 FAIL: led_wdo=1, unexpected FAULT!", $time);

        // ============================================================
        // TEST 8: ARMING state capture
        //   Disable WDG -> Re-enable -> sample enout DURING arm_delay window
        //   Flow: IDLE -> (debounce done) -> ARMING [enout=0] -> RUNNING [enout=1]
        //   EXPECT at sample point A (inside arm_delay): led_enout=0, led_wdo=0
        //   EXPECT at sample point B (after arm_delay) : led_enout=1, led_wdo=0
        // ============================================================
        test_num = 8;
        $display("[%0t ns] TEST 8: ARMING state capture", $time);

        // Step 1: Press S2 to disable -> IDLE
        s2_en = 0;
        #10_500_000;  // debounce to IDLE

        // Step 2: Release S2 -> debounce fires -> FSM enters ARMING
        s2_en = 1;
        #10_500_000;  // debounce done - FSM now in ARMING, enout still 0

        // Sample A: inside arm_delay (150 us), enout must still be 0
        if (led_enout == 0)
            $display("[%0t ns] TEST 8 PASS (A): led_enout=0, still in ARMING.", $time);
        else
            $display("[%0t ns] TEST 8 FAIL (A): led_enout=1, ARMING skipped!", $time);

        if (led_wdo == 0)
            $display("[%0t ns] TEST 8 PASS (A): led_wdo=0, no fault during ARMING.", $time);
        else
            $display("[%0t ns] TEST 8 FAIL (A): led_wdo=1, unexpected FAULT in ARMING!", $time);

        // Step 3: Wait arm_delay to complete (150 us + margin)
        #200_000;

        // Sample B: after arm_delay, FSM -> RUNNING, enout must be 1
        if (led_enout == 1)
            $display("[%0t ns] TEST 8 PASS (B): led_enout=1, ARMING->RUNNING complete.", $time);
        else
            $display("[%0t ns] TEST 8 FAIL (B): led_enout=0, did not leave ARMING!", $time);

        // ============================================================
        // TEST 9: Disable (IDLE) while RUNNING — no FAULT on transition
        //   From RUNNING state: press S2 (en_n=0) -> IDLE immediately
        //   EXPECT: led_enout=0 (IDLE), led_wdo=0 (wdo_n stays 1, no fault output)
        //   (This differs from TEST 6 which disables from FAULT state)
        // ============================================================
        test_num = 9;
        $display("[%0t ns] TEST 9: Disable WDG mid-RUNNING -> IDLE (no fault)", $time);

        // Currently in RUNNING (from TEST 8 end). Press S2.
        s2_en = 0;
        #10_500_000;  // debounce -> final_en=0 -> FSM->IDLE

        if (led_enout == 0)
            $display("[%0t ns] TEST 9 PASS: led_enout=0, WDG -> IDLE cleanly.", $time);
        else
            $display("[%0t ns] TEST 9 FAIL: led_enout=1, WDG did not go IDLE!", $time);

        if (led_wdo == 0)
            $display("[%0t ns] TEST 9 PASS: led_wdo=0, no fault on disable.", $time);
        else
            $display("[%0t ns] TEST 9 FAIL: led_wdo=1, unexpected fault on disable!", $time);

        // ============================================================
        // TEST 10: Hardware reset (rst_n=0) clears all state mid-run
        //   Re-enable WDG -> RUNNING -> assert rst_n=0 -> check cleared
        //   Then release rst_n=1 -> WDG re-arms automatically
        //   EXPECT after rst_n=0: led_enout=0, led_wdo=0
        //   EXPECT after rst_n=1 + debounce + arm_delay: led_enout=1, led_wdo=0
        // ============================================================
        test_num = 10;
        $display("[%0t ns] TEST 10: Hardware reset (rst_n) clears state mid-run", $time);

        // Step 1: Re-enable WDG -> wait until RUNNING
        s2_en = 1;
        #10_500_000;  // debounce
        #200_000;     // arm_delay -> now RUNNING

        $display("[%0t ns] TEST 10: WDG is RUNNING, asserting rst_n=0...", $time);

        // Step 2: Assert reset
        rst_n = 0;
        #200;  // hold reset for a few ns (2 clock edges at 37ns period is enough)

        // Sample: everything must be cleared
        if (led_enout == 0)
            $display("[%0t ns] TEST 10 PASS: led_enout=0, reset cleared ENOUT.", $time);
        else
            $display("[%0t ns] TEST 10 FAIL: led_enout=1, ENOUT not cleared by reset!", $time);

        if (led_wdo == 0)
            $display("[%0t ns] TEST 10 PASS: led_wdo=0, reset cleared WDO.", $time);
        else
            $display("[%0t ns] TEST 10 FAIL: led_wdo=1, WDO not cleared by reset!", $time);

        // Step 3: Release reset -> WDG re-arms (en_n=1 still released)
        $display("[%0t ns] TEST 10: Releasing rst_n=1, WDG should re-arm...", $time);
        rst_n = 1;
        #10_500_000;  // debounce
        #200_000;     // arm_delay

        if (led_enout == 1)
            $display("[%0t ns] TEST 10 PASS: led_enout=1, WDG re-armed after reset.", $time);
        else
            $display("[%0t ns] TEST 10 FAIL: led_enout=0, WDG did not re-arm!", $time);

        if (led_wdo == 0)
            $display("[%0t ns] TEST 10 PASS: led_wdo=0, clean start after reset.", $time);
        else
            $display("[%0t ns] TEST 10 FAIL: led_wdo=1, unexpected FAULT after reset!", $time);

        $display("[%0t ns] === ALL TESTS COMPLETED ===", $time);
        $finish;
    end

endmodule
