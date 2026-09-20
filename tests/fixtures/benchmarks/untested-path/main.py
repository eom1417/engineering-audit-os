import argparse
import refunds


def main():
    argparse.ArgumentParser(prog='refunds').parse_args()
    return refunds.refund(100, 5)
