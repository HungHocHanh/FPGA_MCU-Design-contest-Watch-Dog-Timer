module top (
    input wire clk,
    input wire rst_n,
    input wire wdi_n,
    input wire en_n,
    output wire wdo_led_n,
    output wire enout_led_n,
    input wire uart_rx,
    output wire uart_tx
);

    wire [7:0] rx_data, tx_data;
    wire rx_valid, tx_valid, tx_ready;
    
    uart_rx u_rx (
        .clk(clk), .rst_n(rst_n), .rxd(uart_rx), 
        .data(rx_data), .valid(rx_valid)
    );
    
    uart_tx u_tx (
        .clk(clk), .rst_n(rst_n), .tdata(tx_data), .tvalid(tx_valid),
        .tready(tx_ready), .tx(uart_tx)
    );
    
    wire [7:0] reg_addr;
    wire [31:0] reg_wdata, reg_rdata;
    wire reg_we, reg_re, soft_kick;
    
    uart_frame_parser u_parser (
        .clk(clk), .rst_n(rst_n),
        .rx_data(rx_data), .rx_valid(rx_valid),
        .tx_data(tx_data), .tx_valid(tx_valid), .tx_ready(tx_ready),
        .reg_addr(reg_addr), .reg_wdata(reg_wdata), .reg_we(reg_we), 
        .reg_re(reg_re), .reg_rdata(reg_rdata), .soft_kick(soft_kick)
    );
    
    wire en_sw, wdi_src, clr_fault;
    wire [31:0] twd, trst;
    wire [15:0] tarm;
    wire en_eff, fault_act, wdo_val, enout_val, last_kick;
    
    regfile u_reg (
        .clk(clk), .rst_n(rst_n),
        .addr(reg_addr), .wdata(reg_wdata), .we(reg_we), .re(reg_re), .rdata(reg_rdata),
        .en_sw(en_sw), .wdi_src(wdi_src), .clr_fault(clr_fault),
        .tWD_ms(twd), .tRST_ms(trst), .arm_delay_us(tarm),
        .en_effective(en_eff), .fault_active(fault_act), 
        .enout(enout_val), .wdo(wdo_val), .last_kick_src(last_kick)
    );
    
    wire wdi_clean;
    wire wdi_fall;
    wire en_clean;
    
    sync_debounce u_wdi_deb (
        .clk(clk), .rst_n(rst_n), .btn_n(wdi_n),
        .btn_clean(wdi_clean), .btn_fall(wdi_fall)
    );
    
    sync_debounce u_en_deb (
        .clk(clk), .rst_n(rst_n), .btn_n(en_n),
        .btn_clean(en_clean), .btn_fall()
    );

    wire final_en = en_sw | (~en_clean);
    wire final_kick = (wdi_src == 1'b1) ? 1'b0 : wdi_fall;
    assign en_eff = final_en;

    reg last_kick_reg;
    assign last_kick = last_kick_reg;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) last_kick_reg <= 0;
        else if (soft_kick) last_kick_reg <= 1;
        else if (final_kick) last_kick_reg <= 0;
    end

    watchdog_core u_wdg (
        .clk(clk), .rst_n(rst_n),
        .en(final_en), .kick(final_kick),
        .uart_kick(soft_kick), .clr_fault(clr_fault),
        .twd_ms(twd), .trst_ms(trst), .arm_delay_us(tarm),
        .wdo_n(wdo_val), .enout(enout_val),
        .fault_active(fault_act)
    );

    // Output mapping to LEDs (active-high: 1 = sáng, 0 = tắt)
    assign wdo_led_n = ~wdo_val;    // D3: sáng khi FAULT
    assign enout_led_n = enout_val; // D4: sáng khi RUNNING/FAULT

endmodule
