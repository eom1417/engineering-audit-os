import argparse
from rules import apply_discount


def main():
    argparse.ArgumentParser(prog='clean').parse_args()
    return apply_discount(100)
