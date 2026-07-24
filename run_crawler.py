#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/empire_os')

# Import crawler_runner directly
from empire_os.crawler_runner import main

if __name__ == '__main__':
    main()
