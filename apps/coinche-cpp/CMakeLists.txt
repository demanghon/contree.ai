cmake_minimum_required(VERSION 3.14)
project(cointree_cpp LANGUAGES CXX)
# Optimization Flags for "Super Vectorized" Performance
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
if(MSVC)
    add_compile_options(/O2 /arch:AVX2)
else()
    add_compile_options(-O3 -march=native -fvisibility=hidden)
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Find Python and Pybind11
find_package(Python 3.8 COMPONENTS Interpreter Development)
# We assume pybind11 is installed in the python environment
execute_process(
    COMMAND "${Python_EXECUTABLE}" -m pybind11 --cmake
    OUTPUT_VARIABLE PYBIND11_CMAKE_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
)
if(NOT EXISTS "${PYBIND11_CMAKE_DIR}")
    message(STATUS "Pybind11 not found via python module, attempting fetch...")
    include(FetchContent)
    FetchContent_Declare(
      pybind11
      GIT_REPOSITORY https://github.com/pybind/pybind11.git
      GIT_TAG        v2.11.1
    )
    FetchContent_MakeAvailable(pybind11)
else()
    list(APPEND CMAKE_PREFIX_PATH "${PYBIND11_CMAKE_DIR}")
    find_package(pybind11 CONFIG REQUIRED)
endif()

# Source Files
set(SOURCES bindings.cpp search/minimax.cpp)

# Define the Extension Module
pybind11_add_module(cointree_cpp ${SOURCES})

# Include Directories
target_include_directories(cointree_cpp PRIVATE .)
target_include_directories(cointree_cpp PRIVATE ${PYTHON_INCLUDE_DIRS})

# Install to src/engine for easy import
install(TARGETS cointree_cpp LIBRARY DESTINATION "${CMAKE_SOURCE_DIR}/src/engine")
