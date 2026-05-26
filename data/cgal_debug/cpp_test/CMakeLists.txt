cmake_minimum_required(VERSION 3.16)
project(cgal_boolean_debug LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_BUILD_TYPE Release)

if(MSVC)
    add_compile_options(/Zm1200)
endif()

include(ExternalProject)

# CGAL 6.2-beta1 (header-only, no build)
set(CGAL62_DIR "${CMAKE_CURRENT_SOURCE_DIR}/external/cgal62")
if(NOT EXISTS "${CGAL62_DIR}/include")
    message(STATUS "Downloading CGAL 6.2-beta1...")
    ExternalProject_Add(cgal62_download
        URL https://github.com/CGAL/cgal/releases/download/v6.2-beta1/CGAL-6.2-beta1.zip
        SOURCE_DIR "${CGAL62_DIR}"
        CONFIGURE_COMMAND ""
        BUILD_COMMAND ""
        INSTALL_COMMAND ""
        LOG_DOWNLOAD ON
    )
endif()

set(EXTERNAL_DIR "C:/brg/code/compas_cgal/external")
set(CGAL_INCLUDE_DIR "${CGAL62_DIR}/include")
set(BOOST_INCLUDE_DIR "${EXTERNAL_DIR}/boost")
set(EIGEN_INCLUDE_DIR "${EXTERNAL_DIR}/eigen")

include_directories(
    ${CGAL_INCLUDE_DIR}
    ${BOOST_INCLUDE_DIR}
    ${EIGEN_INCLUDE_DIR}
)

add_definitions(
    -DCGAL_HEADER_ONLY
    -DBOOST_ALL_NO_LIB
    -DBOOST_ALL_DYN_LINK=0
    -DCGAL_DISABLE_GMP
    -DCGAL_USE_BOOST_MP
)

set(CGAL_DO_NOT_USE_MPZF ON CACHE BOOL "")
set(CGAL_USE_GMPXX OFF CACHE BOOL "")
set(CGAL_DISABLE_GMP ON CACHE BOOL "")
set(CMAKE_DISABLE_FIND_PACKAGE_GMP ON CACHE BOOL "")
set(CMAKE_DISABLE_FIND_PACKAGE_MPFR ON CACHE BOOL "")
set(CGAL_NT_USE_BOOST_MP ON CACHE BOOL "")

add_executable(boolean_test main.cpp)
if(TARGET cgal62_download)
    add_dependencies(boolean_test cgal62_download)
endif()
