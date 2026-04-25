vlib work
vmap work work
vlog rtl/sync_debounce.v rtl/uart_rx.v rtl/uart_tx.v rtl/uart_frame_parser.v rtl/regfile.v rtl/watchdog_core.v rtl/top.v tb_top.v
vsim -voptargs="+acc" tb_top
add wave /tb_top/*
run -all
