module uart_frame_parser (
    input wire clk,
    input wire rst_n,

    // UART RX Interface
    input wire [7:0] rx_data,
    input wire rx_valid,

    // UART TX Interface
    output reg [7:0] tx_data,
    output reg tx_valid,
    input wire tx_ready,

    // Register File Interface
    output reg [7:0] reg_addr,
    output reg [31:0] reg_wdata,
    output reg reg_we,
    output reg reg_re,
    input wire [31:0] reg_rdata,
    
    // Internal Kick
    output reg soft_kick
);

    // internal states
    localparam S_IDLE = 0, S_CMD = 1, S_ADDR = 2, S_LEN = 3, S_DATA = 4, S_CHK = 5;
    localparam S_TX_PREPARE = 6, S_TX_WAIT = 7, S_TX_LOAD = 8;

    reg [3:0] rx_state;
    reg [7:0] cmd;
    reg [7:0] addr;
    reg [7:0] len;
    reg [7:0] chk_acc;
    
    reg [31:0] data_buf;
    reg [1:0] data_idx;

    // Tx buffer
    reg [7:0] tx_buffer [0:8];
    reg [3:0] tx_len;
    reg [3:0] tx_idx;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rx_state <= S_IDLE;
            reg_we <= 0;
            reg_re <= 0;
            soft_kick <= 0;
            tx_valid <= 0;
            tx_data <= 0;
        end else begin
            reg_we <= 0;
            reg_re <= 0;
            soft_kick <= 0;

            case (rx_state)
                S_IDLE: begin
                    if (rx_valid && rx_data == 8'h55) begin
                        rx_state <= S_CMD;
                        chk_acc <= 0;
                    end
                end
                S_CMD: begin
                    if (rx_valid) begin
                        cmd <= rx_data;
                        chk_acc <= chk_acc ^ rx_data;
                        rx_state <= S_ADDR;
                    end
                end
                S_ADDR: begin
                    if (rx_valid) begin
                        addr <= rx_data;
                        chk_acc <= chk_acc ^ rx_data;
                        rx_state <= S_LEN;
                    end
                end
                S_LEN: begin
                    if (rx_valid) begin
                        len <= rx_data;
                        chk_acc <= chk_acc ^ rx_data;
                        if (rx_data == 0) begin
                            rx_state <= S_CHK;
                        end else begin
                            rx_state <= S_DATA;
                            data_idx <= 0;
                        end
                    end
                end
                S_DATA: begin
                    if (rx_valid) begin
                        chk_acc <= chk_acc ^ rx_data;
                        case (data_idx)
                            0: data_buf[7:0] <= rx_data;
                            1: data_buf[15:8] <= rx_data;
                            2: data_buf[23:16] <= rx_data;
                            3: data_buf[31:24] <= rx_data;
                        endcase
                        if (data_idx + 2'd1 == len[1:0] || data_idx == 2'd3) begin
                            rx_state <= S_CHK;
                        end else begin
                            data_idx <= data_idx + 2'd1;
                        end
                    end
                end
                S_CHK: begin
                    if (rx_valid) begin
                        if (chk_acc == rx_data) begin
                            case (cmd)
                                8'h01: begin // WRITE
                                    reg_addr <= addr;
                                    reg_wdata <= data_buf;
                                    reg_we <= 1;
                                    
                                    tx_buffer[0] <= 8'h55;
                                    tx_buffer[1] <= 8'h01;
                                    tx_buffer[2] <= addr;
                                    tx_buffer[3] <= 8'h00;
                                    tx_buffer[4] <= 8'h01 ^ addr ^ 8'h00;
                                    tx_len <= 5;
                                    rx_state <= S_TX_LOAD;
                                end
                                8'h02: begin // READ
                                    reg_addr <= addr;
                                    reg_re <= 1;
                                    // Chờ 1 cycle để reg_rdata ổn định
                                    rx_state <= S_TX_PREPARE;
                                end
                                8'h03: begin // KICK
                                    soft_kick <= 1;
                                    tx_buffer[0] <= 8'h55;
                                    tx_buffer[1] <= 8'h03;
                                    tx_buffer[2] <= 8'h00;
                                    tx_buffer[3] <= 8'h00;
                                    tx_buffer[4] <= 8'h03 ^ 8'h00 ^ 8'h00;
                                    tx_len <= 5;
                                    rx_state <= S_TX_LOAD;
                                end
                                8'h04: begin // STATUS
                                    reg_addr <= 8'h10;
                                    reg_re <= 1;
                                    // Chờ 1 cycle để reg_rdata ổn định
                                    rx_state <= S_TX_PREPARE;
                                end
                            endcase
                        end else begin
                            rx_state <= S_IDLE;
                        end
                    end
                end
                S_TX_PREPARE: begin
                    // Cycle này reg_rdata đã ổn định, fill buffer
                    tx_buffer[0] <= 8'h55;
                    tx_buffer[1] <= cmd;
                    tx_buffer[2] <= (cmd == 8'h02) ? addr : 8'h10;
                    tx_buffer[3] <= 8'h04;
                    tx_buffer[4] <= reg_rdata[7:0];
                    tx_buffer[5] <= reg_rdata[15:8];
                    tx_buffer[6] <= reg_rdata[23:16];
                    tx_buffer[7] <= reg_rdata[31:24];
                    tx_buffer[8] <= cmd ^ ((cmd == 8'h02) ? addr : 8'h10) ^ 8'h04 ^ reg_rdata[7:0] ^ reg_rdata[15:8] ^ reg_rdata[23:16] ^ reg_rdata[31:24];
                    tx_len <= 9;
                    rx_state <= S_TX_LOAD;
                end
                S_TX_LOAD: begin
                    // Buffer đã fill xong, bắt đầu gửi byte đầu tiên
                    tx_idx <= 0;
                    tx_valid <= 1;
                    tx_data <= tx_buffer[0];
                    rx_state <= S_TX_WAIT;
                end
                S_TX_WAIT: begin
                    if (tx_ready && tx_valid) begin
                        if (tx_idx + 4'd1 == tx_len) begin
                            tx_valid <= 0;
                            rx_state <= S_IDLE;
                        end else begin
                            tx_idx <= tx_idx + 4'd1;
                            tx_data <= tx_buffer[tx_idx + 4'd1];
                            tx_valid <= 1;
                        end
                    end
                end
            endcase
        end
    end
endmodule

