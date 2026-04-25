module uart_tx #(
    parameter CLK_FREQ = 27_000_000,
    parameter BAUD_RATE = 9600
)(
    input wire clk,
    input wire rst_n,
    input wire [7:0] tdata,
    input wire tvalid,
    output reg tready,
    output reg tx
);

    localparam BIT_PERIOD = CLK_FREQ / BAUD_RATE;

    reg [15:0] cnt;
    reg [3:0] bit_idx;
    reg [9:0] shift_reg;
    reg [1:0] state; // 0: IDLE, 1: TX

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= 0;
            cnt <= 0;
            bit_idx <= 0;
            shift_reg <= 10'b1111111111;
            tready <= 1;
            tx <= 1;
        end else begin
            case (state)
                0: begin // IDLE
                    tx <= 1;
                    if (tvalid && tready) begin
                        shift_reg <= {1'b1, tdata, 1'b0}; // STOP, DATA, START
                        tready <= 0;
                        state <= 1;
                        cnt <= 0;
                        bit_idx <= 0;
                    end
                end
                1: begin // TX
                    tx <= shift_reg[0];
                    if (cnt == BIT_PERIOD - 1) begin
                        cnt <= 0;
                        shift_reg <= {1'b1, shift_reg[9:1]};
                        if (bit_idx == 4'd9) begin
                            tready <= 1;
                            state <= 0;
                        end else begin
                            bit_idx <= bit_idx + 4'd1;
                        end
                    end else begin
                        cnt <= cnt + 16'd1;
                    end
                end
            endcase
        end
    end
endmodule
