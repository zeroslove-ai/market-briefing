#!/usr/bin/env python3
"""미국 장 종료(마감) 옵션플로우 브리핑 — close 모드 진입점."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from option_flow_report import main

sys.exit(main("close"))
