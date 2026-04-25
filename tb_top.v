`timescale 1ns/1ps
module tb_top();

    reg clk;
    reg s1_wdi;
    reg s2_en;
    wire led_wdo;
    wire led_enout;
    reg rx;
    wire tx;

    top uut (
        .clk(clk),
        .wdi_n(s1_wdi),
        .en_n(s2_en),
        .wdo_led_n(led_wdo),
        .enout_led_n(led_enout),
        .uart_rx(rx),
        .uart_tx(tx)
    );

    initial begin
        clk = 0;
        forever #18.518 clk = ~clk; // ~27MHz
    end

    // Fast simulation helper
    // In tb, the real 1ms requires 27K cycles.
    // For ModelSim to not take forever simulating 2 seconds, we can just run it out, 
    // 2s real time = ~2 billion ns = 2 seconds of sim time, which is totally fast enough for modelsim.

    initial begin
        s1_wdi = 1;
        s2_en = 1;
        rx = 1;

        #2000;
        $display("[%0t] Starting Simulation...", $time);
        
        // 1. Disable / Enable Test
        $display("[%0t] Pushing EN button (Active Low)...", $time);
        s2_en = 0; 
        
        // Wait arm delay 150us
        #160_000; 
        $display("[%0t] Arm Delay elapsed. Watchdog is Running.", $time);
        
        if (led_enout != 0) $display("[%0t] FAIL: ENOUT is not active!", $time);
        else $display("[%0t] PASS: ENOUT is active.", $time);
        
        // 2. Normal Kick Test (send kick before timeout)
        #500_000; 
        $display("[%0t] Kicking watchdog via WDI...", $time);
        s1_wdi = 0;
        #50_000;
        s1_wdi = 1;

        // 3. Timeout Test (Wait 1600ms = 1.6s = 1.6e9 ns)
        $display("[%0t] Waiting for 1600ms timeout...", $time);
        #(1_650_000_000); 
        
        if (led_wdo == 0) $display("[%0t] PASS: WDO Fault occurred!", $time);
        else $display("[%0t] FAIL: WDO Fault did NOT occur!", $time);

        // Wait RST hold time (200ms = 0.2s = 200e6 ns)
        #(210_000_000);
        if (led_wdo == 1) $display("[%0t] PASS: WDO Fault Released!", $time);
        else $display("[%0t] FAIL: WDO Fault NOT Released!", $time);

        $display("[%0t] All Tests Completed.", $time);
        $finish;
    end

endmodule
