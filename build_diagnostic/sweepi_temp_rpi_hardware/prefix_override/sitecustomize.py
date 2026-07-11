import sys
if sys.prefix == '/usr':
    sys.real_prefix = sys.prefix
    sys.prefix = sys.exec_prefix = '/home/sweepi/SweePi/install_diagnostic/sweepi_temp_rpi_hardware'
