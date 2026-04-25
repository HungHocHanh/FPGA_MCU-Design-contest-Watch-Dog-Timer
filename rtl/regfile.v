module regfile (
    input wire clk,
    input wire rst_n,

    // UART Parser Interface
    input wire [7:0] addr,
    input wire [31:0] wdata,
    input wire we,
    input wire re,
    output reg [31:0] rdata,

    // Registers mapped to Watchdog Core
    output reg en_sw,
    output reg wdi_src,
    output reg clr_fault, // Write 1 to clear
    output reg [31:0] tWD_ms,
    output reg [31:0] tRST_ms,
    output reg [15:0] arm_delay_us,
    
    // Status from Watchdog Core
    input wire en_effective,
    input wire fault_active,
    input wire enout,
    input wire wdo,
    input wire last_kick_src
);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            en_sw <= 0;
            wdi_src <= 0;
            clr_fault <= 0;
            tWD_ms <= 32'd1600;
            tRST_ms <= 32'd200;
            arm_delay_us <= 16'd150;
            rdata <= 0;
        end else begin
            clr_fault <= 0; // Auto clear

            if (we) begin
                case (addr)
                    8'h00: begin // CTRL
                        en_sw <= wdata[0];
                        wdi_src <= wdata[1];
                        if (wdata[2]) clr_fault <= 1;
                    end
                    8'h04: tWD_ms <= wdata;
                    8'h08: tRST_ms <= wdata;
                    8'h0C: arm_delay_us <= wdata[15:0];
                endcase
            end

            if (re) begin
                case (addr)
                    8'h00: rdata <= {29'b0, 1'b0, wdi_src, en_sw};
                    8'h04: rdata <= tWD_ms;
                    8'h08: rdata <= tRST_ms;
                    8'h0C: rdata <= {16'b0, arm_delay_us};
                    8'h10: rdata <= {27'b0, last_kick_src, wdo, enout, fault_active, en_effective};
                    default: rdata <= 0;
                endcase
            end
        end
    end
endmodule
