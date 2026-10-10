# tsbus: the v3 card's bus code as a MicroPython C module (phase 3 of the v3
# port plan). Built into the TSPICO_V3 board (src/boards/TSPICO_V3 sets
# USER_C_MODULES to this file).

add_library(usermod_tsbus INTERFACE)

target_sources(usermod_tsbus INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/tsbus.c
)

target_include_directories(usermod_tsbus INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}
)

pico_generate_pio_header(usermod_tsbus ${CMAKE_CURRENT_LIST_DIR}/tsbus.pio)

target_link_libraries(usermod_tsbus INTERFACE
    hardware_dma
    hardware_pio
    hardware_vreg
    pico_multicore
)

target_link_libraries(usermod INTERFACE usermod_tsbus)
