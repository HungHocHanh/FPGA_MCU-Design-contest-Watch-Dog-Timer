# Chi Tiết Kiến Trúc Code: Watchdog Monitor UART
Tài liệu này giải thích chi tiết cấu trúc từng đoạn code Verilog trong dự án, logic hoạt động và lý do thiết kế (Tại sao lại làm thế).

---

## 1. `rtl/top.v` (Top-Level Module)

**Đoạn code quan trọng:**
```verilog
    // Output mapping to LEDs (active low, turn on when 0)
    assign led_wdo = wdo_val;
    assign led_enout = ~enout_val;
```

* **Chức năng:** Là file khung, nhiệm vụ duy nhất là khởi tạo (instantiate) tất cả các module con và đấu dây (wire) chúng lại với nhau. Nó cũng tạo ra tín hiệu reset hệ thống ban đầu (`rst_n`) bằng một bộ đếm nhỏ sử dụng xung clock.
* **Tại sao lại làm thế?**
  * **Tính module hoá:** Tách rời giao diện I/O vật lý của FPGA khỏi logic bên trong. Các chân ở `top.v` sẽ map 1-1 với file `.cst`.
  * **Giải quyết Active-Low LEDs:** Trên board Kiwi 1P5, LED sáng khi tín hiệu = 0 (kéo xuống GND). Do logic nội bộ đang hiểu `wdo_val` = 0 là lúc Fault nên gắn trực tiếp vào `led_wdo`. Còn `enout_val` = 1 là lúc Running, ta đảo bit `~enout_val` để đèn LED sáng. Điều này giúp code trong các khối logic duy trì tính chuẩn mực (1 là True) mà không cần bận tâm phần cứng LED.

---

## 2. `rtl/sync_debounce.v` (Mạch chống dội nút nhấn)

**Đoạn code quan trọng:**
```verilog
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
             sync1 <= 1'b1; sync2 <= 1'b1;
        ...
        end else begin
             sync1 <= in_async; sync2 <= sync1;
        end
    end
```

* **Chức năng:** Module này lấy tín hiệu nút bấm hoặc tín hiệu ngoại vi (`in_async`), đẩy qua 2 flip-flop (sync1, sync2), sau đó đưa vào một bộ đếm `cnt` delay khoảng 20ms (`MAX_COUNT`). Chỉ khi tín hiệu ổn định không đổi trong 20ms này thì ngõ ra `out_stable` mới cập nhật.
* **Tại sao lại làm thế?** 
  * **2-stage synchronizer:** Thiết kế với 2 flip-flop nhằm chống hiện tượng dao động lửng (Metastability) khi xung nội và tín hiệu nhấn nút không đồng bộ với nhau. Nếu không có nó, các trạng thái FSM đằng sau có thể bị treo.
  * **Bộ đếm 20ms:** Nút bấm cơ học khi bị nhấn sẽ bị rung (bounce) tạo ra hàng loạt xung 0-1-0-1 rác trong vài mili-giây. Delay 20ms bảo đảm chỉ nhận diện đúng 1 lần bấm duy nhất, giúp nút "Kick" Watchdog không bị đếm nhầm.

---

## 3. `rtl/uart_rx.v` & `rtl/uart_tx.v` (Giao tiếp Nối tiếp)

**Đoạn code quan trọng ở `uart_rx.v` (START Bit Detection):**
```verilog
    1: begin // START
        if (cnt == HALF_PERIOD) begin ...
```

* **Chức năng:** Bộ thu tín hiệu UART. 
* **Tại sao lại làm thế?** Ở trạng thái lấy bit START, nó đợi đến `HALF_PERIOD` (đúng điểm giữa của 1 chu kì xung baudrate) rồi mới chốt tín hiệu. Điều này giúp hạn chế tối đa việc đọc sai bit nếu nhiễu xảy ra ở đầu hoặc cuối sườn dữ liệu truyền.

**Đoạn code quan trọng ở `uart_tx.v` (Shift Register):**
```verilog
    shift_reg <= {1'b1, tdata, 1'b0}; // STOP, DATA, START
```

* **Chức năng:** Bộ phát UART. 
* **Tại sao lại làm thế?** Module này nối luôn bit START (0), 8-bit Data, và bit STOP (1) vào cùng 1 thanh ghi dịch (`shift_reg` 10 bit). Khi đến lượt, nó chỉ việc dịch (shift) thanh ghi này qua phải mỗi chu kỳ bit. Phương pháp này giúp tiết kiệm tài nguyên flip-flop của FPGA và giảm số lượng logic so với việc dùng MUX rườm rà.

