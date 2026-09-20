import argparse
from api import total
from export import exported_total


def main():
    parser = argparse.ArgumentParser(prog='billing')
    parser.parse_args()
    return total(100), exported_total(100)
