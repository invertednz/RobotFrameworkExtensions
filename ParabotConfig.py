###############################################################################################################
# Configure Selenium GRID:
# Parabot is able to auto-start Selenium Hub and Remote Controls, to enable this feature set 
# AUTOSTART_SELENIUM to True. To disable it set the variable to False. If the feature is enable
# ANT_BATCH_FILE and SELENIUM_GRID_DIR need to be specified.
# Note: if the feature is disabled Parabot assumes a Selenium Hub with sufficient Remote Controls
# is running on http://127.0.0.1:4444. One RC per test block (see below) will be required.
###############################################################################################################
# Configure Logging:
# A directory to place log files in
LOG_DIR = "Logs"
###############################################################################################################
# Configure parallelization:
# Test suite will be split into blocks of x tests, these blocks will be executed in parallel.
# MAX_PARALLEL_TESTS defines the maximum number of blocks and therefore the maximum number of 
# tests being executed in parallel. To avoid blocks from containing to few tests, MIN_TESTS_PER_BLOCK
# specifies the minimum number of tests required to build a block.
# E.g. a suite with 20 parallel Tests will be split into: 
# - 5 Blocks with MAX_PARALLEL_TESTS=5 and MIN_TESTS_PER_BLOCK=3
# - 2 Blocks with MAX_PARALLEL_TESTS=5 and MIN_TESTS_PER_BLOCK=10
# Time_between_test_start_up = time between one set of tests starting and the next set, the parallel blocks
# Should be a min of 5, for above 10 parallel tests the min should be 20.

MAX_PARALLEL_TESTS = 4
MIN_TESTS_PER_BLOCK = 1

time_between_test_start_up = 40

###############################################################################################################
# Dynamic pybot variables:
# Specifies an 3D-array with variables passed to the single pybot instances
# Each row contains a variablename - value(s) combination (array, name at index 0, values at 1++)
# One variable value will be passed to each python instance using --variable name:value
# If multiple values are defined parabot will iterate over the values and assign one to each pybot
DYN_ARGS =  [
    # specify different users
    ["USER", "Hans", "Klaus", "Peter", "Martin", "Eric"],
    # passwords
    ["PASS", "HansPassword", "KlausPassword", "PetersPassword", "MartinsPassword", "EricsPassword"]
]
