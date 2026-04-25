module watchdog_core #(
    parameter CLK_HZ = 27_000_000
) (
    input  wire        clk, rst_n,
    input  wire        en,           // Enable (active-high, sau debounce)
    input  wire        kick,         // Falling edge từ WDI button
    input  wire        uart_kick,    // Kick từ UART CMD 0x03
    input  wire        clr_fault,    // CLR_FAULT bit từ CTRL register
    input  wire [31:0] twd_ms,       // Watchdog timeout (ms)
    input  wire [31:0] trst_ms,      // WDO hold time (ms)
    input  wire [15:0] arm_delay_us, // Arm delay (µs)
    output reg         wdo_n,        // WDO active-low
    output reg         enout,        // ENOUT
    output reg         fault_active  // Status flag
);
    localparam CYC_PER_MS = CLK_HZ / 1000;
    localparam CYC_PER_US = CLK_HZ / 1_000_000;
    localparam [1:0] IDLE=0, ARMING=1, RUNNING=2, FAULT=3;

    reg [1:0]  state;
    reg [31:0] timer;
    wire any_kick = kick | uart_kick;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state<=IDLE; timer<=0; wdo_n<=1; enout<=0; fault_active<=0;
        end else case (state)
        IDLE: begin
            wdo_n<=1; enout<=0; fault_active<=0;
            if (en) begin state<=ARMING; timer<=arm_delay_us*CYC_PER_US; end
        end
        ARMING: begin  // Bỏ qua WDI trong arm_delay
            if (!en) state<=IDLE;
            else if (timer>0) timer<=timer-32'd1;
            else begin state<=RUNNING; timer<=twd_ms*CYC_PER_MS; enout<=1; end
        end
        RUNNING: begin
            if (!en) begin state<=IDLE; enout<=0; end
            else if (any_kick) timer<=twd_ms*CYC_PER_MS; // Reset timer
            else if (timer>0)  timer<=timer-32'd1;
            else begin  // TIMEOUT!
                state<=FAULT; wdo_n<=0; fault_active<=1;
                timer<=trst_ms*CYC_PER_MS;
            end
        end
        FAULT: begin
            if (clr_fault || !en) begin
                wdo_n<=1; fault_active<=0;
                if (en) begin state<=RUNNING; timer<=twd_ms*CYC_PER_MS; end
                else    begin state<=IDLE;    enout<=0; end
            end else if (timer>0) timer<=timer-32'd1;
            else begin  // tRST hết, bắt đầu chu kỳ mới
                state<=RUNNING; wdo_n<=1; fault_active<=0;
                timer<=twd_ms*CYC_PER_MS;
            end
        end
        endcase
    end
endmodule
