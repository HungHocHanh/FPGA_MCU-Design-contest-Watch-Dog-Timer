module uart_rx #(
    parameter CLK_HZ = 27_000_000,
    parameter BAUD   = 9600
) (
    input  wire       clk, rst_n, rxd,
    output reg  [7:0] data,
    output reg        valid   // 1-clock pulse khi nhận xong 1 byte
);
    localparam FULL = CLK_HZ / BAUD;
    localparam HALF = FULL / 2;
    reg [1:0] sync; reg [15:0] cnt; reg [3:0] bit_idx;
    reg [7:0] shift; reg active;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin sync<=2'b11; active<=0; valid<=0; end
        else begin
            sync  <= {sync[0], rxd};
            valid <= 0;
            if (!active) begin
                if (!sync[1]) begin  // Start bit detected
                    active<=1; cnt<=(FULL+HALF-1); bit_idx<=0;
                end
            end else if (cnt>0) cnt<=cnt-16'd1;
            else begin
                cnt <= FULL[15:0]-16'd1;
                if (bit_idx<8) begin
                    shift   <= {sync[1], shift[7:1]};
                    bit_idx <= bit_idx+4'd1;
                end else begin  // Stop bit
                    active<=0; data<=shift; valid<=1;
                end
            end
        end
    end
endmodule