---

## 4. `rtl/uart_frame_parser.v` (Bộ Phân giải Lệnh Header)

**Đoạn code quan trọng (Máy trạng thái xử lý khung UART):**
```verilog
    S_IDLE: begin
        if (rx_valid && rx_data == 8'h55) begin
             rx_state <= S_CMD;
```

* **Chức năng:** Nhận từng byte rời rạc, gom thành 1 tập lệnh hoàn chỉnh. Nếu dbyte đầu không phải `0x55`, nó bỏ qua hoàn toàn. Ngoài ra nó tính toán mã `checksum` bằng hàm XOR tuần tự để đối chiếu byte cuối cùng.
* **Tại sao lại làm thế?** Bởi vì UART rất dễ bị nhiễu dây sinh ra byte rác, hay khi rút cắm dây dở dang cũng tạo ra dữ liệu hỏng. Bọc bằng Header ảo (`0x55`) và Checksum giúp hệ thống FPGA nhận diện được đâu mới là một khung cấu hình chuẩn chỉnh. Nó bảo vệ các thanh ghi giới hạn an toàn (`tWD`, `tRST`) không bị ghi đè bởi rác từ đường truyền.

---

## 5. `rtl/regfile.v` (Bộ File Thanh Ghi)

**Đoạn code quan trọng:**
```verilog
    assign rdata = (addr == 8'h00) ? r_ctrl :
                   (addr == 8'h04) ? r_twd : ...
```

* **Chức năng:** Tạo ra vùng nhớ gồm 4 thanh ghi chứa thông số cấu hình và 1 thanh ghi ảo lưu Status của hệ thống. 
* **Tại sao lại làm thế?** Để tách bạch mạch UART (tốc độ chậm, thiên về thông tin) và Watchdog Core (tốc độ cao, chạy FSM liên tục). Nhờ có RegFile, FSM có thể liên tục lấy tham số cấu hình nhanh chóng thay vì phải đợi tín hiệu nối tiếp. Nó đóng vai trò như Memory mapped I/O trong các dòng vi điều khiển ARM. Thanh ghi `addr 8'h00` có self-clear đặc biệt ở bit [2] (clear lỗi rồi tự rớt về 0 tránh bị dính trạng thái).

---

## 6. `rtl/watchdog_core.v` (Lõi Watchdog FSM)

**Đoạn code quan trọng (Xử lý State Machine):**
```verilog
    ST_RUNNING: begin
        if (valid_kick) begin
            cnt <= 0; 
        end else if (cnt >= tWD_ms * CYCLES_PER_MS) begin
            state <= ST_FAULT;
...
```

* **Chức năng:** Trái tim của toàn hệ thống, mô phỏng cách IC phần cứng TPS3431 hoạt động thông qua một Máy Trạng Thái Hữu Hạn (FSM). Bao gồm:
  - `ST_DISABLED`: Tắt Watchdog, không làm gì.
  - `ST_ARMING`: Giai đoạn trễ lúc khởi động. Delay `arm_delay_us`.
  - `ST_RUNNING`: Lúc hoạt động bình thường, liên tục chờ Kick.
  - `ST_FAULT`: Kích hoạt chân xuất tín hiệu lỗi sang logic thấp để reset MCU bên ngoài. Trong thời gian `tRST`, sẽ đếm ngược rồi tự phục hồi về `ST_RUNNING`.
* **Tại sao lại làm thế?** 
  - FSM là cách code quy chuẩn nhất để điều khiển luồng thời gian thực trong FPGA/Hardware, rõ ràng và không bị khóa (non-blocking) lẫn nhau. 
  - Khối lượng thời gian được tính dựa trên tần số xung nhịp đồng hồ FPGA chuẩn (`CYCLES_PER_MS = 27,000,000 / 1000`). Bằng việc mang các tham số cấu hình tĩnh (`tWD_ms`) nhân trực tiếp với số cycle, FSM đảm bảo độ chính xác đếm ngược của hệ thống gần như tuyệt đối (jitter nằm mức nanosecond).
  - Tách logic phân quyền `valid_kick` ra ngoài FSM giúp cho việc cấu hình "ưu tiên KICK bằng phần mềm (UART) hay bằng nút cứng" được thực thi minh bạch, FSM bên dưới không cần quan tâm xung kick được tạo từ đâu, hễ có xung là nó sẽ `cnt <= 0` chống tràn.
