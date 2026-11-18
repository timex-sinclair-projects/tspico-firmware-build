# tsbus: the v3 card's bus code as a MicroPython C module (phase 3 of the v3
# port plan). Built into the TSPICO_V3 board (src/boards/TSPICO_V3 sets
# USER_C_MODULES to this file).

add_library(usermod_tsbus INTERFACE)

target_sources(usermod_tsbus INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/tsbus.c
    ${CMAKE_CURRENT_LIST_DIR}/usart8251.c
    ${CMAKE_CURRENT_LIST_DIR}/modem2050.c
    ${CMAKE_CURRENT_LIST_DIR}/sp0256.c
    ${CMAKE_CURRENT_LIST_DIR}/megabank.c
)

# usart8251.c, modem2050.c, sp0256.c and megabank.c are plain C (host tests compile them too); on
# the card they take __not_in_flash_func from pico.h, so core 1 never runs
# them from flash.
target_compile_definitions(usermod_tsbus INTERFACE U8251_ON_PICO=1)

target_include_directories(usermod_tsbus INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}
)

# The issue-#254 diagnostic build: TSBUS_DIAG=1 in the environment (use its
# own BUILD directory, so the normal build's objects aren't reused).
if(DEFINED ENV{TSBUS_DIAG})
    add_compile_definitions(TSBUS_DIAG=$ENV{TSBUS_DIAG})   # the QSTR scan sees it too
endif()

pico_generate_pio_header(usermod_tsbus ${CMAKE_CURRENT_LIST_DIR}/tsbus.pio)

target_link_libraries(usermod_tsbus INTERFACE
    hardware_dma
    hardware_pio
    hardware_uart
    hardware_vreg
    pico_multicore
)

# Every flash erase and program goes through tsbus.c's wrappers, which pause
# the modem's DMA channels (they touch APB) meanwhile (the 2068's memory reads are
# answered by DMA, and a stalled APB write holds the DMA up).
target_link_options(usermod_tsbus INTERFACE
    -Wl,--wrap=flash_range_erase
    -Wl,--wrap=flash_range_program
)

target_link_libraries(usermod INTERFACE usermod_tsbus)
