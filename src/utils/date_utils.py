from datetime import datetime

def parse_yyyy_mm_dd(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d")