vlib work
vmap work work
vlog rtl/sync_debounce.v rtl/uart_rx.v rtl/uart_tx.v rtl/uart_frame_parser.v rtl/regfile.v rtl/watchdog_core.v rtl/top.v tb_top.v
vsim -voptargs="+acc" tb_top

add wave -noupdate -divider "Testbench Signals"
add wave -noupdate -radix unsigned /tb_top/test_num
add wave -noupdate /tb_top/clk
add wave -noupdate /tb_top/rst_n
add wave -noupdate /tb_top/s1_wdi
add wave -noupdate /tb_top/s2_en
add wave -noupdate /tb_top/led_wdo
add wave -noupdate /tb_top/led_enout

add wave -noupdate -divider "Watchdog Core State"
add wave -noupdate /tb_top/uut/u_wdg/state
add wave -noupdate -radix unsigned /tb_top/uut/u_wdg/timer
add wave -noupdate /tb_top/uut/u_wdg/en
add wave -noupdate /tb_top/uut/u_wdg/kick
add wave -noupdate /tb_top/uut/u_wdg/uart_kick
add wave -noupdate /tb_top/uut/u_wdg/fault_active

add wave -noupdate -divider "Registers"
add wave -noupdate -radix unsigned /tb_top/uut/u_reg/tWD_ms
add wave -noupdate -radix unsigned /tb_top/uut/u_reg/tRST_ms
add wave -noupdate -radix unsigned /tb_top/uut/u_reg/arm_delay_us
add wave -noupdate /tb_top/uut/u_reg/en_sw

run -all
