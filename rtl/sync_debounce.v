module sync_debounce #(
    parameter CLK_HZ      = 27_000_000,
    parameter DEBOUNCE_MS = 10
) (
    input  wire clk, rst_n,
    input  wire btn_n,       // Active-low từ board
    output reg  btn_clean,   // 1 = đang nhấn (sau debounce)
    output reg  btn_fall     // Pulse 1 clock khi falling edge
);
    localparam CNT_MAX = CLK_HZ / 1000 * DEBOUNCE_MS;
    reg [1:0]  sync_ff;
    reg [$clog2(CNT_MAX+1)-1:0] cnt;
    reg prev;
    wire btn_sync = ~sync_ff[1]; // Đảo vì active-low

    always @(posedge clk or negedge rst_n)
        if (!rst_n) sync_ff <= 2'b00;
        else        sync_ff <= {sync_ff[0], btn_n};

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin cnt <= 0; prev <= 0; btn_clean <= 0; btn_fall <= 0;
        end else begin
            btn_fall <= 0;
            if (btn_sync !== prev) begin
                cnt <= cnt + 1'b1;
                if (cnt >= CNT_MAX-1) begin
                    prev      <= btn_sync;
                    btn_clean <= btn_sync;
                    btn_fall  <= (~btn_sync);  // falling = released → 0
                    cnt       <= 0;
                end
            end else cnt <= 0;
        end
    end
endmodule
